"""Measure the built UI: contrast, overflow, tap targets, headings, focus, errors.

Screenshots are produced for the record, but every claim below is a number read
from the rendered page, because this model cannot see images.
"""
import json
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(r"<home>/OneDrive/Desktop/Programs/dossier/tests/fixtures")))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import uvicorn
from playwright.sync_api import sync_playwright

from dossier.api.app import create_app
from dossier.config import AppConfig

REPO = Path(r"<home>/OneDrive/Desktop/Programs/dossier")
OUT = REPO / ".ui-ux-master" / "receipts" / "p5"
OUT.mkdir(parents=True, exist_ok=True)
WS = Path(r"<home>/AppData/Local/Temp/uiux-workspace")

PANES = ["Folder", "Capture", "Jobs", "Identity", "Build", "Verify", "Audit",
         "Trash", "Sync", "Loop", "Opportunity", "Panel"]
AREA_OF = {"Folder": "Files", "Capture": "Search", "Jobs": "Search", "Identity": "Search",
           "Build": "Papers", "Verify": "Papers", "Audit": "Housekeeping", "Trash": "Housekeeping",
           "Sync": "Housekeeping", "Loop": "Agent", "Opportunity": "Agent",
           "Panel": "Agent"}

MEASURE = r"""
() => {
  // willReadFrequently: this probe reads a 1x1 pixel once per text node, and without
  // the flag Chrome emits a Canvas2D warning per read, which the console check then
  // reports as 33 app warnings that the app never made.
  const canvas = document.createElement('canvas').getContext('2d', {willReadFrequently: true});
  const rgba = (css) => {
    canvas.clearRect(0, 0, 1, 1);
    canvas.fillStyle = '#000';
    canvas.fillStyle = css;
    canvas.fillRect(0, 0, 1, 1);
    const d = canvas.getImageData(0, 0, 1, 1).data;
    return [d[0], d[1], d[2], d[3] / 255];
  };
  const lum = ([r, g, b]) => {
    const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); };
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b);
  };
  const ratio = (a, b) => { const [x, y] = [lum(a), lum(b)].sort((m, n) => n - m); return (x + 0.05) / (y + 0.05); };
  const over = (fg, bg) => {
    const a = fg[3];
    return [fg[0] * a + bg[0] * (1 - a), fg[1] * a + bg[1] * (1 - a), fg[2] * a + bg[2] * (1 - a), 1];
  };
  const background = (el) => {
    let node = el;
    while (node && node !== document.documentElement) {
      const bg = rgba(getComputedStyle(node).backgroundColor);
      if (bg[3] > 0.999) return bg;
      if (bg[3] > 0.002) {
        const below = background(node.parentElement || document.body);
        return over(bg, below);
      }
      node = node.parentElement;
    }
    return rgba(getComputedStyle(document.body).backgroundColor);
  };
  const describes = (el) => (el.getAttribute('aria-label') || el.textContent || '').trim().slice(0, 60);
  const visible = (el) => {
    const box = el.getBoundingClientRect();
    const style = getComputedStyle(el);
    return box.width > 0 && box.height > 0 && style.visibility !== 'hidden' && style.display !== 'none';
  };

  const contrast = [];
  const small = [];
  const unnamed = [];
  const interactive = 'button, input, select, textarea, a[href], [role="tab"], [role="button"], summary';

  for (const el of document.querySelectorAll('body *')) {
    if (!visible(el) || el.closest('[inert]')) continue;
    const style = getComputedStyle(el);
    const ownText = [...el.childNodes].filter(n => n.nodeType === 3).map(n => n.textContent).join('').trim();
    if (ownText) {
      const fg = rgba(style.color);
      const bg = background(el);
      const size = parseFloat(style.fontSize);
      const weight = parseInt(style.fontWeight || '400', 10);
      const large = size >= 24 || (size >= 18.66 && weight >= 700);
      const value = ratio(fg[3] > 0.999 ? fg : over(fg, bg), bg);
      if (value < (large ? 3 : 4.5)) {
        contrast.push({selector: el.tagName.toLowerCase() + (el.className ? '.' + String(el.className).split(' ')[0] : ''),
                       text: ownText.slice(0, 50), ratio: Math.round(value * 100) / 100, size, large,
                       fg: style.color, bg: `rgb(${bg.slice(0, 3).map(Math.round).join(',')})`});
      }
    }
  }

  for (const el of document.querySelectorAll(interactive)) {
    if (!visible(el) || el.closest('[inert]')) continue;
    const box = el.getBoundingClientRect();
    if (el.closest('label') && el.tagName === 'INPUT') continue;
    if (box.width < 24 || box.height < 24) {
      small.push({tag: el.tagName.toLowerCase(), name: describes(el), w: Math.round(box.width), h: Math.round(box.height)});
    }
    const named = (el.getAttribute('aria-label') || '').trim()
      || (el.getAttribute('title') || '').trim()
      || (el.id && document.querySelector(`label[for="${el.id}"]`))
      || el.closest('label')
      || (el.textContent || '').trim();
    if (!named) unnamed.push({tag: el.tagName.toLowerCase(), cls: String(el.className).slice(0, 40)});
  }

  const overflow = [];
  for (const el of document.querySelectorAll('body *')) {
    if (!visible(el) || el.closest('[inert]')) continue;
    // A wide table inside its own scroller is reachable by scrolling, not a defect.
    let scroller = false;
    for (let node = el.parentElement; node && node !== document.body; node = node.parentElement) {
      const style = getComputedStyle(node);
      if (/(auto|scroll)/.test(style.overflowX)) { scroller = true; break; }
    }
    if (scroller) continue;
    const box = el.getBoundingClientRect();
    if (box.right > window.innerWidth + 1) {
      overflow.push({tag: el.tagName.toLowerCase(), cls: String(el.className).slice(0, 40),
                     left: Math.round(box.left), right: Math.round(box.right)});
    }
  }

  const h1 = [...document.querySelectorAll('h1')].filter(visible).map(el => el.textContent.trim().slice(0, 50));
  const landmarks = {
    main: document.querySelectorAll('main').length,
    nav: document.querySelectorAll('nav').length,
    aside: document.querySelectorAll('aside').length,
    live: document.querySelectorAll('[aria-live], [role="status"], [role="alert"]').length,
  };

  return {
    contrast: contrast.slice(0, 40),
    small: small.slice(0, 40),
    unnamed: unnamed.slice(0, 40),
    overflow: overflow.slice(0, 20),
    h1, landmarks,
    scrollWidth: document.documentElement.scrollWidth,
    clientWidth: document.documentElement.clientWidth,
  };
}
"""


def main():
    WS.mkdir(parents=True, exist_ok=True)
    (WS / "resume.md").write_text("# Person\n\n## Skills\nPython, SQL\n", encoding="utf-8")
    (WS / "job-history.md").write_text(
        "| Date | Company | Role | Fit | Resume file | Status |\n|---|---|---|---|---|---|\n"
        "| Sep 2026 | Acme | Engineer Intern | High | a.docx | drafted |\n", encoding="utf-8")
    (WS / "all_boards_data").mkdir(exist_ok=True)
    (WS / "all_boards_data" / "all_jobs.json").write_text(json.dumps([
        {"id": "1", "title": "Software Engineer Intern", "employer": "Acme",
         "location": "Hamilton", "url": "https://example/1", "source": "fixture",
         "work_type": "internship", "description": "Python and SQL."}]), encoding="utf-8")

    app = create_app(AppConfig.create(WS, token="uiux"))
    cfg = uvicorn.Config(app, host="127.0.0.1", port=0, log_level="warning")
    server = uvicorn.Server(cfg)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    for _ in range(200):
        if server.started:
            break
        time.sleep(0.05)
    port = server.servers[0].sockets[0].getsockname()[1]
    base = f"http://127.0.0.1:{port}"

    report = {"url": base, "panes": {}, "console": [], "focus": [], "dark": {}, "reduced": {}}
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        for width, height in ((1440, 900), (768, 900), (390, 844)):
            context = browser.new_context(viewport={"width": width, "height": height})
            page = context.new_page()
            page.on("console", lambda message: report["console"].append(
                {"type": message.type, "text": message.text[:160]})
                if message.type in ("error", "warning") else None)
            page.on("pageerror", lambda error: report["console"].append(
                {"type": "pageerror", "text": str(error)[:160]}))
            page.goto(base, wait_until="networkidle")
            page.wait_for_timeout(400)
            size = f"{width}"
            report["panes"][size] = {}
            for label in PANES:
                page.locator(".area-btn", has_text=AREA_OF[label]).first.click()
                page.wait_for_timeout(120)
                page.locator(".pane-btn", has_text=label).first.click()
                page.wait_for_timeout(350)
                data = page.evaluate(MEASURE)
                heading = page.locator("h1").first
                report["panes"][size][label] = {
                    "h1": data["h1"],
                    "contrast": data["contrast"],
                    "small_targets": data["small"],
                    "unnamed_controls": data["unnamed"],
                    "overflow": data["overflow"],
                    "scrollWidth": data["scrollWidth"],
                    "clientWidth": data["clientWidth"],
                }
                page.screenshot(path=str(OUT / f"{label.lower()}-{width}.png"), full_page=False)
            context.close()

        # Dark theme: the same measurements on the same panes.
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()
        page.goto(base, wait_until="networkidle")
        page.get_by_role("button", name="Use dark theme").click()
        page.wait_for_timeout(300)
        report["dark"]["1440"] = {}
        for label in PANES:
            page.locator(".area-btn", has_text=AREA_OF[label]).first.click()
            page.wait_for_timeout(120)
            page.locator(".pane-btn", has_text=label).first.click()
            page.wait_for_timeout(250)
            data = page.evaluate(MEASURE)
            report["dark"]["1440"][label] = {"contrast": data["contrast"], "h1": data["h1"]}
        page.screenshot(path=str(OUT / "dark-1440.png"), full_page=False)

        # Keyboard: 30 tab stops from the top, each must show a focus ring.
        page.locator("body").click(position={"x": 5, "y": 5})
        for step in range(30):
            page.keyboard.press("Tab")
            # One frame of settle: reading computed style in the same task as the
            # key press can catch the style recalc before `:focus-visible` applies,
            # which reported a false "no ring" on the date field.
            page.evaluate("() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))")
            state = page.evaluate("""() => {
                const el = document.activeElement;
                if (!el || el === document.body) return null;
                const style = getComputedStyle(el);
                const ring = (style.outlineStyle !== 'none' && parseFloat(style.outlineWidth) >= 2)
                    || (style.boxShadow && style.boxShadow !== 'none');
                const box = el.getBoundingClientRect();
                return {tag: el.tagName.toLowerCase(), label: (el.getAttribute('aria-label') || el.textContent || '').trim().slice(0, 40),
                        ring, visible: box.width > 0 && box.height > 0 && box.top < window.innerHeight && box.bottom > 0,
                        type: el.type || '', cls: String(el.className).slice(0, 40), id: el.id || '',
                        html: el.outerHTML.slice(0, 120), outline: `${style.outlineStyle} ${style.outlineWidth}`};
            }""")
            # A pane that re-renders between the key press and the read can leave
            # `activeElement` pointing at a node the framework has already replaced:
            # that node no longer matches `:focus`, so its outline reads as none even
            # though the focused control on screen has a ring. Re-read once, and only
            # record a miss when the element is still the focused one.
            if state and not state.get("ring"):
                page.wait_for_timeout(60)
                again = page.evaluate("""() => {
                    const el = document.activeElement;
                    if (!el || el === document.body) return null;
                    const style = getComputedStyle(el);
                    return {focused: el.matches(':focus'),
                            ring: (style.outlineStyle !== 'none' && parseFloat(style.outlineWidth) >= 2)
                                  || (style.boxShadow && style.boxShadow !== 'none')};
                }""")
                if again and again.get("focused") and not again.get("ring"):
                    report["focus"].append(state)
            elif state:
                report["focus"].append(state)
        context.close()

        # Reduced motion: the sketch and the pulse must not animate.
        context = browser.new_context(viewport={"width": 1440, "height": 900}, reduced_motion="reduce")
        page = context.new_page()
        page.goto(base, wait_until="networkidle")
        page.wait_for_timeout(300)
        report["reduced"] = page.evaluate("""() => {
            const probe = document.createElement('span');
            probe.className = 'skeleton';
            document.body.appendChild(probe);
            const duration = getComputedStyle(probe).animationDuration;
            probe.remove();
            return {skeleton_animation: duration};
        }""")
        context.close()
        browser.close()

    server.should_exit = True
    thread.join(timeout=15)

    (REPO / ".ui-ux-master" / "measure.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

    for size, panes in report["panes"].items():
        headings = sum(1 for row in panes.values() if len(row["h1"]) != 1)
        bad_contrast = sum(len(row["contrast"]) for row in panes.values())
        small = sum(len(row["small_targets"]) for row in panes.values())
        for pane_name, row in panes.items():
            for target in row["small_targets"]:
                print(f"  {size}px small target in {pane_name}: {target}")
        unnamed = sum(len(row["unnamed_controls"]) for row in panes.values())
        overflow = sum(len(row["overflow"]) for row in panes.values())
        print(f"{size}px: panes without exactly one h1={headings}, contrast fails={bad_contrast}, "
              f"<24px targets={small}, unnamed controls={unnamed}, overflowed elements={overflow}")
    print("console:", len(report["console"]))
    dark_fail = sum(len(row["contrast"]) for row in report["dark"].get("1440", {}).values())
    rings = [row for row in report["focus"] if not row["ring"]]
    invisible = [row for row in report["focus"] if row["visible"] is False]
    print(f"dark contrast fails={dark_fail}; focus stops={len(report['focus'])}, "
          f"without a ring={len(rings)}, off-screen={len(invisible)}")
    # Name the offender: a bare count sent the last person who read this hunting.
    for row in rings + invisible:
        print(f"  focus defect: {row['tag']} type={row.get('type')!r} class={row.get('cls')!r} id={row.get('id')!r} "
              f"ring={row['ring']} outline={row.get('outline')!r} html={row.get('html')!r}")
    print("reduced motion:", report["reduced"])


if __name__ == "__main__":
    main()
