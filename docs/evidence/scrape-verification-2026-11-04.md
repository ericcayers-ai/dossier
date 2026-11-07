# Capture system — verification receipts, 2026-11-04

Every claim below is a command that was run in the repo on this machine, with its exit code and
counted output. Nothing here is inferred from reading.

## 1. Full suite

```text
.venv\Scripts\python.exe -m pytest -o addopts="" --basetemp=C:/dossier-pytest-temp -p no:warnings -q
330 passed in 29.13s          exit 0
```

Baseline before this session, same command shape: **269 passed**. The 61 new tests are
`tests/test_scrape.py` (49), four FTS5-input regressions in `tests/test_search_ranking.py`,
six feed-wiring tests in `tests/test_feeds.py`, and two API tests (token-free console URL,
cookie-only authorisation).

## 2. The engines exist and are selected

```text
.venv\Scripts\python.exe -m dossier.cli scrape status --root <home>/.pi/agent/tmp/ws
captured postings: 3
  engine  obscura     ready    obscura 0.2.5
  engine  playwright  ready    1.64.1
  recipe  listing-template       web          list   no cadence declared; runs only when asked
  recipe  public-posting         web          single no cadence declared; runs only when asked
  recipe  local-listing          fixture      list   due
  session fixture                saved    2026-11-03T11:10:48+00:00 cookies=1
```

## 3. Public page, obscura, with robots checked

```text
.venv\Scripts\python.exe -m dossier.cli scrape capture http://127.0.0.1:8765/job/1 \
    --no-screenshot --root <home>/.pi/agent/tmp/ws --json
"driver": "obscura", "robots": {"checked": true, "allowed": true,
  "reason": "robots.txt permits this path", "status": 200}, "complete": true,
"posting": "job-posting-web-senior-engineer-at-acme.md"
```

The archived file: frontmatter (`source: web`, `url`, `captured_at`, `driver: obscura`, `title`,
`session: no`, `robots: robots.txt permits this path`) then the posting text with the site's
navigation, footer and `<script>` body absent.

## 4. Authenticated content, Playwright, saved session

```text
.venv\Scripts\python.exe -m dossier.cli scrape session-import --source fixture \
    --cookies <home>/.pi/agent/tmp/cookies.txt --url http://127.0.0.1:8765/login
session imported for fixture: 1 cookie(s)                                        exit 0

.venv\Scripts\python.exe -m dossier.cli scrape capture http://127.0.0.1:8765/private \
    --source fixture --session --driver playwright --no-screenshot --refresh ...
complete: http://127.0.0.1:8765/private
  driver: playwright  source: web  session: True                                  exit 0
```

The archived file carries `session: yes (fixture)` and the members-only listing
("Insider Role", "Secretive"), i.e. the cookie gate was passed by the stored jar, not bypassed.
Without `--session` the same URL returns `AuthRequired` naming
`dossier scrape login fixture` (test: `test_a_missing_session_on_a_gated_page_is_a_named_blocker`).

## 5. JavaScript rendering

```text
selector '#slot:has-text("Rendered by JavaScript")'  ->  "Rendered by JavaScript" in the archived body
```

`#slot` exists in the served HTML immediately; waiting for the text the timer writes is what proves
the engine ran the page's script (`test_playwright_renders_javascript_before_extraction`).

## 6. Refusals happen before the request

```text
scrape capture http://127.0.0.1:8765/challenge
PARTIAL: ... ChallengeDetected: served a human-verification interstitial ('checking your browser').
Nothing here answers a challenge.                                               exit 1

scrape capture http://127.0.0.1:8765/blocked/page
PARTIAL: ... Blocked: robots.txt does not permit ... (robots.txt disallows this path
for a generic crawler)                                                          exit 1

scrape capture https://www.linkedin.com/jobs/view/123
SourceRefused: linkedin is not permitted for automated access (prohibited)      exit 2
```

The fixture server's own request log confirms `/blocked/page` never reached the origin
(`test_robots_is_enforced_against_a_real_origin`). The prohibited board is refused before an engine
is even selected (`test_a_prohibited_board_is_refused_before_any_fetch`, which fails the test if the
fetch function is entered).

## 7. A paginated list run, duplicates, refresh

```text
scrape run --recipe local-listing --json
complete: true   items: 3   written: 2   duplicates: 1   pages_fetched: 2
```

Three items across two listing pages (`rel=next` followed), one already archived and skipped,
`complete: true`. `--limit 1` on the same board returns `complete: false`, `truncated: true`,
`reason: "stopped at --limit 1 of 2 listed items"` (unit test, fake fetch).

## 8. Policy on the feed layer

```text
.venv\Scripts\python.exe -m dossier.cli feeds list --root <tmp>
arbeitnow  official_public fetchable   https://www.arbeitnow.com/api/job-board-api
ashby      official_public fetchable  --board required https://api.ashbyhq.com/posting-api/job-board/{board}
greenhouse official_public fetchable  --board required https://boards-api.greenhouse.io/v1/boards/{board}/jobs
himalayas  official_public fetchable   https://himalayas.app/jobs/api
lever      official_public fetchable  --board required https://api.lever.co/v0/postings/{site}?mode=json
remotive   official_public fetchable   https://remotive.com/api/remote-jobs
```

`feeds fetch greenhouse --board acme --limit 1` with a stubbed transport wrote
`greenhouse_data/all_jobs.json` (1 row, `employer: Acme`, `<script>` stripped from the description),
a provenance file, and exited **1** because the fetch was truncated — `partial-is-not-exhaustive`
applied to a feed as well as a browser.

## 9. The built UI serves, renders, and reaches the capture API

```text
cd ui; npm ci; npm run build
dist/index.html 0.49 kB | dist/assets/index-*.css 30.01 kB | dist/assets/index-*.js 308.11 kB
built in 261ms                                                                  exit 0
```

`tsc -b` ran first, so the existing frontend type-checks. Served on a live uvicorn socket and driven
by Chromium at 1400×900:

```json
{"title": "Dossier", "built_ui": true,
 "headings": ["Files","Jobs","Audit","Trash","Sync","Agent","Verify","Trajectory","Explorer"],
 "api_scrape": {"status": 200, "recipes": 3,
                "engines": {"obscura": true, "playwright": true}, "postings": 5}}
```

The Explorer listed the five captured postings. The same request used **no `?token=`** in the URL —
the httponly cookie from `GET /` authorised it, which is the end-to-end proof for the change in §7 of
`docs/AUDIT-2026-11-04.md`. Screenshot:
`docs/evidence/dossier-ui-2026-11-04.png` (Chromium, full page).

**Not visually inspected.** The model that produced it has no image input, so the render claim rests
on the extracted DOM text and the screenshot file existing, not on a human having looked at it. The
`rendered-inspection` gate is therefore satisfied for *producing* the image and **not** for judging
it; a person or a vision model should open the PNG before anyone calls the UI "verified".

## 10. Contract and packs

```text
dossier agent adapters --check --root .
{"AGENTS.md": true, "CLAUDE.md": true, "GEMINI.md": true, ".cursor/rules/dossier.mdc": true,
 ".claude/skills/dossier/SKILL.md": true, "docs/PIPELINE.md": true, "docs/CONTRACT.md": true,
 "docs/agent/INJECT.md": true}                                                   exit 0
```

Mode `capture` and gates `session-is-the-users` / `challenge-is-a-blocker` appear in the generated
packs; `test_matrix` parses `dossier scrape status --root "<ws>"` and runs it against a fresh
workspace, and resolves every gate's enforcer symbol.

## 11. End-to-end user journey (2026-11-04, second pass)

`tests/test_e2e_ui.py` — 6 tests, 11.43 s, all passing. It starts a real uvicorn socket on
an ephemeral port serving the built `ui/dist`, points it at a real local origin
(`tests/fixtures/scrape_site.py`), and drives Chromium at 1440×1000. Every assertion reads
rendered text; the screenshots are evidence of what the assertions already proved.

```text
tests/test_e2e_ui.py ......                                              [100%]
6 passed in 11.43s
```

| Step | Assertion (DOM) | Side effect checked on disk |
|---|---|---|
| Shell renders | `.brand` = Dossier, nav has Capture and Build, status "API ready" | — |
| Capture one page | result row reads `complete`, driver `obscura` | `job-posting-web-senior-engineer-at-acme.md` exists and contains "Python" |
| Scrape the board | recipe row `complete`; table names "Platform Engineer" | 3 `job-posting-*.md` files |
| Opportunity tree | heading "Opportunity tree"; both nodes visible; "Branches to" rendered | `.dossier/tree.json` holds `opp-acme`, `ms-acme` and the link |
| Provide a template | "written" + 4 filled; "Every template check passed" | `resume-acme.docx`: values present, no `{{Name}}`, template paragraph intact, first run still bold |
| Workspace | Explorer lists `job-posting-*` and `resume-acme.docx`; `/api/scrape` reports ≥3 postings | — |

Screenshots (Chromium, full page): `docs/evidence/e2e-01-shell.png` … `e2e-07-workspace.png`.
**Not visually inspected**: the model that produced them has no image input, so the render
claim rests on the extracted DOM text. A person or a vision model should open the PNGs
before anyone calls the UI "verified" by eye.

## 12. Challenge ladder and template gate

```text
tests/test_scrape.py     59 passed   # incl. block / auto-ladder / self-clearing challenge
tests/test_challenge.py  13 passed   # policy resolution, solver, waiter, token injection
tests/test_template.py   17 passed   # fill, formatting, leftover gate, verify, CLI, API
```

- `challenge: block` → `ChallengeBlocked`, nothing archived, policy named in the reason.
- `challenge: auto` on a page that never clears → attempts `['plain', 'stealth+wait', …]`
  recorded in `result["challenge"]`, `complete: false`.
- A page whose interstitial clears after ~1.2 s is **captured** under `challenge: await`,
  with `waited_s` recorded — the fixture serves it at `/challenge-clears`.
- A strict template fill with three missing fields writes **no file** and reports the three
  leftovers; `--allow-leftovers` writes and reports them.
- The template gate fails on a leftover, on an absent value, and on a deleted template
  paragraph.

Full suite after both passes: **370 passed in 46.37 s** (269 at the start of the day).

Two more tests cover the shipped sign-in function itself: `sign_in` waits for the selector,
stores the cookie, and saves nothing when the element never appears (the fixture's
`/auto-login` signs itself in and then reveals `#signed-in`).
