import asyncio
import json
import mimetypes
from pathlib import Path
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles

from ..bundles import resolve_bundle
from ..audit import audit_workspace, build_handoff
from ..config import AppConfig
from ..db import open_db, search
from ..indexer import crawl, watch
from ..safety import Conflict, FileStamp, PathEscape, atomic_write, resolve_in_root, stamp, trash


def _loopback_origin(origin: str) -> bool:
    parsed = urlparse(origin)
    return parsed.scheme in {"http", "https"} and parsed.hostname in {"127.0.0.1", "localhost"}


#: Routes that hold the connection open. Declared here so a client (or a test
#: sweeping the API) can tell a stream from a request that returns.
STREAMING_PATHS = frozenset({"/api/events"})


def create_app(config: AppConfig) -> FastAPI:
    config.ensure()
    connection = open_db(config.db_path)
    crawl(config, connection)
    app = FastAPI(title="Dossier")
    app.state.config = config
    app.state.conn = connection
    app.state.events = asyncio.Queue()
    app.state.watch_task = None

    @app.exception_handler(PathEscape)
    async def path_error(request: Request, exc: PathEscape):
        return JSONResponse({"detail": str(exc)}, status_code=400)

    @app.middleware("http")
    async def auth(request: Request, call_next):
        if request.url.path.startswith("/api/"):
            origin = request.headers.get("origin")
            if origin and not _loopback_origin(origin):
                return JSONResponse({"detail": "origin rejected"}, status_code=403)
            supplied = request.headers.get("authorization", "")
            header_token = supplied.removeprefix("Bearer ").strip() if supplied.startswith("Bearer ") else ""
            cookie_token = request.cookies.get("dossier_token", "")
            query_token = request.query_params.get("token", "")
            if header_token != config.token and cookie_token != config.token and query_token != config.token:
                return Response("Unauthorized", status_code=401)
        return await call_next(request)

    @app.on_event("startup")
    async def start_watcher():
        async def on_change(changes):
            for change, path in changes:
                await app.state.events.put({"type": change.name.lower(), "path": str(path)})
        app.state.watch_task = asyncio.create_task(watch(config, connection, on_change))

    @app.on_event("shutdown")
    async def stop_watcher():
        task = app.state.watch_task
        if task:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        connection.close()

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
        return {"rel": rel, "content": path.read_text(encoding="utf-8", errors="replace"), "stamp": stamp(path).__dict__}

    @app.put("/api/file")
    async def put_file(payload: dict):
        try:
            path = resolve_in_root(config.root, str(payload["rel"]))
            expected_data = payload.get("expect")
            expected = FileStamp(**expected_data) if expected_data else None
            if expected is not None and path.exists() and stamp(path) != expected:
                raise Conflict("file changed on disk")
            if path.exists():
                trash(config, path)
            result = atomic_write(path, str(payload.get("content", "")).encode("utf-8"), expected)
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
        return FileResponse(path, media_type=mimetypes.guess_type(path.name)[0] or "application/octet-stream", headers={"Content-Disposition": f'inline; filename="{filename}"'})

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

    @app.get("/api/render")
    def render(rel: str):
        from ..convert import convert
        source = resolve_in_root(config.root, rel)
        if source.suffix.casefold() != ".docx":
            raise HTTPException(400, "only DOCX files have a server render")
        cache_dir = config.dossier_dir / "cache" / "render"
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache_path = cache_dir / f"{stamp(source).sha256}.pdf"
        if not cache_path.exists():
            convert(source, cache_path)
        return FileResponse(cache_path, media_type="application/pdf", headers={"Content-Disposition": f'inline; filename="{source.stem}.pdf"'})

    @app.get("/api/export")
    def export(rel: str, target: str):
        from ..convert import convert
        source = resolve_in_root(config.root, rel)
        destination = resolve_in_root(config.root, target)
        return {"path": str(convert(source, destination))}

    @app.get("/api/actions")
    def actions():
        from ..actions import load_actions
        return [action.__dict__ for action in load_actions(config)]

    @app.post("/api/actions")
    def run_action(payload: dict):
        from ..actions import run_action as execute_action
        try:
            return execute_action(config, payload["id"], payload["rel"], bool(payload.get("confirmed"))).__dict__
        except PermissionError as exc:
            raise HTTPException(428, str(exc)) from exc
        except (ValueError, PathEscape) as exc:
            raise HTTPException(400, str(exc)) from exc

    @app.get("/api/jobs")
    def jobs():
        from ..engine.corpus import load as load_corpus
        return load_corpus(config.root)

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

    # -- engine surfaces ---------------------------------------------------
    @app.get("/api/workspace")
    def workspace_state():
        from ..agent import workspace as workspace_module
        return workspace_module.resolve(config.root).to_dict()

    @app.get("/api/doctor")
    def doctor():
        from ..engine import doctor as doctor_module
        return doctor_module.report(config.root)

    @app.get("/api/sources")
    def sources():
        from ..engine import sources as sources_module
        return sources_module.ledger(config.root)

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
