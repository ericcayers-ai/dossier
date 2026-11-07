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
    assert result["url"] == "https://boards-api.greenhouse.io/v1/boards/acme/jobs"
    assert result["records"] == 2
    assert result["jobs"][0]["employer"] == "Acme"
    assert result["jobs"][0]["location"] == "Hamilton"
    assert http.calls == [result["url"]]


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
