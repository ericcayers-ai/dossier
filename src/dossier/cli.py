"""Dossier command line.

Two audiences, one binary. A human runs `dossier --root <folder>` to open the
workspace. A model runs `dossier agent brief` to get its task packet and
`dossier verify` to prove the work. Every gate command exits non-zero on
failure, so a batch generator can assert on it instead of reading a summary.
"""

from __future__ import annotations

import argparse
import json
import socket
import sys
import threading
import webbrowser
from pathlib import Path
from .copy import plural


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _emit(payload, as_json: bool, text: str = "") -> None:
    if as_json:
        print(json.dumps(payload, indent=2, ensure_ascii=False, default=str))
    else:
        print(text or json.dumps(payload, indent=2, ensure_ascii=False, default=str))


def _require_root(value: str | None) -> Path:
    if not value:
        raise SystemExit("--root is required for this command")
    root = Path(value).expanduser().resolve()
    if not root.is_dir():
        raise SystemExit(f"not a folder: {root}")
    return root


# -- serve -----------------------------------------------------------------

def _serve(root: Path, port: int, open_browser: bool) -> int:
    import uvicorn

    from .api.app import create_app
    from .config import AppConfig

    config = AppConfig.create(root)
    application = create_app(config)
    port = port or _free_port()
    # No token in the printed URL. `GET /` sets the httponly cookie the API accepts
    # (api/app.py), so the address never needs the value — and a bearer token in a
    # URL lands in terminal scrollback, shell history and any log that captures
    # this line, which `token-never-leaks` forbids.
    url = f"http://127.0.0.1:{port}/"
    print(f"Dossier URL: {url}", flush=True)
    if open_browser:
        threading.Timer(0.6, webbrowser.open, args=(url,)).start()
    uvicorn.run(application, host="127.0.0.1", port=port, log_level="info")
    return 0


# -- agent -----------------------------------------------------------------

def _agent(args) -> int:
    from . import agent

    action = args.agent_action

    if action == "manifest":
        _emit(agent.contract(), args.json)
        return 0
    if action == "route":
        matches = agent.route(args.text, limit=args.limit)
        _emit({"request": args.text, "matches": matches,
               "confident": bool(matches and matches[0]["score"] >= 10)},
              args.json)
        return 0 if matches else 1

    root = _require_root(getattr(args, "root", None))

    if action == "brief":
        from .agent import brief

        packet = brief.build(root, args.mode, args.text or "")
        if args.markdown:
            print(brief.render(packet, vendor=args.vendor))
        else:
            _emit(packet.to_dict(), True if args.json or not args.markdown else False)
        return 0

    if action == "prompt":
        from .agent import brief

        print(brief.system_prompt(root))
        return 0

    if action == "next":
        from .agent import loop

        unit = loop.next_unit(root)
        if args.json:
            _emit(unit, True)
        else:
            print(f"{unit['mode']} ({unit['kind']}) — {unit['reason']}")
            if unit.get("targets"):
                for target in unit["targets"][:8]:
                    print(f"  target: {target}")
            if unit.get("needs_user"):
                print("  needs the user before it can proceed")
        return 0

    if action == "status":
        from .agent import loop

        _emit(loop.status(root), args.json)
        return 0

    if action == "commit":
        from .agent import loop

        payload = json.loads(Path(args.handback).read_text(encoding="utf-8")) if args.handback \
            else json.loads(sys.stdin.read())
        result = loop.commit(root, payload)
        _emit(result, args.json)
        return 0 if result.get("accepted") else 1

    if action == "ask":
        # Fail-closed: with no endpoint, model id or key this reports unavailable
        # and changes nothing. It never falls back to a model, and `apply` is
        # refused by `model.AUTO_FORBIDDEN_MODES` (gate: no-auto-submit).
        from . import model

        report = model.availability(root)
        if not report["available"]:
            _emit(report, args.json, f"model unavailable: {report['reason']}")
            return 2
        try:
            result = model.ask(root, args.mode, args.text or "")
        except model.ModelModeRefused as exc:
            _emit({"available": True, "refused": str(exc)}, args.json, f"refused: {exc}")
            return 2
        except model.ModelError as exc:
            _emit({"available": True, "error": str(exc)}, args.json, f"model error: {exc}")
            return 1
        problems = result["commit"].get("problems") or []
        _emit(result, args.json,
              f"mode {result['mode']}: accepted={result['accepted']}"
              + (f" ({'; '.join(problems)})" if problems else ""))
        return 0 if result["accepted"] else 1

    if action == "adapters":
        from .agent import adapters

        if args.check:
            results = {rel: adapters.verify_block(root, rel) for rel in adapters.packs(root)}
            _emit(results, args.json)
            return 0 if all(results.values()) else 1
        results = adapters.write_all(root)
        _emit(results, args.json, "\n".join(f"{rel}: {state}" for rel, state in results.items()))
        return 0

    raise SystemExit(f"unknown agent action {action}")


# -- deterministic engines -------------------------------------------------

def _doctor(args) -> int:
    from .engine import doctor

    report = doctor.report(getattr(args, "root", None))
    if args.json:
        _emit(report, True)
    else:
        print(f"verdict: {report['verdict']}")
        print(f"python: {report['platform']['python']} ({report['platform']['system']} "
              f"{report['platform']['release']})")
        for name, available in report["capabilities"].items():
            print(f"  {'ok  ' if available else 'MISS'} {name}")
        for blocker in report["blockers"]:
            print(f"  blocker: {blocker}")
    return 0 if report["verdict"] == "ready" else 1


def _workspace(args) -> int:
    from .agent import workspace as workspace_module

    space = workspace_module.resolve(_require_root(getattr(args, "root", None)))
    payload = space.to_dict()
    if args.json:
        _emit(payload, True)
        return 0
    print(f"{space.name} — {space.root}")
    for key, value in space.counts.items():
        print(f"  {key}: {value}")
    if space.identity_doc:
        print(f"  identity: {space.identity_doc.rel}")
    print(f"  tracker: {space.tracker.get('rows')} rows {space.tracker.get('status_counts', {})}")
    if space.corpus.get("present"):
        print(f"  corpus: {space.corpus.get('rows')} rows, {space.corpus.get('sources_count')} boards, "
              f"fits {space.corpus.get('fits')}")
    for line in space.ready:
        print(f"  ready: {line}")
    for line in space.blockers:
        print(f"  blocker: {line}")
    return 0


def _open_index(root: Path, reindex: bool = False):
    """Open the workspace index, creating it and crawling once when it is empty.

    `AppConfig.create` only describes the layout; without `ensure()` the
    `.dossier` directory does not exist and SQLite cannot create its file, so
    the first `dossier audit` on a fresh folder used to die with
    "unable to open database file".
    """
    from .config import AppConfig
    from .db import open_db
    from .indexer import crawl

    config = AppConfig.create(root).ensure()
    connection = open_db(config.db_path)
    indexed = connection.execute("SELECT count(*) FROM files").fetchone()[0]
    stats = crawl(config, connection) if (reindex or indexed == 0) else None
    return config, connection, stats


def _audit(args) -> int:
    from . import audit as audit_module

    root = _require_root(getattr(args, "root", None))
    _config, connection, stats = _open_index(root, reindex=args.reindex)
    try:
        result = audit_module.audit_workspace(root, connection)
    finally:
        connection.close()
    if args.json:
        payload = dict(result)
        payload["indexed_now"] = (
            {"seen": stats.seen, "indexed": stats.indexed, "errors": stats.errors}
            if stats is not None else None
        )
        _emit(payload, True)
    else:
        if stats is not None:
            print(f"indexed now: seen={stats.seen} indexed={stats.indexed} errors={stats.errors}")
        print(f"audit {result['generated_on']}")
        for check in result["checks"]:
            print(f"  [{check['status']:>9}] {check['label']} — {check['detail']}")
    failed = [check for check in result["checks"] if check["status"] == "attention"]
    return 1 if failed else 0


def _handoff(args) -> int:
    from . import audit as audit_module

    root = _require_root(getattr(args, "root", None))
    _config, connection, _stats = _open_index(root)
    try:
        result = audit_module.build_handoff(root, connection)
    finally:
        connection.close()
    out = Path(args.out) if args.out else root / "resync" / "handoff.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    from .safety import trash_then_write_text

    trash_then_write_text(root, out, json.dumps(result["packet"], indent=2, ensure_ascii=False))
    prompt_path = out.with_suffix(".md")
    trash_then_write_text(root, prompt_path, result["prompt"])
    if args.json:
        _emit({"packet": str(out), "prompt": str(prompt_path), "counts": result["packet"]["counts"]}, True)
    else:
        print(f"packet: {out}")
        print(f"prompt: {prompt_path}")
        print(f"counts: {result['packet']['counts']}")
    return 0


def _corpus(args) -> int:
    from .engine import corpus

    root = _require_root(getattr(args, "root", None))
    action = args.corpus_action
    if action == "build":
        result = corpus.write(root, args.out)
        _emit(result, args.json, json.dumps({k: result[k] for k in
              ("folder", "rows", "distinct_ids", "duplicate_ids", "sources")}, indent=2))
        return 1 if result.get("duplicate_ids") else 0
    if action == "rank":
        jobs = corpus.load(root)
        if not jobs:
            raise SystemExit("no corpus at all_boards_data/all_jobs.json")
        report = corpus.rank_report(jobs, limit=args.limit)
        if args.write:
            from datetime import date
            from .safety import trash_then_write_text

            target = root / f"ranked-jobs-{date.today().isoformat()}.json"
            trash_then_write_text(root, target, json.dumps(corpus.rank(jobs), indent=2,
                                                          ensure_ascii=False))
            report["written"] = str(target)
        _emit(report, args.json)
        return 0
    if action == "propagate":
        jobs = corpus.load(root)
        ranking_path = Path(args.ranking)
        if not ranking_path.exists():
            raise SystemExit(f"no ranking view at {ranking_path}")
        ranking = json.loads(ranking_path.read_text(encoding="utf-8"))
        report = corpus.propagate_fit(jobs, ranking)
        if report["unmatched"]:
            _emit(report, args.json)
            return 1
        corpus.build_facets(jobs, root / "all_boards_data", root=root)
        report["corpus_hash"] = corpus.aggregate_hash(jobs)
        _emit(report, args.json)
        return 0
    if action == "folders":
        _emit([str(path) for path in corpus.board_folders(root)], args.json)
        return 0
    if action == "dedupe":
        jobs = corpus.load(root)
        kept, report = corpus.dedupe(jobs)
        _emit(report, args.json)
        return 0
    raise SystemExit(f"unknown corpus action {action}")


def _tree(args) -> int:
    from .engine import tree

    root = _require_root(getattr(args, "root", None))
    action = args.tree_action
    if action == "status":
        _emit(tree.status(root), args.json)
        return 0
    if action == "add":
        payload = {
            "id": args.id,
            "type": args.node_type,
            "title": args.title,
            "state": args.state,
            "date": args.date,
            "details": args.details,
        }
        _emit(tree.upsert_node(root, payload), args.json)
        return 0
    if action == "link":
        _emit(tree.link_nodes(root, args.parent, args.child), args.json)
        return 0
    if action == "view":
        if args.json:
            _emit(tree.graph(root), True)
        else:
            print(tree.to_ascii(root) if args.format == "ascii" else tree.to_mermaid(root))
        return 0
    if action == "sync":
        result = tree.sync(root)
        _emit(result, args.json)
        return 0 if result["sources_present"] else 1
    raise SystemExit(f"unknown tree action {action}")


def _track(args) -> int:
    from .engine import tracker

    root = _require_root(getattr(args, "root", None))
    action = args.track_action
    if action == "summary":
        _emit(tracker.summary(root), args.json)
        return 0
    if action == "cadence":
        result = tracker.cadence(root, overdue_only=args.overdue)
        if args.json:
            _emit(result, True)
        else:
            print(f"follow-up cadence — {result['analysis_date']}")
            print(f"  {result['total_tracked']} tracked, {result['actionable']} actionable, "
                  f"{result['undated']} without a confirmed date")
            print(f"  counts: {result['counts']}")
            for entry in result["entries"]:
                print(f"  #{entry['number']} {entry['company'][:24]:<24} {entry['status']:<10} "
                      f"{entry['urgency']:<8} next={entry['next_date'] or '-'}")
            for entry in result["needs_date"]:
                print(f"  #{entry['number']} {entry['company'][:24]:<24} needs an Applied date")
        return 0
    if action == "outcome":
        result = tracker.record_outcome(root, args.number, args.outcome,
                                        applied_date=args.applied, confirmed=args.confirmed,
                                        note=args.note or "")
        _emit(result, args.json)
        return 0 if result.get("written") else 1
    if action == "followup":
        result = tracker.append_followup(root, args.number, args.date,
                                         channel=args.channel or "", contact=args.contact or "",
                                         note=args.note or "")
        _emit(result, args.json)
        return 0 if result.get("written") else 1
    raise SystemExit(f"unknown track action {action}")


def _keywords(args) -> int:
    from .engine import jd_skill_gap

    root = _require_root(getattr(args, "root", None))
    action = args.keywords_action
    if action == "gap":
        posting = Path(args.posting)
        if not posting.is_absolute():
            posting = root / args.posting
        posting = posting.resolve()
        resume = Path(args.resume) if args.resume else root / "resume.md"
        if not resume.is_absolute():
            resume = (root / args.resume) if args.resume else resume
        if not posting.exists():
            raise SystemExit(f"no posting at {posting}")
        if not resume.exists():
            raise SystemExit(f"no resume extract at {resume}")
        out = Path(args.out) if args.out else root / f"{posting.stem}.skillgap.json"
        result = jd_skill_gap.write(posting, resume, out)
        if args.json:
            _emit(result, True)
        else:
            print(f"skills found: {result['skills_found']}  "
                  f"requirement section: {result['saw_requirement_section']}")
            print(f"  existing  ({len(result['existing'])}): {', '.join(result['existing']) or '-'}")
            print(f"  supported ({len(result['supported'])}): {', '.join(result['supported']) or '-'}")
            print(f"  gap       ({len(result['gap'])}): {', '.join(result['gap']) or '-'}")
            if result["warning"]:
                print(f"  warning: {result['warning']}")
            print(f"  wrote: {out}")
        return 0 if result["saw_requirement_section"] else 1
    if action == "aggregate":
        result = jd_skill_gap.aggregate(root)
        if args.write:
            target = root / "upskill.md"
            lines = ["# Recurring gaps", "",
                     "Counted across every keyword report in this workspace.", ""]
            for entry in result["recurring_gaps"]:
                lines.append(f"- **{entry['skill']}** — {plural(entry['postings'],'posting')}")
            lines += ["", "A recurring gap is a learning target or an honest omission — "
                          "never a licence to word-stuff."]
            from .safety import trash_then_write_text

            trash_then_write_text(root, target, "\n".join(lines))
            result["written"] = str(target)
        _emit(result, args.json)
        return 0
    raise SystemExit(f"unknown keywords action {action}")


def _negotiate(args) -> int:
    from .engine import negotiate

    root = _require_root(getattr(args, "root", None))
    result = negotiate.analyze_paths(root, wage=args.wage, frequency=args.frequency,
                                     occurrences=args.occurrences)
    if result.get("error"):
        _emit(result, args.json)
        return 1
    if args.write:
        result["written"] = str(negotiate.write_drafts(root, result))
    if args.json:
        _emit(result, True)
    else:
        print(f"stories scanned: {result['stories_scanned']}  claims found: {result['claims_found']}")
        print(f"verified: {result['verified']}  excluded by the verbatim gate: "
              f"{result['excluded_unverified']}")
        for entry in result["calculable"]:
            print(f"\n  {entry['story']}")
            print(f"  {entry['calculation']['formula']}")
        for entry in result["uncalculable"]:
            print(f"  uncalculable — {entry['story']}: {entry['reason']}")
    return 0


def _render(args) -> int:
    from .engine import render

    if args.docx:
        docx = Path(args.docx).resolve()
        pdf = Path(args.pdf).resolve() if args.pdf else docx.with_suffix(".pdf")
        result = render.export_pdf(docx, pdf)
        _emit(result, args.json)
        return 0
    root = _require_root(getattr(args, "root", None))
    result = render.render_stale(root)
    if result.get("stale"):
        from datetime import date
        result["report"] = str(render.write_report(
            root, f"render-{date.today().isoformat()}.json", result))
    if result.get("failed"):
        _emit(result, args.json)
        return 1
    _emit(result, args.json,
          f"stale={result['stale']} rebuilt={result['rebuilt']} failed={len(result['failed'])}"
          + (f" report={result['report']}" if result.get("report") else ""))
    if args.visual and result.get("rebuilt_detail"):
        for entry in result["rebuilt_detail"]:
            png = render.pdf_to_png(root / entry["pdf"],
                                    root / ".dossier" / "render" / (Path(entry["pdf"]).stem + ".png"))
            print(f"  page image: {png}")
    return 0


def _verify(args) -> int:
    from .engine import verify

    approved = None
    if getattr(args, "approved", None):
        approved = json.loads(Path(args.approved).read_text(encoding="utf-8"))

    action = args.verify_action
    if action == "source-diff":
        result = verify.source_diff(Path(args.base), Path(args.candidate), approved)
        _emit(result, args.json)
        return 0 if result["ok"] else 1
    if action == "text-layer":
        keywords = args.keyword or []
        result = verify.text_layer(Path(args.pdf), expect=args.expect or [], keywords=keywords)
        _emit(result, args.json)
        return 0 if result["ok"] else 1
    if action == "visual":
        margins = None
        geometry = args.margins_from or args.base
        if geometry:
            from .engine.tailor import layout_spec
            margins = layout_spec(Path(geometry))["margins_pt"]
        result = verify.visual(Path(args.pdf), expected_pages=args.expected_pages, margins=margins,
                               image=Path(args.image) if getattr(args, "image", None) else None)
        _emit(result, args.json)
        # ok is false when no page image could be produced, so a pass here means
        # a page was actually rasterised — not merely that the geometry was clean.
        return 0 if result["ok"] else 1
    if action == "template":
        spec = json.loads(Path(args.spec).read_text(encoding="utf-8")) if args.spec else {}
        result = verify.template_fill(Path(args.template), Path(args.candidate), spec)
        if args.json:
            _emit(result, True)
        else:
            for check in result["checks"]:
                print(f"  [{'pass' if check['ok'] else 'FAIL'}] {check['id']} — {check['detail']}")
            print(f"passed: {result['passed']}")
        return 0 if result["passed"] else 1
    if action == "all":
        # A resume is expected to carry several dates; a letter legitimately
        # carries one, so the expectation is derived from what was supplied.
        min_dates = args.min_dates if args.min_dates is not None else (2 if args.base else 0)
        result = verify.all(
            Path(args.base) if args.base else None,
            Path(args.candidate) if args.candidate else None,
            Path(args.pdf) if args.pdf else None,
            expected_pages=args.expected_pages,
            approved=approved,
            keywords=args.keyword or [],
            min_dates=min_dates,
            margins_from=Path(args.margins_from) if args.margins_from else None,
        )
        if args.json:
            _emit(result, True)
        else:
            for check in result["checks"]:
                print(f"  [{'pass' if check['ok'] else 'FAIL'}] {check['id']} — {check['detail']}")
            for skipped in result["skipped"]:
                print(f"  [skip] {skipped}")
            print(f"passed: {result['passed']}")
        return 0 if result["passed"] else 1
    raise SystemExit(f"unknown verify action {action}")


def _sources(args) -> int:
    from .engine import sources
    from .safety import trash_then_write_text
    from datetime import date as _date

    root = _require_root(getattr(args, "root", None))

    if args.open or args.close:
        name = (args.open or args.close).strip().casefold()
        path = root / ".dossier" / "sources.json"
        try:
            table = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            table = {}
        if not isinstance(table, dict):
            table = {}
        if args.open:
            policy = args.policy or "user_supplied"
            if policy not in sources.POLICY_VALUES:
                raise ValueError(f"unknown policy {policy!r}; known: {', '.join(sources.POLICY_VALUES)}")
            table[name] = {"policy": policy, "status": "available",
                           "detail": f"Opened by the workspace owner on {_date.today().isoformat()}."}
            if args.robots is not None:
                table[name]["robots"] = bool(args.robots)
        else:
            # Closing removes the override, so the shipped default applies again.
            table.pop(name, None)
        trash_then_write_text(root, path, json.dumps(table, indent=2, ensure_ascii=False))
        if args.json:
            _emit({"action": "open" if args.open else "close", "source": name,
                   "file": str(path.relative_to(root)),
                   "policy": sources.policy(name, root)}, True)
            return 0
        print(f"{name}: policy is now {sources.policy(name, root)}")
        return 0

    result = sources.ledger(root)
    if args.json:
        _emit(result, True)
        return 0
    print(f"coverage: {result['coverage'].get('detail', 'none')}")
    for name, row in result["sources"].items():
        records = row.get("records")
        print(f"  {name:<12} {row['policy']:<15} {row['status']:<12} "
              f"records={records if records is not None else '-'}")
    if result["needs_user_supply"]:
        print(f"  needs the user to supply: {', '.join(result['needs_user_supply'])}")
    return 0


def _sanitize(args) -> int:
    from .engine import sources

    text = Path(args.path).read_text(encoding="utf-8", errors="replace") if args.path \
        else sys.stdin.read()
    result = sources.sanitize(text, args.source or "unknown")
    if args.json:
        _emit(result, True)
    else:
        print(f"flagged: {result['flagged']}")
        for finding in result["findings"]:
            print(f"  {finding['kind']}: {finding}")
        print(f"clean characters: {len(result['clean'])}")
    # posting-is-data is a gate, not a report: a posting that carried hidden
    # carriers or instruction-shaped text exits non-zero so a caller can branch on
    # the exit code instead of parsing prose. `flagged` is the same condition the
    # --json payload reports, so the two channels cannot disagree.
    return 1 if result["flagged"] else 0


def _identity(args) -> int:
    """The identity surface: ask, mine, merge, write, match.

    `status` is the cheap one (no browser, no network); `match` reads the corpus and
    scores it. Both are deterministic.
    """
    from .engine import identity

    root = _require_root(getattr(args, "root", None))
    action = args.identity_action

    if action == "status":
        data = identity.profile(root)
        payload = {**data, "questions": identity.questions_with_state(root),
                   "answers": identity.load_answers(root)}
        if args.json:
            _emit(payload, True)
            return 0
        print(f"identity: {data['answered']}/{plural(data['questions'],'question').split(' ',1)[1]} answered, "
              f"{plural(data['sources'].get('document', 0),'value')} mined from documents")
        for name, entry in data["fields"].items():
            value = entry["value"]
            shown = ", ".join(str(item) for item in value) if isinstance(value, list) else str(value)
            print(f"  {name:<14} {entry['source']:<8} {shown[:100]}")
        if data["missing_required"]:
            print(f"  missing required: {', '.join(data['missing_required'])}")
        return 0

    if action == "questions":
        rows = identity.questions_with_state(root)
        if args.json:
            _emit({"questions": rows}, True)
            return 0
        for row in rows:
            mark = "known" if row["answered"] else ("REQUIRED" if row["required"] else "open")
            print(f"  {row['id']:<14} {mark:<9} {row['prompt']}")
            if row["choices"]:
                print(f"  {'':<14} {'':<9} one of: {', '.join(row['choices'])}")
        return 0

    if action == "answer":
        if args.from_json:
            payload = json.loads(Path(args.from_json).read_text(encoding="utf-8"))
            answers = payload.get("answers", payload) if isinstance(payload, dict) else {}
        else:
            if not args.question or args.value is None:
                raise ValueError("identity answer needs --question <id> --value <value>, "
                                 "or --from-json <file>")
            answers = {args.question: args.value}
        saved = identity.save_answers(root, answers)
        data = identity.profile(root)
        if args.json:
            _emit({**saved, "complete": data["complete"],
                   "missing_required": data["missing_required"]}, True)
        else:
            print(f"saved {plural(len(saved['saved']),'answer')}; "
                  f"{'profile complete' if data['complete'] else 'still missing: ' + ', '.join(data['missing_required'])}")
        return 0

    if action == "mine":
        proposals = identity.mine_documents(root)
        if args.json:
            _emit({"proposals": proposals}, True)
            return 0
        for item in proposals:
            value = item["value"]
            shown = ", ".join(str(part) for part in value) if isinstance(value, list) else str(value)
            print(f"  {item['field']:<14} {item['confidence']:<7} {shown[:80]}")
            print(f"  {'':<14} {item['source']}:{item['line']}  {item['evidence'][:90]}")
        return 0

    if action == "write":
        report = identity.write_identity(root, name=args.out)
        if args.json:
            _emit(report, True)
        else:
            print(f"wrote {plural(report['fields'],'field')} to {report['path']}")
            if report["missing_required"]:
                print(f"  still unanswered: {', '.join(report['missing_required'])}")
        return 0

    if action == "match":
        if args.posting:
            result = identity.match_posting(Path(args.posting), root)
        else:
            result = identity.rank_corpus(root, limit=args.limit, min_band=args.min_band or "")
        if args.json:
            _emit(result, True)
            return 0
        if not result.get("present"):
            print(result.get("reason", "no corpus"))
            return 1
        print(f"scored {result['scored']} of {plural(result['rows'],'row')}: "
              + ", ".join(f"{band} {count}" for band, count in result["band_counts"].items()))
        for row in result.get("matched", []):
            print(f"  {row['band']:<8} {row['score']:>3}  {row.get('title', '')[:38]:<38} "
                  f"{row.get('employer', '')[:22]:<22} {row.get('source', '')}")
        for row in result.get("disqualified", []):
            print(f"  DISQUAL  {row.get('title', '')[:38]:<38} {row['disqualifiers'][0][:60]}")
        return 0

    if action == "labels":
        from .engine import evaluation

        report = evaluation.worksheet(root, limit=args.limit)
        out = Path(args.out) if args.out else root / ".dossier" / "eval" / f"labels-{report['corpus_hash']}.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        if args.json:
            _emit({**{k: v for k, v in report.items() if k != "rows"},
                   "rows": len(report["rows"]), "path": str(out)}, True)
            return 0
        graded = sum(1 for row in report["rows"] if row["grade"])
        print(f"labelling worksheet: {plural(len(report['rows']),'row')} -> {out}")
        print(f"  {plural(graded,'row')} proposed from the tracker's own Fit column (source: tracker);")
        print(f"  {plural(len(report['rows']) - graded,'row')} need your grade (strong/possible/unlikely/skip).")
        if report["unmatched_tracker_rows"]:
            print(f"  {plural(len(report['unmatched_tracker_rows']),'tracker row')} matched no posting; "
                  "they are listed in the file with their reason.")
        return 0

    if action == "eval":
        from .engine import evaluation

        if not args.labels:
            raise ValueError("identity eval needs --labels <file> (see `dossier identity labels`)")
        report = evaluation.evaluate_workspace(root, args.labels, k=args.k, source=args.source)
        verdict = None
        if args.baseline:
            baseline_path = Path(args.baseline)
            if not baseline_path.exists():
                raise ValueError(f"no baseline at {baseline_path}; record one with --write-baseline")
            baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
            verdict = evaluation.compare_to_baseline(report, baseline)
        if args.write_baseline:
            target = Path(args.write_baseline)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(evaluation.record_baseline(report), indent=2),
                              encoding="utf-8")
        if args.json:
            _emit({**report, "verdict": verdict}, True)
        else:
            if not report.get("present"):
                print(report.get("reason", "no evaluation"))
                print(f"  graded rows offered: {report.get('grades_offered', 0)}, "
                      f"matched a scored row: {report.get('n_graded', 0)}")
            else:
                product = report["product"]
                arrival = report["baseline_arrival"]
                print(f"graded {report['n_graded']} of {plural(report['rows'],'row')} "
                      f"({plural(report['grades_off_corpus'],'grade')} matched no row)")
                print(f"  {'':<22}{'nDCG@' + str(report['k']):>10}{'P@' + str(report['k']):>10}"
                      f"{'slots P@' + str(report['k']):>12}{'recall@25':>11}{'spearman':>10}")
                print(f"  {'identity score':<22}{product['ndcg']!s:>10}"
                      f"{product['precision']!s:>10}{product['precision_slots']!s:>12}"
                      f"{product['recall']!s:>11}{product['spearman']!s:>10}")
                print(f"  {'arrival order':<22}{arrival['ndcg']!s:>10}"
                      f"{arrival['precision']!s:>10}{arrival['precision_slots']!s:>12}"
                      f"{arrival['recall']!s:>11}{arrival['spearman']!s:>10}")
                print(f"  grades: " + ", ".join(f"{k} {v}" for k, v in report["grade_counts"].items())
                      + f"; from {report['sources']}")
                print(f"  judged rows in the first {report['k']}: {product['judged_in_top_k']}"
                      " (an ungraded row in the top slots counts as a miss)")
        if verdict is not None:
            if verdict["ok"]:
                print("gate fit-is-measured: pass — no metric fell below the recorded baseline")
                return 0
            for failure in verdict["failures"]:
                print(f"gate fit-is-measured: FAIL — {failure}")
            return 1
        return 0

    raise SystemExit(f"unknown identity action {action}")


def _feeds(args) -> int:
    """The public-JSON layer: list what may be fetched, or fetch one board.

    This is the caller the six adapters never had. It writes the same
    `<source>_data/all_jobs.json` shape the corpus builder already reads, so a
    fetched board flows into `dossier corpus build` and `rank` with no new format.
    """
    from . import feeds as feed_module
    from .engine import sources as source_engine
    from .safety import trash_then_write_text
    from .scrape.extract import text as html_text
    from datetime import date, datetime, timezone

    action = args.feed_action
    root = _require_root(getattr(args, "root", None))

    if action == "list":
        table = source_engine.effective_policies(root)
        rows = []
        for name in sorted(feed_module.ADAPTERS):
            entry = table.get(name, {})
            rows.append({"source": name, "policy": entry.get("policy", "manual_only"),
                         "permitted": source_engine.permitted(name, root),
                         "needs_board": name in feed_module.BOARD_PLACEHOLDERS,
                         "endpoint": feed_module.ENDPOINTS[name]})
        if args.json:
            _emit({"feeds": rows}, True)
            return 0
        for row in rows:
            print(f"{row['source']:<10} {row['policy']:<15} "
                  f"{'fetchable' if row['permitted'] else 'refused':<10} "
                  f"{'--board required' if row['needs_board'] else ''} {row['endpoint']}")
        return 0

    if action == "fetch":
        source = args.source.strip().casefold()
        # Refused before the client exists, so a prohibited board never opens a socket.
        source_engine.assert_allowed(source, root)
        result = feed_module.fetch_board(source, board=args.board, root=root)
        rows = result["jobs"]
        limit = max(1, args.limit)
        truncated = len(rows) > limit
        rows = rows[:limit]
        for row in rows:
            # posting-is-data: a description is third-party text and is sanitised
            # before it reaches the corpus, exactly like an archived posting file.
            description = row.get("description") or ""
            if "<" in description:
                # Board descriptions are HTML. The tags are not requirements, and a
                # `<script>` body reads like prose to a naive tokenizer.
                description = html_text(description)
            cleaned = source_engine.sanitize(description, source)
            row["description"] = cleaned["clean"]
            if cleaned["flagged"]:
                row["_postings_sanitized"] = cleaned["findings"]
        out_dir = Path(args.out) if args.out else root
        target = out_dir / f"{source}_data" / "all_jobs.json"
        payload = json.dumps(rows, indent=2, ensure_ascii=False)
        trash_then_write_text(root, target, payload)
        provenance = root / ".dossier" / "scrape" / "feeds" / (
            f"{source}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json")
        provenance.parent.mkdir(parents=True, exist_ok=True)
        provenance.write_text(json.dumps({"source": source, "url": result["url"],
                                          "captured_on": date.today().isoformat(),
                                          "records": len(rows),
                                          "truncated": truncated}, indent=2), encoding="utf-8")
        summary = {"source": source, "url": result["url"], "records": len(rows),
                   "total": result["records"], "truncated": truncated,
                   "path": str(target), "out": str(out_dir),
                   "complete": not truncated}
        if args.json:
            _emit(summary, True)
        else:
            print(f"{'complete' if not truncated else 'PARTIAL'}: {source} - "
                  f"{len(rows)} of {plural(result['records'],'record')} -> {target}")
            if truncated:
                print(f"  reason: stopped at --limit {limit}; the board may hold more")
        return 0 if not truncated else 1

    raise SystemExit(f"unknown feeds action {action}")


def _scrape(args) -> int:
    """Capture a page, or report what could be captured and why it was not.

    Exit codes are the contract every other gate in this CLI uses: 0 means the
    capture is complete, 1 means it is partial or refused for a reason the user
    must act on, 2 means the request itself was wrong (a bad recipe, a policy
    refusal, a missing engine).
    """
    from .scrape import browser, recipes as recipe_module, runner
    from .scrape.errors import ScrapeError
    from .scrape.session import SessionStore, import_netscape_cookies

    action = args.scrape_action
    root = _require_root(getattr(args, "root", None))

    if action == "status":
        result = runner.status(root)
        if args.json:
            _emit(result, True)
            return 0
        print(f"captured postings: {result['captured_postings']}")
        for name, row in result["engines"].items():
            state = "ready" if row["available"] else "MISSING"
            print(f"  engine  {name:<11} {state:<8} {row.get('version') or row['detail'][:60]}")
        for recipe in result["recipes"]:
            mark = "due" if recipe["due"] else recipe["reason"]
            print(f"  recipe  {recipe['id']:<22} {recipe['source']:<12} {recipe['kind']:<6} {mark}")
        for error in result["recipe_errors"]:
            print(f"  BROKEN  {error['path']}: {error['error']}")
        for row in result["sessions"]:
            state = "expired" if row["expired"] else "saved"
            print(f"  session {row['source']:<22} {state:<8} {row.get('saved_at') or ''} "
                  f"cookies={row.get('cookie_count')}")
        if not result["sessions"]:
            print("  session (none) - an authenticated capture needs `dossier scrape login`")
        challenge = result.get("challenge") or {}
        solver = challenge.get("solver") or {}
        print(f"  challenge policy {challenge.get('configured', '?')} "
              f"(default {challenge.get('default', '?')}); solver "
              f"{'configured' if solver.get('configured') else 'not configured'}")
        return 0

    if action == "recipes":
        found, errors = recipe_module.discover(root, include_shipped=not args.workspace_only)
        payload = {"recipes": [recipe.to_dict() for recipe in found], "errors": errors}
        if args.json:
            _emit(payload, True)
            return 1 if errors else 0
        for recipe in found:
            print(f"{recipe.id:<24} {recipe.origin:<9} {recipe.source:<12} "
                  f"{'list' if recipe.is_list else 'single':<6} {recipe.start_url}")
        for error in errors:
            print(f"BROKEN {error['path']}: {error['error']}")
        return 1 if errors else 0

    if action == "login":
        store = SessionStore(root)
        reports = browser.available()
        if not reports["playwright"]["available"]:
            raise ScrapeError(reports["playwright"]["detail"])
        print(f"Opening {args.url} in a browser window. Sign in yourself; Dossier types nothing "
              "and stores only the cookies the browser receives.")
        confirm = None
        if not args.selector:
            def confirm():
                try:
                    input("Finish signing in, then press Enter here to save the session... ")
                except EOFError:
                    raise ScrapeError(
                        "no confirmation was read, so no session was saved. Re-run with "
                        "--selector <element only visible when signed in> in a non-interactive "
                        "shell.") from None
        meta = browser.PlaywrightDriver().sign_in(
            url=args.url, store=store, source=args.source,
            success_selector=args.selector or "", timeout_s=args.timeout,
            headless=args.headless, confirm=confirm)
        if args.json:
            _emit(meta, True)
        else:
            print(f"session saved for {meta['source']}: {plural(meta['cookie_count'],'cookie')} "
                  f"from {meta['source_url']}")
        return 0

    if action == "session-import":
        store = SessionStore(root)
        text = Path(args.cookies).read_text(encoding="utf-8", errors="replace")
        meta = import_netscape_cookies(store, args.source, text, source_url=args.url)
        if args.json:
            _emit(meta, True)
        else:
            print(f"session imported for {meta['source']}: {plural(meta['cookie_count'],'cookie')}")
        return 0

    if action == "session-clear":
        removed = SessionStore(root).clear(args.source)
        _emit({"source": args.source, "removed": removed}, args.json,
              f"{'removed' if removed else 'no session for'} {args.source}")
        return 0

    if action == "capture":
        result = runner.capture_url(
            root, args.url, source=args.source, driver=args.driver,
            headless=not args.headed, screenshot=not args.no_screenshot,
            timeout_s=args.timeout, wait_until=args.wait_until, selector=args.selector,
            session=args.session, robots=args.robots, delay_ms=args.delay_ms,
            refresh=args.refresh, challenge=args.challenge,
            await_clear_s=args.await_seconds, min_match=args.min_match or 0)
        if args.json:
            _emit(result, True)
        else:
            verdict = "complete" if result.get("complete") else "PARTIAL"
            print(f"{verdict}: {result['url']}")
            if result.get("reason"):
                print(f"  reason: {result['reason']}")
            if result.get("posting"):
                print(f"  posting: {result['posting']}")
            if result.get("driver"):
                print(f"  driver: {result['driver']}  source: {result.get('source')}  "
                      f"session: {result.get('session', {}).get('used')}")
        return 0 if result.get("complete") else 1

    if action == "run":
        found, errors = recipe_module.discover(root)
        if errors and args.recipe:
            broken = [row for row in errors if Path(row["path"]).stem == args.recipe]
            if broken:
                raise ScrapeError(broken[0]["error"])
        chosen = []
        if args.recipe:
            match = [recipe for recipe in found if recipe.id == args.recipe]
            if not match:
                raise ValueError(f"unknown recipe {args.recipe!r}; known: "
                                 f"{', '.join(r.id for r in found) or 'none'}")
            chosen = match
        elif args.due:
            chosen = runner.due_recipes(root)[: args.max_recipes]
            if not chosen:
                _emit({"ran": [], "reason": "no recipe is due"}, args.json,
                      "no recipe is due")
                return 0
        else:
            raise ValueError("scrape run needs --recipe <id> or --due")

        results = []
        for recipe in chosen:
            result = runner.run_recipe(
                root, recipe, limit=args.limit, pages=args.pages, driver=args.driver,
                headless=None if args.headed is False else (not args.headed),
                refresh=args.refresh, screenshot=not args.no_screenshot,
                delay_ms=args.delay_ms, challenge=args.challenge,
                await_clear_s=args.await_seconds, min_match=args.min_match)
            results.append(result)
            if not args.json:
                verdict = "complete" if result["complete"] else "PARTIAL"
                print(f"{verdict}: {recipe.id} - {result['items_captured']} captured, "
                      f"{len(result['duplicates'])} duplicate, {len(result['failures'])} failed")
                if result.get("reason"):
                    print(f"  reason: {result['reason']}")
                for failure in result["failures"][:5]:
                    print(f"  failed {failure['stage']}: {failure['url']} - {failure['error'][:140]}")
        if args.json:
            _emit({"runs": results,
                   "complete": all(row["complete"] for row in results)}, True)
        return 0 if all(row["complete"] for row in results) else 1

    raise SystemExit(f"unknown scrape action {action}")


def _panel(args) -> int:
    """Seven reviewers, seven scores, and the exact line that cost the most."""
    from .engine import panel as panel_engine
    from .extract import extract_text
    from .safety import resolve_in_root

    root = _require_root(getattr(args, "root", None))
    resume = resolve_in_root(root, args.resume)
    if not resume.exists():
        raise FileNotFoundError(f"no resume at {args.resume!r} in {root}")
    text, meta = extract_text(resume)
    if meta.get("error"):
        raise ValueError(f"could not read {args.resume}: {meta['error']}")
    posting = ""
    if args.posting:
        posting_path = resolve_in_root(root, args.posting)
        posting, posting_meta = extract_text(posting_path)
        if posting_meta.get("error"):
            raise ValueError(f"could not read {args.posting}: {posting_meta['error']}")
    result = panel_engine.run(text, posting=posting, target_role=args.role or "")
    if args.json:
        _emit(result, True)
    else:
        print(panel_engine.render(result))
    return 0 if result["verdict"] != "fail" else 1


def _tailor(args) -> int:
    from .engine import tailor

    action = args.tailor_action
    if action == "inspect":
        spec = tailor.layout_spec(Path(args.docx))
        _emit(spec, args.json)
        if not args.json:
            print(f"font: {spec['primary_font']}  accent: {spec['primary_accent']}")
            print(f"tables: {spec['tables']}  paragraphs: {spec['paragraphs']}")
        return 0
    if action == "blocks":
        _emit(tailor.read_blocks(Path(args.docx)), args.json)
        return 0
    if action == "fields":
        fields = tailor.template_fields(Path(args.template))
        _emit({"template": args.template, "fields": fields}, args.json,
              "\n".join(fields) or "no {{placeholders}} found")
        return 0
    if action == "template":
        spec = json.loads(Path(args.spec).read_text(encoding="utf-8"))
        result = tailor.fill_template(Path(args.template), Path(args.out), spec,
                                     root=getattr(args, "root", None),
                                     strict=not args.allow_leftovers)
        if args.json:
            _emit(result, True)
        else:
            filled = sum(result["replaced"].values())
            print(f"filled {plural(filled,'placeholder')} in {plural(result['paragraphs_touched'],'paragraph')} "
                  f"-> {result['output']}")
            if result["unused"]:
                print(f"  unused {plural(len(result['unused']),'field')}: {', '.join(result['unused'])}")
            if result["leftovers"]:
                print(f"  UNFILLED: {', '.join(result['leftovers'])}")
        return 0
    if action == "replace":
        replacements = json.loads(Path(args.map).read_text(encoding="utf-8"))
        result = tailor.apply_replacements(Path(args.base), Path(args.out), replacements,
                                           root=getattr(args, "root", None))
        payload = {"output": result.output, "applied": result.applied, "missed": result.missed}
        _emit(payload, args.json)
        return 0 if not result.missed else 1
    if action == "cover-letter":
        payload = json.loads(Path(args.spec).read_text(encoding="utf-8"))
        # A spec is user-authored JSON. Splatting it as **kwargs turned the
        # documented command into `TypeError: got an unexpected keyword argument
        # 'role'` the moment a spec carried a natural extra field, so the split is
        # explicit and lives in the engine: undeclared keys are reported in the
        # payload itself (a --json caller must see them too, not only stderr) and
        # a missing declared field is an error through the normal exit path.
        try:
            fields, ignored = tailor.cover_letter_spec(payload)
        except ValueError as exc:
            if args.json:
                _emit({"ok": False, "detail": str(exc),
                       "expected": list(tailor.COVER_LETTER_FIELDS)}, True)
                return 2
            raise SystemExit(str(exc)) from None
        result = tailor.cover_letter(Path(args.base), Path(args.out),
                                     root=getattr(args, "root", None), **fields)
        if ignored:
            result["ignored_keys"] = ignored
            result["warning"] = (
                f"ignored {plural(len(ignored),'undeclared spec key')}: " + ", ".join(ignored)
                + "; the letter was built from the declared fields only")
        _emit(result, args.json)
        if ignored and not args.json:
            print(f"warning: {result['warning']}")
        return 0
    if action == "import":
        result = tailor.import_base(Path(args.source), _require_root(getattr(args, "root", None)),
                                    name=args.name, overwrite=args.overwrite)
        _emit(result, args.json)
        return 0 if result.get("imported") else 1
    raise SystemExit(f"unknown tailor action {action}")


# -- trash -----------------------------------------------------------------

def _describe_prune(report: dict) -> str:
    """A readable account of one prune: what went, what stayed, and why."""
    if not report["enabled"]:
        return report["reason"]
    head = (f"trash retention: {plural(report['retention_days'],'day')} "
            f"(from {report['retention_source']}), cutoff {report['cutoff']}")
    if report["dry_run"]:
        head += "  [dry run: nothing deleted]"
    lines = [head]
    if report["reason"]:
        lines.append(report["reason"])
    lines.append(f"removed {report['removed_count']}, freed {report['freed_bytes']} bytes, "
                 f"kept {report['kept_count']}, skipped {report['skipped_count']}, "
                 f"{report['entries_remaining']} timestamped entries left")
    for row in report["removed"]:
        lines.append(f"  - {row['entry']}  age {row.get('age_days')}d  {row['reason']}")
    for row in report["kept"]:
        lines.append(f"  = {row['entry']}  {row['reason']}")
    for row in report["skipped"]:
        lines.append(f"  ! {row['entry']}  {row['reason']}")
    for warning in report["warnings"]:
        lines.append(f"  warning: {warning}")
    return "\n".join(lines)


def _trash(args) -> int:
    from .config import AppConfig
    from .safety import last_prune_report, list_trash, prune_trash, retention_settings

    root = _require_root(getattr(args, "root", None))
    config = AppConfig.create(root)
    action = args.trash_action

    if action == "list":
        listing = list_trash(config)
        settings = retention_settings(config)
        payload = {**listing, "root": str(config.dossier_dir / "trash"),
                   "retention": settings, "last_prune": last_prune_report(config)}
        if args.json:
            _emit(payload, True)
            return 0
        total = sum(row["size"] for group in ("entries", "external", "unmanaged")
                    for row in listing[group])
        lines = [
            f"trash: {len(listing['entries'])} restorable, "
            f"{len(listing['external'])} external, "
            f"{len(listing['unmanaged'])} unmanaged  ({total} bytes)",
            f"retention: {plural(settings['retention_days'],'day')} from {settings['source']}; "
            f"set {settings['environment_variable']} or 'retention_days' in "
            f"{settings['config_file']} (0 keeps every backup forever)",
        ]
        for row in listing["entries"]:
            lines.append(f"  {row['trashed_at']}  {row['rel']}  ({row['size']} bytes)")
        for row in listing["external"]:
            lines.append(f"  {row['trashed_at']}  [outside the workspace] "
                         f"{row['name']}  ({row['size']} bytes)")
        for row in listing["unmanaged"]:
            lines.append(f"  [unmanaged] {row['trash_rel']}  ({row['size']} bytes)")
        for warning in settings["warnings"]:
            lines.append(f"  warning: {warning}")
        _emit(payload, False, "\n".join(lines))
        return 0

    if action == "prune":
        report = prune_trash(config, retention_days=args.days, apply=not args.dry_run)
        _emit(report, args.json, _describe_prune(report))
        return 0

    raise SystemExit(f"unknown trash action {action}")


# -- parser ----------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="dossier", description="Local Dossier workspace and job-search engine")
    parser.add_argument("--root", help="folder to open")
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--open", action="store_true", help="open the workspace in the default browser")
    parser.add_argument("--json", action="store_true", help="emit JSON")
    sub = parser.add_subparsers(dest="command")

    def add(name: str, help_text: str) -> argparse.ArgumentParser:
        child = sub.add_parser(name, help=help_text)
        child.add_argument("--root", default=argparse.SUPPRESS)
        child.add_argument("--json", action="store_true")
        return child

    serve = sub.add_parser("serve", help="run the local workspace service")
    serve.add_argument("--root", default=argparse.SUPPRESS)
    serve.add_argument("--port", type=int, default=0)
    serve.add_argument("--open", action="store_true", dest="open_browser")
    serve.set_defaults(handler=lambda args: _serve(
        _require_root(args.root), args.port, args.open_browser))

    agent = add("agent", "the injectable agent surface")
    agent_sub = agent.add_subparsers(dest="agent_action", required=True)
    # Every sibling leaf takes `--root`, and the contract says every command
    # does, so the documented leaf position must not be an argparse error. The
    # manifest itself is workspace-independent, so the value is accepted and
    # ignored rather than required.
    manifest_leaf = agent_sub.add_parser("manifest", help="the whole contract as JSON")
    manifest_leaf.add_argument("--root", default=argparse.SUPPRESS)
    agent_prompt = agent_sub.add_parser("prompt", help="standing system prompt for an injected model")
    agent_prompt.add_argument("--root", default=argparse.SUPPRESS)
    route = agent_sub.add_parser("route", help="which mode is this request")
    route.add_argument("text")
    route.add_argument("--limit", type=int, default=4)
    route.add_argument("--root", default=argparse.SUPPRESS)
    brief = agent_sub.add_parser("brief", help="the task packet for one mode")
    brief.add_argument("--mode", required=True)
    brief.add_argument("--text", default="")
    brief.add_argument("--markdown", action="store_true", help="render as prompt-ready markdown")
    brief.add_argument("--vendor", default="generic",
                       choices=["generic", "hermes", "claude-code", "codex", "cursor", "gemini"])
    brief.add_argument("--root", default=argparse.SUPPRESS)
    next_unit = agent_sub.add_parser("next", help="the next unit of work")
    next_unit.add_argument("--root", default=argparse.SUPPRESS)
    status = agent_sub.add_parser("status", help="loop state and workspace summary")
    status.add_argument("--root", default=argparse.SUPPRESS)
    commit = agent_sub.add_parser("commit", help="absorb a session's JSON handback")
    commit.add_argument("--handback", help="path to a JSON file (default: stdin)")
    commit.add_argument("--root", default=argparse.SUPPRESS)
    ask = agent_sub.add_parser("ask", help="run one mode through a configured model API")
    ask.add_argument("--mode", required=True)
    ask.add_argument("--text", default="")
    ask.add_argument("--root", default=argparse.SUPPRESS)
    adapters = agent_sub.add_parser("adapters", help="generate or check vendor prompt packs")
    adapters.add_argument("--check", action="store_true")
    adapters.add_argument("--root", default=argparse.SUPPRESS)
    for child in agent_sub.choices.values():
        if "--json" not in child._option_string_actions:
            child.add_argument("--json", action="store_true")
    # No `root=` default here: argparse copies a subparser's namespace over the
    # parent's, so a group-level default would clobber a global `--root`. The
    # group's own `--root` is SUPPRESS, and `_agent` reads it defensively.
    agent.set_defaults(handler=_agent)

    for name, handler, help_text in (
        ("doctor", _doctor, "environment capability report"),
        ("workspace", _workspace, "resolve the workspace state"),
        ("audit", _audit, "read-only reconciliation"),
        ("handoff", _handoff, "emit a reconciliation packet"),
        ("sources", _sources, "board policy and coverage ledger"),
        ("negotiate", _negotiate, "verbatim-gated negotiation ROI"),
    ):
        child = add(name, help_text)
        child.set_defaults(handler=handler)

    # The ledger's own two verbs: a workspace can open or close one board without
    # hand-editing JSON, and the change lands through the trash like any other write.
    sources_leaf = sub.choices["sources"]
    sources_leaf.add_argument("--open", metavar="NAME",
                              help="make one board fetchable in this workspace")
    sources_leaf.add_argument("--close", metavar="NAME",
                              help="drop a workspace override for one board")
    sources_leaf.add_argument("--policy",
                              help="policy to apply with --open (default user_supplied)")
    sources_leaf.add_argument("--robots", action=argparse.BooleanOptionalAction, default=None,
                              help="record a robots.txt decision for that board")

    audit = sub.choices["audit"]
    audit.add_argument("--reindex", action="store_true", help="refresh the index before auditing")
    handoff = sub.choices["handoff"]
    handoff.add_argument("--out", help="where to write the packet")
    negotiate = sub.choices["negotiate"]
    negotiate.add_argument("--wage", type=float)
    negotiate.add_argument("--frequency", choices=["daily", "weekly", "biweekly", "monthly",
                                                   "quarterly", "annually"])
    negotiate.add_argument("--occurrences", type=float)
    negotiate.add_argument("--write", action="store_true", help="write negotiation-drafts.md")

    corpus = add("corpus", "normalize, rank and dedupe the job corpus")
    corpus_sub = corpus.add_subparsers(dest="corpus_action", required=True)
    for action_name in ("build", "rank", "propagate", "folders", "dedupe"):
        child = corpus_sub.add_parser(action_name)
        child.add_argument("--root", default=argparse.SUPPRESS)
        child.add_argument("--json", action="store_true")
    corpus_sub.choices["build"].add_argument("--out", default="all_boards_data")
    corpus_sub.choices["rank"].add_argument("--limit", type=int, default=40)
    corpus_sub.choices["rank"].add_argument("--write", action="store_true")
    corpus_sub.choices["propagate"].add_argument("--ranking", required=True)
    corpus.set_defaults(handler=_corpus)

    trajectory = add("tree", "career trajectory DAG")
    trajectory_sub = trajectory.add_subparsers(dest="tree_action", required=True)
    for action_name in ("status", "add", "link", "view", "sync"):
        child = trajectory_sub.add_parser(action_name)
        child.add_argument("--root", default=argparse.SUPPRESS)
        child.add_argument("--json", action="store_true")
    node = trajectory_sub.choices["add"]
    node.add_argument("--id")
    node.add_argument("--type", dest="node_type", required=True, choices=[
        "experience", "contact", "touchpoint", "meeting", "opportunity", "milestone",
    ])
    node.add_argument("--title", required=True)
    node.add_argument("--state", default="planned", choices=["planned", "active", "complete", "cancelled"])
    node.add_argument("--date", help="YYYY-MM-DD")
    node.add_argument("--details", default="")
    link = trajectory_sub.choices["link"]
    link.add_argument("--parent", required=True)
    link.add_argument("--child", required=True)
    trajectory_sub.choices["view"].add_argument("--format", choices=["ascii", "mermaid"], default="ascii")
    trajectory.set_defaults(handler=_tree)

    track = add("track", "application log and follow-up cadence")
    track_sub = track.add_subparsers(dest="track_action", required=True)
    for action_name in ("summary", "cadence", "outcome", "followup"):
        child = track_sub.add_parser(action_name)
        child.add_argument("--root", default=argparse.SUPPRESS)
        child.add_argument("--json", action="store_true")
    track_sub.choices["cadence"].add_argument("--overdue", action="store_true")
    outcome = track_sub.choices["outcome"]
    outcome.add_argument("number", type=int)
    outcome.add_argument("outcome")
    outcome.add_argument("--applied", help="YYYY-MM-DD, required for an actionable status")
    outcome.add_argument("--confirmed", action="store_true",
                         help="the user confirmed they submitted it")
    outcome.add_argument("--note", default="")
    follow = track_sub.choices["followup"]
    follow.add_argument("number", type=int, help="tracker row number")
    follow.add_argument("--date", required=True, help="YYYY-MM-DD the follow-up was sent")
    follow.add_argument("--channel", default="", help="email | linkedin | phone | other")
    follow.add_argument("--contact", default="")
    follow.add_argument("--note", default="")
    track.set_defaults(handler=_track)

    keywords = add("keywords", "requirement extraction and gap classification")
    keywords_sub = keywords.add_subparsers(dest="keywords_action", required=True)
    for action_name in ("gap", "aggregate"):
        child = keywords_sub.add_parser(action_name)
        child.add_argument("--root", default=argparse.SUPPRESS)
        child.add_argument("--json", action="store_true")
    gap = keywords_sub.choices["gap"]
    gap.add_argument("--posting", required=True)
    gap.add_argument("--resume")
    gap.add_argument("--out")
    keywords_sub.choices["aggregate"].add_argument("--write", action="store_true")
    keywords.set_defaults(handler=_keywords)

    render = add("render", "render DOCX to PDF and rebuild stale renders")
    render.add_argument("--docx")
    render.add_argument("--pdf")
    render.add_argument("--visual", action="store_true", help="also write a page image per rebuild")
    render.set_defaults(handler=_render)

    trash = add("trash", "the backup folder: what is in it, and its age cap")
    trash_sub = trash.add_subparsers(dest="trash_action", required=True)
    for action_name in ("list", "prune"):
        child = trash_sub.add_parser(action_name)
        child.add_argument("--root", default=argparse.SUPPRESS)
        child.add_argument("--json", action="store_true")
    trash_sub.choices["prune"].add_argument(
        "--days", type=int,
        help="override the retention window in days (0 keeps every backup forever)")
    trash_sub.choices["prune"].add_argument(
        "--dry-run", action="store_true",
        help="report what would be pruned without deleting anything")
    trash.set_defaults(handler=_trash)

    verify = add("verify", "verification gates")
    verify_sub = verify.add_subparsers(dest="verify_action", required=True)
    diff = verify_sub.add_parser("source-diff")
    diff.add_argument("--base", required=True)
    diff.add_argument("--candidate", required=True)
    diff.add_argument("--approved", help="JSON file of {old_paragraph: new_paragraph} that are allowed to differ")
    layer = verify_sub.add_parser("text-layer")
    layer.add_argument("--pdf", required=True)
    layer.add_argument("--expect", action="append")
    layer.add_argument("--keyword", action="append")
    visual = verify_sub.add_parser("visual")
    visual.add_argument("--pdf", required=True)
    visual.add_argument("--base")
    visual.add_argument("--margins-from", help="a .docx whose section margins define the printable area")
    visual.add_argument("--expected-pages", type=int)
    visual.add_argument("--image", help="where to write the rendered page image "
                                        "(default: <pdf stem>-page-1.png beside the PDF)")
    every = verify_sub.add_parser("all")
    template_check = verify_sub.add_parser("template", help="check a document built from a template")
    template_check.add_argument("--template", required=True)
    template_check.add_argument("--candidate", required=True)
    template_check.add_argument("--spec", help="the fields JSON the document was built from")
    every.add_argument("--base")
    every.add_argument("--candidate")
    every.add_argument("--pdf")
    every.add_argument("--approved", help="JSON file of approved {old_paragraph: new_paragraph} changes")
    every.add_argument("--margins-from", help="a .docx whose section margins define the printable area")
    every.add_argument("--min-dates", type=int,
                       help="minimum recognisable years in the text layer (default: 2 with --base, else 0)")
    every.add_argument("--expected-pages", type=int)
    every.add_argument("--keyword", action="append")
    for child in verify_sub.choices.values():
        child.add_argument("--root", default=argparse.SUPPRESS, help=argparse.SUPPRESS)
        child.add_argument("--json", action="store_true")
    verify.set_defaults(handler=_verify)

    sanitize = add("sanitize", "strip hidden carriers from a posting")
    sanitize.add_argument("path", nargs="?")
    sanitize.add_argument("--source", default="unknown")
    sanitize.set_defaults(handler=_sanitize)

    feeds = add("feeds", "the public JSON board feeds")
    feeds_sub = feeds.add_subparsers(dest="feed_action", required=True)

    identity = add("identity", "what you are looking for, and how well a job fits")
    identity_sub = identity.add_subparsers(dest="identity_action", required=True)

    def identity_leaf(name: str, help_text: str) -> argparse.ArgumentParser:
        child = identity_sub.add_parser(name, help=help_text)
        child.add_argument("--root", default=argparse.SUPPRESS, help=argparse.SUPPRESS)
        child.add_argument("--json", action="store_true")
        return child

    identity_leaf("status", "the merged profile and its sources")
    identity_leaf("questions", "the questionnaire, with what is already known")
    answer_leaf = identity_leaf("answer", "record one answer, or a batch from JSON")
    answer_leaf.add_argument("--question", help="question id (dossier identity questions)")
    answer_leaf.add_argument("--value", help="the value; a list question takes commas")
    answer_leaf.add_argument("--from-json", help="a file of {question_id: value}")
    identity_leaf("mine", "what the workspace's own documents propose, with provenance")
    write_leaf = identity_leaf("write", "write the grounded profile into *-IDENTITY.md")
    write_leaf.add_argument("--out", help="which identity document to update")
    match_leaf = identity_leaf("match", "score the corpus (or one posting) against the profile")
    match_leaf.add_argument("--limit", type=int, default=20)
    match_leaf.add_argument("--min-band", choices=["strong", "possible", "unlikely"])
    match_leaf.add_argument("--posting", help="score one job-posting-*.md instead of the corpus")
    labels_leaf = identity_leaf("labels", "write a labelling worksheet; grades stay null until you write them")
    labels_leaf.add_argument("--out", help="where to write (default: .dossier/eval/labels-<hash>.json)")
    labels_leaf.add_argument("--limit", type=int, default=200)
    eval_leaf = identity_leaf("eval", "score the ranking against a labels file; fails below the baseline")
    eval_leaf.add_argument("--labels", help="the labels file a person filled")
    eval_leaf.add_argument("--k", type=int, default=10, help="cutoff for nDCG/precision (default 10)")
    eval_leaf.add_argument("--source", choices=["auto", "postings", "corpus"], default="auto",
                           help="score archived postings (default) or the captured corpus")
    eval_leaf.add_argument("--baseline", help="fail when a metric drops below this recorded file")
    eval_leaf.add_argument("--write-baseline", help="record the current metrics as the baseline")
    identity.set_defaults(handler=_identity)

    def feed_leaf(name: str, help_text: str) -> argparse.ArgumentParser:
        child = feeds_sub.add_parser(name, help=help_text)
        child.add_argument("--root", default=argparse.SUPPRESS, help=argparse.SUPPRESS)
        child.add_argument("--json", action="store_true")
        return child

    feed_leaf("list", "which boards have a public endpoint, and which are refused")
    feed_fetch = feed_leaf("fetch", "fetch one public board into <source>_data/all_jobs.json")
    feed_fetch.add_argument("source")
    feed_fetch.add_argument("--board", default="", help="the board or site slug")
    feed_fetch.add_argument("--out", help="where to write (default: the workspace root)")
    feed_fetch.add_argument("--limit", type=int, default=500,
                            help="cap the records written; a truncated fetch is partial")
    feeds.set_defaults(handler=_feeds)

    scrape = add("scrape", "capture pages a public feed cannot serve")
    scrape_sub = scrape.add_subparsers(dest="scrape_action", required=True)

    def scrape_leaf(name: str, help_text: str) -> argparse.ArgumentParser:
        child = scrape_sub.add_parser(name, help=help_text)
        child.add_argument("--root", default=argparse.SUPPRESS, help=argparse.SUPPRESS)
        child.add_argument("--json", action="store_true")
        return child

    scrape_leaf("status", "recipes, sessions, engines, and what is due")
    recipes_leaf = scrape_leaf("recipes", "every runnable recipe, and every broken one")
    recipes_leaf.add_argument("--workspace-only", action="store_true",
                              help="hide the recipes shipped with Dossier")
    login = scrape_leaf("login", "open a window so the user can sign in; store the cookies")
    login.add_argument("--source", required=True)
    login.add_argument("--url", required=True, help="the page the user signs in on")
    login.add_argument("--selector", default="",
                       help="an element only visible once signed in; ends the wait")
    login.add_argument("--timeout", type=float, default=180,
                       help="seconds to wait for the sign-in (default 180)")
    login.add_argument("--headless", action="store_true",
                       help="no visible window; only useful with --selector")
    session_import = scrape_leaf("session-import", "store a Netscape cookie export")
    session_import.add_argument("--source", required=True)
    session_import.add_argument("--cookies", required=True, help="cookies.txt from the user's browser")
    session_import.add_argument("--url", required=True, help="the page those cookies belong to")
    session_clear = scrape_leaf("session-clear", "delete a stored session")
    session_clear.add_argument("--source", required=True)
    capture = scrape_leaf("capture", "capture one page and archive it as a posting")
    capture.add_argument("url")
    capture.add_argument("--source", default="", help="board name; resolved from the host first")
    capture.add_argument("--driver", default="auto", choices=["auto", "obscura", "playwright"])
    capture.add_argument("--headed", action="store_true", help="show the browser window")
    capture.add_argument("--session", action="store_true", help="use the saved session for this board")
    capture.add_argument("--selector", default="", help="wait for this CSS selector")
    capture.add_argument("--wait-until", default="load",
                         choices=["load", "domcontentloaded", "networkidle", "commit"])
    capture.add_argument("--timeout", type=float, default=30)
    capture.add_argument("--delay-ms", type=int, default=1500,
                         help="minimum gap between requests to one host")
    capture.add_argument("--robots", action=argparse.BooleanOptionalAction, default=None,
                         help="obey robots.txt (default) or record that you asked it not to")
    capture.add_argument("--challenge", default=None,
                         choices=["auto", "block", "await", "stealth", "stealth-await", "solve"],
                         help="how to answer a human-verification interstitial (default: the workspace's policy)")
    capture.add_argument("--await", dest="await_seconds", type=float, default=None,
                         help="seconds a challenge page may be given to clear itself")
    capture.add_argument("--min-match", type=int, default=None,
                         help="archive only if relevance to your identity is at least this "
                              "(0-100); a filtered page is reported, not archived")
    capture.add_argument("--no-screenshot", action="store_true")
    capture.add_argument("--refresh", action="store_true",
                         help="re-capture a URL that already has a posting")
    run = scrape_leaf("run", "walk a recipe: list pages, then each item")
    run.add_argument("--recipe", help="recipe id (dossier scrape recipes lists them)")
    run.add_argument("--due", action="store_true", help="run every recipe whose cadence elapsed")
    run.add_argument("--max-recipes", type=int, default=5)
    run.add_argument("--limit", type=int, help="cap the items captured")
    run.add_argument("--pages", type=int, help="cap the listing pages walked")
    run.add_argument("--driver", default="auto", choices=["auto", "obscura", "playwright"])
    run.add_argument("--headed", action="store_true")
    run.add_argument("--delay-ms", type=int)
    run.add_argument("--no-screenshot", action="store_true")
    run.add_argument("--refresh", action="store_true")
    run.add_argument("--challenge", default=None,
                     choices=["auto", "block", "await", "stealth", "stealth-await", "solve"],
                     help="override the recipe's challenge policy for this run")
    run.add_argument("--await", dest="await_seconds", type=float, default=None)
    run.add_argument("--min-match", type=int, default=None,
                     help="archive only items scoring at least this (0-100)")
    scrape.set_defaults(handler=_scrape)

    panel = add("panel", "seven reviewers score a resume and quote the line that cost you")
    panel.add_argument("--resume", required=True, help="the resume, relative to the workspace")
    panel.add_argument("--posting", help="the job posting, relative to the workspace")
    panel.add_argument("--role", help="the target role, when the posting does not name it")
    panel.set_defaults(handler=_panel)
    tailor = add("tailor", "document mechanics")
    tailor_sub = tailor.add_subparsers(dest="tailor_action", required=True)
    inspect = tailor_sub.add_parser("inspect")
    inspect.add_argument("docx")
    blocks = tailor_sub.add_parser("blocks")
    blocks.add_argument("docx")
    fields_leaf = tailor_sub.add_parser("fields", help="list a template's {{placeholders}}")
    fields_leaf.add_argument("--template", required=True)
    template_leaf = tailor_sub.add_parser("template", help="fill the user's own .docx template")
    template_leaf.add_argument("--template", required=True)
    template_leaf.add_argument("--spec", required=True, help="JSON: {fields: {...}, replace: {...}}")
    template_leaf.add_argument("--out", required=True)
    template_leaf.add_argument("--allow-leftovers", action="store_true",
                               help="write the document even if placeholders remain")
    replace = tailor_sub.add_parser("replace")
    replace.add_argument("--base", required=True)
    replace.add_argument("--out", required=True)
    replace.add_argument("--map", required=True, help="JSON file of {old_paragraph: new_paragraph}")
    cover = tailor_sub.add_parser("cover-letter")
    cover.add_argument("--base", required=True)
    cover.add_argument("--out", required=True)
    cover.add_argument("--spec", required=True, help="JSON file of cover-letter fields")
    import_base = tailor_sub.add_parser("import", help="copy a user's base resume into the workspace")
    import_base.add_argument("--from", dest="source", required=True)
    import_base.add_argument("--name", default="base-resume.docx")
    import_base.add_argument("--overwrite", action="store_true")
    for child in tailor_sub.choices.values():
        child.add_argument("--root", default=argparse.SUPPRESS, help=argparse.SUPPRESS)
        child.add_argument("--json", action="store_true")
    tailor.set_defaults(handler=_tailor)

    return parser


def _use_utf8_stdio() -> None:
    """Print UTF-8 regardless of the console's legacy codepage.

    On Windows the default stdout encoding is cp1252, which both mangles the
    em dashes the reports use and raises UnicodeEncodeError on any character it
    cannot map, so a captured posting containing an arrow, a CJK employer name
    or an emoji would crash a reporting command. `errors="replace"` guarantees
    a degraded glyph rather than a traceback.
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (ValueError, OSError):
            pass


def main(argv: list[str] | None = None) -> int:
    _use_utf8_stdio()
    parser = build_parser()
    args = parser.parse_args(argv)
    handler = getattr(args, "handler", None)
    if handler is None:
        if args.root:
            return _serve(Path(args.root).expanduser().resolve(), args.port, args.open)
        parser.print_help()
        return 0
    try:
        return handler(args)
    except SystemExit as exc:
        if isinstance(exc.code, int):
            return exc.code
        print(exc.code, file=sys.stderr)
        return 2
    except (FileNotFoundError, NotADirectoryError, PermissionError, ValueError, RuntimeError) as exc:
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
