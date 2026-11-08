import asyncio
import json
import mimetypes
import secrets
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles

from ..bundles import resolve_bundle
from ..audit import audit_workspace, build_handoff
from ..config import AppConfig
from ..db import open_db, search
# Imported by name: this module also defines a route called `sources()`, and an
# `import sources` would be shadowed by it inside `create_app`.
from ..engine.sources import is_posting, sanitize, sanitize_row
from ..indexer import crawl, watch
from ..safety import (Conflict, FileStamp, PathEscape, last_prune_report, matches,
                      prune_trash, resolve_in_root, retention_settings, stamp, trash,
                      trash_then_write)


def _loopback_origin(origin: str) -> bool:
    parsed = urlparse(origin)
    return parsed.scheme in {"http", "https"} and parsed.hostname in {"127.0.0.1", "localhost"}


#: Routes that hold the connection open. Declared here so a client (or a test
#: sweeping the API) can tell a stream from a request that returns.
STREAMING_PATHS = frozenset({"/api/events"})


def create_app(config: AppConfig) -> FastAPI:
    config.ensure()
    # One bounded retention pass per session: a long-idle trash gets capped
    # without the user doing anything, and the report is returned by
    # `GET /api/trash` as `startup_prune`. Deliberately NOT run on every write --
    # that would stat the whole folder per overwrite, and a prune failure must
    # never be able to fail a write (gate: never-only-copy).
    try:
        startup_prune = prune_trash(config)
    except Exception as exc:  # a prune may never stop the workspace from opening
        startup_prune = {"exceptional": True, "error": f"{type(exc).__name__}: {exc}"}
    connection = open_db(config.db_path)
    crawl(config, connection)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        """Create the watch task before `yield`, tear it down after.

        One lifespan replaces the two deprecated `@app.on_event` hooks. The
        order is the same one they ran in — watch task first, then the SQLite
        connection closed on the way out — so no route or auth behaviour moves.
        """
        async def on_change(changes):
            for change, path in changes:
                await app.state.events.put({"type": change.name.lower(), "path": str(path)})
        task = asyncio.create_task(watch(config, connection, on_change))
        app.state.watch_task = task
        try:
            yield
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            app.state.watch_task = None
            connection.close()

    app = FastAPI(title="Dossier", lifespan=lifespan)
    app.state.config = config
    app.state.conn = connection
    app.state.events = asyncio.Queue()
    app.state.watch_task = None

    @app.exception_handler(PathEscape)
    async def path_error(request: Request, exc: PathEscape):
        return JSONResponse({"detail": str(exc)}, status_code=400)

    # Lighthouse on the built app named 710 KiB of uncompressed first-party JavaScript and
    # 863 KiB of assets with no cache policy. Both are cheap here: gzip on anything over
    # 1 KiB, and an immutable year for `/assets/`, whose filenames carry a content hash.
    app.add_middleware(GZipMiddleware, minimum_size=1024)

    @app.middleware("http")
    async def asset_cache(request: Request, call_next):
        response = await call_next(request)
        if request.url.path.startswith("/assets/"):
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        return response

    @app.middleware("http")
    async def no_store(request: Request, call_next):
        """API answers are state, not a cacheable resource, and every answer carries the
        headers that make an inline response inert.

        A live workspace changes under the client (a capture lands, a document is
        written), and a heuristically cached GET showed a stale file tree until a
        hard reload. `no-store` is the honest header for a local-first app.

        The three security headers are cheap and close real classes: `nosniff` stops
        `/api/raw` being type-sniffed into script, `frame-ancestors 'none'` stops the
        app being framed, and `no-referrer` stops a URL (and anything in it) leaking
        to a third party from a rendered document.
        """
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("Content-Security-Policy", "frame-ancestors 'none'")
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.middleware("http")
    async def auth(request: Request, call_next):
        if request.url.path.startswith("/api/"):
            origin = request.headers.get("origin")
            if origin and not _loopback_origin(origin):
                return JSONResponse({"detail": "origin rejected"}, status_code=403)
            supplied = request.headers.get("authorization", "")
            header_token = supplied.removeprefix("Bearer ").strip() if supplied.startswith("Bearer ") else ""
            cookie_token = request.cookies.get("dossier_token", "")
            # A `?token=` query parameter used to be accepted as well, and the client
            # appended it to `<img>`, `<a>` and EventSource URLs. That put the bearer
            # token in the address bar, the browser history, the `Referer` of any
            # link followed, and the server's own access log — the opposite of the
            # `token-never-leaks` gate. The SameSite=Lax cookie authorises every one
            # of those requests already, so the query form is gone, not deprecated.
            if not (secrets.compare_digest(header_token, config.token)
                    or secrets.compare_digest(cookie_token, config.token)):
                return Response("Unauthorized", status_code=401)
        return await call_next(request)

    dist = Path(__file__).parents[3] / "ui" / "dist"

    @app.get("/")
    def index():
        if dist.joinpath("index.html").exists():
            response = FileResponse(dist / "index.html", media_type="text/html")
        else:
            response = HTMLResponse("<h1>Dossier</h1><p>Build ui/ first.</p>")
        response.set_cookie("dossier_token", config.token, httponly=True, samesite="lax")
        return response

    if dist.joinpath("assets").exists():
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

    @app.get("/favicon.svg", include_in_schema=False)
    def favicon():
        path = dist / "favicon.svg"
        if not path.is_file():
            raise HTTPException(404, "favicon not found")
        return FileResponse(path, media_type="image/svg+xml")

    def tree_node(path: Path) -> dict:
        if path.is_dir():
            children = []
            for child in sorted(path.iterdir(), key=lambda item: (not item.is_dir(), item.name.casefold())):
                if child.name in {".dossier", ".git", "__pycache__", "node_modules"}:
                    continue
                try:
                    if child.is_symlink() and not child.resolve().is_relative_to(config.root):
                        continue
                    children.append(tree_node(child))
                except (OSError, ValueError):
                    continue
            return {"name": path.name, "rel": path.relative_to(config.root).as_posix() if path != config.root else "", "directory": True, "children": children}
        stat = path.stat()
        return {"name": path.name, "rel": path.relative_to(config.root).as_posix(), "directory": False, "ext": path.suffix.casefold(), "size": stat.st_size, "mtime_ns": stat.st_mtime_ns}

    @app.get("/api/health")
    def health():
        count = connection.execute("SELECT count(*) AS count FROM files").fetchone()["count"]
        return {"ok": True, "root": str(config.root), "indexed": count}

    @app.get("/api/tree")
    def tree(dir: str = "", view: str = "files"):
        if view == "trajectory":
            if dir:
                raise HTTPException(400, "dir cannot be used with trajectory view")
            from ..engine import tree as trajectory_tree
            return trajectory_tree.graph(config.root)
        if view != "files":
            raise HTTPException(400, "view must be files or trajectory")
        path = resolve_in_root(config.root, dir)
        if not path.is_dir():
            raise HTTPException(404, "directory not found")
        return tree_node(path).get("children", [])

    @app.get("/api/tree/export")
    def tree_export(format: str = "ascii"):
        from ..engine import tree as trajectory_tree
        if format == "ascii":
            content = trajectory_tree.to_ascii(config.root)
        elif format == "mermaid":
            content = trajectory_tree.to_mermaid(config.root)
        else:
            raise HTTPException(400, "format must be ascii or mermaid")
        return Response(content, media_type="text/plain; charset=utf-8")

    @app.post("/api/tree/nodes")
    def tree_upsert_node(payload: dict):
        from ..engine import tree as trajectory_tree
        try:
            return trajectory_tree.upsert_node(config.root, payload)
        except trajectory_tree.TreeError as exc:
            raise HTTPException(400, str(exc)) from exc

    @app.post("/api/tree/links")
    def tree_link_nodes(payload: dict):
        from ..engine import tree as trajectory_tree
        try:
            return trajectory_tree.link_nodes(config.root, payload.get("parent_id"), payload.get("child_id"))
        except trajectory_tree.TreeError as exc:
            raise HTTPException(400, str(exc)) from exc

    @app.post("/api/tree/sync")
    def tree_sync(payload: dict | None = None):
        from ..engine import tree as trajectory_tree
        try:
            return trajectory_tree.sync(config.root)
        except (OSError, ValueError) as exc:
            raise HTTPException(400, f"trajectory source sync failed: {exc}") from exc

    @app.post("/api/tree/packet")
    def tree_packet(payload: dict):
        from ..engine import tree as trajectory_tree
        try:
            def _nonnegative_integer(value: object, name: str) -> int:
                if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                    raise trajectory_tree.TreeError(f"{name} must be a non-negative integer")
                return value
            if not isinstance(payload.get("query", ""), str):
                raise trajectory_tree.TreeError("query must be a string")
            limit = _nonnegative_integer(payload.get("limit", 40), "limit")
            if limit == 0:
                raise trajectory_tree.TreeError("limit must be positive")
            context_limit = _nonnegative_integer(payload.get("context_limit", 200), "context_limit")
            return trajectory_tree.generate_next_packet(
                config.root,
                limit=limit,
                query=payload.get("query", ""),
                context_limit=context_limit,
            )
        except trajectory_tree.TreeError as exc:
            raise HTTPException(400, str(exc)) from exc

    @app.get("/api/file")
    def get_file(rel: str):
        path = resolve_in_root(config.root, rel)
        if not path.is_file():
            raise HTTPException(404, "file not found")
        content = path.read_text(encoding="utf-8", errors="replace")
        payload = {"rel": rel, "content": content, "stamp": stamp(path).__dict__}
        # posting-is-data holds at ingestion: a captured posting is sanitised on
        # the way out of the API, not only when someone remembers to run
        # `dossier sanitize`. The findings travel with the text so the caller can
        # see what was stripped instead of trusting a silent edit.
        if is_posting(rel):
            sanitised = sanitize(content, source=Path(rel).stem)
            payload["content"] = sanitised["clean"]
            payload["sanitized"] = True
            payload["findings"] = sanitised["findings"]
        return payload

    @app.put("/api/file")
    async def put_file(payload: dict):
        try:
            path = resolve_in_root(config.root, str(payload["rel"]))
            expected_data = payload.get("expect")
            expected = FileStamp(**expected_data) if expected_data else None
            # Check before trashing, so a rejected write leaves no trash copy of
            # a file it refused to touch. `expect=None` is "no precondition", not
            # "must not exist": a client that sends no stamp may still save an
            # existing file, which is what made every save after the first 409.
            if not matches(path, expected):
                raise Conflict("file changed on disk")
            result = trash_then_write(
                config, path, str(payload.get("content", "")).encode("utf-8"), expected)
            return {"rel": str(payload["rel"]), "stamp": result.__dict__}
        except PathEscape as exc:
            raise HTTPException(400, str(exc)) from exc
        except (Conflict, KeyError, TypeError, ValueError) as exc:
            status = 409 if isinstance(exc, Conflict) else 400
            raise HTTPException(status, str(exc)) from exc

    @app.get("/api/raw")
    def raw(rel: str):
        path = resolve_in_root(config.root, rel)
        if not path.is_file():
            raise HTTPException(404, "file not found")
        filename = path.name.replace('"', "'")
        media_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        # Markup served from this origin would execute with the app's own cookie and API
        # authority (a folder can hold any HTML a capture dropped there), so anything the
        # browser can execute is handed over as a download inside a sandbox rather than
        # rendered inline. `nosniff` stops a mislabelled file being sniffed into script.
        executable = media_type.startswith(("text/html", "application/xhtml")) or media_type in {
            "image/svg+xml", "text/xml", "application/xml",
        }
        disposition = "attachment" if executable else "inline"
        headers = {
            "Content-Disposition": f'{disposition}; filename="{filename}"',
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "sandbox; frame-ancestors 'none'",
        }
        return FileResponse(path, media_type=media_type, headers=headers)

    @app.get("/api/search")
    def do_search(q: str, limit: int = 50):
        if not q.strip():
            return []
        return search(connection, q, min(max(limit, 1), 200))

    @app.get("/api/bundle")
    def bundle(rel: str):
        return resolve_bundle(connection, rel).__dict__

    @app.get("/api/events")
    async def events(seconds: int = 300):
        """Server-sent file events.

        Bounded on purpose. An unbounded stream is an endpoint any naive client
        — including a script enumerating the API — hangs on forever. The bound
        is generous enough for the UI, which reconnects, and finite enough that
        nothing can block indefinitely.
        """
        budget = min(max(seconds, 1), 3600)
        deadline = asyncio.get_event_loop().time() + budget

        async def stream():
            yield "data: {\"type\":\"connected\"}\n\n"
            while asyncio.get_event_loop().time() < deadline:
                remaining = deadline - asyncio.get_event_loop().time()
                try:
                    event = await asyncio.wait_for(app.state.events.get(), timeout=min(15, remaining))
                    yield f"data: {json.dumps(event)}\n\n"
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
            yield "data: {\"type\":\"closed\"}\n\n"

        return StreamingResponse(stream(), media_type="text/event-stream")

    def _render_target(rel: str) -> tuple[Path, Path]:
        source = resolve_in_root(config.root, rel)
        if source.suffix.casefold() != ".docx":
            raise HTTPException(400, "only DOCX files have a server render")
        cache_dir = config.dossier_dir / "cache" / "render"
        cache_dir.mkdir(parents=True, exist_ok=True)
        return source, cache_dir / f"{stamp(source).sha256}.pdf"

    @app.get("/api/render")
    def render(rel: str):
        """Serve a cached render. A GET must not convert: `conventions.md:33` forbids slow
        work behind a GET, and a Word conversion takes seconds on a cold cache. The build
        has its own route, so a client that hits a miss is told to POST instead of waiting
        on a request it cannot see the progress of."""
        source, cache_path = _render_target(rel)
        if not cache_path.exists():
            raise HTTPException(409, "no cached render for this revision; POST /api/render to build it")
        return FileResponse(cache_path, media_type="application/pdf",
                            headers={"Content-Disposition": f'inline; filename="{source.stem}.pdf"'})

    @app.post("/api/render")
    def build_render(payload: dict):
        from ..convert import convert
        source, cache_path = _render_target(str(payload.get("rel") or ""))
        if not cache_path.exists():
            # Word is an external process: it can be busy, licensed out, or missing.
            # A converter failure is "not right now", not a crash — the client gets a
            # sentence it can show, and the cache stays empty so a retry is honest.
            try:
                convert(source, cache_path)
            except Exception as exc:  # noqa: BLE001 - any converter failure is 503
                raise HTTPException(503, f"the DOCX renderer could not run: {exc}") from exc
        return {"rel": str(payload.get("rel")), "cached": True,
                "fidelity": next((route["fidelity"] for route in
                                  __import__("dossier.engine.render", fromlist=["routes"]).routes(".docx")
                                  if route["target"] == ".pdf"), "faithful"),
                "bytes": cache_path.stat().st_size}

    @app.get("/api/convert/routes")
    def convert_routes(rel: str):
        """What this file can become, and how faithfully, before anyone clicks."""
        from ..engine import render as render_module
        source = resolve_in_root(config.root, rel)
        return {"rel": rel, "ext": source.suffix.casefold(),
                "routes": render_module.routes(source.suffix)}

    @app.get("/api/export")
    def export(rel: str, target: str):
        from ..convert import convert
        source = resolve_in_root(config.root, rel)
        destination = resolve_in_root(config.root, target)
        # An export target may already exist; the replaced file goes to the
        # trash first (gate: never-only-copy).
        if destination.exists():
            trash(config, destination)
        return {"path": str(convert(source, destination))}

    # -- trash ---------------------------------------------------------------
    @app.get("/api/trash")
    def trash_listing():
        """What every overwrite left behind, newest first, and the age cap on it.

        `entries` are restorable (each names the original workspace-relative
        path); `external` are backups of files that lived outside the workspace;
        `unmanaged` is anything else in the folder, reported rather than mapped
        back — `render_stale`'s flat-named PDF backups have no honest reverse.

        `retention` is the effective policy and where the number came from, so the
        cap is visible without reading a config file. `startup_prune` is what this
        session's start-up pass did (empty when it changed nothing) and
        `last_prune` is the last recorded pass, so a prune that ran on a previous
        start is still inspectable.
        """
        from ..safety import list_trash

        listing = list_trash(config)
        return {**listing, "root": str(config.dossier_dir / "trash"),
                "retention": retention_settings(config),
                "startup_prune": startup_prune,
                "last_prune": last_prune_report(config)}

    @app.post("/api/trash/prune")
    def trash_prune(payload: dict | None = None):
        """Apply the age cap now. `dry_run` reports what would go without deleting."""
        payload = payload or {}
        try:
            retention = payload.get("retention_days")
            retention = int(retention) if retention is not None else None
        except (TypeError, ValueError) as exc:
            raise HTTPException(400, "retention_days must be a whole number of days") from exc
        return prune_trash(config, retention_days=retention,
                           apply=not bool(payload.get("dry_run")))

    @app.post("/api/trash/restore")
    def trash_restore(payload: dict):
        """Put one trashed file back, trashing whatever occupies the path now."""
        from ..safety import restore_from_trash

        try:
            return restore_from_trash(
                config,
                str(payload.get("rel", "")),
                str(payload["trash_rel"]) if payload.get("trash_rel") else None,
            )
        except PathEscape as exc:
            raise HTTPException(400, str(exc)) from exc
        except FileNotFoundError as exc:
            raise HTTPException(404, str(exc)) from exc
        except (ValueError, KeyError, TypeError) as exc:
            raise HTTPException(400, str(exc)) from exc

    @app.get("/api/actions")
    def actions():
        from ..actions import load_actions
        return [action.__dict__ for action in load_actions(config)]

    @app.post("/api/actions")
    def run_action(payload: dict):
        from ..actions import run_action as execute_action
        # A body without `id`/`rel` used to reach the engine and surface as a 500, which
        # the route sweep counted as a failure. A malformed request is the caller's
        # problem and deserves a 400 with a sentence.
        missing = [field for field in ("id", "rel") if not str(payload.get(field) or "").strip()]
        if missing:
            raise HTTPException(400, f"the action request needs {', '.join(missing)}")
        try:
            return execute_action(config, str(payload["id"]), str(payload["rel"]),
                                  bool(payload.get("confirmed"))).__dict__
        except PermissionError as exc:
            raise HTTPException(428, str(exc)) from exc
        except KeyError as exc:
            raise HTTPException(404, f"no configured action with id {exc.args[0]!r}") from exc
        except (ValueError, PathEscape) as exc:
            raise HTTPException(400, str(exc)) from exc

    @app.get("/api/jobs")
    def jobs():
        from ..engine.corpus import load as load_corpus
        # A board capture can carry the whole posting body in `description`;
        # posting-is-data applies at ingestion for the job rows too, not only for
        # a posting opened as a file.
        return [sanitize_row(row) for row in load_corpus(config.root)]

    @app.get("/api/jobs/history")
    def job_history():
        from ..engine.tracker import parse as parse_tracker
        return parse_tracker(config.root)

    @app.get("/api/jobs/due")
    def jobs_due():
        from ..engine.tracker import cadence
        return cadence(config.root)["entries"]

    @app.get("/api/jobs/feeds")
    def feed_catalog():
        from ..feeds import ADAPTERS, ENDPOINTS, PROHIBITED
        return {"permitted": {name: {"policy": cls.policy, "endpoint": ENDPOINTS[name]} for name, cls in ADAPTERS.items()}, "prohibited": sorted(PROHIBITED)}

    @app.get("/api/audit")
    def audit():
        return audit_workspace(config.root, connection)

    @app.get("/api/ai/handoff")
    def ai_handoff():
        return build_handoff(config.root, connection)

    # -- agent layer -------------------------------------------------------
    @app.get("/api/agent/manifest")
    def agent_manifest():
        from ..agent import contract
        return contract()

    @app.get("/api/agent/status")
    def agent_status():
        from ..agent import loop
        return loop.status(config.root)

    @app.get("/api/agent/next")
    def agent_next():
        from ..agent import loop
        return loop.next_unit(config.root)

    @app.get("/api/agent/route")
    def agent_route(q: str = "", limit: int = 4):
        from ..agent import route as route_request
        matches = route_request(q, limit=min(max(limit, 1), 10))
        return {"request": q, "matches": matches,
                "confident": bool(matches and matches[0]["score"] >= 10)}

    @app.get("/api/agent/brief")
    def agent_brief(mode: str, text: str = "", format: str = "json"):
        from ..agent import brief as brief_module
        packet = brief_module.build(config.root, mode, text)
        if format == "markdown":
            return Response(brief_module.render(packet), media_type="text/markdown")
        return packet.to_dict()

    @app.get("/api/agent/prompt")
    def agent_prompt():
        from ..agent import brief as brief_module
        return Response(brief_module.system_prompt(config.root), media_type="text/markdown")

    @app.get("/api/agent/adapters")
    def agent_adapters():
        from ..agent import adapters
        packs = adapters.packs(config.root)
        return {
            "packs": sorted(packs),
            "current": {rel: adapters.verify_block(config.root, rel) for rel in packs},
        }

    @app.post("/api/agent/commit")
    def agent_commit(payload: dict):
        from ..agent import loop
        return loop.commit(config.root, payload)

    @app.post("/api/agent/ask")
    def agent_ask(payload: dict):
        """One mode through a configured model API, fail-closed.

        `apply` is refused inside `model.ask` (`AUTO_FORBIDDEN_MODES`), so the
        route needs no second allow-list and the `no-auto-submit` gate holds on
        both surfaces. Unconfigured means 503 with nothing changed.
        """
        from .. import model

        report = model.availability(config.root)
        if not report["available"]:
            raise HTTPException(status_code=503, detail=report["reason"])
        try:
            return model.ask(
                config.root,
                str(payload.get("mode", "")),
                str(payload.get("text", "")),
            )
        except model.ModelModeRefused as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from None
        except model.ModelUnavailable as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from None
        except model.ModelError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from None

    # -- engine surfaces ---------------------------------------------------
    @app.get("/api/workspace")
    def workspace_state():
        from ..agent import workspace as workspace_module
        return workspace_module.resolve(config.root).to_dict()

    @app.get("/api/panel")
    def panel(resume: str = "", posting: str = "", role: str = ""):
        """Seven reviewers, one score each, and the exact line behind each objection."""
        from ..engine import panel as panel_module
        from ..extract import extract_text
        if not resume:
            raise HTTPException(400, "name the resume, relative to this workspace")
        path = resolve_in_root(config.root, resume)
        if not path.exists():
            raise HTTPException(404, f"no file at {resume}")
        text, meta = extract_text(path)
        if meta.get("error"):
            raise HTTPException(400, f"{resume}: {meta['error']}")
        posting_text = ""
        if posting:
            posting_path = resolve_in_root(config.root, posting)
            if not posting_path.exists():
                raise HTTPException(404, f"no file at {posting}")
            posting_text, posting_meta = extract_text(posting_path)
            if posting_meta.get("error"):
                raise HTTPException(400, f"{posting}: {posting_meta['error']}")
        return panel_module.run(text, posting=posting_text, target_role=role)

    @app.get("/api/doctor")
    def doctor():
        from ..engine import doctor as doctor_module
        return doctor_module.report(config.root)

    @app.get("/api/sources")
    def sources():
        from ..engine import sources as sources_module
        return sources_module.ledger(config.root)

    # -- identity and relevance -------------------------------------------
    @app.get("/api/identity")
    def identity_state():
        """The profile, the questionnaire with what is already known, and the mines."""
        from ..engine import identity as identity_module
        data = identity_module.profile(config.root)
        # `questions` is the COUNT in the profile; the list is `question_list`, so a
        # client cannot mistake one for the other.
        return {**data,
                "question_list": identity_module.questions_with_state(config.root),
                "proposals": identity_module.mine_documents(config.root)}

    @app.post("/api/identity/answers")
    def identity_answer(payload: dict):
        """Record answers. A blank value clears one; the profile reports the gap."""
        from ..engine import identity as identity_module
        answers = payload.get("answers")
        if answers is None and payload.get("question"):
            answers = {str(payload["question"]): payload.get("value")}
        if not isinstance(answers, dict):
            raise HTTPException(400, "answers must be an object of {question_id: value}")
        try:
            saved = identity_module.save_answers(config.root, answers)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from None
        data = identity_module.profile(config.root)
        return {**saved, "complete": data["complete"],
                "missing_required": data["missing_required"],
                "fields": len(data["fields"])}

    @app.post("/api/identity/write")
    def identity_write(payload: dict | None = None):
        from ..engine import identity as identity_module
        payload = payload or {}
        try:
            return identity_module.write_identity(
                config.root, name=payload.get("name") or payload.get("out"))
        except (ValueError, FileNotFoundError) as exc:
            raise HTTPException(400, str(exc)) from None

    @app.get("/api/match")
    def match(limit: int = 40, min_band: str = ""):
        from ..engine import identity as identity_module
        if min_band and min_band not in {"strong", "possible", "unlikely"}:
            raise HTTPException(400, "min_band must be strong, possible or unlikely")
        return identity_module.rank_corpus(config.root, limit=min(max(limit, 1), 200),
                                           min_band=min_band)

    @app.get("/api/match/posting")
    def match_posting(rel: str):
        from ..engine import identity as identity_module
        path = resolve_in_root(config.root, rel)
        if not path.is_file():
            raise HTTPException(404, f"no posting at {rel}")
        return identity_module.match_posting(path, config.root)

    # -- templates --------------------------------------------------------
    @app.get("/api/tailor/fields")
    def template_fields(template: str):
        """The `{{placeholders}}` a user's template declares, so a form can ask for them."""
        from ..engine import tailor as tailor_module
        path = resolve_in_root(config.root, template)
        try:
            return {"template": template, "fields": tailor_module.template_fields(path)}
        except FileNotFoundError:
            raise HTTPException(404, f"no template at {template}") from None

    @app.post("/api/tailor/template")
    def template_fill(payload: dict):
        """Fill the user's own .docx from a fields map. Layout is never rebuilt."""
        from ..engine import tailor as tailor_module
        template = str(payload.get("template") or "").strip()
        out = str(payload.get("out") or "").strip()
        if not template or not out:
            raise HTTPException(400, "template and out are required")
        spec = payload.get("spec")
        if spec is None and payload.get("spec_path"):
            import json as _json
            try:
                spec = _json.loads(resolve_in_root(config.root, str(payload["spec_path"]))
                                   .read_text(encoding="utf-8"))
            except (OSError, ValueError) as exc:
                raise HTTPException(400, f"the spec file could not be read: {exc}") from None
        try:
            return tailor_module.fill_template(
                resolve_in_root(config.root, template), resolve_in_root(config.root, out),
                spec or {}, root=config.root,
                strict=not bool(payload.get("allow_leftovers")))
        except tailor_module.TemplateFillError as exc:
            # 422, not 500: the document was refused on purpose and carries the list.
            raise HTTPException(422, detail={"message": str(exc), "leftovers": exc.leftovers,
                                             "report": exc.report}) from None
        except (ValueError, FileNotFoundError) as exc:
            raise HTTPException(400, str(exc)) from None

    @app.get("/api/verify/template")
    def verify_template(template: str, candidate: str, spec: str = ""):
        from ..engine import verify as verify_module
        payload = {}
        if spec:
            import json as _json
            try:
                payload = _json.loads(resolve_in_root(config.root, spec).read_text(encoding="utf-8"))
            except (OSError, ValueError) as exc:
                raise HTTPException(400, f"the spec file could not be read: {exc}") from None
        return verify_module.template_fill(
            resolve_in_root(config.root, template), resolve_in_root(config.root, candidate), payload)

    @app.post("/api/verify/template")
    def verify_template_inline(payload: dict):
        """The same check with the fields inline, so the Build pane can verify what it just built."""
        from ..engine import verify as verify_module
        template = str(payload.get("template") or "").strip()
        candidate = str(payload.get("candidate") or "").strip()
        if not template or not candidate:
            raise HTTPException(400, "template and candidate are required")
        spec = payload.get("spec") or {}
        if not isinstance(spec, dict):
            raise HTTPException(400, "spec must be an object")
        try:
            return verify_module.template_fill(
                resolve_in_root(config.root, template),
                resolve_in_root(config.root, candidate), spec)
        except FileNotFoundError as exc:
            raise HTTPException(404, str(exc)) from None

    # -- capture -----------------------------------------------------------
    @app.get("/api/scrape")
    def scrape_status():
        """Recipes, sessions, engines and what is due. Read-only and cheap.

        Deliberately not a capture: a capture takes seconds to minutes and belongs
        to an explicit request, not to a pane opening. The one mutating route is
        `POST /api/scrape/capture`, and it is bounded to a single page.
        """
        from ..scrape import runner
        return runner.status(config.root)

    @app.get("/api/scrape/recipes")
    def scrape_recipes():
        from ..scrape import recipes as recipes_module
        found, errors = recipes_module.discover(config.root)
        return {"recipes": [recipe.to_dict() for recipe in found], "errors": errors}

    @app.post("/api/scrape/capture")
    def scrape_capture(payload: dict):
        """Capture one page the user named. Policy, robots and sessions all apply.

        One page per request, and `session` is opt-in: an endpoint that could walk
        a whole board on a signed-in session is an endpoint that can be pointed at
        the wrong board by a mistake in a client.
        """
        from ..scrape import guard, runner
        from ..scrape.errors import (AuthRequired, Blocked, ChallengeDetected,
                                     DriverUnavailable, RecipeError, ScrapeError)

        url = str(payload.get("url") or "").strip()
        if not url:
            raise HTTPException(400, "url is required")
        try:
            guard.assert_capture_allowed(url, str(payload.get("source") or ""), config.root)
        except PermissionError as exc:
            raise HTTPException(403, str(exc)) from exc
        try:
            return runner.capture_url(
                config.root, url,
                source=str(payload.get("source") or ""),
                driver=str(payload.get("driver") or "auto"),
                headless=not bool(payload.get("headed")),
                screenshot=bool(payload.get("screenshot", True)),
                selector=str(payload.get("selector") or ""),
                session=bool(payload.get("session")),
                refresh=bool(payload.get("refresh")),
                challenge=str(payload.get("challenge") or "auto"),
                await_clear_s=float(payload["await_seconds"]) if payload.get("await_seconds") else None,
                min_match=int(payload.get("min_match") or 0),
            )
        except (AuthRequired, ChallengeDetected, Blocked) as exc:
            # A refusal is not a server fault: the client asked for something the
            # site or the workspace does not permit, and the reason belongs in 409.
            raise HTTPException(409, f"{type(exc).__name__}: {exc}") from exc
        except DriverUnavailable as exc:
            raise HTTPException(503, str(exc)) from exc
        except (RecipeError, ScrapeError) as exc:
            raise HTTPException(400, str(exc)) from exc

    @app.post("/api/scrape/run")
    def scrape_run(payload: dict):
        """Walk one recipe. Bounded: 50 items and 10 listing pages per request.

        A route that could run an unbounded crawl on a signed-in session is a route
        a stray client can point at the wrong board. `--due` belongs to the CLI and
        to a scheduled task, not to an open HTTP request.
        """
        from ..scrape import recipes as recipes_module, runner
        from ..scrape.errors import (AuthRequired, Blocked, ChallengeDetected,
                                     DriverUnavailable, RecipeError, ScrapeError)

        recipe_id = str(payload.get("recipe") or "").strip()
        if not recipe_id:
            raise HTTPException(400, "recipe is required")
        found, errors = recipes_module.discover(config.root)
        match = next((recipe for recipe in found if recipe.id == recipe_id), None)
        if match is None:
            broken = next((row for row in errors if Path(row["path"]).stem == recipe_id), None)
            raise HTTPException(404, broken["error"] if broken
                                else f"unknown recipe {recipe_id!r}")
        try:
            limit = int(payload.get("limit") or 25)
            pages = int(payload.get("pages") or min(match.max_pages, 10))
        except (TypeError, ValueError):
            raise HTTPException(400, "limit and pages must be whole numbers") from None
        try:
            return runner.run_recipe(
                config.root, match, limit=min(max(limit, 1), 50),
                pages=min(max(pages, 1), 10),
                challenge=str(payload.get("challenge") or "") or None,
                await_clear_s=float(payload["await_seconds"]) if payload.get("await_seconds") else None,
                min_match=int(payload["min_match"]) if payload.get("min_match") is not None else None)
        except (AuthRequired, ChallengeDetected, Blocked) as exc:
            raise HTTPException(409, f"{type(exc).__name__}: {exc}") from exc
        except DriverUnavailable as exc:
            raise HTTPException(503, str(exc)) from exc
        except (RecipeError, ScrapeError, ValueError) as exc:
            raise HTTPException(400, str(exc)) from exc

    @app.get("/api/track")
    def track_summary():
        from ..engine import tracker
        return tracker.summary(config.root)

    @app.get("/api/track/cadence")
    def track_cadence(overdue: bool = False):
        from ..engine import tracker
        return tracker.cadence(config.root, overdue_only=overdue)

    @app.get("/api/corpus")
    def corpus_summary(limit: int = 40):
        from ..engine import corpus
        jobs = corpus.load(config.root)
        if not jobs:
            return {"present": False, "rows": 0}
        report = corpus.rank_report(jobs, limit=min(max(limit, 1), 200))
        report["present"] = True
        report["hash"] = corpus.aggregate_hash(jobs)
        return report

    @app.get("/api/verify")
    def verify_summary(base: str = "", candidate: str = "", pdf: str = "",
                       expected_pages: int = 0):
        from ..engine import verify as verify_module
        return verify_module.all(
            resolve_in_root(config.root, base) if base else None,
            resolve_in_root(config.root, candidate) if candidate else None,
            resolve_in_root(config.root, pdf) if pdf else None,
            expected_pages=expected_pages or None,
        )

    return app
