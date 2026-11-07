# UI/UX pass — handoff (2026-11-04)

Run with `ui-ux-master` (P0–P7), register `surface`, mode `Operate`. Refine, not replace.

## What shipped

**Shell.** Two-level navigation: five areas (Files, Search, Papers, Housekeeping, Agent), each
mounting only its own panes. Eleven flat buttons in one strip clipped at 1100 px and had no
hierarchy; the header now reads as a place, then a tab. The two narrow-width drawer toggles
moved into the pane row, so the area strip no longer overlaps its own controls at 390 px. A
closed drawer is `inert`, not merely translated off-screen, so it leaves the tab order.

**Tokens.** A 4 px spacing scale (`--s1…--s16`), named chrome heights (`--top-h` 78,
`--status-h` 28, `--pane-head-h` 42, `--pane-pad-x/y`), `--ink-inverse`/`--signal-strong` for a
legible filled primary (3.68:1 → 5.6:1), `--stale-ink` for small amber text (3.84:1 → 4.9:1),
`--signal-soft`/`--stale-soft` washes, `--overlay-shadow` (overlays only), `--z-scrim|panel|palette`,
`--dur-1|--dur-2` with one easing. 157 off-scale spacing values were moved onto the scale.

**Dark mode was broken and is fixed.** `body { color: var(--ink) }` resolves at `body`, and an
inherited custom property is not re-resolved inside `.app[data-theme="dark"]`, so the dark UI
kept the *light* ink: 233 text/background pairs under 4.5:1. The theme attribute now lives on
`<html>`; measured 0 failures after.

**States.** One `Loading` (skeleton, layout-preserving), one `ErrorState`, one `EmptyState`
(now actually used), and every pane keeps its `h1` while its body loads. Jobs and Identity got
real `role="tabpanel"`s with `aria-controls`; the palette’s buttons are a list, not fake
`role="option"`s; the tree exposes `aria-level`.

**Copy.** `PARTIAL` → `Partial`, enum leakage and CLI instructions out of prose, `n/a` instead of
a bare dash in table cells, 67 → 7 em dashes.

**Bugs found by measuring, not looking:** the dark-ink inheritance above; a stale API response
(a written document did not appear in the tree until a hard reload — now `Cache-Control:
no-store` on `/api/*`); the 390 px header overlap; `--top-h` used but never defined; a
`status_counts` dereference behind a guard that did not cover it; the Opportunity node’s
default state had no visual rule.

## Receipts

```text
node <home>\.dsh\skills\taste-skill\scripts\lint.mjs ui/src --app        # 0 FAIL, 5 WARN
node <home>\.dsh\skills\hallmark\scripts\sloplint.mjs ui/src --scope app # 0 FAIL, 0 REFLEX
.venv\Scripts\python.exe .ui-ux-master\measure.py                               # the numbers below
.venv\Scripts\python.exe -m pytest -o addopts="" -q                             # 394 passed
```

Measure, after the pass (before: 1 contrast fail, 41 sub-24 px targets, 233 dark failures):

```text
1440 / 768 / 390 px   contrast 0 · targets 0 · unnamed 0 · overflow 0 · one h1 per pane
dark 1440px           contrast 0
keyboard (30 stops)   30 ringed, 0 off-screen
reduced motion        .skeleton animation-duration 0s
console               0 errors (the 33 notices are the instrument's own canvas readback)
```

Screenshots: `.ui-ux-master/receipts/p5/` (33: 11 panes × 3 widths + `dark-1440.png`) and the
pre-pass set in `receipts/p0/` for comparison.

**Not looked at by a human or a vision model.** Every claim above is a number read from the
rendered DOM; this model has no image input. The screenshots are the artefact a person should
check, at 1440, 768, 390 and in dark.

## Still open

- Five input surfaces and two table designs; the paddings and fonts are now on-scale, the
  components are not merged. `.result-line` is still a 3-column grid with per-pane overrides.
- `--move` is an alias kept for older rules; `--s5/--s8/--s12/--s16` are defined and used
  sparingly.
- No Lighthouse run (the app is `127.0.0.1`-only and the audit is DOM-measured); an SEO/metadata
  pass is irrelevant for a local app, but `index.html` still has a single generic `<title>`.
- Motion is still minimal by design; no scroll or entrance choreography was added.

## Re-run

```powershell
cd ui; npm run build
.venv\Scripts\python.exe .ui-ux-master\measure.py
node ~/.dsh/skills/taste-skill/scripts/lint.mjs ui/src --app
node ~/.dsh/skills/hallmark/scripts/sloplint.mjs ui/src --scope app
.venv\Scripts\python.exe -m pytest -o addopts="" -q
```

## 2026-11-05 — density and copy pass

Owner report: "too cluttered… too much text and subtext". Measured, not eyeballed:
visible words inside `<main>` went **29,224 → 2,928** across the 11 panes (−90 %), Jobs
24,882 → 642 by paging the corpus 50 rows at a time, Loop 2,805 → 1,094 by turning the
18-row prose gates table into `<details>` rows and putting the system prompt behind a
disclosure. Separators (`·`) 141 → 8. `sloplint` 2 REFLEX → **0**; the 11 pane leads
(`h1` + explanatory sentence, the `DfC3_uyAuWY` tell) are gone; `text-wrap: balance`,
themed selection/caret/scrollbars, and a per-pane `<title>` added. Receipt:
`docs/evidence/design-pass-2026-11-05.md`.

Pane headings now equal their tab labels except the Folder empty state, which keeps its
authored line. Any doc quoting the old headings ("Agent surface", "Workspace audit",
"AI sync prompt", "Opportunity tree", "Build from your template") is out of date.

Still not looked at by a human or a vision model. Screenshots are in
`.ui-ux-master/receipts/p5/` (pre-pass) and the live walk's `receipts/live-*.png`.
