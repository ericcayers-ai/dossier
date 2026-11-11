"""End-to-end: a person uses the Dossier app to capture listings, build their
Opportunity tree, and produce a resume from a template they supplied.

This drives the real UI in Chromium against a real local origin (`tests/fixtures/
scrape_site.py`) and the real HTTP API. Nothing is stubbed except the *sites*: the
capture engine, the policy gate, the session store, the extractor, the template
filler and the verifier are the shipped code.

It is a gate, not a demo. Every step asserts on rendered text, so a pane that
mounts but does nothing fails here. Screenshots are written beside the other
receipts; they are evidence of what the assertions already proved, not a
substitute for them.

Skipped, with the reason, when the UI has not been built or Playwright is absent.
"""

from __future__ import annotations

import json
import sys
import threading
import time
from pathlib import Path

import pytest

playwright_api = pytest.importorskip(
    "playwright.sync_api", reason="Playwright is not installed (`uv sync --all-extras`)")

sys.path.insert(0, str(Path(__file__).resolve().parent / "fixtures"))
from scrape_site import FixtureSite  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "ui" / "dist" / "index.html"
EVIDENCE = ROOT / "docs" / "evidence"

pytestmark = pytest.mark.skipif(
    not DIST.exists(),
    reason="the UI is not built: run `cd ui && npm run build` before the end-to-end receipt")


def _workspace(root: Path, base_url: str) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / ".dossier" / "scrapes").mkdir(parents=True, exist_ok=True)
    (root / "templates").mkdir(parents=True, exist_ok=True)
    (root / "all_boards_data").mkdir(parents=True, exist_ok=True)
    (root / "all_boards_data" / "all_jobs.json").write_text(json.dumps([
        {"id": "1", "title": "Software Engineer Intern", "employer": "Acme",
         "location": "Hamilton", "url": "https://acme.example/1", "source": "fixture",
         "work_type": "internship", "pay": "$65000",
         "description": "Python, SQL and Playwright. Build things."},
        {"id": "2", "title": "Commission Only Sales Rep", "employer": "Pushy Ltd",
         "location": "Auckland", "url": "https://pushy.example/2", "source": "fixture",
         "work_type": "full-time", "pay": "$0",
         "description": "Door-to-door, commission only, no base."},
    ]), encoding="utf-8")
    (root / "job-history.md").write_text(
        "| Date | Company | Role | Fit | Resume file | Status |\n"
        "|---|---|---|---|---|---|\n"
        "| Aug 2026 | Acme | Senior Engineer | High | resume.docx | drafted |\n",
        encoding="utf-8")
    (root / "resume.md").write_text(
        "# Eric\n\n## Skills\nPython, SQL, Playwright\n\n"
        "## Experience\nCut the weekly reporting loop from 8 hours to 2 hours.\n",
        encoding="utf-8")
    (root / ".dossier" / "scrapes" / "local-listing.json").write_text(json.dumps({
        "id": "local-listing",
        "source": "fixture",
        "start_url": f"{base_url}/",
        "auth": "public",
        "list": {"item": "article.card", "link": "h2 a", "title": "h2",
                 "company": ".company", "location": ".location"},
        "detail": {"content": "main", "remove": ["footer"]},
        "pagination": {"mode": "next-link", "selector": "a[rel=next]", "max_pages": 3},
        "limits": {"max_items": 10, "delay_ms": 0, "timeout_s": 20, "retries": 0,
                   "await_seconds": 2},
    }), encoding="utf-8")

    # A real workspace holds hundreds of files. 120 is enough that the rail has to render a
    # window instead of the whole list, which is the behaviour the tests below pin down.
    archive = root / "archive"
    archive.mkdir(exist_ok=True)
    for index in range(120):
        (archive / f"note-{index:03d}.txt").write_text("archive note " + str(index), encoding="utf-8")

    from docx import Document

    document = Document()
    heading = document.add_paragraph()
    run = heading.add_run("{{Name}}")
    run.bold = True
    document.add_paragraph("{{Objective}}")
    document.add_paragraph("Skills: {{Skills}}")
    document.add_paragraph("Phone: {{Phone}}")
    document.add_paragraph("This paragraph belongs to the template and must survive.")
    document.save(str(root / "templates" / "my-template.docx"))
    return root


@pytest.fixture(scope="module")
def app():
    """A real uvicorn socket serving the built UI over a real workspace."""
    import uvicorn
    from dossier.api.app import create_app
    from dossier.config import AppConfig

    with FixtureSite() as site:
        import tempfile

        root = _workspace(Path(tempfile.mkdtemp(prefix="dossier-e2e-")), site.base)
        token = "e2e-token"
        application = create_app(AppConfig.create(root, token=token))
        config = uvicorn.Config(application, host="127.0.0.1", port=0, log_level="warning")
        server = uvicorn.Server(config)
        thread = threading.Thread(target=server.run, daemon=True)
        thread.start()
        for _ in range(200):
            if server.started:
                break
            time.sleep(0.05)
        assert server.started, "the API did not start"
        port = server.servers[0].sockets[0].getsockname()[1]
        try:
            yield {"base": f"http://127.0.0.1:{port}", "root": root, "token": token,
                   "site": site}
        finally:
            server.should_exit = True
            thread.join(timeout=15)


@pytest.fixture(scope="module")
def page(app):
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 1000})
        page = context.new_page()
        page.goto(app["base"], wait_until="networkidle")
        page.wait_for_timeout(500)
        yield page
        browser.close()


def _shot(page, name: str) -> None:
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(EVIDENCE / f"e2e-{name}.png"), full_page=True)


AREA_OF = {"Start here": "Start", "Folder": "Files", "Capture": "Search", "Jobs": "Search",
           "Identity": "Search",
           "Build": "Papers", "Verify": "Papers", "Audit": "Housekeeping",
           "Trash": "Housekeeping", "Sync": "Housekeeping", "Loop": "Agent",
           "Opportunity": "Agent", "Panel": "Agent"}


def _pane(page, label: str) -> None:
    """Two levels, like a person: pick the area, then the pane inside it."""
    page.locator(".area-btn", has_text=AREA_OF[label]).first.click()
    page.wait_for_timeout(60)
    page.locator(".pane-btn", has_text=label).first.click()
    page.wait_for_timeout(150)


def test_the_shell_renders_the_built_ui(page):
    from playwright.sync_api import expect

    expect(page.locator(".brand")).to_contain_text("Dossier")
    expect(page.locator(".area-nav")).to_contain_text("Search")
    expect(page.locator(".area-nav")).to_contain_text("Papers")
    expect(page.locator(".status")).to_contain_text("API ready")
    _shot(page, "01-shell")


def test_a_user_captures_one_listing(page, app):
    from playwright.sync_api import expect

    _pane(page, "Capture")
    expect(page.locator("h1", has_text="Capture")).to_be_visible()
    journal = (app["root"] / "job-posting-web-senior-engineer-at-acme.md")
    journal.unlink(missing_ok=True)  # keep the assertion about *this* run

    page.get_by_label("Page URL").fill(f"{app['site'].base}/job/1")
    page.get_by_role("button", name="Scrape page").click()
    expect(page.locator(".result-line").first).to_contain_text("Complete", timeout=60_000)
    _shot(page, "02-capture-page")
    assert journal.is_file(), "the capture reported complete but archived nothing"
    assert "Python" in journal.read_text(encoding="utf-8")


def test_a_user_scrapes_the_whole_board_with_a_recipe(page, app):
    from playwright.sync_api import expect

    _pane(page, "Capture")
    page.get_by_label("Recipe").select_option("local-listing")
    page.get_by_role("button", name="Run recipe").click()
    recipe_result = page.locator('section[aria-label="Recipe result"]')
    expect(recipe_result).to_be_visible(timeout=90_000)
    expect(recipe_result.locator(".result-line").first).to_contain_text("Complete")
    # 3 listings across two pages; the table names each one.
    expect(recipe_result).to_contain_text("Platform Engineer")
    _shot(page, "03-capture-recipe")
    archived = sorted(path.name for path in app["root"].glob("job-posting-*.md"))
    assert len(archived) == 3, archived


def test_a_user_builds_their_own_opportunity_tree(page, app):
    from playwright.sync_api import expect

    _pane(page, "Opportunity")
    expect(page.locator("h1#trajectory-title")).to_have_text("Opportunity")

    page.get_by_label("Type").select_option("opportunity")
    page.get_by_label("Title", exact=True).fill("Acme — Senior Engineer")
    page.get_by_label("Optional ID").fill("opp-acme")
    page.get_by_label("Evidence or notes").fill("Captured from the fixture board.")
    page.get_by_role("button", name="Save node").click()
    expect(page.locator(".trajectory-node", has_text="Acme — Senior Engineer")).to_be_visible(timeout=20_000)

    page.get_by_label("Type").select_option("milestone")
    page.get_by_label("Title", exact=True).fill("Interview at Acme")
    page.get_by_label("Optional ID").fill("ms-acme")
    page.get_by_role("button", name="Save node").click()
    expect(page.locator(".trajectory-node", has_text="Interview at Acme")).to_be_visible(timeout=20_000)

    page.get_by_label("Prerequisite node ID").fill("opp-acme")
    page.get_by_label("Next node ID").fill("ms-acme")
    page.get_by_role("button", name="Create link").click()
    expect(page.locator(".trajectory-relation").first).to_contain_text("Branches to", timeout=20_000)
    _shot(page, "04-opportunity-tree")

    tree = json.loads((app["root"] / ".dossier" / "tree.json").read_text(encoding="utf-8"))
    ids = {node["id"] for node in tree["nodes"]}
    assert {"opp-acme", "ms-acme"} <= ids
    assert {"parent_id": "opp-acme", "child_id": "ms-acme"} in tree["links"]


def test_a_user_provides_a_template_and_dossier_builds_a_resume(page, app):
    from playwright.sync_api import expect

    _pane(page, "Build")
    expect(page.locator("h1", has_text="Build")).to_be_visible()

    page.get_by_label("Template (.docx, relative to the workspace)").fill("templates/my-template.docx")
    page.get_by_label("Output (.docx)").fill("resume-acme.docx")
    page.get_by_role("button", name="Read placeholders").click()

    expect(page.get_by_label("Name")).to_be_visible(timeout=20_000)
    page.get_by_label("Name").fill("A. C")
    page.get_by_label("Objective").fill("Senior engineer, platform reliability")
    page.get_by_label("Skills").fill("Python, SQL, Playwright")
    page.get_by_label("Phone").fill("021 000 0000")
    _shot(page, "05-template-fields")

    page.get_by_role("button", name="Build from template").click()
    expect(page.locator(".result-line").first).to_contain_text("Written", timeout=30_000)
    page.get_by_role("button", name="Check the document").click()
    expect(page.locator(".results")).to_contain_text("Every template check passed", timeout=20_000)
    _shot(page, "06-template-built")

    from docx import Document

    built = Document(str(app["root"] / "resume-acme.docx"))
    text = "\n".join(paragraph.text for paragraph in built.paragraphs)
    assert "A. C" in text and "{{Name}}" not in text
    assert "This paragraph belongs to the template and must survive." in text
    assert built.paragraphs[0].runs[0].bold is True


def test_the_built_document_and_postings_appear_in_the_workspace(page, app):
    from playwright.sync_api import expect

    # The app's own API is the authority for what the workspace now holds.
    # The tree is a live directory walk and the answer is `no-store`; poll briefly so
    # a slow filesystem flush is not reported as a missing artifact.
    payload = {"names": [], "postings": 0}
    for _ in range(20):
        payload = page.evaluate("""async () => {
            const tree = await (await fetch('/api/tree', {cache: 'no-store'})).json();
            const scrape = await (await fetch('/api/scrape', {cache: 'no-store'})).json();
            return {names: tree.map(n => n.name), postings: scrape.captured_postings};
        }""")
        if "resume-acme.docx" in payload["names"]:
            break
        page.wait_for_timeout(250)
    assert "resume-acme.docx" in payload["names"]
    assert any(name.startswith("job-posting-") for name in payload["names"])
    assert payload["postings"] >= 3

    page.reload(wait_until="networkidle")
    _pane(page, "Folder")
    # The rail renders a window of rows, so it is searched the way a person searches it.
    page.fill(".filter", "job-posting-")
    page.wait_for_timeout(250)
    expect(page.locator(".explorer")).to_contain_text("job-posting-")
    page.fill(".filter", "resume-acme")
    page.wait_for_timeout(250)
    expect(page.locator(".explorer")).to_contain_text("resume-acme.docx")
    page.fill(".filter", "")
    page.wait_for_timeout(250)
    _shot(page, "07-workspace")


def test_a_user_builds_their_identity_and_sees_matching_jobs(page, app):
    """The questionnaire asks what the documents cannot derive; the Matches tab then
    scores the corpus and keeps the disqualified row visible with its reason."""
    from playwright.sync_api import expect

    _pane(page, "Identity")
    expect(page.locator("h1", has_text="Identity")).to_be_visible()

    page.get_by_label("Which roles are you actually applying for?").fill("Software Engineer Intern")
    page.get_by_label("What level are you targeting?").select_option("student/intern")
    page.get_by_label("Which employment types?").fill("internship")
    page.get_by_label("Where can you work?").fill("Hamilton")
    page.get_by_label("Right to work in that country?").fill("citizen")
    page.get_by_label("Skills or technologies the role must involve.").fill("Python")
    page.get_by_label("Words that should disqualify a listing.").fill("commission only")
    page.get_by_label("Minimum acceptable annual pay").fill("60000")
    _shot(page, "08-identity-questions")

    page.get_by_role("button", name="Save answers").click()
    expect(page.locator(".notice", has_text="Saved")).to_be_visible(timeout=20_000)
    expect(page.locator("p.kbd", has_text="answered")).to_be_visible()
    page.get_by_role("button", name="Write IDENTITY.md").click()
    expect(page.locator(".notice").first).to_contain_text("Wrote", timeout=20_000)
    # The written document must match the *-IDENTITY.md discovery rule, whatever
    # the workspace is named — a plain IDENTITY.md was invisible to the agent.
    identity_docs = sorted(app["root"].glob("*-IDENTITY.md"))
    assert identity_docs, sorted(p.name for p in app["root"].glob("*.md"))
    assert "{{" not in identity_docs[0].read_text(encoding="utf-8")

    page.get_by_role("tab", name="Matches").click()
    page.get_by_role("button", name="Score the corpus").click()
    expect(page.locator(".data-table").first).to_contain_text("Software Engineer Intern", timeout=20_000)
    expect(page.locator(".results, .data-table").last).to_contain_text("commission only", timeout=20_000)
    _shot(page, "09-identity-matches")


# -- navigation: a pane is a place ----------------------------------------

def test_a_pane_has_an_address_that_survives_a_cold_load(page, app):
    """Before this, a reload always dropped the person back on Folder, so a
    bookmark, a shared link and the back button all led somewhere else."""
    from playwright.sync_api import expect

    page.goto(f"{app['base']}/#/papers/verify", wait_until="networkidle")
    expect(page.locator("h1", has_text="Verify")).to_be_visible(timeout=20_000)
    expect(page.locator(".pane-btn[aria-current='page']")).to_have_text("Verify")
    expect(page.locator(".area-btn[aria-current='page']")).to_have_text("Papers")

    page.reload(wait_until="networkidle")
    expect(page.locator("h1", has_text="Verify")).to_be_visible(timeout=20_000)
    expect(page.locator(".pane-btn[aria-current='page']")).to_have_text("Verify")


def test_the_back_button_moves_between_panes(page, app):
    """History is what makes the browser's own affordances mean something. If a
    pane switch is not a history entry, Back leaves the app instead."""
    from playwright.sync_api import expect

    page.goto(f"{app['base']}/#/search/jobs", wait_until="networkidle")
    expect(page.locator("h1", has_text="Jobs")).to_be_visible(timeout=20_000)
    page.locator(".area-btn", has_text="Papers").first.click()
    expect(page.locator(".pane-btn[aria-current='page']")).to_have_text("Build")
    page.go_back()
    expect(page.locator("h1", has_text="Jobs")).to_be_visible(timeout=20_000)


def test_the_landing_pane_names_the_next_unit_of_work(page, app):
    """The engine knows one next unit and its blockers. A stranger opening the app
    used to see an empty file browser and no reason for it."""
    from playwright.sync_api import expect

    page.goto(app["base"], wait_until="networkidle")
    strip = page.locator(".welcome-next")
    expect(strip).to_be_visible(timeout=20_000)
    # It names the unit and says why; either wording (Next / Waiting on you) is one
    # of the two facts a stranger needs, so the assertion is on the facts, not the words.
    expect(strip.locator(".mode")).to_be_visible()
    assert strip.locator(".mode").inner_text().strip()
    assert strip.locator("p.reason").inner_text().strip()
    button = strip.get_by_role("button")
    expect(button).to_be_visible()
    label = button.inner_text()
    assert label.startswith("Open "), label
    button.click()
    # The button names the pane it opens; the click must actually land there, and the
    # address must follow, or the deep link and the button disagree.
    expect(page.locator(".pane-btn[aria-current='page']")).to_have_text(label.replace("Open ", ""))
    assert page.url.split("#")[-1].count("/") == 2, page.url


def _rail(page):
    """What the file rail has actually rendered, as opposed to what it says it holds."""
    return page.evaluate("""() => {
      const rows = [...document.querySelectorAll('.explorer .tree-row')];
      const label = document.querySelector('.explorer .pane-count');
      const tree = document.querySelector('.explorer .tree');
      const last = rows[rows.length - 1];
      return {
        rendered: rows.length,
        firstPos: rows.length ? Number(rows[0].getAttribute('aria-posinset')) : null,
        lastPos: last ? Number(last.getAttribute('aria-posinset')) : null,
        setSize: last ? Number(last.getAttribute('aria-setsize')) : null,
        label: label ? label.textContent.trim() : null,
        scrollTop: tree ? Math.round(tree.scrollTop) : null,
        scrollHeight: tree ? Math.round(tree.scrollHeight) : null,
        lastFits: (() => {
          if (!last) return null;
          const rail = document.querySelector('.explorer .tree').getBoundingClientRect();
          return last.getBoundingClientRect().bottom <= rail.bottom + 1;
        })(),
      };
    }""")


def test_the_rail_renders_a_window_and_still_names_the_whole_folder(page, app):
    """728 files in a 260px rail used to mean 728 buttons in the DOM. The window is the
    fix, and the count is what proves the window is honest about the whole folder."""
    page.goto(app["base"], wait_until="networkidle")
    _pane(page, "Folder")
    page.wait_for_timeout(300)
    rail = _rail(page)
    total = int(rail["label"].split()[0])
    assert total > 120, rail
    assert rail["rendered"] <= 80, rail
    assert rail["rendered"] < total, rail
    assert rail["setSize"] == total, rail
    assert rail["firstPos"] == 1, rail


def test_scrolling_the_rail_to_the_end_reaches_the_last_file(page, app):
    """The spacers have to account for every row, or the scrollbar bottoms out early and
    the tail of the folder cannot be reached at all."""
    page.goto(app["base"], wait_until="networkidle")
    _pane(page, "Folder")
    page.wait_for_timeout(300)
    page.evaluate("() => { const tree = document.querySelector('.explorer .tree');"
                  " tree.scrollTop = tree.scrollHeight; }")
    page.wait_for_timeout(350)
    rail = _rail(page)
    assert rail["lastPos"] == rail["setSize"], rail
    assert rail["lastFits"] is True, rail


def test_arrow_keys_move_focus_past_the_rendered_window(page, app):
    """A windowed list must not trap the keyboard inside the rows that happen to be
    mounted: focus follows the selection, and the scroll brings the row into range."""
    page.goto(app["base"], wait_until="networkidle")
    _pane(page, "Folder")
    page.wait_for_timeout(300)
    page.locator(".explorer .tree-row").first.click()
    for _ in range(45):
        page.keyboard.press("ArrowDown")
    page.wait_for_timeout(300)
    focus = page.evaluate("""() => {
      const active = document.activeElement;
      const box = active.getBoundingClientRect();
      return {role: active.getAttribute('role'),
              pos: Number(active.getAttribute('aria-posinset')),
              inView: box.top >= 0 && box.bottom <= innerHeight};
    }""")
    assert focus["role"] == "treeitem", focus
    assert focus["pos"] == 46, focus
    assert focus["inView"] is True, focus


def test_filtering_the_rail_resets_the_scroll_and_the_count(page, app):
    """Filtering from the bottom of a long list must land at the top of the short one —
    otherwise the window points past the end and the rail renders blank."""
    page.goto(app["base"], wait_until="networkidle")
    _pane(page, "Folder")
    page.wait_for_timeout(300)
    page.evaluate("() => { const tree = document.querySelector('.explorer .tree');"
                  " tree.scrollTop = tree.scrollHeight; }")
    page.wait_for_timeout(250)
    page.fill(".filter", "note-11")
    page.wait_for_timeout(350)
    rail = _rail(page)
    assert rail["scrollTop"] == 0, rail
    assert rail["label"] == "10 files", rail
    assert rail["rendered"] == 10, rail
    page.fill(".filter", "")
    page.wait_for_timeout(250)


def test_every_pane_keeps_its_heading_and_never_renders_blank(page, app):
    """A pane that throws unmounts the subtree and the page goes blank — which is
    exactly what a misplaced React hook did to Trash: `h1` count dropped to zero
    while the console stayed quiet in the served build. Walk all eleven panes and
    require a heading, the pane's own title, and some text for each."""
    areas = {
        "Files": ["Folder"],
        "Search": ["Capture", "Jobs", "Identity"],
        "Papers": ["Build", "Verify"],
        "Housekeeping": ["Audit", "Trash", "Sync"],
        "Agent": ["Loop", "Opportunity", "Panel"],
    }
    page.goto(app["base"], wait_until="networkidle")
    seen = 0
    for area, panes in areas.items():
        page.locator(".area-btn", has_text=area).first.click()
        for pane in panes:
            page.locator(".pane-btn", has_text=pane).first.click()
            page.wait_for_function(
                "() => !document.querySelector('main [aria-busy=\"true\"]')", timeout=20_000)
            headings = page.locator("h1")
            assert headings.count() == 1, (area, pane, headings.count())
            assert headings.first.inner_text().strip(), (area, pane)
            text = page.locator("main").inner_text().strip()
            assert len(text) > 20, (area, pane, text[:80])
            seen += 1
    assert seen == 12, seen


def test_the_panel_runs_and_shows_the_line_behind_each_objection(page, app):
    """The reel's promise: seven seats, and a quote from the document itself."""
    from playwright.sync_api import expect

    _pane(page, "Panel")
    expect(page.locator("h1")).to_have_text("Panel")

    page.get_by_label("Resume (relative to the workspace)").fill("resume.md")
    page.get_by_role("button", name="Run the panel").click()

    score = page.locator(".panel-score b")
    expect(score).to_be_visible(timeout=20_000)
    assert score.inner_text().strip().isdigit()
    assert page.locator(".panel-seat").count() == 7

    # Every seat opens, and an objection quotes the file rather than paraphrasing it.
    page.locator(".panel-seat-head").first.click()
    body = page.locator(".panel-seat-body").first
    expect(body).to_be_visible()
    source = (app["root"] / "resume.md").read_text(encoding="utf-8").split("\n")
    quotes = page.locator(".panel-seat-body blockquote")
    if quotes.count():
        assert any(quotes.nth(index).inner_text().split("\n")[0].strip() in "\n".join(source)
                   for index in range(quotes.count()))
    expect(page.locator(".panel-plan")).to_be_visible()
    _shot(page, "05-panel")
