"""The capture layer: policy, sessions, extraction, and the honesty of `complete`.

Two groups.

The first needs no browser and no network: recipe validation, source resolution,
the session store's structural refusal to keep a credential, robots semantics,
pacing, extraction, and the `partial-is-not-exhaustive` arithmetic (driven by a
fake fetch, so a specific failure is the only thing under test).

The second drives the real engines against `tests/fixtures/scrape_site.py`: a
public page through obscura, a page rendered by JavaScript and a cookie-gated page
through Playwright, a challenge, a robots refusal, and a list recipe that walks
`rel=next`. Each test skips — visibly, with the reason — when that engine is not
installed, because a capture test that quietly passes without a browser is worse
than no test.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from urllib.parse import urlparse

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent / "fixtures"))

from scrape_site import FixtureSite  # noqa: E402

from dossier.engine.sources import SourceRefused  # noqa: E402
from dossier.scrape import browser, extract, guard, recipes, runner  # noqa: E402
from dossier.scrape.errors import (AuthRequired, Blocked, ChallengeDetected,  # noqa: E402
                                   RecipeError, Transient)
from dossier.scrape.session import (SessionStore, import_netscape_cookies,  # noqa: E402
                                    parse_netscape_cookies)

ROOT = Path(__file__).resolve().parents[1]

#: One cookies.txt line pair, as a browser exports it.
COOKIE_FILE = (
    "# Netscape HTTP Cookie File\n"
    "#HttpOnly_.example.com\tTRUE\t/\tTRUE\t1893456000\tsession\tabc123\n"
    "example.com\tFALSE\t/jobs\tFALSE\t0\ttheme\tdark\n"
)


def _recipe_dict(**overrides) -> dict:
    data = {
        "id": "fixture-listing",
        "source": "web",
        "start_url": "https://example.com/jobs",
        "auth": "public",
        "list": {"item": "article.card", "link": "h2 a", "title": "h2",
                 "company": ".company", "location": ".location"},
        "detail": {"content": "main", "remove": []},
        "pagination": {"mode": "none", "max_pages": 1},
        "limits": {"max_items": 10, "delay_ms": 0, "timeout_s": 10, "retries": 0},
    }
    data.update(overrides)
    return data


def _write_recipe(root: Path, data: dict) -> Path:
    folder = root / ".dossier" / "scrapes"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{data['id']}.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


# --------------------------------------------------------------------------
# recipes
# --------------------------------------------------------------------------

def test_a_typo_in_a_recipe_is_an_error_not_a_silent_one_page_run():
    with pytest.raises(RecipeError) as caught:
        recipes.validate(_recipe_dict(paginaton={"mode": "next-link"}))
    assert "unknown key" in str(caught.value)


def test_a_selector_lxml_cannot_parse_fails_before_any_request():
    with pytest.raises(RecipeError) as caught:
        recipes.validate(_recipe_dict(list={"item": "div[", "link": "a"}))
    assert "selector" in str(caught.value)


def test_pagination_requires_the_parameter_it_needs():
    with pytest.raises(RecipeError):
        recipes.validate(_recipe_dict(pagination={"mode": "query", "max_pages": 2}))
    with pytest.raises(RecipeError):
        recipes.validate(_recipe_dict(pagination={"mode": "next-link", "max_pages": 2}))


def test_a_start_url_must_be_absolute_http():
    with pytest.raises(RecipeError):
        recipes.validate(_recipe_dict(start_url="/jobs"))


def test_the_shipped_recipes_all_validate():
    found, errors = recipes.discover(ROOT, include_shipped=True)
    shipped = [recipe for recipe in found if recipe.origin == "shipped"]
    assert shipped, "no shipped recipe was discovered; templates/scrapes is not being read"
    assert not errors, errors


def test_a_broken_workspace_recipe_is_reported_and_does_not_fall_back(tmp_path):
    _write_recipe(tmp_path, {"id": "listing-template", "source": "web"})  # invalid: no start_url
    found, errors = recipes.discover(tmp_path)
    assert errors and errors[0]["path"].endswith("listing-template.json")
    # The shipped recipe with the same id must not stand in for the user's file.
    assert all(recipe.id != "listing-template" for recipe in found)


# --------------------------------------------------------------------------
# policy and source resolution
# --------------------------------------------------------------------------

def test_the_host_decides_the_board_not_the_recipe(tmp_path):
    assert guard.resolve_source("https://nz.linkedin.com/jobs/view/1") == "linkedin"
    assert guard.resolve_source("https://www.seek.co.nz/job/1") == "seek"
    # `web` is the absence of a claim, so the host still wins.
    assert guard.resolve_source("https://linkedin.com/jobs/view/1", "web") == "linkedin"
    assert guard.resolve_source("https://careers.example.org/job/1") == "web"


def test_a_recipe_cannot_relabel_a_prohibited_board():
    with pytest.raises(SourceRefused):
        guard.resolve_source("https://www.linkedin.com/jobs/view/1", "indeed")


def test_a_prohibited_board_is_refused_before_any_fetch(tmp_path, monkeypatch):
    called = {"n": 0}

    def never_called(*args, **kwargs):
        called["n"] += 1
        raise AssertionError("a prohibited board reached the network")

    monkeypatch.setattr(runner, "_fetched", never_called)
    with pytest.raises(SourceRefused) as caught:
        runner.capture_url(tmp_path, "https://www.linkedin.com/jobs/view/123")
    assert "prohibited" in str(caught.value)
    assert called["n"] == 0


def test_a_prohibited_recipe_is_refused_before_a_listing_request(tmp_path, monkeypatch):
    called = {"n": 0}

    def never_called(*args, **kwargs):
        called["n"] += 1
        raise AssertionError("a prohibited recipe reached the network")

    monkeypatch.setattr(runner, "_fetched", never_called)
    recipe = recipes.validate(_recipe_dict(source="linkedin",
                                            start_url="https://www.linkedin.com/jobs/search"))
    with pytest.raises(SourceRefused):
        runner.run_recipe(tmp_path, recipe, delay_ms=0)
    assert called["n"] == 0


def test_a_workspace_can_open_one_board_and_only_that_board(tmp_path):
    (tmp_path / ".dossier").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".dossier" / "sources.json").write_text(
        json.dumps({"linkedin": {"policy": "user_supplied", "status": "available"}}), encoding="utf-8")
    assert guard.assert_capture_allowed("https://www.linkedin.com/jobs/view/1", "", tmp_path) == "linkedin"
    with pytest.raises(SourceRefused):
        guard.assert_capture_allowed("https://www.glassdoor.com/job/1", "", tmp_path)


# --------------------------------------------------------------------------
# robots
# --------------------------------------------------------------------------

class FakeHttp:
    def __init__(self, status: int, body: str = ""):
        self.status, self.body = status, body

    def get(self, url):
        class Response:
            status_code = self.status
            text = self.body
        return Response()


def test_robots_disallow_is_a_blocked_before_the_browser(tmp_path, monkeypatch):
    monkeypatch.setattr(guard, "robots_allowed",
                        lambda url, root, **kwargs: {"allowed": False,
                                                     "reason": "disallowed by the test"})
    monkeypatch.setattr(browser, "capture",
                        lambda *a, **k: pytest.fail("the browser started despite robots"))
    with pytest.raises(Blocked):
        runner._fetched(tmp_path, "https://example.com/private/1", source="web", driver="auto",
                        headless=True, timeout_s=5, wait_until="load", selector="",
                        screenshot=False, session=False, robots=True, delay_ms=0,
                        allow_private=False)


def test_robots_5xx_is_treated_as_disallow(tmp_path):
    report = guard.robots_allowed("https://example.com/job/1", tmp_path,
                                 http=FakeHttp(503), cache=False)
    assert report["allowed"] is False
    assert "disallow" in report["reason"]


def test_robots_404_means_no_rules(tmp_path):
    report = guard.robots_allowed("https://example.com/job/1", tmp_path,
                                 http=FakeHttp(404), cache=False)
    assert report["allowed"] is True


def test_robots_path_rules_are_per_path(tmp_path):
    body = "User-agent: *\nDisallow: /private/\n"
    allowed = guard.robots_allowed("https://example.com/jobs/1", tmp_path,
                                  http=FakeHttp(200, body), cache=False)
    blocked = guard.robots_allowed("https://example.com/private/1", tmp_path,
                                  http=FakeHttp(200, body), cache=False)
    assert allowed["allowed"] is True
    assert blocked["allowed"] is False


def test_pacing_waits_the_declared_gap_and_reports_it():
    clock = {"t": 100.0}
    slept: list[float] = []

    def fake_sleep(seconds):
        slept.append(seconds)
        clock["t"] += seconds

    guard._LAST_CALL.clear()
    first = guard.pace("https://example.com/a", 1500, sleep=fake_sleep, clock=lambda: clock["t"])
    second = guard.pace("https://example.com/b", 1500, sleep=fake_sleep, clock=lambda: clock["t"])
    assert first == 0.0
    assert second == 1.5
    assert slept == [1.5]
    guard._LAST_CALL.clear()


# --------------------------------------------------------------------------
# sessions
# --------------------------------------------------------------------------

def _state(**overrides) -> dict:
    cookie = {"name": "session", "value": "abc", "domain": ".example.com", "path": "/",
              "expires": -1, "httpOnly": True, "secure": True, "sameSite": "Lax"}
    cookie.update(overrides)
    return {"cookies": [cookie], "origins": [{"origin": "https://example.com",
                                              "localStorage": [{"name": "k", "value": "v"}]}]}


def test_a_session_keeps_only_cookies_and_origins(tmp_path):
    store = SessionStore(tmp_path)
    payload = {**_state(), "password": "hunter2", "username": "someone", "profile": {"deep": 1}}
    meta = store.save("example", payload, source_url="https://example.com/login")
    written = store.storage_path("example").read_text(encoding="utf-8")
    assert "hunter2" not in written
    assert "username" not in written
    assert meta["dropped_keys"] == ["password", "profile", "username"]
    assert meta["method"] == "user-login"
    assert meta["cookie_count"] == 1


def test_a_session_cannot_be_created_by_an_automated_method(tmp_path):
    store = SessionStore(tmp_path)
    with pytest.raises(Exception) as caught:
        store.save("example", _state(), source_url="https://example.com/login", method="automated")
    assert "user-login" in str(caught.value)


def test_an_empty_browser_state_is_not_a_session(tmp_path):
    store = SessionStore(tmp_path)
    with pytest.raises(Exception):
        store.save("example", {"cookies": [], "origins": []}, source_url="https://example.com/login")
    assert store.status() == []


def test_a_session_is_never_attached_to_another_host(tmp_path):
    store = SessionStore(tmp_path)
    store.save("example", _state(), source_url="https://example.com/login")
    assert store.cookies_for("example", "https://jobs.example.com/1")
    assert store.cookies_for("example", "https://elsewhere.test/1") == []
    with pytest.raises(AuthRequired) as caught:
        store.assert_session_domain("example", "https://elsewhere.test/1")
    assert "does not belong to" in str(caught.value)


def test_an_expired_session_asks_the_user_to_sign_in_again(tmp_path):
    store = SessionStore(tmp_path)
    store.save("example", _state(expires=1000), source_url="https://example.com/login")
    assert store.expired("example") is True
    with pytest.raises(AuthRequired) as caught:
        store.assert_session_domain("example", "https://example.com/jobs")
    assert "expired" in str(caught.value)


def test_a_missing_session_names_the_command_that_creates_one(tmp_path):
    store = SessionStore(tmp_path)
    with pytest.raises(AuthRequired) as caught:
        store.assert_session_domain("example", "https://example.com/jobs")
    assert "dossier scrape login example" in str(caught.value)


def test_a_corrupt_session_file_reads_as_no_session(tmp_path):
    store = SessionStore(tmp_path)
    store.directory.mkdir(parents=True, exist_ok=True)
    store.storage_path("example").write_text("{not json", encoding="utf-8")
    assert store.load("example") is None


def test_a_netscape_export_keeps_the_httponly_session_cookie():
    cookies = parse_netscape_cookies(COOKIE_FILE)
    session = [cookie for cookie in cookies if cookie["name"] == "session"]
    assert session and session[0]["httpOnly"] is True
    assert session[0]["domain"] == ".example.com"
    assert session[0]["expires"] == 1893456000


def test_imported_cookies_are_stored_as_a_session(tmp_path):
    store = SessionStore(tmp_path)
    meta = import_netscape_cookies(store, "example", COOKIE_FILE,
                                   source_url="https://example.com/login")
    assert meta["method"] == "imported-cookies"
    assert meta["cookie_count"] == 2
    assert store.cookies_for("example", "https://example.com/jobs")


def test_an_empty_cookie_file_is_refused(tmp_path):
    with pytest.raises(Exception):
        import_netscape_cookies(SessionStore(tmp_path), "example", "# nothing here\n",
                                source_url="https://example.com/login")


def test_status_never_prints_a_cookie_value(tmp_path):
    store = SessionStore(tmp_path)
    store.save("example", _state(), source_url="https://example.com/login")
    rows = store.status()
    assert rows and rows[0]["cookie_count"] == 1
    assert "abc" not in json.dumps(rows)


# --------------------------------------------------------------------------
# extraction
# --------------------------------------------------------------------------

def test_extraction_drops_chrome_and_keeps_the_requirements():
    html = ("""<html><head><title>Role</title></head><body>
    <nav>Home Jobs</nav><main><h1>Engineer</h1><p>Build.</p>
    <ul><li>Python</li><li>SQL</li></ul><script>tracker()</script></main>
    <footer>Newsletter</footer></body></html>""")
    body = extract.text(html)
    assert "Python" in body and "SQL" in body
    assert "Newsletter" not in body
    assert "Home Jobs" not in body
    assert "tracker" not in body


def test_a_selector_beats_the_default_heuristic():
    html = "<html><body><div id='post'><p>Selected text</p></div><main><p>Other</p></main></body></html>"
    assert extract.text(html, selector="#post").strip() == "Selected text"


def test_a_challenge_is_recognised_from_the_title_or_the_opening_text():
    assert extract.challenge_marker("Just a moment...", "")
    assert extract.challenge_marker("", "Please verify you are human to continue")
    assert extract.challenge_marker("Senior Engineer", "We do not use a captcha") is None


# --------------------------------------------------------------------------
# complete / partial, driven by a fake fetch
# --------------------------------------------------------------------------

def _fake_fetch(pages: dict, calls: list | None = None):
    def fetch(root, url, **kwargs):
        if calls is not None:
            calls.append(url)
        if url not in pages:
            raise AssertionError(f"unexpected fetch of {url}")
        html = pages[url]
        return {"url": url, "final_url": url, "status": 200, "driver": "fake",
                "elapsed_ms": 1, "title": extract.page_title(html),
                "description": "", "text": extract.text(html), "html": html,
                "screenshot": None, "session": {"used": False},
                "robots": {"checked": True, "allowed": True, "reason": "test"},
                "policy": {"source": "web", "policy": "user_supplied"},
                "paced_ms": 0, "notes": []}
    return fetch


LIST_HTML = """<html><body><main>
<article class="card"><h2><a href="https://example.com/job/1">One</a></h2>
<span class="company">Acme</span></article>
</main></body></html>"""
DETAIL_HTML = """<html><head><title>One at Acme</title></head><body><main>
<h1>One</h1><p>Requirements: Python.</p></main></body></html>"""


def test_a_list_that_matches_nothing_is_partial_not_complete(tmp_path, monkeypatch):
    empty = "<html><body><main><p>No roles today.</p></main></body></html>"
    monkeypatch.setattr(runner, "_fetched", _fake_fetch({"https://example.com/jobs": empty}))
    recipe = recipes.validate(_recipe_dict(start_url="https://example.com/jobs"))
    result = runner.run_recipe(tmp_path, recipe, delay_ms=0)
    assert result["complete"] is False
    assert "matched no items" in result["reason"]


def test_a_full_list_run_is_complete_and_writes_provenance(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "_fetched", _fake_fetch({
        "https://example.com/jobs": LIST_HTML,
        "https://example.com/job/1": DETAIL_HTML,
    }))
    recipe = recipes.validate(_recipe_dict(start_url="https://example.com/jobs"))
    result = runner.run_recipe(tmp_path, recipe, delay_ms=0)
    assert result["complete"] is True, result
    assert result["items_captured"] == 1
    posting = tmp_path / result["written"][0]["path"]
    text = posting.read_text(encoding="utf-8")
    assert "url: https://example.com/job/1" in text
    assert "driver: fake" in text
    assert "Requirements: Python." in text
    provenance = tmp_path / result["written"][0]["provenance"]
    assert json.loads(provenance.read_text(encoding="utf-8"))["sha256"]


TWO_CARDS_HTML = """<html><body><main>
<article class="card"><h2><a href="https://example.com/job/1">One</a></h2>
<span class="company">Acme</span></article>
<article class="card"><h2><a href="https://example.com/job/2">Two</a></h2>
<span class="company">Beta</span></article>
</main></body></html>"""


def test_a_limit_makes_the_run_partial(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "_fetched", _fake_fetch({
        "https://example.com/jobs": TWO_CARDS_HTML,
        "https://example.com/job/1": DETAIL_HTML,
    }))
    recipe = recipes.validate(_recipe_dict(start_url="https://example.com/jobs"))
    result = runner.run_recipe(tmp_path, recipe, limit=1, delay_ms=0)
    assert result["complete"] is False
    assert result["truncated"] is True
    assert result["items"] == 1
    assert "limit 1 of 2" in result["reason"]


def test_one_failed_item_makes_the_run_partial_even_when_others_land(tmp_path, monkeypatch):
    base = _fake_fetch({
        "https://example.com/jobs": LIST_HTML,
        "https://example.com/job/1": DETAIL_HTML,
    })

    def flaky(root, url, **kwargs):
        if url.endswith("/job/1"):
            raise Blocked("403 from the detail page")
        return base(root, url, **kwargs)

    monkeypatch.setattr(runner, "_fetched", flaky)
    recipe = recipes.validate(_recipe_dict(start_url="https://example.com/jobs"))
    result = runner.run_recipe(tmp_path, recipe, delay_ms=0)
    assert result["complete"] is False
    assert result["failures"][0]["stage"] == "detail"


def test_a_transient_failure_is_retried_and_a_block_is_not(tmp_path, monkeypatch):
    calls: list[str] = []
    good = _fake_fetch({"https://example.com/jobs": LIST_HTML,
                        "https://example.com/job/1": DETAIL_HTML}, calls)

    def sometimes(root, url, **kwargs):
        if url.endswith("/jobs") and calls.count(url) < 1:
            calls.append(url)
            raise Transient("connection reset")
        return good(root, url, **kwargs)

    monkeypatch.setattr(runner, "_fetched", sometimes)
    recipe = recipes.validate(_recipe_dict(start_url="https://example.com/jobs",
                                           limits={"max_items": 1, "delay_ms": 0,
                                                   "timeout_s": 10, "retries": 1}))
    result = runner.run_recipe(tmp_path, recipe, delay_ms=0)
    assert result["complete"] is True
    assert calls.count("https://example.com/jobs") == 2

    blocked_calls: list[str] = []

    def always_blocked(root, url, **kwargs):
        blocked_calls.append(url)
        raise Blocked("403")

    monkeypatch.setattr(runner, "_fetched", always_blocked)
    result = runner.run_recipe(tmp_path, recipe, delay_ms=0)
    assert result["complete"] is False
    assert len(blocked_calls) == 1  # a refusal is not retried


def test_a_duplicate_is_skipped_and_a_refresh_trashes_the_old_copy(tmp_path, monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr(runner, "_fetched", _fake_fetch({
        "https://example.com/jobs": LIST_HTML,
        "https://example.com/job/1": DETAIL_HTML,
    }, calls))
    recipe = recipes.validate(_recipe_dict(start_url="https://example.com/jobs"))
    first = runner.run_recipe(tmp_path, recipe, delay_ms=0)
    assert first["items_captured"] == 1
    second = runner.run_recipe(tmp_path, recipe, delay_ms=0)
    assert second["items_captured"] == 0
    assert second["duplicates"][0]["duplicate"] is True
    refreshed = runner.run_recipe(tmp_path, recipe, delay_ms=0, refresh=True)
    assert refreshed["items_captured"] == 1
    trash = list((tmp_path / ".dossier" / "trash").rglob("job-posting-*.md"))
    assert trash, "an overwrite did not leave a copy in .dossier/trash/"


def test_a_single_page_recipe_archives_the_start_url(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "_fetched", _fake_fetch({"https://example.com/job/1": DETAIL_HTML}))
    recipe = recipes.validate({"id": "one", "source": "web",
                               "start_url": "https://example.com/job/1"})
    result = runner.run_recipe(tmp_path, recipe, delay_ms=0)
    assert result["complete"] is True
    assert (tmp_path / result["written"][0]["path"]).is_file()


def test_the_run_log_records_a_partial_run(tmp_path, monkeypatch):
    good = _fake_fetch({"https://example.com/jobs": LIST_HTML,
                        "https://example.com/job/1": DETAIL_HTML})

    def detail_blocked(root, url, **kwargs):
        if url.endswith("/job/1"):
            raise Blocked("403 on the detail page")
        return good(root, url, **kwargs)

    monkeypatch.setattr(runner, "_fetched", detail_blocked)
    recipe = recipes.validate(_recipe_dict(start_url="https://example.com/jobs"))
    runner.run_recipe(tmp_path, recipe, delay_ms=0)
    log = (tmp_path / runner.RUN_LOG).read_text(encoding="utf-8").splitlines()
    assert log and json.loads(log[-1])["complete"] is False


def test_status_reports_recipes_sessions_and_due(tmp_path, monkeypatch):
    _write_recipe(tmp_path, _recipe_dict(id="weekly", cadence_hours=24))
    SessionStore(tmp_path).save("example", _state(), source_url="https://example.com/login")
    report = runner.status(tmp_path)
    row = next(item for item in report["recipes"] if item["id"] == "weekly")
    assert row["due"] is True and "never captured" in row["reason"]
    assert report["due"] == ["weekly"]
    assert report["sessions"][0]["source"] == "example"
    assert set(report["engines"]) == {"obscura", "playwright"}
    assert "partial" in report["rule"]


def test_due_disappears_once_a_run_is_logged(tmp_path, monkeypatch):
    _write_recipe(tmp_path, _recipe_dict(id="weekly", cadence_hours=24))
    monkeypatch.setattr(runner, "_fetched", _fake_fetch({
        "https://example.com/jobs": LIST_HTML,
        "https://example.com/job/1": DETAIL_HTML,
    }))
    found, _errors = recipes.discover(tmp_path)
    recipe = next(item for item in found if item.id == "weekly")
    runner.run_recipe(tmp_path, recipe, delay_ms=0)
    assert runner.due_recipes(tmp_path) == []


# --------------------------------------------------------------------------
# the real engines, against the fixture site
# --------------------------------------------------------------------------

@pytest.fixture
def site():
    with FixtureSite() as running:
        yield running


def _has(engine: str) -> bool:
    return bool(browser.available()[engine]["available"])


@pytest.fixture
def public_engine():
    if not _has("obscura"):
        pytest.skip("obscura is not installed; the public-capture path is unverified here")
    return "obscura"


@pytest.fixture
def session_engine():
    if not _has("playwright"):
        pytest.skip("Playwright is not installed (`uv sync --extra browser`)")
    return "playwright"


def _cookies_for(host: str, name: str = "session", value: str = "ok") -> str:
    return (f"# Netscape HTTP Cookie File\n{host}\tFALSE\t/\tFALSE\t0\t{name}\t{value}\n")


def test_obscura_archives_a_public_page_without_its_chrome(tmp_path, site, public_engine):
    result = runner.capture_url(tmp_path, f"{site.base}/job/1", driver="obscura",
                                screenshot=False, delay_ms=0)
    assert result["complete"] is True, result
    posting = (tmp_path / result["posting"]).read_text(encoding="utf-8")
    assert "Python" in posting and "Clear writing" in posting
    assert "Newsletter" not in posting
    assert f"url: {site.base}/job/1" in posting
    assert "driver: obscura" in posting


def test_a_second_capture_of_one_url_is_a_duplicate(tmp_path, site, public_engine):
    first = runner.capture_url(tmp_path, f"{site.base}/job/1", driver="obscura",
                               screenshot=False, delay_ms=0)
    second = runner.capture_url(tmp_path, f"{site.base}/job/1", driver="obscura",
                                screenshot=False, delay_ms=0)
    assert first["written"] is True
    assert second["duplicate"] is True


def test_playwright_replays_a_saved_session_for_cookie_gated_content(tmp_path, site, session_engine):
    host = urlparse(site.base).hostname
    import_netscape_cookies(SessionStore(tmp_path), "fixture",
                            _cookies_for(host), source_url=f"{site.base}/login")
    result = runner.capture_url(tmp_path, f"{site.base}/private", source="fixture",
                                driver="playwright", session=True, screenshot=False,
                                delay_ms=0)
    assert result["complete"] is True, result
    assert result["session"]["used"] is True
    assert "Insider Role" in (tmp_path / result["posting"]).read_text(encoding="utf-8")


def test_a_missing_session_on_a_gated_page_is_a_named_blocker(tmp_path, site, session_engine):
    result = runner.capture_url(tmp_path, f"{site.base}/private", source="fixture",
                                driver="playwright", session=True, screenshot=False,
                                delay_ms=0)
    assert result["complete"] is False
    assert "AuthRequired" in result["reason"]
    assert "dossier scrape login fixture" in result["reason"]


def test_playwright_renders_javascript_before_extraction(tmp_path, site, session_engine):
    # `#slot` exists in the served HTML immediately, so waiting for it would prove
    # nothing. Waiting for the text the timer writes is the actual claim: the
    # engine ran the page's JavaScript before the text was taken.
    result = runner.capture_url(tmp_path, f"{site.base}/dynamic", driver="playwright",
                                selector='#slot:has-text("Rendered by JavaScript")',
                                screenshot=False, delay_ms=0)
    assert result["complete"] is True, result
    assert "Rendered by JavaScript" in (tmp_path / result["posting"]).read_text(encoding="utf-8")


def test_a_challenge_is_reported_when_the_policy_blocks(tmp_path, site, session_engine):
    result = runner.capture_url(tmp_path, f"{site.base}/challenge", driver="playwright",
                                screenshot=False, delay_ms=0, challenge="block")
    assert result["complete"] is False
    assert "ChallengeDetected" in result["reason"] or "ChallengeBlocked" in result["reason"]
    assert not list(tmp_path.glob("job-posting-*.md"))


def test_the_auto_policy_tries_each_phase_and_records_the_trail(tmp_path, site, session_engine):
    """`auto` is not silent: it escalates through the phases and, when the page never
    becomes readable, reports every attempt with the policy that allowed it."""
    result = runner.capture_url(tmp_path, f"{site.base}/challenge", driver="playwright",
                                screenshot=False, delay_ms=0, challenge="auto",
                                await_clear_s=1)
    assert result["complete"] is False
    record = result["challenge"]
    assert record["policy"] == "auto"
    phases = [attempt["phase"] for attempt in record["attempts"]]
    assert phases[0] == "plain" and "stealth+wait" in phases


def test_a_challenge_that_clears_itself_is_captured_not_blocked(tmp_path, site, session_engine):
    """Patience is part of the answer: a page that stops being an interstitial within
    the wait window is captured, with the wait recorded."""
    result = runner.capture_url(tmp_path, f"{site.base}/challenge-clears", driver="playwright",
                                screenshot=False, delay_ms=0, challenge="await",
                                await_clear_s=5)
    assert result["complete"] is True, result
    assert result["challenge"]["waited_s"] >= 0
    assert "Clear of the check" in (tmp_path / result["posting"]).read_text(encoding="utf-8")


def test_robots_is_enforced_against_a_real_origin(tmp_path, site, public_engine):
    result = runner.capture_url(tmp_path, f"{site.base}/blocked/page", driver="obscura",
                                screenshot=False, delay_ms=0)
    assert result["complete"] is False
    assert "robots" in result["reason"].casefold()
    assert "/blocked/page" not in site.requests  # refused before the origin saw it


def test_a_list_recipe_walks_next_link_pagination(tmp_path, site, public_engine):
    result = runner.run_recipe(
        tmp_path, recipes.Recipe(
            id="fixture", source="fixture", start_url=f"{site.base}/",
            list={"item": "article.card", "link": "h2 a", "title": "h2",
                  "company": ".company", "location": ".location"},
            detail={"content": "main", "remove": ["footer"]},
            pagination={"mode": "next-link", "selector": "a[rel=next]", "max_pages": 3},
            limits={"max_items": 10, "delay_ms": 0, "timeout_s": 20, "retries": 0},
        ), driver="obscura", delay_ms=0)
    assert result["complete"] is True, result
    assert result["items"] == 3
    titles = sorted(entry["title"] for entry in result["written"])
    assert titles == ["Data Analyst", "Platform Engineer", "Senior Engineer"]


def test_the_api_capture_route_refuses_a_prohibited_board(tmp_path):
    from fastapi.testclient import TestClient
    from dossier.api.app import create_app
    from dossier.config import AppConfig

    app = create_app(AppConfig.create(tmp_path, token="scrape-token"))
    client = TestClient(app, raise_server_exceptions=False)
    headers = {"Authorization": "Bearer scrape-token"}
    response = client.post("/api/scrape/capture",
                           json={"url": "https://www.linkedin.com/jobs/view/1"}, headers=headers)
    assert response.status_code == 403
    assert "prohibited" in response.text
    assert client.get("/api/scrape", headers=headers).status_code == 200
    assert client.get("/api/scrape/recipes", headers=headers).status_code == 200


# -- the sign-in path (the shipped function, not a stand-in) ----------------

def test_sign_in_waits_for_the_selector_and_saves_the_cookie(tmp_path, site, session_engine):
    from dossier.scrape.session import SessionStore
    """`PlaywrightDriver.sign_in` is what `dossier scrape login` runs. The fixture's
    `/auto-login` signs itself in and *then* reveals the element the wait polls, so
    this exercises the real wait, the real storage_state and the real store."""
    store = SessionStore(tmp_path)
    meta = browser.PlaywrightDriver().sign_in(
        url=f"{site.base}/auto-login", store=store, source="fixture",
        success_selector="#signed-in", timeout_s=20, headless=True)
    assert meta["method"] == "user-login"
    assert meta["cookie_count"] >= 1
    assert store.cookies_for("fixture", f"{site.base}/private")
    assert store.assert_session_domain("fixture", f"{site.base}/private")


def test_sign_in_saves_nothing_when_the_selector_never_appears(tmp_path, site, session_engine):
    store = SessionStore(tmp_path)
    with pytest.raises(AuthRequired) as caught:
        browser.PlaywrightDriver().sign_in(
            url=f"{site.base}/auto-login", store=store, source="fixture",
            success_selector="#never-appears", timeout_s=2, headless=True)
    assert "Nothing was saved" in str(caught.value)
    assert store.status() == []


# -- relevance filtering ---------------------------------------------------

def _identity(root):
    from dossier.engine import identity
    identity.save_answers(root, {
        "target_roles": "Software Engineer Intern", "seniority": "student/intern",
        "employment": "internship", "location": "Hamilton", "right_to_work": "citizen",
        "must_have": "Python", "deal_breakers": "commission only", "salary_floor": 60000})


def test_a_capture_can_refuse_an_irrelevant_page_and_says_it_did(tmp_path, monkeypatch):
    _identity(tmp_path)
    monkeypatch.setattr(runner, "_fetched", _fake_fetch({"https://example.com/job/1": DETAIL_HTML}))
    result = runner.capture_url(tmp_path, "https://example.com/job/1", min_match=90,
                                delay_ms=0)
    assert result["complete"] is False
    assert result["filtered"] is True
    assert "below the floor 90" in result["reason"]
    assert result["match"]["score"] < 90
    assert not list(tmp_path.glob("job-posting-*.md")), "a filtered page must not be archived"
    log = (tmp_path / runner.RUN_LOG).read_text(encoding="utf-8").splitlines()
    assert json.loads(log[-1])["filtered"] is True


def test_an_archived_posting_carries_its_match_band(tmp_path, monkeypatch):
    _identity(tmp_path)
    monkeypatch.setattr(runner, "_fetched", _fake_fetch({"https://example.com/job/1": DETAIL_HTML}))
    result = runner.capture_url(tmp_path, "https://example.com/job/1", delay_ms=0)
    assert result["filtered"] is False
    text = (tmp_path / result["posting"]).read_text(encoding="utf-8")
    assert "match: " in text
    assert result["match"]["band"] in {"strong", "possible", "unlikely"}


def test_a_recipe_run_records_filtered_items_without_counting_them_as_failures(tmp_path, monkeypatch):
    _identity(tmp_path)
    job_html = """<html><head><title>Commission only sales</title></head><body><main>
    <h1>Commission only sales</h1><p>Door-to-door, commission only, no base.</p></main></body></html>"""
    monkeypatch.setattr(runner, "_fetched", _fake_fetch({
        "https://example.com/jobs": LIST_HTML,
        "https://example.com/job/1": job_html,
    }))
    recipe = recipes.validate(_recipe_dict(start_url="https://example.com/jobs",
                                           limits={"max_items": 5, "delay_ms": 0,
                                                   "timeout_s": 10, "retries": 0,
                                                   "min_match": 1}))
    result = runner.run_recipe(tmp_path, recipe, delay_ms=0)
    assert result["filtered"] and result["filtered"][0]["score"] <= 25
    assert result["failures"] == []


def test_a_shim_argument_carrying_a_cmd_metacharacter_is_refused(tmp_path):
    """`cmd /c` re-parses its command line, so `&` in a URL would fork a command.

    Measured: the list form truncates the URL at the `&`. That is the injection, so an
    argument carrying a cmd metacharacter is refused on the shim path only; the `.exe`
    path passes argv untouched.
    """
    from dossier.scrape import browser

    shim = tmp_path / "obscura.cmd"
    shim.write_text("@echo off\n", encoding="ascii")
    with pytest.raises(RuntimeError, match="re-parse"):
        browser._obscura_command(shim, ["fetch", "http://127.0.0.1:1/job/1?a=1&calc"])

    benign = browser._obscura_command(shim, ["fetch", "http://127.0.0.1:1/job/1"])
    assert benign[:3] == ["cmd", "/c", str(shim)]

    exe = tmp_path / "obscura.exe"
    assert browser._obscura_command(exe, ["fetch", "http://x/?a=1&b=2"]) == [
        str(exe), "fetch", "http://x/?a=1&b=2"]
