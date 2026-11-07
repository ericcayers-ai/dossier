# Audit (P1) — measured baseline, then the same instrument after the pass

Two read-only lanes ran in parallel (a real-browser audit and a design-system code audit);
their reports are `.ui-ux-master/audit-browser.md` and `.ui-ux-master/audit-code.md`, and every
finding below was re-checked here with `.ui-ux-master/measure.py` (the script that remains in
the repo as the re-runnable instrument). The gate baseline at the start:

```text
taste-skill lint  (--app)                0 FAIL, 5 WARN
hallmark sloplint (--scope app)         14 FAIL, 134 REFLEX, 13 WARN
```

## P0 — blocks use or is unsafe

| # | Finding | Evidence | Status |
|---|---|---|---|
| P0-1 | `--top-h` used by `.rail`, `.explorer`, `.scrim`, defined nowhere → invalid at computed-value time, so the slide-overs lost their top edge and the scrim lost its top | code audit P0-1, `tokens.css` | fixed: `--top-h` (78), plus `--status-h`, `--pane-head-h`, `--pane-pad-*` |
| P0-2 | `.state-planned` (the default for every new Opportunity node) had no rule; `.trajectory-state` was dead | code audit P0-2 | fixed |
| P0-3 | two nav levels both rendered “Agent”, both `aria-current="page"` | code audit P0-3 | fixed: the pane is “Loop”; `aria-label` uses the area’s label |
| P0-4 | `counts.summary.status_counts` dereferenced behind a guard that did not cover it | code audit P0-4 | fixed: `?? {}` |
| P0-5 | **dark theme served light-theme ink**: `body { color: var(--ink) }` resolves at `body`, and inheritance does not re-resolve a custom property inside `.app[data-theme=dark]` | measurement: 233 pairs < 4.5:1 in dark | fixed: theme lives on `<html>`; dark now 0 failures |
| P0-6 | 41 controls under 24×24 px (chips, status-bar buttons, table sort buttons, one-word tabs) | browser audit: 40 occurrences / 6 controls; measurement: 41 | fixed: 24 px floor on buttons + chips + sort headers |
| P0-7 | the topbar overlapped its own controls at 390 px (Explorer toggle intercepted the nav) | Playwright click timeout at 390 | fixed: toggles moved into the pane row; area strip scrolls in its own container |

## P1 — visible defects

| # | Finding | Status |
|---|---|---|
| P1-1 | `.agent-kind.hybrid` at 3.84:1 (the single contrast failure) | fixed via `--stale-ink` (4.9:1) |
| P1-2 | 134 spacing values off the 4 px scale | fixed: 157 values moved onto the scale across 3 stylesheets |
| P1-3 | three different page paddings for sibling panes; agent/trajectory differed from the rest | fixed: one `--pane-pad-x/y` |
| P1-4 | a pane that dropped its `h1` while loading (Audit, Sync, Trash) | fixed: heading stays, body skeletons |
| P1-5 | `PARTIAL` shouted next to lowercase `complete`; enum values and CLI paths in prose | fixed: sentence case, user-facing wording, code spans for real paths |
| P1-6 | four empty-state implementations, and a fifth (`EmptyState`) that nothing imported | fixed: `EmptyState` used in Explorer and Jobs; `.empty` retained for inline table cells |
| P1-7 | tablists with `role="tab"` and no panel, no `aria-controls` (Jobs, Identity, Viewer) | fixed: ids, `aria-controls`, `role="tabpanel"` |
| P1-8 | `aria-label` on a `<pre>` with no role (ignored); `role="tree"` with no level; `role="option"` on buttons | fixed: `role="region" tabIndex`, `aria-level`, list semantics |
| P1-9 | `.primary` white-on-signal at 3.68:1, documented as an accepted trade-off | fixed: `--ink-inverse` on `--signal-strong` (5.6:1); DESIGN.md updated |
| P1-10 | stale API responses (a written document did not appear in the tree until a hard reload) | fixed: `Cache-Control: no-store` on `/api/*` |
| P1-11 | `DESIGN.md` contradicted the code on colour, motion and layout | fixed: the three sections rewritten to the shipped values |

## P2 — consistency debt, still open

- Nine declared tokens are consumed rarely (`--s5`, `--s8`, `--s12`, `--s16`, `--signal-soft-strong` in one rule); the scale is
  used where it matters and the rest are available, not enforced.
- Five input surfaces remain (`.filter`, `.field`, `.sync-text`, `.palette input`, trajectory forms); paddings and fonts are
  now on-scale but not yet one component.
- `.result-line` is still a 3-column grid with per-pane overrides; free text now wraps, the structure is unchanged.
- `--move` remains as an alias of `--dur-2` for older rules.

## The instrument, after the pass

```text
1440 / 768 / 390 px   contrast fails 0 · targets <24px 0 · unnamed controls 0 · overflow 0
                      h1 per pane 1 · console errors 0 (only the instrument's own canvas notices)
dark 1440px           contrast fails 0
keyboard              30 tab stops, 30 with a visible ring, 0 off-screen
reduced motion        .skeleton animation-duration: 0s
taste-skill lint      0 FAIL, 5 WARN   (3 answered/waived in waivers.md)
hallmark sloplint     0 FAIL, 0 REFLEX, 12 WARN
```

## P8 — 2026-11-05: density and copy (the "too much text" pass)

Triggered by the owner's report that the UI is "way too cluttered… too much text and
subtext". Measured with `.dsh/scratch/dossier-live-2026-11-05/density.py` plus the two
linters; full table and rule provenance in `docs/evidence/design-pass-2026-11-05.md`.

| # | Finding | Fix |
|---|---|---|
| P8-1 | Every one of the 11 panes opened with an `h1` plus an explanatory sentence — the `eyebrow + heading + subtext` reflex `DfC3_uyAuWY` names | leads deleted; the pane label and the data carry it |
| P8-2 | The Loop pane rendered all 18 gates as a table of paragraphs and the system prompt unconditionally: 2,805 words | gates are 18 `<details>` rows; prompt behind a disclosure: 1,094 words |
| P8-3 | Jobs rendered the whole corpus (24,882 words, 172 KB) | 50-row page with "Show 50 more" and `Showing 50 of 554` |
| P8-4 | 141 middle-dot meta strings | 8 remain, all inside generated content |
| P8-5 | 5 coloured side stripes + `.notice` (`2189`) + 3 trajectory states — the craft-floor ban | top hairline or full 1 px box |
| P8-6 | No `text-wrap: balance` anywhere: headings orphaned words | `h1, h2` + trajectory head |
| P8-7 | Selection, caret and scrollbars were browser defaults — the "assembled not built" tell | themed from the palette |
| P8-8 | Pane titles disagreed with their tabs ("Agent surface", "Workspace audit", "AI sync prompt", "Opportunity tree", "Build from your template") | 10/11 now equal the tab label |
| P8-9 | One fixed `<title>` on every route (`DdS5oHtPvcA` #5) | `document.title` follows the pane |

After: **0 REFLEX, 3 WARN** (sloplint; the 3 are waived), **0 FAIL, 5 WARN** (taste-skill;
all pre-existing waivers), `measure.py` still all zeros at 1440/768/390, dark 0 failures,
426 tests passing.

### P8b — coverage, semantics and the browser floor

Second pass on the same report ("did you do everything the reels digest told you"). Measured
with a new instrument, `a11y.py`, plus the live Vercel rules the `web-design-guidelines` skill
tells you to fetch. Full matrix: `docs/evidence/coverage-2026-11-05.md`.

| # | Finding | Fix |
|---|---|---|
| P8-10 | 2 px `--stale` box edge on the next-unit strip and both blocker rows: `inspect.mjs` reads those as *panel* borders (7.53:1 on the dark ground) | edge removed, state moved to colour on the words |
| P8-11 | Text within 8–12 px of the screen edge at 390 and 1440 | `.status`, `.topbar-main`, `.pane-nav` mobile paddings to 16 px |
| P8-12 | No skip link, `<main>` had no id | skip link (visible on focus) + `main#main-content` |
| P8-13 | 28 `<th>` without `scope` | `scope="col"`, including the sortable-header factory |
| P8-14 | `h1 → h3` jump in Opportunity | node titles `h2` |
| P8-15 | Palette claimed `role="list"`/`listitem` on buttons and pointed `aria-activedescendant` at nodes nothing announced | `combobox`/`listbox`/`option` + `aria-expanded` + `autocomplete` + `spellCheck={false}` + `…` placeholder |
| P8-16 | No meta description, no theme-colour | both added; theme-colour follows the toggle using the resolved `--ground` |
| P8-17 | `touch-action`, tap highlight, `overscroll-behavior`, native `select` colours, 749 painted tree rows, loss of unsaved edits on Ctrl+R, identifiers exposed to auto-translate | all fixed: `manipulation`, transparent tap highlight, `contain`, `select` colours, `content-visibility: auto`, `beforeunload` guard, `translate="no"` |
| P8-18 | The gate reported 33 console warnings the app never made (its own 1×1 canvas readback) | `willReadFrequently` on the probe; `console: 0` |
| P8-19 | The repo's own graph was stale (`graft check` failing) | rebuilt: 1,415 nodes, in sync |

After: `inspect.mjs` **0 findings** at 1440/768/390, `a11y.py` clean on 11 panes and 2 dialogs,
`measure.py` all zeros with `console: 0`, `sloplint` 0 REFLEX, `426 passed`, `cybersafe_scan` 0.

### P8c — 2026-11-06: Lighthouse, zoom, CLS, and the rules the hub had not opened

Round 2 of the same order. Instruments added: `zoom.py` (200% text, 0 clipped nodes in all 11
panes), `cls.py` (worst pane 0.0387), `drawers.py` (slide-over sits 1 px under the header at
390 px — accepted, a token change would make it 6 px worse where the header renders at 73),
and **Lighthouse 12** via `npx` with the Playwright Chromium.

| # | Finding | Fix |
|---|---|---|
| P8-20 | `aria-required-children`: `.tabs[role=tablist]` held no `role="tab"` while no document was open | tablist role is conditional; the viewer is a `tabpanel` with `aria-controls` |
| P8-21 | `label-content-name-mismatch`: the toggle said "Files" and was announced as "Show or hide the file explorer" (WCAG 2.5.3) | both toggles lead with the visible word |
| P8-22 | 710 KiB of uncompressed JS, 863 KiB of uncached assets | `GZipMiddleware(minimum_size=1024)`; `/assets/*` immutable for a year, `/api/*` stays `no-store` |
| P8-23 | `ux-copy` rule "label the button with the action": two `Cancel`, one `Close` | "Keep editing", "Do not run it", "Close the shortcuts" |

Lighthouse **63 / 94 / 100 → 92 / 100 / 100**, FCP 5.5 s → 2.4 s, LCP 6.7 s → 2.9 s.

### P8d — 2026-11-06: the performance work, guarded

`App.tsx` lazy-loads every pane plus `Viewer`/`Palette` (the 515 KB CodeMirror chunk was a
static dependency of the first paint); `Explorer.tsx` renders a 41-row window of 728 with
`role="presentation"` spacers and `aria-setsize`/`aria-posinset`. Lighthouse **92 → 99**, FCP
2.4 s → **1.4 s**, first-load bytes 298 → **106 KiB**, DOM 2,984 → **225**.

Five tests now pin behaviour that would otherwise fail silently: four end-to-end for the window
(rendered-rows vs the count label, scroll-to-end reaching `posinset == setsize`, 45 arrow keys
landing on `posinset=46`, filter resetting scroll and count) and one API test for
`cache-control: immutable` + `content-encoding: gzip` on `/assets/*` with `/api/*` still
`no-store`. Suite: **431 passed**.

### P8e — 2026-11-06: the reel digest, entry by entry

`docs/evidence/reel-matrix-2026-11-06.md` reads all 1,370 lines of `reelkit/DIGESTS.md` and
gives each of the **94** entries a verdict (13 applied, 16 honoured, 5 mapped, 1 filed, 59
N/A), with the 13 non-entry `##` headings named so 94 + 13 = the 107 `grep -c '^## '` reports.

Three real gaps closed, all with numbers:

| entry | gap | fix | proof |
|---|---|---|---|
| §7 | a labels sheet built from the owner's folder held real employer names one `git add -A` from publication | `.gitignore` rule + an invariant test over `git ls-files` | passes over 108 tracked files |
| §62/§66 | traversal and per-route auth were architectural claims, not tests | 5 hostile paths → 400; 52 API routes → 401 anonymously | `tests/test_api.py` |
| §70 | "no telemetry" was a promise | `telemetry.py` records every request origin | 38 requests, **0** external hosts |

Suite **434 passed**. `graft check` OK (1,427 nodes). `measure.py` console 0, 0 contrast
fails, 30/30 focus. `sloplint` 0 FAIL / 0 REFLEX. `ui/dist` ships **0** source maps.
