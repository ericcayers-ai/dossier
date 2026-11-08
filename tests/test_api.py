import os
import re
from pathlib import Path

import pytest
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
    document.save(root / "sample_resume_Northbridge_TechnicalSupportEngineer_Sep2026.docx")
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

    bundle = client.get("/api/bundle", params={"rel": "sample_resume_Northbridge_TechnicalSupportEngineer_Sep2026.docx"}, headers=headers).json()
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


def test_the_ask_route_is_fail_closed_and_never_auto_submits(config, monkeypatch):
    """A12's mirrored route: unconfigured means 503 with nothing changed, and
    `apply` is refused before any client is built."""
    client = TestClient(create_app(config))
    headers = {"Authorization": "Bearer test-token"}

    unconfigured = client.post("/api/agent/ask", headers=headers, json={"mode": "diagnose"})
    assert unconfigured.status_code == 503
    assert unconfigured.json()["detail"]

    # A configured path pointed at a port nothing listens on, so `apply` reaching
    # the client would fail loudly rather than silently.
    monkeypatch.setenv("DOSSIER_MODEL_ENDPOINT", "http://127.0.0.1:9/never-called")
    monkeypatch.setenv("DOSSIER_MODEL_ID", "some-model")
    monkeypatch.setenv("DOSSIER_MODEL_KEY", "sentinel-value-not-a-real-key")
    refused = client.post("/api/agent/ask", headers=headers, json={"mode": "apply"})
    assert refused.status_code == 400
    assert "never run automatically" in refused.json()["detail"]
    assert "sentinel-value-not-a-real-key" not in refused.text


def test_the_trash_routes_list_and_restore_a_superseded_file(config):
    """B's Trash pane reads `GET /api/trash` and posts to `/api/trash/restore`."""
    root = config.root
    (root / "notes.md").write_text("first", encoding="utf-8")
    client = TestClient(create_app(config))
    headers = {"Authorization": "Bearer test-token"}

    saved = client.put("/api/file", headers=headers,
                       json={"rel": "notes.md", "content": "second"})
    assert saved.status_code == 200

    listing = client.get("/api/trash", headers=headers).json()
    assert listing["root"].endswith("trash")
    entries = [row for row in listing["entries"] if row["rel"] == "notes.md"]
    assert len(entries) == 1
    entry = entries[0]
    assert entry["trash_rel"].startswith(".dossier/trash/")
    assert entry["size"] == len("first")
    assert entry["trashed_at"]

    restored = client.post("/api/trash/restore", headers=headers,
                           json={"rel": entry["rel"], "trash_rel": entry["trash_rel"]})
    assert restored.status_code == 200
    assert restored.json()["restored"] is True
    assert (root / "notes.md").read_text(encoding="utf-8") == "first"

    # The restore did not lose the file it replaced.
    after = client.get("/api/trash", headers=headers).json()
    assert sorted(row["size"] for row in after["entries"] if row["rel"] == "notes.md") == [
        len("first"), len("second")]


def test_the_restore_route_refuses_a_target_outside_the_trash(config):
    root = config.root
    (root / "notes.md").write_text("current", encoding="utf-8")
    client = TestClient(create_app(config))
    headers = {"Authorization": "Bearer test-token"}

    outside = client.post("/api/trash/restore", headers=headers,
                          json={"rel": "notes.md", "trash_rel": "notes.md"})
    assert outside.status_code == 400
    assert (root / "notes.md").read_text(encoding="utf-8") == "current"

    missing = client.post("/api/trash/restore", headers=headers, json={"rel": "notes.md"})
    assert missing.status_code == 404

    no_rel = client.post("/api/trash/restore", headers=headers, json={})
    assert no_rel.status_code == 400


# -- the token is a cookie, not a URL parameter ----------------------------

def test_the_printed_console_url_carries_no_token():
    """`token-never-leaks` forbids a token in a log or handoff. The address the
    server prints is captured by terminal scrollback and by any log that wraps the
    process, so it must not carry the bearer value."""
    import inspect

    from dossier import cli

    source = inspect.getsource(cli._serve)
    assert "?token=" not in source
    assert "Dossier URL" in source


def test_the_cookie_alone_authorises_the_api(tmp_path):
    """The browser loads `/`, receives the httponly cookie, and every later request
    is authorised by it — which is what makes printing a token-free URL safe."""
    from fastapi.testclient import TestClient
    from dossier.api.app import create_app
    from dossier.config import AppConfig

    app = create_app(AppConfig.create(tmp_path, token="cookie-token"))
    client = TestClient(app)
    page = client.get("/")
    assert page.status_code == 200
    assert client.cookies.get("dossier_token") == "cookie-token"
    assert client.get("/api/health").status_code == 200
    # And the same request with no cookie and no header is still refused.
    assert TestClient(app).get("/api/health").status_code == 401


def test_the_built_assets_are_gzipped_and_cached_immutably(tmp_path):
    """Lighthouse named 710 KiB of uncompressed JavaScript and 863 KiB of assets with no
    cache policy on this app. Both are answered here: a hashed asset is immutable for a
    year, and anything over 1 KiB crosses the wire compressed. The API must not inherit
    the cache — a workspace changes under the client."""
    from dossier.api.app import create_app
    from dossier.config import AppConfig

    dist = Path(__file__).resolve().parents[1] / "ui" / "dist"
    assets = sorted((dist / "assets").glob("*.js")) if (dist / "assets").is_dir() else []
    if not assets:
        pytest.skip("the UI is not built: run `cd ui && npm run build`")

    client = TestClient(create_app(AppConfig.create(tmp_path, token="asset-token")))
    url = f"/assets/{assets[0].name}"
    packed = client.get(url, headers={"Accept-Encoding": "gzip"})
    assert packed.status_code == 200
    assert packed.headers["cache-control"] == "public, max-age=31536000, immutable"
    assert packed.headers.get("content-encoding") == "gzip"
    assert packed.headers.get("vary", "").lower().find("accept-encoding") >= 0

    # An identical request without gzip is not compressed, and decodes to the same bytes —
    # the assertion is on the header, because httpx decompresses `.content` for us.
    plain = client.get(url, headers={"Accept-Encoding": "identity"})
    assert plain.headers.get("content-encoding") is None
    assert plain.content == packed.content
    assert len(plain.content) == assets[0].stat().st_size

    api = client.get("/api/health", headers={"Authorization": "Bearer asset-token"})
    assert api.headers["cache-control"] == "no-store"


def test_no_route_answers_a_path_that_escapes_the_workspace(tmp_path):
    """A workspace app that takes a `rel` from the browser must never join it onto the root
    without proof it stays there. This is the unglamorous half of the trajectory feature:
    the tree, the bundle, the render and the export all accept a path."""
    from dossier.api.app import create_app
    from dossier.config import AppConfig

    client = TestClient(create_app(AppConfig.create(tmp_path, token="escape-token")))
    headers = {"Authorization": "Bearer escape-token"}
    hostile = ["../outside.txt", "/etc/passwd", "sub/../../outside.txt"]
    if os.name == "nt":
        # A backslash is a separator on Windows only; on POSIX a backslash is a legal filename character,
        # so asserting 400 for one there would test nothing.
        hostile += ["..\\outside.txt", "C:\\Windows\\win.ini"]
    for rel in hostile:
        response = client.get("/api/file", params={"rel": rel}, headers=headers)
        assert response.status_code == 400, (rel, response.status_code, response.text[:120])
        assert "escapes root" in response.text or "absolute" in response.text, rel


def test_every_declared_api_route_is_behind_the_token(tmp_path):
    """A new route that forgets the middleware would be an open door on a server that binds a
    loopback port, so the invariant is asserted against the app's own route table rather than
    against one hand-picked endpoint."""
    from dossier.api.app import create_app
    from dossier.config import AppConfig

    app = create_app(AppConfig.create(tmp_path, token="route-token"))
    declared = sorted({route.path for route in app.routes if route.path.startswith("/api/")})
    assert len(declared) >= 20, declared          # the contract is wide; a shrinking list is a bug
    anonymous = TestClient(app)
    for path in declared:
        url = re.sub(r"{[^}]+}", "x", path)
        assert anonymous.get(url).status_code == 401, path
        assert anonymous.post(url, json={}).status_code == 401, path


def test_the_panel_route_scores_seven_seats_and_quotes_real_lines(config):
    """The panel is the one route whose answer is a quote; check the quote is real."""
    root = config.root
    (root / "resume.md").write_text(
        "# Sam Rivers\n\n## Experience\n\n"
        "- Responsible for helping the team with various tasks\n"
        "- Built a Python parser that cut handling time by 40%\n\n"
        "## Education\n\n2019 University of Waikato\n\n## Skills\n\nPython, SQL\n",
        encoding="utf-8")
    (root / "posting.md").write_text(
        "Support engineer wanted.\nPython and SQL required.\nLinux exposure preferred.\n",
        encoding="utf-8")
    client = TestClient(create_app(config))
    headers = {"Authorization": "Bearer test-token"}
    answer = client.get("/api/panel?resume=resume.md&posting=posting.md", headers=headers)
    assert answer.status_code == 200, answer.text
    data = answer.json()
    assert len(data["seats"]) == 7
    assert 0 <= data["score"] <= 100
    lines = (root / "resume.md").read_text(encoding="utf-8").split("\n")
    posting_lines = (root / "posting.md").read_text(encoding="utf-8").split("\n")
    quotes = [finding for seat in data["seats"] for finding in seat["findings"] if finding["quote"]]
    assert quotes, "the fixture has objections to quote"
    for finding in quotes:
        pool = posting_lines if finding.get("source") == "posting" else lines
        assert finding["quote"] in pool[finding["line"] - 1]

    assert client.get("/api/panel", headers=headers).status_code == 400
    assert client.get("/api/panel?resume=nope.md", headers=headers).status_code == 404


def test_a_get_never_converts_and_the_post_owns_the_build(config):
    """`CONVENTIONS.md:33`: a GET never performs a slow operation. The render split is
    what makes that true — GET serves cache, POST builds, and a miss says which."""
    from docx import Document

    root = config.root
    document = Document()
    document.add_paragraph("A page of text for the renderer.")
    document.save(root / "page.docx")
    client = TestClient(create_app(config))
    headers = {"Authorization": "Bearer test-token"}

    first = client.get("/api/render?rel=page.docx", headers=headers)
    assert first.status_code == 409, first.text
    assert "POST /api/render" in first.json()["detail"]

    built = client.post("/api/render", json={"rel": "page.docx"}, headers=headers)
    if built.status_code == 503:
        # The converter is an external process and may be busy. The contract is a
        # sentence, not a traceback, and the cache stays empty so a retry is honest.
        assert "DOCX renderer" in built.json()["detail"]
        assert client.get("/api/render?rel=page.docx", headers=headers).status_code == 409
        pytest.skip(f"renderer unavailable this run: {built.json()['detail'][:80]}")
    assert built.status_code == 200, built.text
    assert built.json()["cached"] is True
    assert built.json()["fidelity"] == "faithful"

    second = client.get("/api/render?rel=page.docx", headers=headers)
    assert second.status_code == 200
    assert second.headers["content-type"] == "application/pdf"

    routes = client.get("/api/convert/routes?rel=page.docx", headers=headers)
    assert routes.status_code == 200
    classes = {route["target"]: route["fidelity"] for route in routes.json()["routes"]}
    assert classes[".pdf"] == "faithful"
    assert classes[".md"] == "semantic"


def test_a_converter_failure_is_a_sentence_not_a_traceback(config, monkeypatch):
    """Word is an external process; it can be busy or absent. The route must answer
    503 with a sentence and leave the cache empty, so the next attempt is honest."""
    from docx import Document
    import dossier.convert as convert_module

    root = config.root
    document = Document()
    document.add_paragraph("text")
    document.save(root / "page.docx")

    def refuse(source, target):
        raise RuntimeError("Word is not responding")

    monkeypatch.setattr(convert_module, "convert", refuse, raising=True)
    client = TestClient(create_app(config))
    headers = {"Authorization": "Bearer test-token"}
    answer = client.post("/api/render", json={"rel": "page.docx"}, headers=headers)
    assert answer.status_code == 503, answer.text
    assert "DOCX renderer could not run" in answer.json()["detail"]
    assert client.get("/api/render?rel=page.docx", headers=headers).status_code == 409


def test_a_token_in_the_query_string_is_not_accepted(tmp_path):
    """The bearer token lives in a header or the Lax cookie, never in a URL.

    A `?token=` was accepted once, and the client appended it to `<img>`, `<a>` and
    EventSource URLs — which put the credential in the address bar, in browser
    history, in the `Referer` of a followed link and in the access log. The gate that
    forbids it is `token-never-leaks`; this is the half that the CLI test never covered.
    """
    from dossier.config import AppConfig

    client = TestClient(create_app(AppConfig.create(tmp_path, token="query-token")))
    assert client.get("/api/health?token=query-token").status_code == 401
    # the header still works, so the refusal is about the channel and not the value
    assert client.get("/api/health", headers={"Authorization": "Bearer query-token"}).status_code == 200


def test_raw_serves_markup_as_a_download_inside_a_sandbox(tmp_path):
    """A page in the folder must not become script with the app's own authority."""
    from dossier.config import AppConfig

    (tmp_path / "note.md").write_text("plain text")
    (tmp_path / "page.html").write_text("<script>alert(1)</script>")
    (tmp_path / "drawing.svg").write_text("<svg xmlns='http://www.w3.org/2000/svg'/>")
    client = TestClient(create_app(AppConfig.create(tmp_path, token="raw-token")))
    headers = {"Authorization": "Bearer raw-token"}

    for name in ("page.html", "drawing.svg"):
        answer = client.get(f"/api/raw?rel={name}", headers=headers)
        assert answer.status_code == 200, answer.text
        assert answer.headers["x-content-type-options"] == "nosniff"
        assert "sandbox" in answer.headers["content-security-policy"]
        assert answer.headers["content-disposition"].startswith("attachment"), name

    plain = client.get("/api/raw?rel=note.md", headers=headers)
    assert plain.status_code == 200
    assert plain.headers["content-disposition"].startswith("inline")
    assert plain.headers["x-content-type-options"] == "nosniff"
