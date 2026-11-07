"""Before/after evidence for the layman pass: the same fourteen screenshots and the
same numbers, taken once with `--label before` and again with `--label after`.

The point of one script for both runs is that the measurement does not change with
the thing being measured. Every number below is read from the rendered page in
Chromium, not from the source:

  areas / panes          the top-level and in-area destinations the header offers
  words in main          what the screen asks the reader to read
  primaries              labelled buttons that look like the one obvious action
  jargon in nav          how many internal words the chrome uses
  contrast               computed WCAG ratio for every nav label and the h1
  h1 count               a pane that throws would drop to zero

The two workspaces are rebuilt from scratch on every run, so "before" and "after"
are measured against byte-identical inputs: one realistic job-search folder, and
one empty folder, which is what a first-time user actually opens.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import tempfile
import threading
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO))

import uvicorn  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

from dossier.api.app import create_app  # noqa: E402
from dossier.config import AppConfig  # noqa: E402

# Words the app uses internally. A newcomer is not supposed to know any of them.
JARGON = ["rail", "trajectory", "identity", "unit of work", "corpus", "agent", "recipe",
          "handoff", "cadence", "manifest", "artefact", "artifact", "reconcile", "gate",
          "blocker", "upskill", "negotiate", "verbatim", "facet", "dedupe", "pane",
          "bundle", "lexicon", "canonical", "stale", "applies to"]

# The four screens the brief names, plus the first-run folder.
SCREENS = [
    ("01-start", "", "the app as it opens"),
    ("02-capture", "#/search/capture", "paste a job link"),
    ("03-build", "#/papers/build", "the tailored document"),
    ("04-jobs", "#/search/jobs", "the postings"),
]

MEASURE = r"""
(selectors) => {
  const canvas = document.createElement('canvas').getContext('2d', {willReadFrequently: true});
  const rgba = (css) => {
    canvas.clearRect(0, 0, 1, 1);
    canvas.fillStyle = '#000'; canvas.fillStyle = css; canvas.fillRect(0, 0, 1, 1);
    const d = canvas.getImageData(0, 0, 1, 1).data;
    return [d[0], d[1], d[2], d[3] / 255];
  };
  const lum = ([r, g, b]) => {
    const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); };
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b);
  };
  const ratio = (a, b) => { const [x, y] = [lum(a), lum(b)].sort((m, n) => n - m); return (x + 0.05) / (y + 0.05); };
  const over = (fg, bg) => [fg[0]*fg[3]+bg[0]*(1-fg[3]), fg[1]*fg[3]+bg[1]*(1-fg[3]), fg[2]*fg[3]+bg[2]*(1-fg[3]), 1];
  const background = (el) => {
    let node = el;
    while (node && node !== document.documentElement) {
      const bg = rgba(getComputedStyle(node).backgroundColor);
      if (bg[3] > 0.999) return bg;
      if (bg[3] > 0.002) return over(bg, background(node.parentElement || document.body));
      node = node.parentElement;
    }
    return rgba(getComputedStyle(document.body).backgroundColor);
  };
  const contrast = {};
  for (const sel of selectors) {
    const el = document.querySelector(sel);
    if (!el) { contrast[sel] = null; continue; }
    const style = getComputedStyle(el);
    const parts = [];
    for (const node of el.childNodes) {
      if (node.nodeType === 3 && node.textContent.trim()) parts.push(node.textContent.trim());
    }
    const text = (parts.join(' ') || el.textContent || '').trim().slice(0, 40);
    contrast[sel] = {text, ratio: Number(ratio(rgba(style.color), background(el)).toFixed(2)),
                     size: Math.round(parseFloat(style.fontSize))};
  }
  const labels = (sel) => [...document.querySelectorAll(sel)].map((el) => el.textContent.trim());
  const main = document.querySelector('main');
  const text = main ? main.innerText : '';
  const primaries = [...document.querySelectorAll('main .primary, main [type=submit]')]
      .filter((el) => el.offsetParent !== null).map((el) => el.textContent.trim());
  const fields = [...document.querySelectorAll('main input, main select, main textarea')]
      .filter((el) => !el.closest('details:not([open])') && el.getClientRects().length > 0).length;
  const areas = document.querySelector('.area-nav');
  return {
    areas: labels('.area-nav .area-btn'),
    panes: labels('.pane-nav .pane-btn'),
    overflowX: Math.max(0, document.documentElement.scrollWidth - window.innerWidth),
    areasClipped: areas ? Math.max(0, areas.scrollWidth - areas.clientWidth) : 0,
    toggleLabels: labels('.pane-nav .icon-btn'),
    activeArea: (document.querySelector('.area-btn[aria-current="page"]') || {}).textContent || '',
    h1: [...document.querySelectorAll('h1')].map((el) => el.textContent.trim()),
    words: text.trim() ? text.trim().split(/\s+/).length : 0,
    primaries,
    fields,
  /* `fields` counts what the screen asks you to fill in: a closed disclosure does
     not ask, and Chromium still lays its contents out, so visibility is read from
     the DOM (`details:not([open])`), not from a client rect. */
    buttons: [...document.querySelectorAll('main button')].filter((el) => el.offsetParent !== null).length,
    contrast,
  };
}
"""

CONTRAST_SELECTORS = [".area-btn", ".area-btn.active", ".pane-btn.active", "main h1",
                      ".pane-purpose", ".brand", ".search-trigger"]


def build_workspace(root: Path, *, empty: bool) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    if empty:
        (root / "readme-note.txt").write_text("", encoding="utf-8")
        return root
    (root / ".dossier" / "scrapes").mkdir(parents=True, exist_ok=True)
    (root / "templates").mkdir(parents=True, exist_ok=True)
    (root / "all_boards_data").mkdir(parents=True, exist_ok=True)
    rows = [{"id": str(index), "title": title, "employer": employer, "location": "Hamilton",
             "url": f"https://acme.example/{index}", "source": "fixture",
             "work_type": "full-time", "pay": "$65000",
             "description": "Python, SQL and Playwright. Build things."}
            for index, (title, employer) in enumerate([
                ("Software Engineer", "Acme"), ("Platform Engineer", "Globex"),
                ("Data Analyst", "Initech"), ("Junior Developer", "Umbrella")], start=1)]
    (root / "all_boards_data" / "all_jobs.json").write_text(json.dumps(rows), encoding="utf-8")
    (root / "job-history.md").write_text(
        "| Date | Company | Role | Fit | Resume file | Status |\n"
        "|---|---|---|---|---|---|\n"
        "| Aug 2026 | Acme | Software Engineer | High | resume-acme.docx | drafted |\n",
        encoding="utf-8")
    (root / "resume.md").write_text(
        "# Eric\n\n## Skills\nPython, SQL, Playwright\n\n"
        "## Experience\nCut the weekly reporting loop from 8 hours to 2 hours.\n",
        encoding="utf-8")
    (root / "job-posting-software-engineer-at-acme.md").write_text(
        "# Software Engineer at Acme\n\nPython, SQL, Playwright. Build things.\n",
        encoding="utf-8")
    archive = root / "archive"
    archive.mkdir(exist_ok=True)
    for index in range(120):
        (archive / f"note-{index:03d}.txt").write_text(f"archive note {index}", encoding="utf-8")

    from docx import Document

    document = Document()
    document.add_paragraph("A. C — Engineer")
    document.add_paragraph("Skills: Python, SQL, Playwright")
    document.add_paragraph("Cut the weekly reporting loop from 8 hours to 2 hours.")
    document.save(str(root / "resume-master.docx"))

    template = Document()
    template.add_paragraph()
    template.add_paragraph("{{Objective}}")
    template.add_paragraph("Skills: {{Skills}}")
    template.save(str(root / "templates" / "my-template.docx"))
    return root


def serve(root: Path):
    application = create_app(AppConfig.create(root, token="ux-token"))
    config = uvicorn.Config(application, host="127.0.0.1", port=0, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    for _ in range(300):
        if server.started:
            break
        time.sleep(0.05)
    assert server.started, "the API did not start"
    port = server.servers[0].sockets[0].getsockname()[1]
    return server, thread, f"http://127.0.0.1:{port}"


def shoot(page, label: str, name: str, width: int, rows: dict) -> None:
    page.set_viewport_size({"width": width, "height": 1000})
    page.wait_for_timeout(450)
    data = page.evaluate(MEASURE, CONTRAST_SELECTORS)
    data["jargonInNav"] = sorted({word for word in JARGON
                                  for text in (data["areas"] + data["panes"] + data["h1"])
                                  if re.search(rf"\b{re.escape(word)}\b", text, re.I)})
    page.screenshot(path=str(OUT / f"{label}-{name}-{width}.png"), full_page=True)
    rows[f"{name}-{width}"] = data


def run(label: str) -> dict:
    tmp = Path(tempfile.mkdtemp(prefix="ux-layman-"))
    full = build_workspace(tmp / "workspace", empty=False)
    empty = build_workspace(tmp / "empty-folder", empty=True)
    rows: dict[str, dict] = {}
    for name, root in (("workspace", full), ("first-run-empty", empty)):
        server, thread, base = serve(root)
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True)
                context = browser.new_context(viewport={"width": 1440, "height": 1000})
                page = context.new_page()
                errors: list[str] = []
                page.on("console", lambda message: errors.append(message.text)
                        if message.type == "error" else None)
                if name == "workspace":
                    for screen, hash_, _ in SCREENS:
                        page.goto(base + ("/" + hash_ if hash_ else "/"), wait_until="networkidle")
                        page.wait_for_timeout(600)
                        for width in (1440, 390):
                            shoot(page, label, screen, width, rows)
                else:
                    page.goto(base + "/", wait_until="networkidle")
                    page.wait_for_timeout(700)
                    for width in (1440, 390):
                        shoot(page, label, "05-first-run-empty", width, rows)
                rows["consoleErrors"] = errors
                browser.close()
        finally:
            server.should_exit = True
            thread.join(timeout=15)
    shutil.rmtree(tmp, ignore_errors=True)
    path = OUT / f"{label}-metrics.json"
    path.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"wrote": str(path), "screens": sorted(rows)}, indent=2))
    return rows


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", choices=["before", "after"], required=True)
    run(parser.parse_args().label)
