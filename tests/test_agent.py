"""Tests for the injectable agent layer."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from dossier import agent
from dossier.agent import adapters, brief, loop, workspace


# -- manifest --------------------------------------------------------------

def test_every_mode_has_a_real_stage():
    stages = {stage.id for stage in agent.STAGES}
    assert stages
    for item in agent.MODES:
        assert item.stage in stages, f"{item.id} names unknown stage {item.stage}"


def test_mode_ids_are_unique():
    ids = [item.id for item in agent.MODES]
    assert len(ids) == len(set(ids))


def test_every_referenced_gate_exists():
    known = {gate.id for gate in agent.GATES}
    for item in agent.MODES:
        for gate in item.gates:
            assert gate in known, f"{item.id} references unknown gate {gate}"


def test_every_gate_id_is_unique_and_names_an_enforcer():
    ids = [gate.id for gate in agent.GATES]
    assert len(ids) == len(set(ids))
    for gate in agent.GATES:
        assert gate.enforced_by.strip()
        assert gate.never.strip()


def test_deterministic_modes_declare_an_engine():
    for item in agent.engine_modes():
        assert item.engine, f"{item.id} is deterministic but names no engine"


def test_contract_is_json_serialisable():
    payload = agent.contract()
    json.dumps(payload)
    assert payload["schema_version"] == agent.SCHEMA_VERSION
    assert len(payload["modes"]) == len(agent.MODES)


# -- routing ---------------------------------------------------------------

@pytest.mark.parametrize("text,expected", [
    ("tailor my resume for this posting", "build"),
    ("diagnose my resume please", "diagnose"),
    ("what keywords am i missing for this role", "keywords"),
    ("track my applications", "track"),
    ("mock interview practice", "interview"),
    ("help me negotiate the offer", "negotiate"),
    ("what should i learn next", "upskill"),
])
def test_route_picks_the_right_mode(text, expected):
    matches = agent.route(text)
    assert matches, f"no route for {text!r}"
    assert matches[0]["id"] == expected


def test_route_returns_nothing_for_unrelated_text():
    assert agent.route("what is the weather in hamilton") == []


def test_pipeline_from_walks_the_next_chain():
    chain = agent.pipeline_from("build")
    assert chain[0] == "build"
    assert "verify" in chain
    assert len(chain) == len(set(chain))


# -- workspace -------------------------------------------------------------

def _make_workspace(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "DEVELOPER-IDENTITY.md").write_text("# Identity\n", encoding="utf-8")
    (root / "resume.md").write_text("## Skills\nPython, SQL\n", encoding="utf-8")
    (root / "job-history.md").write_text(
        "# Log\n\n| Date | Company | Role | Fit | Resume file | Status |\n"
        "|---|---|---|---|---|---|\n"
        "| Aug 2026 | Acme | Engineer | High | a.docx | drafted |\n"
        "| Aug 2026 | Beta | Analyst | Medium | b.docx | applied |\n",
        encoding="utf-8",
    )
    (root / "follow-ups.md").write_text(
        "# Follow-ups\n\n- Applied 2026-09-01 to Beta #2\n", encoding="utf-8")
    (root / "job-posting-Acme-Engineer.md").write_text(
        "# Engineer\n\n## Requirements\n- Python\n- Docker\n", encoding="utf-8")
    boards = root / "seek_data"
    boards.mkdir()
    jobs = [
        {"id": 1, "title": "Engineer", "employer": "Acme", "location": "Hamilton", "url": "u1",
         "pay_amount": 30, "pay_unit": "hourly", "fit": "High", "source": "seek"},
        {"id": 2, "title": "Analyst", "employer": "Beta", "location": "Hamilton", "url": "u2",
         "fit": "Medium", "source": "seek"},
    ]
    (boards / "all_jobs.json").write_text(json.dumps(jobs), encoding="utf-8")
    aggregate = root / "all_boards_data"
    aggregate.mkdir()
    (aggregate / "all_jobs.json").write_text(json.dumps(jobs), encoding="utf-8")
    return root


def test_workspace_resolves_the_real_facts(tmp_path):
    root = _make_workspace(tmp_path / "Tailored")
    space = workspace.resolve(root)
    assert space.identity_doc is not None
    assert space.resume_extract is not None
    assert space.counts["postings"] == 1
    assert space.tracker["rows"] == 2
    assert space.tracker["status_counts"] == {"applied": 1, "drafted": 1}
    assert space.tracker["confirmed_application_dates"] == {"2": "2026-09-01"}
    assert space.tracker["actionable_without_date"] == []
    assert space.corpus["present"] is True
    assert space.corpus["rows"] == 2
    assert space.corpus["unscored"] == 0
    assert space.corpus["board_folders"] == ["seek_data"]
    assert space.corpus["fits"] == {"High": 1, "Medium": 1}


def test_workspace_reports_a_missing_base_document_as_a_blocker(tmp_path):
    root = _make_workspace(tmp_path / "Tailored")
    space = workspace.resolve(root)
    assert space.base_documents == []
    assert any("base .docx" in blocker for blocker in space.blockers)


def test_workspace_flags_a_duplicate_corpus_id(tmp_path):
    root = _make_workspace(tmp_path / "Tailored")
    (root / "all_boards_data" / "all_jobs.json").write_text(json.dumps([
        {"id": 1, "title": "A", "employer": "X", "fit": "High"},
        {"id": 1, "title": "B", "employer": "Y", "fit": "Low"},
    ]), encoding="utf-8")
    space = workspace.resolve(root)
    assert space.corpus["duplicate_ids"] == 1
    assert space.corpus["unscored"] == 0
    assert any("duplicate id" in blocker for blocker in space.blockers)


def test_write_state_lands_in_the_dossier_dir(tmp_path):
    root = _make_workspace(tmp_path / "Tailored")
    space = workspace.resolve(root)
    path = workspace.write_state(space, root / ".dossier")
    assert path.exists()
    assert json.loads(path.read_text(encoding="utf-8"))["root"] == str(root.resolve())


# -- brief -----------------------------------------------------------------

def test_brief_carries_the_whole_packet(tmp_path):
    root = _make_workspace(tmp_path / "Tailored")
    packet = brief.build(root, "keywords", "what am i missing")
    assert packet.mode == "keywords"
    assert packet.objective
    assert packet.inputs, "a brief with no resolved inputs is not executable"
    assert packet.deterministic, "every brief must carry a runnable command"
    assert packet.gates, "the keywords mode declares gates"
    assert packet.handback_schema["required"]
    assert packet.request == "what am i missing"


def test_brief_renders_markdown_with_every_section(tmp_path):
    root = _make_workspace(tmp_path / "Tailored")
    text = brief.render(brief.build(root, "build"), vendor="claude-code")
    for heading in ("## Objective", "## Standing rules", "## Workspace", "## Inputs you may open",
                    "## Run these first", "## Hard gates", "## Prove it", "## Hand back"):
        assert heading in text, f"missing {heading}"
    assert "Claude Code" in text


def test_system_prompt_lists_both_halves_of_the_contract(tmp_path):
    root = _make_workspace(tmp_path / "Tailored")
    text = brief.system_prompt(root)
    assert "What the engine already owns" in text
    assert "What only you can do" in text
    assert "Gates that are never softened" in text


# -- adapters --------------------------------------------------------------

def test_adapters_write_every_pack_and_verify(tmp_path):
    root = _make_workspace(tmp_path / "Tailored")
    results = adapters.write_all(root)
    assert set(results) == set(adapters.packs(root))
    assert all(state in {"created", "appended", "replaced"} for state in results.values())
    for rel in results:
        assert adapters.verify_block(root, rel), f"{rel} did not carry a current managed block"


def test_upsert_preserves_content_outside_the_markers(tmp_path):
    root = _make_workspace(tmp_path / "Tailored")
    agents_md = root / "AGENTS.md"
    agents_md.write_text("# House rules\n\nKeep me.\n", encoding="utf-8")
    assert adapters.upsert_block(agents_md, "first body") == "appended"
    assert adapters.upsert_block(agents_md, "second body") == "replaced"
    text = agents_md.read_text(encoding="utf-8")
    assert "Keep me." in text
    assert "second body" in text
    assert "first body" not in text


def test_cursor_pack_keeps_frontmatter_at_the_top(tmp_path):
    root = _make_workspace(tmp_path / "Tailored")
    adapters.write_all(root)
    text = (root / ".cursor" / "rules" / "dossier.mdc").read_text(encoding="utf-8")
    assert text.startswith("---\n")


# -- loop ------------------------------------------------------------------

def test_next_unit_prefers_the_missing_base_document(tmp_path):
    root = _make_workspace(tmp_path / "Tailored")
    unit = loop.next_unit(root)
    assert unit["mode"] == "build"
    assert unit["needs_user"] is True


def test_next_unit_finds_duplicate_ids_before_cosmetics(tmp_path):
    root = _make_workspace(tmp_path / "Tailored")
    (root / "base-resume.docx").write_bytes(b"")  # a base exists, so that blocker clears
    (root / "all_boards_data" / "all_jobs.json").write_text(json.dumps([
        {"id": 1, "title": "A", "employer": "X", "fit": "High"},
        {"id": 1, "title": "B", "employer": "Y", "fit": "Low"},
    ]), encoding="utf-8")
    unit = loop.next_unit(root)
    assert unit["mode"] == "corpus"


def test_next_unit_reports_no_outstanding_defect_on_a_clean_workspace(tmp_path):
    root = _make_workspace(tmp_path / "Tailored")
    (root / "base-resume.docx").write_bytes(b"")
    (root / "nz-job-search-coverage-2026-09-01.json").write_text(
        json.dumps({"captured_on": "2999-01-01", "merged_rows": 2}), encoding="utf-8")
    (root / "all_boards_data").mkdir(exist_ok=True)
    (root / "all_boards_data" / "all_jobs.json").write_text(json.dumps([
        {"id": 1, "title": "A", "employer": "X", "fit": "High"},
    ]), encoding="utf-8")
    (root / "keywords-Acme-Engineer.md").write_text("# keywords\n", encoding="utf-8")
    (root / "Ayers_Resume_Acme_Engineer.docx").write_bytes(b"")
    unit = loop.next_unit(root)
    assert unit["mode"] in {"audit", "keywords", "render", "followup", "build", "sources"}


def test_next_unit_advances_once_a_mechanical_skillgap_report_exists(tmp_path):
    """The keywords mode writes `<posting-stem>.skillgap.json`. Accepting only a
    `keywords-*.md` report would leave the loop reporting the same unit forever
    after a session had already done it."""
    root = _make_workspace(tmp_path / "Tailored")
    (root / "base-resume.docx").write_bytes(b"")
    unit = loop.next_unit(root)
    assert unit["mode"] == "keywords"

    (root / "job-posting-Acme-Engineer.skillgap.json").write_text(
        json.dumps({"gap": [], "existing": ["Python"], "skills_found": 1}), encoding="utf-8")
    assert loop.next_unit(root)["mode"] != "keywords"


def test_commit_rejects_a_handback_missing_fields(tmp_path):
    root = _make_workspace(tmp_path / "Tailored")
    result = loop.commit(root, {"mode": "build"})
    assert result["accepted"] is False
    assert "missing required field" in result["problems"][0]


def test_commit_rejects_a_completion_claim_without_evidence(tmp_path):
    root = _make_workspace(tmp_path / "Tailored")
    artifact = root / "out.md"
    artifact.write_text("x", encoding="utf-8")
    result = loop.commit(root, {
        "mode": "diagnose", "status": "completed",
        "artifacts": [{"path": str(artifact), "role": "analysis"}],
        "evidence": [], "gaps": [],
    })
    assert result["accepted"] is False
    assert any("no evidence" in problem for problem in result["problems"])


def test_commit_rejects_an_artifact_that_is_not_on_disk(tmp_path):
    root = _make_workspace(tmp_path / "Tailored")
    result = loop.commit(root, {
        "mode": "diagnose", "status": "completed",
        "artifacts": [{"path": "ghost.md", "role": "analysis"}],
        "evidence": ["42 passed"], "gaps": [],
    })
    assert result["accepted"] is False
    assert any("not found on disk" in problem for problem in result["problems"])


def test_commit_accepts_a_real_handback_and_advances_the_loop(tmp_path):
    root = _make_workspace(tmp_path / "Tailored")
    artifact = root / "diagnosis.md"
    artifact.write_text("real", encoding="utf-8")
    result = loop.commit(root, {
        "mode": "diagnose", "status": "completed",
        "artifacts": [{"path": "diagnosis.md", "role": "analysis"}],
        "evidence": ["wrote diagnosis.md (1284 bytes)"], "gaps": [],
    })
    assert result["accepted"] is True
    assert result["sessions"] == 1
    assert result["recorded"]["artifacts"] == ["diagnosis.md"]

    state = loop.status(root)
    assert state["sessions"] == 1
    assert state["recent"][0]["mode"] == "diagnose"
    assert (root / ".dossier" / "agent-loop.json").exists()


def test_reset_clears_history_and_says_how_much(tmp_path):
    root = _make_workspace(tmp_path / "Tailored")
    artifact = root / "diagnosis.md"
    artifact.write_text("real", encoding="utf-8")
    loop.commit(root, {"mode": "diagnose", "status": "completed",
                       "artifacts": [{"path": "diagnosis.md", "role": "analysis"}],
                       "evidence": ["ok"], "gaps": []})
    result = loop.reset(root)
    assert result["cleared"] == 1
    assert loop.status(root)["sessions"] == 0


def test_no_brief_leaks_a_token(tmp_path):
    root = _make_workspace(tmp_path / "Tailored")
    rendered = brief.render(brief.build(root, "audit"))
    assert "token" not in rendered.lower() or "bearer" not in rendered.lower()
