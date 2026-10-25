import json

import pytest

from dossier.engine import tree


def add(root, node_id, node_type="experience", state="planned", date=None, **extra):
    payload = {"id": node_id, "type": node_type, "title": node_id.replace("-", " "), "state": state}
    if date is not None:
        payload["date"] = date
    payload.update(extra)
    return tree.upsert_node(root, payload)


def test_load_returns_empty_graph_without_creating_workspace_files(tmp_path):
    root = tmp_path / "new-workspace"
    root.mkdir()

    assert tree.load(root) == {"version": 1, "nodes": [], "links": [], "sources": {}}
    assert not (root / ".dossier").exists()


@pytest.mark.parametrize("node_type", ["experience", "contact", "touchpoint", "meeting", "opportunity", "milestone"])
def test_upsert_accepts_every_declared_node_type(tmp_path, node_type):
    node = add(tmp_path, f"node-{node_type}", node_type=node_type)

    assert node["type"] == node_type
    assert tree.load(tmp_path)["nodes"][0]["id"] == node["id"]


def test_upsert_updates_existing_node_without_erasing_omitted_fields(tmp_path):
    add(tmp_path, "experience-1", state="complete", date="2026-01-01", details="Grounded note")

    updated = tree.upsert_node(tmp_path, {"id": "experience-1", "title": "Renamed experience"})

    assert updated["title"] == "Renamed experience"
    assert updated["state"] == "complete"
    assert updated["date"] == "2026-01-01"
    assert updated["details"] == "Grounded note"


@pytest.mark.parametrize("payload", [
    {"id": "bad id", "type": "experience", "title": "A"},
    {"id": "node-1", "type": "resume", "title": "A"},
    {"id": "node-1", "type": "experience", "title": "  "},
    {"id": "node-1", "type": "experience", "title": "A", "state": "applied"},
    {"id": "node-1", "type": "experience", "title": "A", "date": "2026-02-30"},
])
def test_upsert_rejects_invalid_node_fields(tmp_path, payload):
    with pytest.raises(tree.TreeError):
        tree.upsert_node(tmp_path, payload)


def test_link_requires_existing_endpoints_and_rejects_duplicate_edges(tmp_path):
    add(tmp_path, "parent", state="complete")

    with pytest.raises(tree.TreeError, match="child"):
        tree.link_nodes(tmp_path, "parent", "missing")

    add(tmp_path, "child")
    tree.link_nodes(tmp_path, "parent", "child")
    with pytest.raises(tree.TreeError, match="duplicate"):
        tree.link_nodes(tmp_path, "parent", "child")


def test_link_rejects_cycles(tmp_path):
    add(tmp_path, "a")
    add(tmp_path, "b")
    add(tmp_path, "c")
    tree.link_nodes(tmp_path, "a", "b")
    tree.link_nodes(tmp_path, "b", "c")

    with pytest.raises(tree.TreeError, match="cycle"):
        tree.link_nodes(tmp_path, "c", "a")


def test_link_rejects_parent_after_child_chronologically(tmp_path):
    add(tmp_path, "parent", state="complete", date="2026-05-02")
    add(tmp_path, "child", date="2026-05-01")

    with pytest.raises(tree.TreeError, match="chronological"):
        tree.link_nodes(tmp_path, "parent", "child")


def test_child_is_blocked_until_every_parent_is_complete(tmp_path):
    add(tmp_path, "parent-done", state="complete")
    add(tmp_path, "parent-open", state="active")
    add(tmp_path, "child")
    tree.link_nodes(tmp_path, "parent-done", "child")
    tree.link_nodes(tmp_path, "parent-open", "child")

    child = next(node for node in tree.graph(tmp_path)["nodes"] if node["id"] == "child")
    assert child["actionable"] is False
    assert child["blocked_by"] == ["parent-open"]

    with pytest.raises(tree.TreeError, match="prerequisite"):
        tree.upsert_node(tmp_path, {"id": "child", "state": "active"})


def test_child_becomes_actionable_when_all_parents_are_complete(tmp_path):
    add(tmp_path, "parent", state="complete")
    add(tmp_path, "child")
    tree.link_nodes(tmp_path, "parent", "child")

    child = next(node for node in tree.graph(tmp_path)["nodes"] if node["id"] == "child")
    assert child["actionable"] is True
    assert child["blocked_by"] == []


def test_parent_cannot_be_reopened_while_active_child_depends_on_it(tmp_path):
    add(tmp_path, "parent", state="complete")
    add(tmp_path, "child", state="active")
    tree.link_nodes(tmp_path, "parent", "child")

    with pytest.raises(tree.TreeError, match="prerequisite"):
        tree.upsert_node(tmp_path, {"id": "parent", "state": "planned"})


def test_overwrite_is_atomic_and_preserves_the_previous_tree_in_trash(tmp_path):
    add(tmp_path, "experience-1", details="before")

    add(tmp_path, "experience-1", details="after")

    backups = list((tmp_path / ".dossier" / "trash").rglob("tree.json"))
    assert len(backups) == 1
    assert json.loads(backups[0].read_text(encoding="utf-8"))["nodes"][0]["details"] == "before"
    assert json.loads((tmp_path / ".dossier" / "tree.json").read_text(encoding="utf-8"))["nodes"][0]["details"] == "after"


def test_ascii_and_mermaid_exports_are_deterministic_and_include_links(tmp_path):
    add(tmp_path, "experience", state="complete")
    add(tmp_path, "email", "touchpoint", state="complete")
    add(tmp_path, "meeting", "meeting")
    tree.link_nodes(tmp_path, "experience", "email")
    tree.link_nodes(tmp_path, "email", "meeting")

    ascii_first = tree.to_ascii(tmp_path)
    mermaid_first = tree.to_mermaid(tmp_path)

    assert ascii_first == tree.to_ascii(tmp_path)
    assert "experience" in ascii_first and "email" in ascii_first and "meeting" in ascii_first
    assert mermaid_first == tree.to_mermaid(tmp_path)
    assert mermaid_first.startswith("graph TD")
    assert "-->" in mermaid_first


def test_status_counts_nodes_links_and_blockers(tmp_path):
    add(tmp_path, "parent", state="active")
    add(tmp_path, "child")
    tree.link_nodes(tmp_path, "parent", "child")

    status = tree.status(tmp_path)

    assert status["node_count"] == 2
    assert status["link_count"] == 1
    assert status["blocked_count"] == 1
    assert status["by_type"]["experience"] == 2


def _write_sources(root, jobs, tracker_rows):
    aggregate = root / "all_boards_data"
    aggregate.mkdir(parents=True, exist_ok=True)
    (aggregate / "all_jobs.json").write_text(json.dumps(jobs), encoding="utf-8")
    lines = [
        "| Date | Company | Role | Fit | Resume file | Status |",
        "|---|---|---|---|---|---|",
        *tracker_rows,
    ]
    (root / "job-history.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_sync_imports_all_jobs_and_unique_tracker_rows_without_marking_applied(tmp_path):
    root = tmp_path / "workspace"
    root.mkdir()
    jobs = [
        {"id": 1, "title": "Engineer", "employer": "Acme", "source": "SEEK", "url": "https://example.test/1", "location": "Hamilton", "fit": "High"},
        {"id": 2, "title": "Analyst", "employer": "Beta", "source": "SEEK", "url": "https://example.test/2", "location": "Auckland", "fit": "Medium"},
    ]
    _write_sources(root, jobs, ["| Sep 2026 | Acme | Engineer | High | Ayers_Resume_Engineer_Acme.docx + CoverLetter | drafted |"])

    report = tree.sync(root)
    graph = tree.load(root)
    job_node = next(node for node in graph["nodes"] if node["type"] == "opportunity" and node["data"]["source_index"] == 1)
    assert report["jobs_seen"] == 2
    assert report["tracker_rows"] == 1
    assert report["tracker_matched"] == 1
    assert sum(node["type"] == "opportunity" for node in graph["nodes"]) == 2
    assert len(graph["nodes"]) == 6
    assert graph["sources"]["corpus"]["rows"] == 2
    assert graph["sources"]["tracker"]["rows"] == 1
    assert job_node["state"] == "planned"
    assert job_node["data"]["tracker"]["status"] == "drafted"


def test_sync_uses_exact_tracker_artifact_names_and_leaves_sources_read_only(tmp_path):
    root = tmp_path / "workspace"
    root.mkdir()
    resume_name = "Ayers_Resume_Engineer_Acme.docx"
    (root / resume_name).write_bytes(b"resume")
    (root / "Ayers_Resume_Engineer_Acme_CoverLetter.docx").write_bytes(b"letter")
    (root / "_preview").mkdir()
    (root / "_preview" / "Ayers_Resume_Engineer_Acme_CoverLetter.pdf").write_bytes(b"pdf")
    _write_sources(root, [{"id": 1, "title": "Engineer", "employer": "Acme"}], [
        f"| Sep 2026 | Acme | Engineer | High | {resume_name} + CoverLetter | drafted |"
    ])
    before = {path: path.read_bytes() for path in [root / "job-history.md", root / "all_boards_data" / "all_jobs.json", root / resume_name, root / "Ayers_Resume_Engineer_Acme_CoverLetter.docx", root / "_preview" / "Ayers_Resume_Engineer_Acme_CoverLetter.pdf"]}

    tree.sync(root)

    node = next(node for node in tree.load(root)["nodes"] if node["data"].get("source_index") == 1)
    assert set(node["artifacts"]) == {resume_name, "Ayers_Resume_Engineer_Acme_CoverLetter.docx", "_preview/Ayers_Resume_Engineer_Acme_CoverLetter.pdf"}
    assert all(path.read_bytes() == content for path, content in before.items())


def test_sync_builds_prospective_sequence_for_uniquely_matched_tracker_jobs_only(tmp_path):
    root = tmp_path / "workspace"
    root.mkdir()
    jobs = [
        {"id": 1, "title": "Engineer", "employer": "Acme", "url": "https://example.test/1", "source": "SEEK", "description": "resume-supported opportunity"},
        {"id": 2, "title": "Analyst", "employer": "Beta", "url": "https://example.test/2", "source": "SEEK", "description": "other opportunity"},
    ]
    _write_sources(root, jobs, ["| Sep 2026 | Acme | Engineer | High | missing.docx | drafted |"])

    report = tree.sync(root)
    graph = tree.graph(root)
    indexed = {node["id"]: node for node in graph["nodes"]}
    opportunity = next(node for node in graph["nodes"] if node["data"].get("source_title") == "Engineer")
    proposals = [node for node in graph["nodes"] if node["data"].get("tracker_proposal")]
    proposal_edges = [edge for edge in graph["links"] if edge.get("origin") == "tracker-sync"]

    assert report["proposed_nodes_added"] == 4
    assert {node["type"] for node in proposals} == {"contact", "touchpoint", "meeting", "milestone"}
    assert len(proposal_edges) == 4
    assert any(edge["parent_id"] == opportunity["id"] for edge in proposal_edges)
    assert any(indexed[edge["child_id"]]["type"] == "milestone" for edge in proposal_edges)
    assert all(node["data"]["tracker_proposal"]["prospective_only"] for node in proposals)
    assert all(node["state"] == "planned" for node in proposals)
    assert all(not node["data"]["tracker_proposal"].get("confirmed_event") for node in proposals)
    assert sum(node["type"] == "opportunity" for node in graph["nodes"]) == 2
    assert report["tracker_matched"] == 1 and report["tracker_separate"] == 0


def test_sync_is_idempotent_and_preserves_manual_nodes_and_states(tmp_path):
    root = tmp_path / "workspace"
    root.mkdir()
    _write_sources(root, [{"id": 1, "title": "Engineer", "employer": "Acme", "url": "https://example.test/1", "source": "SEEK", "description": "Role"}], [])
    add(root, "my-experience", state="complete")

    tree.sync(root)
    imported_id = next(node["id"] for node in tree.load(root)["nodes"] if node["data"].get("source_index") == 1)
    tree.upsert_node(root, {"id": imported_id, "state": "active"})
    first = tree.sync(root)
    second = tree.sync(root)

    graph = tree.graph(root)
    assert len(graph["nodes"]) == 2  # one manual experience and one corpus opportunity
    assert {node["id"] for node in graph["nodes"]} == {imported_id, "my-experience"}
    assert next(node for node in graph["nodes"] if node["id"] == imported_id)["state"] == "active"
    assert first["nodes_added"] == 0 and second["nodes_added"] == 0
    assert first["nodes_updated"] == 0 and second["nodes_updated"] == 0


def test_sync_keeps_unmatched_tracker_rows_separate_and_does_not_guess(tmp_path):
    root = tmp_path / "workspace"
    root.mkdir()
    first = {"id": 1, "title": "Engineer", "employer": "Acme", "location": "Hamilton", "source": "SEEK", "url": "https://example.test/1", "description": "one"}
    _write_sources(root, [first], [])
    tree.sync(root)
    original_job_id = next(node["id"] for node in tree.load(root)["nodes"] if node["type"] == "opportunity")
    _write_sources(root, [{**first, "id": 99, "fit": "High"}], [])
    repeated = tree.sync(root)
    assert repeated["nodes_added"] == 0
    assert next(node["id"] for node in tree.load(root)["nodes"] if node["type"] == "opportunity") == original_job_id

    _write_sources(root, [first, {**first, "id": 11, "description": "two"}], ["| Sep 2026 | Acme | Engineer | High | missing.docx | drafted |"])
    report = tree.sync(root)
    graph = tree.load(root)
    assert report["tracker_ambiguous"] == 1
    assert "history:1" in {node["id"] for node in graph["nodes"]}
    assert all("tracker" not in node["data"] for node in graph["nodes"] if node["id"].startswith("job:"))
    assert next(node for node in graph["nodes"] if node["id"] == "history:1")["state"] == "planned"
    assert original_job_id in {node["id"] for node in graph["nodes"]}


def test_sync_preserves_long_source_titles_verbatim_without_losing_the_job_row(tmp_path):
    root = tmp_path / "workspace"
    root.mkdir()
    raw_title = "Captured feed wrapper " + ("Hamilton professional opportunity details " * 12)
    _write_sources(root, [{"id": 1789, "title": raw_title, "employer": "Trade Me listing"}], [])
    report = tree.sync(root)
    node = next(node for node in tree.load(root)["nodes"] if node["data"].get("source_index") == 1)
    assert report["jobs_seen"] == 1
    assert node["data"]["source_title"] == raw_title
    assert len(node["title"]) <= 240


def test_sync_refuses_ambiguous_identical_corpus_records_before_writing(tmp_path):
    root = tmp_path / "workspace"
    root.mkdir()
    duplicated = {"id": 1, "title": "Engineer", "employer": "Acme", "url": "https://example.test/1", "source": "SEEK", "description": "Same source row"}
    _write_sources(root, [duplicated, {**duplicated, "id": 2}], [])
    with pytest.raises(tree.TreeError, match="ambiguous duplicate corpus identity"):
        tree.sync(root)
    assert tree.load(root)["nodes"] == []


def test_next_branch_packet_is_bounded_and_counts_omitted_opportunities(tmp_path):
    root = tmp_path / "workspace"
    root.mkdir()
    jobs = [{"id": index, "title": f"Engineer {index}", "employer": "Acme", "url": f"https://example.test/{index}", "source": "SEEK", "description": f"private description {index}", "fit": "High"} for index in range(1, 46)]
    _write_sources(root, jobs, [])
    tree.sync(root)
    packet = tree.generate_next_packet(root, limit=40)
    assert packet["schema"] == "dossier.trajectory-next-branch/v1"
    assert packet["sourceCoverage"]["totalOpportunities"] == 45
    assert packet["sourceCoverage"]["includedOpportunities"] == 40
    assert packet["sourceCoverage"]["omittedOpportunities"] == 5
    assert len(packet["nodes"]) == 40
    assert "never mark an application applied" in packet["instruction"]
    assert all("private description" not in json.dumps(node) for node in packet["nodes"])


def test_sync_does_not_delete_manual_nodes_when_corpus_shrinks(tmp_path):
    root = tmp_path / "workspace"
    root.mkdir()
    _write_sources(root, [{"id": 1, "title": "Engineer", "employer": "Acme", "url": "https://example.test/1", "source": "SEEK", "description": "Role"}], [])
    add(root, "manual", state="complete")
    tree.sync(root)
    _write_sources(root, [], [])
    report = tree.sync(root)
    graph = tree.graph(root)
    assert "manual" in {node["id"] for node in graph["nodes"]}
    assert report["retained_missing_source"] == 1
    latest = next(node for node in graph["nodes"] if node["data"].get("source_stale"))
    assert latest["actionable"] is False

