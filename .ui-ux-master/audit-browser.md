# Browser audit — Dossier UI (built `ui/dist`)

Read-only audit. No file under `src/`, `ui/` or `tests/` was modified.

**Build audited (pinned copy — the dist was rebuilt twice *during* the audit, 02:38 and 02:41):**

| asset | sha256[:16] |
|---|---|
| `index-CzRRevQV.js` | `d7130ef1d79faf0f` |
| `index-CNFD5MJ3.css` | `98ee58041b7fb2a6` |
| `codemirror-BFcqfVmH.js` | `e4fb74d03e993cba` |

A byte-copy of `ui/dist` was served from a temp dir with `/api` proxied, so every
number below comes from one build. Anything rebuilt afterwards is not covered.

**What changed under me:** the 11 flat `.pane-btn` labels in the brief
(Files…Opportunity) no longer exist as a single strip. The build now has a 5-item
`.area-btn` strip plus per-area `.pane-btn` panes. All 11 panes still exist and
were all audited:

| area | panes | 
|---|---|
| Files | Folder |
| Search | Capture · Jobs · Identity |
| Papers | Build · Verify |
| Housekeeping | Audit · Trash · Sync |
| Agent | Agent · Opportunity |

Method: `.venv\Scripts\python.exe` + uvicorn on an ephemeral port (temp workspace,
`token='audit'`), Playwright Chromium 156.0.8078.4 headless, viewport 1440×900
(and 768×1024, 390×844). Contrast is computed from `getComputedStyle` colours
normalised through a 1×1 canvas (the UI emits `lab()` / `oklch()` /
`color-mix()`), alpha composited up the ancestor chain to the first opaque
background. Raw numbers: `audit-browser.json`. Screenshots: `receipts/p0/<pane>-1440.png`
and `<pane>-390.png` (22 files).

## Headline counts

| metric | value |
|---|---|
| panes audited | 11 / 11 |
| text/background pairs measured | 714 |
| pairs below threshold (4.5:1 normal, 3:1 large) | **1** |
| lowest ratio anywhere | 3.84:1 |
| interactive elements measured | 261 |
| interactive elements with no accessible name | **0** |
| interactive elements < 24×24 CSS px | 40 occurrences / 6 distinct controls |
| document-level horizontal overflow @1440 / 768 / 390 | 0 / 0 / 0 panes |
| h1 per pane = exactly 1 | 11 / 11 |
| pane content inside a landmark | 11 / 11 (`<main>`) |
| focus stops sampled | 25 per pane (275) |
| stops with no visible focus indicator | 1 (a `input[type=date]` internal segment) |
| focus stops outside the viewport | 0 |
| console errors | **0** |
| uncaught page errors | **0** |
| failed network requests | **0** |
| HTTP ≥ 400 responses | **0** |

### Pane h1s (clicked, not inferred)

| pane | h1 |
|---|---|
| Folder (Files) | Put the folder on the light table. |
| Capture | Capture |
| Jobs | Jobs |
| Identity | Identity |
| Build | Build from your template |
| Verify | Verify |
| Audit | Workspace audit |
| Trash | Trash |
| Sync | AI sync prompt |
| Agent | Agent surface |
| Opportunity | Opportunity tree |

Heading counts per pane: 1 h1 everywhere; h2 present in Identity (7), Agent (6),
Audit (3), Capture (2). No 0-h1 and no multi-h1 pane.

---

## Findings, ranked

### P0 — blocks use

**P0-1 · At 390 px the Agent pane's packet column collapses to one character wide
and its gates table is cut off.** `agent-pane` `scrollWidth 522` vs `clientWidth 390`;
`.agent-columns > div:nth-of-type(2)` measures `clientWidth 0 / scrollWidth 490`;
the packet `PRE` is **32 px** wide and its commit `TEXTAREA` **48 px** wide, so the
task packet renders one character per line (confirmed in
`receipts/p0/agent-390.png`: `#`, `D`, `o`, `s`, `s`, `i`, `e`, `r`, `t` stacked
vertically). The `.agent-gates table` is `490 px` wide inside a `0 px` column and
is only reachable by horizontally scrolling `.agent-pane` (overflow-x: auto), with
no visible affordance. The Agent pane is effectively unusable on a phone; at 1440
none of this appears.
Evidence: `viewport390.panes.agent`, `audit-browser.json`.

### P1 — visible defect

**P1-1 · Footer status controls are 13–15 px tall — a 3 px tall strip of targets.**
`footer.status > button.status-btn:nth-of-type(1)` = 72.5×13, `:nth-of-type(2)` =
48.4×13, `footer.status > button:nth-of-type(3)` ("Keyboard shortcuts") = 18.1×15.
These appear on all 11 panes at both 1440 and 390 (the only 3 small targets at 390).
They are the sole small targets at 390, so the 24 px tap floor is met everywhere
except this strip. Present in every pane's `inter` list in the JSON.

**P1-2 · At 390 the "Agent" area tab sits outside the viewport until scrolled.**
`.area-nav` `clientWidth 199 / scrollWidth 256`, `overflow-x: auto`; the "Agent"
button measures `x 361 → right 402` against a 390 px viewport (`inViewport: false`).
It is reachable (all 11 panes activated at 390 in `viewport390.navReach`), but the
strip clips the last tab with no visible scroll affordance. At 768 and 1440 all 5
area buttons fit.

**P1-3 · `input[type=date]` swallows four consecutive Tab stops and one of them has
no focus indicator.** In the Opportunity pane, tab stops 17, 18, 19 and 20 all land
on the same `input[type=date]`; stop 20 reports `:focus-visible: false` and
`outline: none 3px` while every surrounding stop paints `outline: solid 2px
lab(54.7552 1.47966 -58.5327) off 2px`. Evidence:
`panes.opportunity.focusNoIndicator`.

**P1-4 · One contrast failure across 714 pairs: `.agent-kind.hybrid`.**
`#b75b00` on `#dbebfb` = **3.84:1** at `11px/400` (needs 4.5:1), selector
`… > button > span.agent-kind.hybrid:nth-of-type(2)`, text `hybrid`, Agent pane.
Every other pair passes; the lowest passing pane minimum is 4.59 (Audit) and the
rest 5.46.

**P1-5 · Agent pane scrolls horizontally at 390.** `agent-pane`
`scrollWidth 522 / clientWidth 390`, dragging the table past the pane edge
(`table` right edge 522 vs pane right 390). This is the same root cause as P0-1 and
is listed separately because it is also what hides the table at 768.

### P2 — polish

**P2-1 · Jobs "Due" tab is 23.3 px wide** (`div.jobs-tabs > button:nth-of-type(3)`,
`23.3×35`) — 0.7 px under the 24 px floor; the other Jobs tabs are 25–45 px.

**P2-2 · Trash "Refresh" is 54.5×19** (`trash-pane > div.audit-head > button`).

**P2-3 · Capture "use saved session" checkbox is a 13×13 input**
(`label.chip:nth-of-type(4) > input`). The wrapping `label.chip` is the real hit
target, so this is cosmetic — but the measured control itself fails 24 px.

**P2-4 · The Bundle Rail is parked off-canvas with `visibility: visible` at ≤768.**
`position: fixed`, `transform: translateX(340px)`, rect `x 390` at a 390 px viewport.
I could not get a focus stop to land inside it (30-stop sample at 390 hit no
`.rail` descendant), so it is not a live keyboard trap on this build — worth an
`inert`/`visibility: hidden` guard so it cannot become one.

---

## Per-pane table

| pane | area | interactives | pairs | <4.5:1 | small targets | h1s | in landmark |
|---|---|---|---|---|---|---|---|
| Folder | Files | 13 | 32 | 0 | 3 (footer) | 1 | main |
| Capture | Search | 24 | 53 | 0 | 4 | 1 | main |
| Jobs | Search | 22 | 44 | 0 | 4 | 1 | main |
| Identity | Search | 34 | 74 | 0 | 3 | 1 | main |
| Build | Papers | 18 | 38 | 0 | 3 | 1 | main |
| Verify | Papers | 19 | 39 | 0 | 3 | 1 | main |
| Audit | Housekeeping | 15 | 80 | 0 | 3 | 1 | main |
| Trash | Housekeeping | 18 | 51 | 0 | 4 | 1 | main |
| Sync | Housekeeping | 17 | 37 | 0 | 3 | 1 | main |
| Agent | Agent | 46 | 188 | 1 | 3 | 1 | main |
| Opportunity | Agent | 35 | 78 | 0 | 3 | 1 | main |

## What holds up

- No console output of any kind, no page errors, no failed requests, no 4xx/5xx
  while clicking all 11 panes at 1440 and 390.
- `documentElement.scrollWidth === clientWidth` at 1440, 768 and 390 on all 11 panes.
  (The 340 px "offender" the sweep reports in every pane is the closed Bundle Rail
  drawer, which is `position: fixed` and translated off-canvas — not page overflow.)
- Every pane has exactly one h1 and lives in `<main>`; the page has one `main`,
  two `nav` landmarks (`.area-nav`, `.pane-nav`, both `aria-label`led) and two
  `aside`s.
- Every interactive element has an accessible name, including inputs whose names
  come from a wrapping `<label>` (no placeholder-only or icon-only controls).
- The focus ring (`outline: solid 2px` offset 2 px, `#3186e9` at 3.62:1 against the
  topbar `#fbfeff`) is visible on 274 of 275 sampled stops and cleared the 3:1
  non-text threshold.

## Residual risks / limits

- Numbers are for the pinned build above. `ui/dist` was rebuilt twice mid-run
  (02:38 → 02:41); a later build is unaudited, and a rebuild during a run would
  invalidate these counts.
- Empty workspace: no document tabs, no jobs corpus, no identity, no trash rows.
  States with real data (wide tables, long file names, the Jobs grid) were not
  exercised, so table/overflow defects there are unmeasured apart from the empty
  Agent gates table.
- Light theme only (`data-theme` default); the dark theme was not measured.
- The 25-stop focus sample is per pane and starts from the body each time; tab
  order beyond 25 stops is unmeasured.
- Contrast assumes a solid backdrop; pairs sitting on a `background-image`
  gradient would be flagged `approx` — none were.
