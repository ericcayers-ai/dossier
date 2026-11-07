# Whole-UI verification against the skills, the docs and the reels

2026-11-06. The ask, in the owner's words, was three escalating instructions: *"this is terrible
to look at … too much text and subtext"*, then *"make sure you actually did everything the reels
digest told you, all possible skills were used"*, then *"make sure all ui/ux is clean and not
cluttered and all superskill and skills etc and docs and reel digests have been all considered"*,
and finally *"read on actual screenshots and go through a full workflow … antislop the whole
thing"*.

This file is the traceability record for that. Every row names an outside judge: a rendered
measurement, a gate output, or a test.

## Method

1. **A whole session in order, photographed.** `%TEMP%\dossier-live-2026-11-05\tour.py` drives
   Chromium through 23 steps of real use — cold load, follow the suggested next unit, filter the
   rail, open a document, preview it, visit all eleven panes, Ctrl-K search, the shortcuts sheet,
   dark theme, a 390 px phone, the same PDF in a headed browser that can display it — and writes a
   screenshot plus `h1`, visible word count and control count per step
   (`visual-2026-11-06/tour.json`).
2. **The screenshots were read, not counted.** Each `01-landing`, `04-viewer`, `07-jobs`,
   `09-build`, `12-trash`, `13-sync`, `14-loop`, `15-opportunity` image was rendered and
   inspected; the findings below quote what was on screen.
3. **Two read-only scouts** audited the source against the skill library and the repo's own
   documents: `skills-audit-2026-11-06.md` (11 skills, 60 checkable rules) and
   `docs-audit-2026-11-06.md` (9 documents, 50 rules). Neither edited anything.
4. **Gates after every change**: `pytest`, `measure.py`, `inspect.mjs --app`, `sloplint`, `a11y.py`,
   Lighthouse, `graft check`.

## What the screen showed, and what changed

Visible words in `<main>` per step, before → after. `tour.py` counts them from `innerText`.

| step | before | after | what was wrong |
|---|---|---|---|
| landing | 84 | 62 | the reason and its first blocker said the same sentence twice; a stat list sat in a comma string |
| Folder → Build | 16 | 28 | the pane offered a guessed template path while the folder held three `.docx` files |
| viewer (PDF) | 2 (blank) | 44 | a browser without a PDF viewer got an empty pane under the words "pdf: read-only view" |
| Sync | 5 (a textarea) | 33 | the packet opened as a wall of raw markdown |
| Loop | 1093 | 221 | the agent task brief was printed in full above the fold |
| Trash | 511 | 153 | 39 rows for `IDENTITY.md`, each with a raw ISO timestamp to the microsecond |
| Opportunity | 102 | 92 | five empty category cards, a meaningless "1810 actionable", two authoring forms |
| Jobs | 641 | 641 | unchanged on purpose: 50 rows of real postings are data, not clutter |

### The fixes, each with its measurement

| # | finding (as seen on screen) | fix | evidence |
|---|---|---|---|
| 1 | Landing: two monospace prose blocks, one repeating the card's own reason | blockers the reason already carries are dropped; >2 collapse behind a summary | landing **84 → 62** words |
| 2 | `.agent-next ul` set `word-break: break-all` and the mono font on a sentence, so "or older tha/n 7 days" split mid-word | scoped that rule off `.agent-blockers`; prose type, normal wrapping | computed `word-break: normal`, font Inter, **0** mid-word breaks |
| 3 | Landing: "1 configured action(s) do not apply to a . file" | plural helper + only when a file is selected, with its real extension | `lib/copy.ts`; `grep "(s)" ui/src` **15 → 0** |
| 4 | Status bar read "API ready · Ready" | idle state is empty, not "Ready" | `App.tsx` saveLine |
| 5 | PDF opened blank | when `navigator.pdfViewerEnabled === false`, say so and offer a new tab | headless `false` → explained panel; headed `true` → `.pdf-frame` present with the right src |
| 6 | Rail printed three "None in this set" blocks | empty roles collapse to one line | rail words per pane; `BundleRail.tsx` |
| 7 | Rail notice ran to the pane edge | `overflow-wrap: anywhere` | `tokens.css` `.notice` |
| 8 | Header showed the open file as `_pr…` — 25 px for a 525 px path | `@media (max-width:1500px)` capped the crumb at 180 px; now `min(52ch,42vw)` with a 16ch floor, and the basename | crumb path **25 → 159 px** |
| 9 | Sync: 40-line markdown packet filled the pane | one-line summary (date + three counts) + the text behind a disclosure | Sync **5 → 33** words, packet collapsed |
| 10 | Loop: the agent brief printed in full | copy button stays, brief behind "Show the brief" | Loop **1093 → 221** |
| 11 | Trash: 39 rows, raw `2026-11-05T14:14:51.525417+00:00` timestamps | grouped per file, newest first, human clock, all copies one click deeper | Trash **511 → 153**; `formatWhen()` added |
| 12 | Trash rows at 390 px: "Restore newest" squeezed to **12 px wide** | rows stack under 700 px, button keeps a 96 px floor above it | gate `<24px targets` 1 → **0** |
| 13 | Opportunity: five "No X yet." cards, "0 links" beside "1810 actionable" | empty groups vanish into one sentence; the zero-link state is explained | Opportunity 102 → 92, then 47 with the forms absent |
| 14 | Build: a guessed `templates/my-resume-template.docx`, no mention that generation is blocked | lists the folder's real `.docx` files in a datalist and says when there are none | `BuildPane docx={docxFiles}`; pane words 16 → 28 |
| 15 | `--signal-soft-strong: var(--signal-soft-strong)` — a token pointing at itself, invalid, so the selected row had **no wash at all** | real 17 % OKLCH mix | computed `background-color: oklch(0.62 0.17 255 / 0.17)` on `.tree-row.selected` |
| 16 | Viewer tabs named `aria-controls="viewer-panel"` but no element carried that id | the panel exists, with `role="tabpanel"` and `aria-labelledby` | both chips resolve; `#viewer-panel` found |
| 17 | 24×24 target rule broken by the disclosures I added (summary rows 15–17 px tall) | every disclosure summary is a 24 px target | gate small targets 1 → **0** at 1440/768/390 |
| 18 | Focus test reported a stop with no ring | the offending stop was an `input[type=date]` that no longer matched `:focus` because the pane had re-rendered mid-read; fields now ring on any focus and the gate re-reads before calling a miss | gate `without a ring` 1 → **0**; probe: Tab to the date field → `matches(':focus')=true`, outline `solid 2px` |
| 19 | Landing still hollow after the copy diet: inspect flagged a 660×540 void | the six counts became a stat row (files 729 · postings 23 · keyword reports 11 · artefacts 76 · renders 99 · proofs 29) | `inspect.mjs --app` **3 findings → 0** |
| 20 | One toolbar mixed "Sync workspace sources" with "Export ASCII", "Generate Next Branch" | sentence case throughout; two filled primaries in Capture reduced to one | `sloplint` FAIL (em dash) → 0 | 
| 21 | Placeholders were instructions ("Filter files", "Filter by role, employer…") | examples instead ("e.g. resume", "e.g. Hamilton") | `Explorer.tsx`, `JobsPane.tsx`, `Palette.tsx` |
| 22 | Theme flip animated every colour on screen at once | one frame with transitions off | `.theme-swapping` rule, declared last |
| 23 | The shortcuts sheet took focus nowhere and returned it nowhere | focus moves to the dialog, Tab is trapped, Escape/Close returns to `?` | `App.tsx` `helpRef`/`helpReturn` |

Two changes were **measured, then reverted**: wrapping the Opportunity authoring forms in a
`<details>` broke the workflow test (`select_option` timed out on a select inside it) and hid the
pane's primary action. The forms stay visible; only the empty cards were removed.

## Skills considered

The catalogue is tiered: one router (`master-superskills`), ten category hubs, and the project
packs. Relevant here are hub **02 interface-experience** plus the member skills that constrain a
local-first React workspace. The full rule-by-rule audit is in `skills-audit-2026-11-06.md`; this
is the summary.

| skill | binds this app how | verdict after this pass |
|---|---|---|
| `frontend-superskill` (hub 02) | routes to the members; anti-slop floor | used as the spine |
| `impeccable` (craft-floor, distill, clarify) | density, copy, one job per screen | applied (word counts per pane, `(s)`, phrasing) |
| `hallmark` / `sloplint` | mechanical slop tells | 0 FAIL / 0 REFLEX / 2 WARN (waived, below) |
| `taste-skill` / `inspect.mjs` | rendered voids, panel balance | 2 findings → **0** |
| `better-accessibility` | focus, targets, ARIA, motion | 15 rules checked; the ring, target and dialog findings above fixed |
| `better-colors` | token-only colour, contrast, one primary | fixed the self-referential token; contrast all pass |
| `better-layout` | tracks that hold long text | `minmax(0,…)` on the pipeline and trash rows |
| `better-typography` | scale, numerals, phone inputs | 16 px fields under 700 px; tabular numerals on counts; `h4` no longer smaller than body |
| `better-ui` | transitions, press states, scrims | added `overscroll-behavior` to the palette list; hover gating extended |
| `better-writing` | errors name the next step; placeholders are examples | placeholders fixed; `count()` used everywhere |
| `visual-verification-receipts` | a screenshot is evidence only with a deterministic assertion beside it | this file: every image claim has a number |
| `interface-review`, `review-animations` | change-scoped review | no diff base supplied; recorded as not-applicable |
| `web-quality-skills` | Core Web Vitals | Lighthouse run, 99/100/100 |
| `code-quality`, `testing-verification` | surgical change, independent gate | one new pane-walk test; suite 438 |
| `writing-docs`, `humanizer` | this document | applied |
| `cybersafe` | no secrets, no telemetry | 0 external hosts, 0 tracked personal data (prior pass) |
| `coverage-audit` | this matrix | this document is its output |
| `dossier-workspace` (project pack) | the repo's own facts and gates | followed |

Skills that are **not applicable** and why: `digital-earth`, `neutral-dev`, `neiro-dev`,
`wireless-triangulator`, `sleepnstep`, `panopto-course-assistant-dev`, `roblox-studio-mcp`,
`minecraft-roblox-city-reconstructor`, `geo-sleuth`/`geolocating-superskill`, `vesterguesser-desk`,
`docx`/`pptx`/`figma-*` (no such surface here), `mlops-ai`, `game-development`,
`spatial`/`instasplatter`, `time-series-forecasting`, `hiring-panel` (filed as a product mode in
`tasks/WORKLIST.md`), `api-design`/`system-design-rederive` (Python side, unchanged this pass).

## Repo documents considered

`docs-audit-2026-11-06.md` carries all 50 rules with evidence. Six were violated when the scout
looked; the ones this pass could fix are fixed, the rest are recorded:

| document rule | verdict now |
|---|---|
| `DESIGN.md:65` "`--signal-soft-strong` is a 17 % signal wash" | **fixed** — the token pointed at itself and painted nothing |
| `ARCHITECTURE.md:102` "a new pane gets one h1, a skeleton, an empty state and an error state" | **fixed in Build** — it had no loading state; it now renders its own explanation and the real `.docx` list |
| `DESIGN.md:165` "export routes are labelled with their fidelity class before the click" | **open** — declared in `engine/render.py`, never surfaced in the UI. Recorded, not silently dropped |
| `CONVENTIONS.md:33` "a GET route never performs a slow operation" | **open** — `GET /api/render` converts on a cache miss; changing it is an API contract change, filed |
| `CONVENTIONS.md:66` "keep STATE.md and HANDOFF.md under 120 lines" | **open** — 174 and 128 lines; trimming them is a separate, deliberate edit |
| `ARCHITECTURE.md:87` "39 `/api/*` routes" | **stale count** — the file carries 52; noted in this receipt, corrected where it is asserted as a gate |

The rest were honoured: read-is-free/write-is-explicit, every overwrite through `.dossier/trash/`,
`inert` slide-overs, one `h1` per pane, loopback + token authorisation, no commit of workspace
data, `no-fabrication` and the required hand-back fields.

## Reel digests considered

The 107-heading audit is `docs/evidence/reel-matrix-2026-11-06.md` (107 rows: `§1`–`§94` entries,
`S1`–`S13` sub-sections, every row with a verdict and evidence). The reels that bind *visual*
work were re-checked against this pass: §32 (anti-slop skills), §48 (20 vibecoded tells), §49
(20 production giveaways), §51 (portfolio tells: no subtext under every heading), §65 (Hallmark
lint as a gate), §70 (no telemetry). Measured after the pass: **0** gradients, **0**
`backdrop-filter`, **0** `transition: all`, **0** emoji icons, **0** marketing adjectives,
`sloplint` 0 FAIL / 0 REFLEX, console 0, **0** external hosts.

## Gate state at the end of this pass

```
pytest -o addopts="" -q                       438 passed (71 s)  · 14 e2e, 10 API
npm run build                                 built in 232 ms, 13 pane chunks
.ui-ux-master/measure.py                      1440/768/390: 0 h1 misses, 0 contrast fails,
                                              0 <24px targets, 0 unnamed, 0 overflow, console 0,
                                              dark 0 fails, 29/29 focus rings, reduced motion 0s
inspect.mjs --app --widths 1440,768,390       0 findings
a11y.py (11 panes + 2 dialogs)                clean
sloplint ui/src --scope app                   0 FAIL, 0 REFLEX, 2 WARN (waived)
graft check                                   OK
Lighthouse (desktop)                          performance 99, accessibility 100, best-practices 100
tour.py                                       23 steps, console 0, HTTP ≥400 0
```

## Waivers, with reasons

- **`.palette` keeps a hairline border under a soft shadow** (`sloplint` F24) — it is the only
  overlay in the app; the border is what an overlay needs at 390 px where the shadow does not read.
- **`markdown.tsx` images carry no `fetchpriority`** (`sloplint` 28a) — the LCP element is the
  shell, not a user image inside a document.
- **`.pulse` animates `background-color`** for 400 ms, once — the alternative is a pseudo-element
  layer on up to 728 rows to avoid one repaint.
- **Physical CSS properties** (`border-left` and friends) stay: the app ships one direction, and a
  logical-property sweep would touch every rule for no visible gain.
- **Submit stays disabled until required fields are filled** rather than validating on submit —
  the form is one field plus a state; a disabled button whose reason is visible beats a bounce.

## Reproduce

```powershell
# 1. a whole session, photographed
.venv\Scripts\python.exe %TEMP%\..\tour.py http://127.0.0.1:8077
# 2. the deterministic gates
.venv\Scripts\python.exe .ui-ux-master\measure.py
node ~/.dsh/skills/taste-skill/scripts/inspect.mjs http://127.0.0.1:8077/ --app --widths 1440,768,390
.venv\Scripts\python.exe -m pytest -o addopts="" -q
# 3. the two read-only audits
#    docs/evidence/skills-audit-2026-11-06.md  (11 skills, 60 rules)
#    docs/evidence/docs-audit-2026-11-06.md    (9 documents, 50 rules)
```

Screenshots: `%TEMP%\dossier-live-2026-11-05\visual-2026-11-06\` (23 steps, plus
`23-pdf-headed.png` and `24-pdf-headless-explained.png`).

## Second pass the same day: friction, not appearance

The first pass made the screens answer; this one measured what a person has to **do**. Three
defects came out of that, and the first one meant saving a file never worked.

### Every save from the UI was a false conflict

`mtime_ns` is about `1.79e18`. That is past `2**53`, so a JavaScript number cannot hold it: the
stamp the browser sends back is **rounded by ~100 ns**.

```
sent by the UI : 1793893969162173700
on disk        : 1793893969162173600      -> 409 "file changed on disk"
```

`FileStamp` equality compared that field exactly, so every `PUT /api/file` with a precondition
was rejected, the conflict bar appeared, and "Unsaved changes" never cleared. Measured before
the fix: `PUT /api/file -> 409`, `still_dirty: true`, conflict bar visible, in a clean profile
*and* with a stale draft.

The precondition is the **content**; the mtime is a cheap hint. `matches()` now compares
`sha256` and `size` exactly and accepts an mtime within 1 µs, which is far tighter than a real
edit and far wider than float rounding. After: `PUT -> 200`, `still_dirty: false`, no conflict
bar. Regression test: `test_a_stamp_rounded_by_javascript_still_matches` (a rounded stamp
matches; different content, different length and a 10 ms change still conflict).

### Navigating to a pane took two clicks and knew nothing about typing

⌘K searched files only, so typing "jobs" returned capture JSON. The palette is now the shortcut
layer: with nothing typed it lists all **11 panes**, and typing filters places and files
together, places first.

| step | before | after |
|---|---|---|
| go to Jobs from anywhere | 2 clicks (area, then pane) | `⌘K` + `jobs` + `Enter` → `#/search/jobs` |
| what does ⌘K offer with no query | "Search names and text." | 11 places, `Folder` … `Opportunity` |

The palette also leaked the index's own markup: a row read `NZ Government <mark>Jobs</mark>
listing`. Snippets now render a real `<mark>`, windowed to 160 characters around the match, so
`<mark>` count is 1 and the literal string is gone.

### The status bar described a mode the document was not in

In Edit mode it said "Markdown preview. Press Edit to type." The `Viewer` now reports its mode
up, and the line reads "Editing. Press ⌘S to save." while the editor is open.

### Copy that belonged to a log, not a person

`grep "(s)"` found the placeholder plural in **15 UI strings** and **21 engine/CLI strings**
that reach the same screens (landing blockers, agent brief, audit checks, verify gate details,
handback errors). All now go through `plural(n, 'row')` in `src/dossier/copy.py` and
`count(n, 'row')` in `ui/src/lib/copy.ts`; `humanise()` puts `applied_roles` back to "Applied
roles" in the identity table. The two remaining `(s)` are developer `ValueError` text in
`tailor.py` and the recipe validator, which a user never reads.

### Friction measured after the fixes

```
cold load -> one next action      0 clicks      "Waiting on you: Build" + Open Build
reach pane nav by keyboard        4 tab stops   Files, Search, Papers
go to Jobs from anywhere          ⌘K + "jobs" + Enter
search -> open a document         ⌘K + 6 chars + Enter     50 results, 1 tab
edit -> saved                     ⌘S            200, dirty cleared
restore the newest copy           2 clicks + 1   (grouped: 45 copies in 2 groups)
build from a template             1 pick + 1     lists the folder's real .docx files
every visible control responds    10/10          no dead controls
```

Gates re-run after these changes: **439 passed** · `measure.py` all zeros · `inspect.mjs` 0
findings · `sloplint` 0 FAIL / 0 REFLEX · `a11y.py` clean · build 303 ms.

### Searching for a name you can see

The palette ranked by the index's own body-text score, so typing a filename returned documents
that merely *mention* it:

| query | before | after |
|---|---|---|
| `_verify_report` | `_verify_letters.py` first (a body match) | `_preview/_verify_report.json` first |
| `Ayers_Resume_AccountingSpendingCategorisation` | 5 unrelated files | the `.docx`, `.docx` letter and `.pdf` with that name |
| `resume` | `verification-search-batch.json` first | `resume.md` first |

`db.search()` now answers **path matches first**, in full, then body matches, de-duplicated.
The path clause is `rel LIKE ? ESCAPE '\'` with the wildcards escaped, so a typed `%` or `_` is a
character, not a pattern. Measured against the live index: 3 queries above.

Gates after this change: **439 passed**, `measure.py` all zeros, Lighthouse **99 / 100 / 100**
(FCP 1.4 s, LCP 2.1 s, CLS 0), `inspect.mjs` 0 findings, `sloplint` 0 FAIL / 0 REFLEX,
`a11y.py` clean.
