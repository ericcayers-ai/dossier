import json

import pytest

from dossier import cli, feeds
from dossier.engine.sources import SourceRefused
from dossier.feeds import FeedPolicyError, Greenhouse, adapter


def test_fixture_adapters():
    assert Greenhouse().parse({'jobs': [{'id': 1, 'title': 'X'}]})[0].title == 'X'


def test_prohibited_no_client():
    """A prohibited board is refused, and a refused board never reaches a client."""
    with pytest.raises(FeedPolicyError):
        adapter('linkedin').fetch()


# -- the wiring the adapters never had -------------------------------------

GREENHOUSE_PAYLOAD = {"jobs": [
    {"id": 1, "title": "Engineer", "company": "Acme", "location": {"name": "Hamilton"},
     "absolute_url": "https://example/1",
     "description": "Build things. <script>tracker()</script>"},
    {"id": 2, "title": "Analyst", "company": "Beta", "location": {"name": "Remote"},
     "absolute_url": "https://example/2", "description": "Explain numbers."},
]}


def fake_http(payload):
    calls = []

    def client(url):
        calls.append(url)
        return payload

    client.calls = calls
    return client


def test_a_board_fetch_maps_to_corpus_rows():
    http = fake_http(GREENHOUSE_PAYLOAD)
    result = feeds.fetch_board("greenhouse", board="acme", http=http)
    assert result["url"] == "https://boards-api.greenhouse.io/v1/boards/acme/jobs?content=true"
    assert result["records"] == 2
    assert result["jobs"][0]["employer"] == "Acme"
    assert result["jobs"][0]["location"] == "Hamilton"
    assert http.calls == [result["url"]]


# -- the posting body: what each board actually sends (measured live 2026-11-12) --

def test_greenhouse_asks_for_the_body_and_reads_content():
    """Without ?content=true Greenhouse sends no body; `content` arrives
    entity-escaped, and `description` is a field it never sends."""
    assert feeds.ENDPOINTS["greenhouse"].endswith("?content=true")
    payload = {"jobs": [{"id": 7, "title": "Engineer", "company_name": "Acme",
                         "content": "&lt;p&gt;Build things.&lt;/p&gt;"
                                    "&lt;ul&gt;&lt;li&gt;Python&lt;/li&gt;&lt;li&gt;SQL&lt;/li&gt;&lt;/ul&gt;"}]}
    job = Greenhouse().parse(payload)[0]
    assert "Python" in job.description and "SQL" in job.description
    assert "<" not in job.description and "&lt;" not in job.description


def test_lever_maps_text_applyurl_categories_and_plain_body():
    from dossier.feeds import Lever
    payload = [{"id": "abc", "text": "Engineer",
                "applyUrl": "https://jobs.lever.co/acme/abc/apply",
                "categories": {"commitment": "Full-time", "location": "Hamilton"},
                "descriptionPlain": "Build things.\nKnow Python.",
                "description": "<p>Build things.</p><p>Know Python.</p>"}]
    job = Lever().parse(payload)[0]
    assert job.title == "Engineer"
    assert job.url == "https://jobs.lever.co/acme/abc/apply"
    assert job.location == "Hamilton"
    assert job.work_type == "Full-time"
    assert job.description == "Build things.\nKnow Python."


def test_lever_falls_back_to_stripping_html_description():
    from dossier.feeds import Lever
    payload = [{"id": "abc", "text": "Engineer",
                "description": "<p>Build things.</p><script>tracker()</script>"}]
    job = Lever().parse(payload)[0]
    assert job.description == "Build things."
    assert "tracker()" not in job.description


def test_ashby_maps_camelcase_fields_and_html_body():
    from dossier.feeds import Ashby
    payload = {"jobs": [{"id": "xyz", "title": "Engineer",
                         "applyUrl": "https://jobs.ashbyhq.com/acme/xyz/application",
                         "location": "Remote", "employmentType": "FullTime",
                         "descriptionHtml": "<p>Build things.</p><ul><li>Python</li></ul>"}]}
    job = Ashby().parse(payload)[0]
    assert job.url == "https://jobs.ashbyhq.com/acme/xyz/application"
    assert job.work_type == "FullTime"
    assert "Python" in job.description and "<" not in job.description


def test_board_slug_fills_the_employer_the_api_omits():
    """Lever and Ashby send no company per posting; the board is the company."""
    lever = feeds.fetch_board("lever", board="acme", http=fake_http(
        [{"id": "a", "text": "Engineer", "descriptionPlain": "Body."}]))
    ashby = feeds.fetch_board("ashby", board="acme", http=fake_http(
        {"jobs": [{"id": "b", "title": "Engineer", "descriptionHtml": "<p>Body.</p>"}]}))
    assert lever["jobs"][0]["employer"] == "acme"
    assert ashby["jobs"][0]["employer"] == "acme"


def test_every_board_scoped_feed_returns_a_readable_body():
    """The measured defect: all three board-scoped feeds wrote empty
    descriptions, so requirement extraction judged postings by title alone."""
    payloads = {
        "greenhouse": {"jobs": [{"id": 1, "title": "Engineer",
                                 "content": "&lt;p&gt;Require Python.&lt;/p&gt;"}]},
        "lever": [{"id": "a", "text": "Engineer", "descriptionPlain": "Require Python."}],
        "ashby": {"jobs": [{"id": "b", "title": "Engineer",
                            "descriptionHtml": "<p>Require Python.</p>"}]},
    }
    for source, payload in payloads.items():
        result = feeds.fetch_board(source, board="acme", http=fake_http(payload))
        row = result["jobs"][0]
        assert row["description"].strip(), f"{source} wrote an empty description"
        assert "Require Python." in row["description"]
        assert "<" not in row["description"]


def test_a_board_scoped_feed_names_the_missing_slug():
    with pytest.raises(ValueError) as caught:
        feeds.endpoint_for("greenhouse")
    assert "--board" in str(caught.value)


def test_an_unknown_feed_names_the_real_ones():
    with pytest.raises(ValueError) as caught:
        feeds.endpoint_for("monster")
    assert "greenhouse" in str(caught.value)


def test_a_prohibited_board_is_refused_before_the_client_is_used(tmp_path):
    http = fake_http(GREENHOUSE_PAYLOAD)
    with pytest.raises(SourceRefused):
        feeds.fetch_board("linkedin", http=http, root=tmp_path)
    assert http.calls == []


def test_a_feed_writes_the_corpus_shape_and_a_provenance_file(tmp_path):
    import httpx

    # The CLI builds its own client, so the transport is stubbed at the httpx
    # layer rather than by a fake callable: that exercises the real code path.
    payload = json.dumps(GREENHOUSE_PAYLOAD).encode("utf-8")

    def handler(request):
        return httpx.Response(200, content=payload,
                              headers={"content-type": "application/json"})

    original = httpx.Client

    class Patched(original):
        def __init__(self, *args, **kwargs):
            kwargs["transport"] = httpx.MockTransport(handler)
            super().__init__(*args, **kwargs)

    httpx.Client = Patched
    try:
        code = cli.main(["feeds", "fetch", "greenhouse", "--board", "acme",
                         "--root", str(tmp_path), "--limit", "1", "--json"])
    finally:
        httpx.Client = original

    assert code == 1, "a truncated fetch must report itself as partial"
    target = tmp_path / "greenhouse_data" / "all_jobs.json"
    rows = json.loads(target.read_text(encoding="utf-8"))
    assert len(rows) == 1 and rows[0]["employer"] == "Acme"
    assert "tracker()" not in rows[0]["description"]
    provenance = list((tmp_path / ".dossier" / "scrape" / "feeds").glob("greenhouse-*.json"))
    assert provenance and json.loads(provenance[0].read_text(encoding="utf-8"))["truncated"] is True
    snapshot = json.loads(next(tmp_path.glob("nz-job-search-coverage-*.json")).read_text(encoding="utf-8"))
    assert snapshot["source_statuses"] == {"greenhouse": "partial"}
    assert "--limit" in snapshot["current_limits"]["greenhouse"]


def test_a_complete_fetch_clears_the_coverage_attention(tmp_path, capsys):
    import httpx

    payload = json.dumps(GREENHOUSE_PAYLOAD).encode("utf-8")

    def handler(request):
        return httpx.Response(200, content=payload,
                              headers={"content-type": "application/json"})

    original = httpx.Client

    class Patched(original):
        def __init__(self, *args, **kwargs):
            kwargs["transport"] = httpx.MockTransport(handler)
            super().__init__(*args, **kwargs)

    httpx.Client = Patched
    try:
        code = cli.main(["feeds", "fetch", "greenhouse", "--board", "acme",
                         "--root", str(tmp_path), "--limit", "50", "--json"])
        assert code == 0
        capsys.readouterr()
        cli.main(["audit", "--root", str(tmp_path), "--json"])
    finally:
        httpx.Client = original

    report = json.loads(capsys.readouterr().out)
    coverage_check = next(check for check in report["checks"] if check["id"] == "coverage")
    assert coverage_check["status"] == "pass", coverage_check
    snapshot = json.loads(next(tmp_path.glob("nz-job-search-coverage-*.json")).read_text(encoding="utf-8"))
    assert snapshot["source_statuses"] == {"greenhouse": "captured"}
    assert snapshot["current_source_counts"] == {"greenhouse": 2}


def test_an_http_error_names_the_status(tmp_path):
    import httpx

    def handler(request):
        return httpx.Response(503)

    original = httpx.Client

    class Patched(original):
        def __init__(self, *args, **kwargs):
            kwargs["transport"] = httpx.MockTransport(handler)
            super().__init__(*args, **kwargs)

    httpx.Client = Patched
    try:
        with pytest.raises(RuntimeError) as caught:
            feeds.fetch_board("remotive", root=tmp_path)
    finally:
        httpx.Client = original
    assert "503" in str(caught.value)
