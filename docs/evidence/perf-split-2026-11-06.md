# Performance: per-pane chunks and a windowed explorer — 2026-11-06

Two things Lighthouse named twice and this repo had not fixed: the panes shipped as one
bundle with an editor nobody had opened, and the explorer put every file in the DOM. Both are
now measured before and after. Instruments: `virtual.py` (new, first-load requests + rendered
rows + keyboard/scroll behaviour), Lighthouse 12 (`npx`, Playwright Chromium), `measure.py`,
`inspect.mjs`, `a11y.py`, `zoom.py`, the 426-test suite.

## What was actually wrong

`App.tsx` imported `Viewer` statically, and `Viewer.tsx` imports `@codemirror/{view,state,commands}`.
So the **515 KB CodeMirror chunk was a static dependency of the first load**, fetched before
anyone had opened a document. `Explorer.tsx` rendered `flatten(tree).map(...)` — **728 buttons**
for a 260 px rail, 2,984 elements in the document.

## Measured before and after

| measure | before | after |
|---|---|---|
| Lighthouse performance | 92 | **99** |
| Lighthouse accessibility / best-practices | 100 / 100 | 100 / 100 |
| First Contentful Paint | 2.4 s | **1.4 s** |
| Largest Contentful Paint | 2.9 s | **2.1 s** |
| Speed Index | 2.4 s | **1.4 s** |
| total byte weight | 298 KiB | **106 KiB** (−64 %) |
| unused JavaScript | 160 KiB | **38 KiB** |
| DOM elements (`dom-size`) | 2,984 (score 0.5) | **225 (score 1)** |
| JS files fetched on first load | 2 (`index` + `codemirror`) | **1 (`index`)** |
| `.tree-row` elements in the DOM | 728 | **41** of 728 |

## The two changes

**1 · Every surface is its own chunk.** `App.tsx` keeps the shell (`Explorer`, `BundleRail`,
`NextStep`) eager and makes `Viewer`, `Palette` and the nine pane surfaces `lazy(() =>
import(...))`, behind one `Suspense` boundary whose fallback is the same skeleton rhythm as
`Loading` (`role="status" aria-busy="true"`, no `h1` — the arriving pane owns the heading).
Vite now emits 13 pane chunks (1.3–12.0 kB each) plus the 515 kB CodeMirror chunk that only
`Viewer` references.

**2 · The explorer renders a window.** The list was already flat (`flatten(tree.data)`), so the
rows became a slice of it: `start = floor(scrollTop / rowH) - 8`, `count = ceil(clientHeight /
rowH) + 16`, with two `role="presentation"` spacers so the scrollbar still measures all 728
rows. `aria-setsize` / `aria-posinset` keep the position announced for the rows that are not
mounted. `ResizeObserver` re-windows on resize; the row height is re-measured from the first
rendered row and **kept fractional**.

That last detail was a real bug found by measuring: Chrome lays the row out at **33.6 px**, and
rounding to 33 would accumulate 0.6 px × 728 = **437 px** of scroll error, so the scrollbar would
bottom out early and clip the last rows. `bottomFits` in `receipts/virtual.json` is the check:
at max scroll the row with `aria-posinset="728"` sits inside the viewport.

## Behaviour verified, not assumed

| check | result |
|---|---|
| first load | 8 requests, **1** JS file, `codemirror` absent (`virtual.py`) |
| DOM | 248 elements at 1440×900, 41 tree rows, count label still says `728 files` |
| scroll to the end | last rendered row `posinset=728`, `setsize=728`, fits the viewport |
| keyboard | click a row, 40 × ArrowDown → focus on `posinset=41`, in viewport, `role=treeitem` |
| filter | `harbourline` → 10 rows, count `10 files`, scroll reset to 0 |
| pane switching | `walk.py`: palette returns 12 results, deep link `#/papers/verify` → h1 `Verify`, 0 console messages, 0 failed requests, shell 166 ms |
| tests | **426 passed** (52 s) with lazy panes and the windowed rail |
| visual gates | `inspect.mjs` **0 findings**; `measure.py` all zeros, console 0; `sloplint` 0 FAIL / 0 REFLEX |
| 200 % text | `zoom.py` 0 clipped nodes, 0 px overflow (row height re-measured, not assumed) |

## Regression guards (they did not exist when the change was made)

A windowed list and a lazy boundary can both break silently, so each behaviour now has a
test rather than a screenshot:

| test | what it pins |
|---|---|
| `test_the_rail_renders_a_window_and_still_names_the_whole_folder` | ≤ 80 rendered rows while `.pane-count` says the true total, and `aria-setsize` equals that total |
| `test_scrolling_the_rail_to_the_end_reaches_the_last_file` | `aria-posinset` of the last rendered row equals the set size, and the row is not clipped by the rail's edge — this is the assertion that catches a rounded row height |
| `test_arrow_keys_move_focus_past_the_rendered_window` | click, 45 × ArrowDown → focus on `posinset=46`, in the viewport |
| `test_filtering_the_rail_resets_the_scroll_and_the_count` | filtering from the bottom lands at `scrollTop == 0`, count `10 files`, 10 rows |
| `test_the_built_assets_are_gzipped_and_cached_immutably` (`tests/test_api.py`) | `/assets/*` sends `cache-control: immutable` and `content-encoding: gzip`, `vary: accept-encoding`; `identity` returns the same bytes uncompressed; `/api/*` keeps `no-store` |

The fixture workspace grew a 120-file `archive/` so the window is real in the test, and the
older explorer assertion now filters before asserting, which is what the rail asks a person to
do. Suite: **431 passed** (14 end-to-end, 8 API).

## What is left, and why it is left

`unused-javascript` 38 KiB and `render-blocking-resources` are the remainder; the next real step
would be route-level prefetch or dropping the icon set, and neither is worth the code. The
`.tree` keyboard model is a roving `tabindex` over `role="treeitem"`, which is not the full
ARIA tree pattern (no `aria-expanded`, because this rail is a flat file list, not a folder
hierarchy) — that is a design decision recorded here rather than an oversight.

## Reproduce

```powershell
cd ui; npm run build                       # 13 pane chunks + codemirror split out
%TEMP%\..\dossier-live-2026-11-05\virtual.py http://127.0.0.1:8077
$env:CHROME_PATH="<home>\AppData\Local\ms-playwright\chromium-1248\chrome-win64\chrome.exe"
npx --yes lighthouse@12 http://127.0.0.1:8077/ --output=json --output-path=receipts\lighthouse.json `
  --only-categories=performance,accessibility,best-practices --chrome-flags="--headless=new"
.venv\Scripts\python.exe -m pytest -o addopts="" -q          # 426 passed
.venv\Scripts\python.exe .ui-ux-master\measure.py            # all zeros, console 0
```
