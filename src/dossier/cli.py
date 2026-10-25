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
    url = f"http://127.0.0.1:{port}/?token={config.token}"
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
    out.write_text(json.dumps(result["packet"], indent=2, ensure_ascii=False), encoding="utf-8")
    prompt_path = out.with_suffix(".md")
    prompt_path.write_text(result["prompt"], encoding="utf-8")
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
            target = root / f"ranked-jobs-{date.today().isoformat()}.json"
            target.write_text(json.dumps(corpus.rank(jobs), indent=2, ensure_ascii=False),
                              encoding="utf-8")
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
        corpus.build_facets(jobs, root / "all_boards_data")
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
                lines.append(f"- **{entry['skill']}** — {entry['postings']} posting(s)")
            lines += ["", "A recurring gap is a learning target or an honest omission — "
                          "never a licence to word-stuff."]
            target.write_text("\n".join(lines), encoding="utf-8")
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
        result = verify.visual(Path(args.pdf), expected_pages=args.expected_pages, margins=margins)
        _emit(result, args.json)
        return 0 if result["ok"] else 1
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

    root = _require_root(getattr(args, "root", None))
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
    return 0


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
    if action == "replace":
        replacements = json.loads(Path(args.map).read_text(encoding="utf-8"))
        result = tailor.apply_replacements(Path(args.base), Path(args.out), replacements)
        payload = {"output": result.output, "applied": result.applied, "missed": result.missed}
        _emit(payload, args.json)
        return 0 if not result.missed else 1
    if action == "cover-letter":
        payload = json.loads(Path(args.spec).read_text(encoding="utf-8"))
        result = tailor.cover_letter(Path(args.base), Path(args.out), **payload)
        _emit(result, args.json)
        return 0
    if action == "import":
        result = tailor.import_base(Path(args.source), _require_root(getattr(args, "root", None)),
                                    name=args.name, overwrite=args.overwrite)
        _emit(result, args.json)
        return 0 if result.get("imported") else 1
    raise SystemExit(f"unknown tailor action {action}")


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
    agent_sub.add_parser("manifest", help="the whole contract as JSON")
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
    adapters = agent_sub.add_parser("adapters", help="generate or check vendor prompt packs")
    adapters.add_argument("--check", action="store_true")
    adapters.add_argument("--root", default=argparse.SUPPRESS)
    for child in agent_sub.choices.values():
        if "--json" not in child._option_string_actions:
            child.add_argument("--json", action="store_true")
    agent.set_defaults(handler=_agent, root=None)

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
    every = verify_sub.add_parser("all")
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

    tailor = add("tailor", "document mechanics")
    tailor_sub = tailor.add_subparsers(dest="tailor_action", required=True)
    inspect = tailor_sub.add_parser("inspect")
    inspect.add_argument("docx")
    blocks = tailor_sub.add_parser("blocks")
    blocks.add_argument("docx")
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


def main(argv: list[str] | None = None) -> int:
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
