import json

from fastapi.testclient import TestClient

from dossier.api.app import create_app
from dossier.config import AppConfig


TOKEN = "trajectory-test-token"
HEADERS = {"Authorization": f"Bearer {TOKEN}"}


def client_for(root):
    return TestClient(create_app(AppConfig.create(root, token=TOKEN)), raise_server_exceptions=False)


def test_tree_graph_endpoint_is_authenticated_and_keeps_legacy_file_listing(tmp_path):
    (tmp_path / "resume.md").write_text("# Resume\n", encoding="utf-8")
    with client_for(tmp_path) as client:
        assert client.get("/api/tree").status_code == 401

        graph_response = client.get("/api/tree?view=trajectory", headers=HEADERS)
        file_response = client.get("/api/tree", headers=HEADERS)
        file_dir_response = client.get("/api/tree?dir=", headers=HEADERS)

    assert graph_response.status_code == 200
    assert graph_response.json() == {"version": 1, "nodes": [], "links": [], "sources": {}}
    assert file_response.status_code == 200
    assert any(node["rel"] == "resume.md" for node in file_response.json())
    assert file_dir_response.status_code == 200
    assert any(node["rel"] == "resume.md" for node in file_dir_response.json())
    invalid_view = client.get("/api/tree?view=graph", headers=HEADERS)
    invalid_link = client.post("/api/tree/links", headers=HEADERS, json={"parent_id": [], "child_id": "child"})
    assert invalid_view.status_code == 400
    assert invalid_link.status_code == 400


def test_api_creates_nodes_links_and_exports_a_complete_path(tmp_path):
    with client_for(tmp_path) as client:
        nodes = [
            {"id": "experience", "type": "experience", "title": "Completed project", "state": "complete", "date": "2026-01-01"},
            {"id": "email", "type": "touchpoint", "title": "Inbound email", "state": "complete", "date": "2026-02-01"},
            {"id": "meeting", "type": "meeting", "title": "Interview", "state": "complete", "date": "2026-03-01"},
            {"id": "opportunity", "type": "opportunity", "title": "Tailored opportunity", "date": "2026-04-01"},
            {"id": "milestone", "type": "milestone", "title": "Offer outcome", "date": "2026-05-01"},
        ]
        for node in nodes:
            response = client.post("/api/tree/nodes", headers=HEADERS, json=node)
            assert response.status_code == 200, response.text
        for parent, child in [("experience", "email"), ("email", "meeting"), ("meeting", "opportunity")]:
            response = client.post("/api/tree/links", headers=HEADERS, json={"parent_id": parent, "child_id": child})
            assert response.status_code == 200, response.text

        graph = client.get("/api/tree?view=trajectory", headers=HEADERS).json()
        ascii_export = client.get("/api/tree/export?format=ascii", headers=HEADERS)
        mermaid_export = client.get("/api/tree/export?format=mermaid", headers=HEADERS)

    assert len(graph["nodes"]) == 5 and len(graph["links"]) == 3
    assert next(node for node in graph["nodes"] if node["id"] == "opportunity")["actionable"] is True
    assert ascii_export.status_code == 200 and "Inbound email" in ascii_export.text
    assert mermaid_export.status_code == 200 and mermaid_export.text.startswith("graph TD")
    assert "-->" in mermaid_export.text


def test_api_creates_nodes_links_and_exports_an_experience_to_milestone_path(tmp_path):
    with client_for(tmp_path) as client:
        stages = [
            {"id": "experience", "type": "experience", "title": "Verified project", "state": "complete", "date": "2026-01-01"},
            {"id": "contact", "type": "contact", "title": "Hiring contact", "state": "complete", "date": "2026-01-10"},
            {"id": "email", "type": "touchpoint", "title": "Inbound email", "state": "complete", "date": "2026-01-12"},
            {"id": "meeting", "type": "meeting", "title": "Interview", "state": "complete", "date": "2026-01-20"},
            {"id": "opportunity", "type": "opportunity", "title": "Tailored job opportunity", "date": "2026-01-25"},
            {"id": "milestone", "type": "milestone", "title": "Offer milestone", "date": "2026-02-01"},
        ]
        for node in stages:
            assert client.post("/api/tree/nodes", headers=HEADERS, json=node).status_code == 200
        edges = [("experience", "contact"), ("contact", "email"), ("email", "meeting"), ("meeting", "opportunity"), ("opportunity", "milestone")]
        for parent, child in edges:
            response = client.post("/api/tree/links", headers=HEADERS, json={"parent_id": parent, "child_id": child})
            assert response.status_code == 200, response.text
        graph = client.get("/api/tree?view=trajectory", headers=HEADERS).json()
        assert next(node for node in graph["nodes"] if node["id"] == "milestone")["actionable"] is False
        assert client.post("/api/tree/nodes", headers=HEADERS, json={"id": "opportunity", "state": "complete"}).status_code == 200
        graph = client.get("/api/tree?view=trajectory", headers=HEADERS).json()
        ascii_export = client.get("/api/tree/export?format=ascii", headers=HEADERS).text
        mermaid_export = client.get("/api/tree/export?format=mermaid", headers=HEADERS).text

    assert len(graph["nodes"]) == 6 and len(graph["links"]) == 5
    assert next(node for node in graph["nodes"] if node["id"] == "milestone")["actionable"] is True
    for label in ("Verified project", "Hiring contact", "Inbound email", "Interview", "Tailored job opportunity", "Offer milestone"):
        assert label in ascii_export
    assert mermaid_export.count("-->") == 5


def test_api_rejects_invalid_nodes_cycles_and_incomplete_prerequisites(tmp_path):
    with client_for(tmp_path) as client:
        invalid = client.post("/api/tree/nodes", headers=HEADERS, json={"type": "resume", "title": "Not a node"})
        parent = client.post("/api/tree/nodes", headers=HEADERS, json={"id": "parent", "type": "experience", "title": "Project", "state": "active"})
        child = client.post("/api/tree/nodes", headers=HEADERS, json={"id": "child", "type": "touchpoint", "title": "Email"})
        link = client.post("/api/tree/links", headers=HEADERS, json={"parent_id": "parent", "child_id": "child"})
        activate = client.post("/api/tree/nodes", headers=HEADERS, json={"id": "child", "state": "active"})
        reverse = client.post("/api/tree/links", headers=HEADERS, json={"parent_id": "child", "child_id": "parent"})
        bad_export = client.get("/api/tree/export?format=html", headers=HEADERS)

    assert invalid.status_code == 400
    assert parent.status_code == child.status_code == 200
    assert link.status_code == 200
    assert activate.status_code == 400
    assert reverse.status_code == 400
    assert bad_export.status_code == 400


def test_api_next_packet_omits_posting_body_and_reports_bounded_coverage(tmp_path):
    jobs = [{
        "id": index,
        "title": f"Engineer {index}",
        "employer": "Acme",
        "url": f"https://example.test/{index}",
        "source": "SEEK",
        "description": f"PRIVATE BODY {index}",
        "fit": "High",
    } for index in range(1, 4)]
    aggregate = tmp_path / "all_boards_data"
    aggregate.mkdir()
    jobs_path = aggregate / "all_jobs.json"
    jobs_path.write_text(json.dumps(jobs), encoding="utf-8")
    history_path = tmp_path / "job-history.md"
    history_path.write_text("# Applications\n", encoding="utf-8")
    before = (jobs_path.read_bytes(), history_path.read_bytes())

    with client_for(tmp_path) as client:
        sync_response = client.post("/api/tree/sync", headers=HEADERS, json={})
        packet_response = client.post("/api/tree/packet", headers=HEADERS, json={"limit": 2, "context_limit": 0})

    assert sync_response.status_code == 200
    assert packet_response.status_code == 200
    packet = packet_response.json()
    assert packet["sourceCoverage"]["includedOpportunities"] == 2
    assert packet["sourceCoverage"]["omittedOpportunities"] == 1
    assert len(packet["nodes"]) == 2
    assert all("PRIVATE BODY" not in json.dumps(node) for node in packet["nodes"])
    assert "never mark an application applied" in packet["instruction"]
    assert (jobs_path.read_bytes(), history_path.read_bytes()) == before


def test_api_sync_imports_workspace_sources_without_changing_them(tmp_path):
    jobs_dir = tmp_path / "all_boards_data"
    jobs_dir.mkdir()
    jobs_path = jobs_dir / "all_jobs.json"
    jobs_path.write_text(json.dumps([{"id": 1, "title": "Engineer", "employer": "Acme", "source": "SEEK"}]), encoding="utf-8")
    history_path = tmp_path / "job-history.md"
    history_path.write_text(
        "| Date | Company | Role | Fit | Resume file | Status |\n"
        "|---|---|---|---|---|---|\n"
        "| Sep 2026 | Acme | Engineer | High | missing.docx | drafted |\n",
        encoding="utf-8",
    )
    before = (jobs_path.read_bytes(), history_path.read_bytes())

    with client_for(tmp_path) as client:
        response = client.post("/api/tree/sync", headers=HEADERS, json={})
        graph = client.get("/api/tree?view=trajectory", headers=HEADERS).json()

    assert response.status_code == 200
    assert response.json()["jobs_seen"] == 1
    assert graph["sources"]["corpus"]["rows"] == 1
    assert graph["sources"]["tracker"]["rows"] == 1
    assert len(graph["sources"]["corpus"]["sha256"]) == 64
    assert sum(node["type"] == "opportunity" for node in graph["nodes"]) == 1
    job = next(node for node in graph["nodes"] if node["type"] == "opportunity")
    assert job["state"] == "planned"
    assert job["data"]["tracker"]["status"] == "drafted"
    assert (jobs_path.read_bytes(), history_path.read_bytes()) == before

