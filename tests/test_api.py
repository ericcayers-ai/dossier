from fastapi.testclient import TestClient
from docx import Document

from dossier.api.app import create_app


def test_api_contract_and_audit(config):
    root = config.root
    (root / "source" ).mkdir()
    (root / "job-posting-Northbridge-TechnicalSupportEngineer.md").write_text("role source")
    (root / "keywords-Northbridge-TechnicalSupportEngineer.md").write_text("technical support")
    document = Document()
    document.add_paragraph("Technical support evidence")
    document.save(root / "Ayers_Resume_Northbridge_TechnicalSupportEngineer_Sep2026.docx")
    (root / "notes.md").write_text("genetic gain")

    client = TestClient(create_app(config))
    assert client.get("/api/health").status_code == 401
    headers = {"Authorization": "Bearer test-token"}
    health = client.get("/api/health", headers=headers)
    assert health.status_code == 200
    assert health.json()["indexed"] == 4

    tree = client.get("/api/tree", headers=headers).json()
    assert any(item["rel"] == "source" and item["directory"] for item in tree)
    assert any(item["rel"] == "notes.md" for item in tree)

    bundle = client.get("/api/bundle", params={"rel": "Ayers_Resume_Northbridge_TechnicalSupportEngineer_Sep2026.docx"}, headers=headers).json()
    assert len(bundle["members"]) == 3
    assert {member["role"] for member in bundle["members"]} == {"source", "analysis", "artifact"}

    file_data = client.get("/api/file", params={"rel": "notes.md"}, headers=headers).json()
    (root / "notes.md").write_text("changed outside Dossier")
    conflict = client.put("/api/file", headers=headers, json={"rel": "notes.md", "content": "blocked", "expect": file_data["stamp"]})
    assert conflict.status_code == 409
    assert (root / "notes.md").read_text() == "changed outside Dossier"

    current = client.get("/api/file", params={"rel": "notes.md"}, headers=headers).json()
    saved = client.put("/api/file", headers=headers, json={"rel": "notes.md", "content": "saved", "expect": current["stamp"]})
    assert saved.status_code == 200
    assert list((config.dossier_dir / "trash").rglob("notes.md"))

    audit = client.get("/api/audit", headers=headers).json()
    assert len(audit["checks"]) >= 7
    assert any(check["id"] == "submission-approval" for check in audit["checks"])
    handoff = client.get("/api/ai/handoff", headers=headers).json()
    assert "review and explicit approval" in handoff["prompt"]
    assert len(handoff["packet"]["file_manifest"]) == 4
    assert isinstance(handoff["packet"]["job_records"], list)
    assert config.token not in handoff["prompt"]


def test_api_path_escape(config):
    client = TestClient(create_app(config))
    assert client.get("/api/tree", params={"dir": "../outside"}, headers={"Authorization": "Bearer test-token"}).status_code == 400
