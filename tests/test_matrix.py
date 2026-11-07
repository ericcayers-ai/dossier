"""The command and route matrix.

A contract that names a command argparse rejects, or an engine symbol that does
not exist, is a gap that only surfaces when a model is already mid-task and
already trusts the brief. This module executes every declared command and every
mounted route, so a gap fails here instead of there.

If you add a mode, a command or a route, these tests cover it without being
edited.
"""

from __future__ import annotations

import importlib
import json
import re
import shlex
from pathlib import Path

import pytest
from docx import Document
from fastapi.testclient import TestClient

from dossier import cli
from dossier.agent import adapters, manifest
from dossier.api.app import create_app

#: Values a `<placeholder>` is replaced with when a command only needs to parse.
#: Anything Parseable stands in for a path; a numeric or date placeholder has to
#: look like what argparse will coerce it to.
PLACEHOLDER_VALUES = {
    "row-number": "1",
    "YYYY-MM-DD": "2026-01-01",
}


def dummy_for(token: str) -> str:
    return PLACEHOLDER_VALUES.get(token.strip("<>"), "placeholder")


def resolve_symbol(dotted: str):
    """Resolve `dossier.a.b.c`, accepting a module or an attribute at the end.

    A contract may name either — `dossier.engine.verify.source_diff` is a
    function and `dossier.agent.brief` is a module — and both are real answers
    to "where is this enforced".
    """
    parts = dotted.split(".")
    if parts[0] != "dossier":
        return None
    resolved = importlib.import_module("dossier")
    for index in range(1, len(parts)):
        prefix = ".".join(parts[: index + 1])
        try:
            resolved = importlib.import_module(prefix)
            continue
        except ModuleNotFoundError:
            pass
        candidate = getattr(resolved, parts[index], None)
        if candidate is None:
            return None
        resolved = candidate
    return resolved


# -- a workspace that satisfies the common prerequisites -------------------

def build_workspace(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "DEVELOPER-IDENTITY.md").write_text("# Identity\n\nGrounded in real evidence.\n", encoding="utf-8")
    (root / "resume.md").write_text(
        "## Skills\nPython, Docker, SQL\n\n"
        "## Experience\n"
        "Cut the weekly reporting loop from 8 hours to 2 hours.\n"
        "Reduced review turnaround by 60%.\n",
        encoding="utf-8")
    (root / "job-history.md").write_text(
        "| Date | Company | Role | Fit | Resume file | Status |\n"
        "|---|---|---|---|---|---|\n"
        "| Aug 2026 | Acme | Engineer | High | a.docx | drafted |\n",
        encoding="utf-8")
    (root / "follow-ups.md").write_text("# Follow-up log\n", encoding="utf-8")
    (root / "job-posting-Acme-Engineer.md").write_text(
        "# Engineer\n\n## Requirements\n- Python\n- Docker\n- Kubernetes\n", encoding="utf-8")
    (root / "interview-prep").mkdir(exist_ok=True)
    (root / "interview-prep" / "story-bank.md").write_text(
        "# Story bank\n\n### [Automation] Reporting loop\n\n"
        "Cut the weekly reporting loop from 8 hours to 2 hours, weekly, at $45/hr.\n",
        encoding="utf-8")

    document = Document()
    document.add_paragraph("Objective: Seeking a role in software engineering.")
    document.save(str(root / "base-resume.docx"))

    tailored = Document()
    tailored.add_paragraph("Objective: Seeking a technical support engineering internship.")
    tailored.save(str(root / "sample_resume_Acme_Engineer_Sep2026.docx"))
    letter = Document()
    letter.add_paragraph("Dear Hiring Manager,")
    letter.save(str(root / "sample_resume_Acme_Engineer_Sep2026_CoverLetter.docx"))

    jobs = [
        {"id": 1, "title": "Engineer", "employer": "Acme", "location": "Hamilton",
         "url": "http://example/1", "fit": "High", "source": "seek"},
        {"id": 2, "title": "Analyst", "employer": "Beta", "location": "Hamilton",
         "url": "http://example/2", "fit": "Medium", "source": "seek"},
    ]
    board = root / "seek_data"
    board.mkdir()
    (board / "all_jobs.json").write_text(json.dumps(jobs), encoding="utf-8")
    aggregate = root / "all_boards_data"
    aggregate.mkdir()
    (aggregate / "all_jobs.json").write_text(json.dumps(jobs), encoding="utf-8")
    (root / "nz-job-search-coverage-2999-01-01.json").write_text(
        json.dumps({"captured_on": "2999-01-01", "merged_rows": 2, "ranking_rows": 2,
                    "current_source_counts": {"seek": 2}, "source_statuses": {"seek": "captured"}}),
        encoding="utf-8")
    return root


@pytest.fixture
def workspace(tmp_path):
    return build_workspace(tmp_path / "workspace")


def argv_for(command: str, root: Path) -> list[str]:
    """Turn a declared command template into argv, substituting the real root."""
    return [str(root) if token == "{root}" else token for token in shlex.split(command)]


def agent_brief(root: Path, mode_id: str) -> dict:
    from dossier.agent import brief

    return brief.build(root, mode_id).to_dict()


def is_placeholder(token: str) -> bool:
    return token.startswith("<") and token.endswith(">")


# -- the contract names real things ----------------------------------------

def test_every_declared_engine_symbol_exists():
    """A mode's `engine` is the code that enforces it. If it names nothing, the
    claim is decorative."""
    missing = [
        (item.id, item.engine) for item in manifest.MODES
        if item.engine and resolve_symbol(f"dossier.{item.engine}") is None
    ]
    assert not missing, f"modes naming an engine that does not exist: {missing}"


def test_every_gate_enforcer_symbol_resolves():
    """Gate enforcers name real code too."""
    pattern = re.compile(r"\bdossier(?:\.engine)?\.\w+(?:\.\w+)*")
    missing = []
    for gate in manifest.GATES:
        for match in pattern.findall(gate.enforced_by):
            if resolve_symbol(match if match.startswith("dossier.") else f"dossier.{match}") is None:
                missing.append((gate.id, match))
    assert not missing, f"gates naming code that does not exist: {missing}"


def test_every_deterministic_mode_declares_a_command():
    for item in manifest.engine_modes():
        assert item.command, f"{item.id} is deterministic but names no command"


def test_every_mode_names_a_real_next_mode():
    """`next` drives the pipeline chain; a typo would silently end it."""
    unknown = sorted({
        (item.id, nxt) for item in manifest.MODES for nxt in item.next
        if nxt not in manifest.MODE_INDEX
    })
    assert not unknown, f"modes naming a next mode that does not exist: {unknown}"


def test_every_declared_need_is_a_known_key():
    """A mode naming an unknown need reports its own prerequisite as permanently
    missing, because nothing resolves it — `base.docx` did exactly that."""
    unknown = sorted({
        need for item in manifest.MODES for need in item.needs
        if need not in manifest.NEED_KEYS
    })
    assert not unknown, f"modes declare needs with no resolvable key: {unknown}"


def test_apply_writes_the_canonical_tracker():
    assert "job-history.md" in manifest.mode("apply").writes
    assert manifest.mode("track").reads == ("job-history.md",)


def test_every_artifact_names_a_real_producer():
    """An artifact's producer is a mode, the user, or a real engine function."""
    unknown = [
        (item.name, item.producer) for item in manifest.ARTIFACTS
        if item.producer != "user"
        and item.producer not in manifest.MODE_INDEX
        and resolve_symbol(f"dossier.{item.producer}") is None
    ]
    assert not unknown, f"artifacts naming a missing producer: {unknown}"


def test_every_mode_reaches_the_generated_docs():
    pipeline = adapters._pipeline_doc()
    contract = adapters._contract_doc()
    for item in manifest.MODES:
        assert f"`{item.id}`" in pipeline, f"{item.id} missing from PIPELINE.md"
        assert f"`{item.id}`" in contract, f"{item.id} missing from CONTRACT.md"


# -- every declared command parses -----------------------------------------

def test_every_declared_command_parses(tmp_path):
    """Exactly the failure this matrix exists for: a brief that hands a model a
    command argparse rejects."""
    parser = cli.build_parser()
    rejected = []
    for item in manifest.MODES:
        if not item.command:
            continue
        argv = argv_for(item.command, tmp_path)
        argv = [dummy_for(token) if is_placeholder(token) else token for token in argv]
        try:
            parser.parse_args(argv[1:])
        except SystemExit:
            rejected.append((item.id, item.command))
    assert not rejected, f"declared commands that argparse rejects: {rejected}"


# -- every command that needs no input actually runs ------------------------

def test_every_self_contained_command_runs(workspace, tmp_path, capsys):
    """A command with no `<placeholder>` is one a brief marks 'runnable as
    written'. Those must exit 0 on a healthy workspace, not merely parse."""
    failures = []
    for item in manifest.MODES:
        if not item.command or "<" in item.command:
            continue
        target = build_workspace(tmp_path / f"run-{item.id}")
        argv = argv_for(item.command, target)[1:] + ["--json"]
        try:
            code = cli.main(argv)
        except Exception as exc:  # noqa: BLE001
            failures.append((item.id, f"{type(exc).__name__}: {exc}"))
            capsys.readouterr()
            continue
        capsys.readouterr()
        if code != 0:
            failures.append((item.id, f"exit {code}"))
    assert not failures, f"self-contained commands that failed: {failures}"
    assert len([m for m in manifest.MODES if m.command and "<" not in m.command]) >= 10


def test_placeholder_commands_say_they_need_values(workspace):
    packet = agent_brief(workspace, "verify")
    engines = [entry for entry in packet["deterministic_commands"] if entry["step"].startswith("engine")]
    assert engines and engines[0]["runnable"] is False
    assert "<" in engines[0]["command"]


def test_runnable_commands_are_marked_runnable(workspace):
    packet = agent_brief(workspace, "audit")
    engines = [entry for entry in packet["deterministic_commands"] if entry["step"].startswith("engine")]
    assert engines and engines[0]["runnable"] is True


# -- every route answers ----------------------------------------------------

def test_no_api_route_returns_a_server_error(workspace):
    from dossier.config import AppConfig
    from dossier.api.app import STREAMING_PATHS

    app = create_app(AppConfig.create(workspace, token="matrix-token"))
    client = TestClient(app, raise_server_exceptions=False)
    headers = {"Authorization": "Bearer matrix-token"}

    routes = [
        route for route in app.routes
        if getattr(route, "path", "").startswith("/api/")
        and "GET" in getattr(route, "methods", set())
        and route.path not in STREAMING_PATHS
    ]
    assert len(routes) >= 20, f"only {len(routes)} API routes found; the matrix is not covering the surface"

    broken = []
    for route in routes:
        response = client.get(route.path, headers=headers)
        if response.status_code >= 500:
            broken.append((route.path, response.status_code, response.text[:120]))
    assert not broken, f"routes answering with a server error: {broken}"


def test_the_streaming_route_is_declared_and_bounded(workspace):
    """The one route that does not return must say so, and must end on its own."""
    from dossier.config import AppConfig
    from dossier.api.app import STREAMING_PATHS

    app = create_app(AppConfig.create(workspace, token="matrix-token"))
    client = TestClient(app, raise_server_exceptions=False)
    headers = {"Authorization": "Bearer matrix-token"}

    assert STREAMING_PATHS == {"/api/events"}
    with client.stream("GET", "/api/events?seconds=1", headers=headers) as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        body = "".join(response.iter_text())
    assert '"type":"connected"' in body
    assert '"type":"closed"' in body, "an unbounded stream would hang any client sweeping the API"


def test_the_fully_specified_routes_all_answer(workspace):
    from dossier.config import AppConfig

    app = create_app(AppConfig.create(workspace, token="matrix-token"))
    client = TestClient(app, raise_server_exceptions=False)
    headers = {"Authorization": "Bearer matrix-token"}

    specified = [
        "/api/health", "/api/tree", "/api/tree?view=trajectory", "/api/search?q=Engineer", "/api/actions",
        "/api/jobs", "/api/jobs/history", "/api/jobs/due", "/api/jobs/feeds",
        "/api/audit", "/api/ai/handoff",
        "/api/agent/manifest", "/api/agent/status", "/api/agent/next",
        "/api/agent/route?q=tailor+my+resume",
        "/api/agent/brief?mode=build", "/api/agent/prompt", "/api/agent/adapters",
        "/api/workspace", "/api/doctor", "/api/sources",
        "/api/track", "/api/track/cadence", "/api/corpus", "/api/verify",
    ]
    failures = []
    for url in specified:
        response = client.get(url, headers=headers)
        if response.status_code != 200:
            failures.append((url, response.status_code, response.text[:100]))
    assert not failures, f"routes that did not answer 200: {failures}"


def test_the_market_agent_endpoints_return_real_shapes(workspace):
    from dossier.config import AppConfig

    app = create_app(AppConfig.create(workspace, token="matrix-token"))
    client = TestClient(app, raise_server_exceptions=False)
    headers = {"Authorization": "Bearer matrix-token"}

    manifest_payload = client.get("/api/agent/manifest", headers=headers).json()
    assert len(manifest_payload["modes"]) == len(manifest.MODES)
    assert all("command" in item for item in manifest_payload["modes"])

    next_unit = client.get("/api/agent/next", headers=headers).json()
    assert next_unit["mode"] in {item.id for item in manifest.MODES}
    assert next_unit["reason"]

    brief_markdown = client.get("/api/agent/brief?mode=build&format=markdown", headers=headers).text
    assert "## Objective" in brief_markdown
    assert "## Run these first" in brief_markdown

    workspace_state = client.get("/api/workspace", headers=headers).json()
    assert workspace_state["counts"]["base_documents"] == 1
    assert workspace_state["blockers"] == []

    audit = client.get("/api/audit", headers=headers).json()
    assert len(audit["checks"]) >= 9


def test_the_cli_help_lists_every_top_level_command(capsys):
    cli.main([])
    output = capsys.readouterr().out
    for name in ("serve", "agent", "doctor", "workspace", "audit", "handoff",
                 "sources", "negotiate", "corpus", "tree", "track", "keywords",
                 "render", "verify", "sanitize", "tailor"):
        assert name in output, f"{name} missing from the CLI help"


def test_adapters_check_matches_what_write_produced(tmp_path):
    root = build_workspace(tmp_path / "repo")
    results = adapters.write_all(root)
    assert results
    assert all(adapters.verify_block(root, rel) for rel in results)
    # Re-running with no change must be idempotent, and the content must not
    # shift because the workspace grew.
    (root / "extra.md").write_text("a new file changes the workspace\n", encoding="utf-8")
    assert all(adapters.verify_block(root, rel) for rel in results), (
        "a generated pack went stale because the workspace changed"
    )


def test_copying_a_workspace_keeps_the_matrix_fixture_honest(tmp_path):
    """Guard for the fixture itself: if it stopped satisfying the declared
    prerequisites, the runnable-command test would pass vacuously."""
    from dossier.agent import brief, workspace as workspace_module

    root = build_workspace(tmp_path / "copy")
    space = workspace_module.resolve(root)
    unresolved = []
    for item in manifest.engine_modes():
        packet = brief.build(root, item.id, workspace=space)
        for row in packet.prerequisites:
            if row["from_user"]:
                continue
            if not row["resolved"]:
                unresolved.append((item.id, row["need"]))
    assert not unresolved, f"the fixture does not satisfy: {unresolved}"
