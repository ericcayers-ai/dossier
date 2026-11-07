# Dossier — design brief

**One-line job of this app:** open any file in a working folder, understand it in context, change it, and move it forward — without leaving the folder or opening five programs.

**Subject grounded (snapshot, 2026-09-12):** the proving-ground folder is
`<resume-corpus-root>` — 374 files, 22.9 MB: 108 `.json`,
85 `.pdf`, 73 `.md`, 62 `.docx`, 37 `.png`, 5 `.py`, 2 `.csv`, 1 `.zip`. These are the figures
this brief was written against and are left as written. **They are a dated snapshot, not a
current measurement.** Re-measured 2026-10-11 the same folder (still excluding `.dossier/`)
holds **728 files, 83.3 MB** — 337 `.json`, 120 `.md`, 99 `.pdf`, 76 `.docx`, 70 `.png`,
8 `.py`, 7 `.txt`, 5 `.js`, 3 `.zip`, 2 `.csv`, 1 `.bak-20260920`. The app is general-purpose;
this folder is what it must survive on day one.

**Audience:** one person, on one Windows machine, working on their own material. No multi-user, no cloud, no accounts.

---

## The one true observation about this data

Nothing in this folder is a lone file. Every unit of real work is a **set**:

```
Northbridge-TechnicalSupportEngineer
├─ job-posting-Northbridge-TechnicalSupportEngineer.md      (source)
├─ keywords-Northbridge-TechnicalSupportEngineer.md         (analysis)
├─ keyword-gap-Northbridge-TechnicalSupportEngineer.json    (analysis)
├─ diagnosis-Northbridge-TechnicalSupportEngineer.md        (analysis)
├─ jd-gap-input-Northbridge-TechnicalSupportEngineer.md     (analysis)
├─ workflow-Northbridge-TechnicalSupportEngineer.md         (analysis)
├─ sample_resume_Northbridge_TechnicalSupportEngineer_Sep2026.docx        (artifact)
├─ sample_resume_..._CoverLetter.docx                                   (artifact)
├─ sample_resume_..._Sep2026.pdf  +  _CoverLetter.pdf                   (render)
├─ layout-pdfs-2026-09-12/…                                            (render)
└─ rendered-…/…-page-1.png, -page-2.png                                (proof)
```

A conventional file explorer shows that as 12 unrelated rows scattered across three folders and two naming conventions. That is the actual problem being solved.

**Signature element: the Bundle Rail.** Select any file and a right rail resolves and shows its whole set — every sibling that shares a normalized stem, grouped by role (source / analysis / artifact / render / proof), each openable in one click, with the set's state visible at a glance (does the `.docx` have a current `.pdf`? is the render newer than the source?). The rail is the one thing this app is remembered for. Everything else stays quiet.

The stem normalizer is data-derived, not clever: strip the known prefixes (`job-posting-`, `keywords-`, `keyword-gap-`, `diagnosis-`, `jd-gap-input-`, `workflow-`, `skill-gap-`), strip the known suffixes (`_CoverLetter`, `-page-N`, date stamps `-YYYY-MM-DD` / `_MmmYYYY`), fold `_` and `-` and case. Bundle rules live in a per-folder `.dossier/bundles.json` so a different folder gets different rules without touching code.

---

## Visual direction

The review loop this folder already encodes is: generate → render to PNG → **look at it**. That is a light table — a backlit sheet you lay work on to inspect it. The interface is the light table; the documents are the only things with color.

Deliberately not: warm cream + high-contrast serif + terracotta; near-black + one acid accent; broadsheet hairline columns. Those are the three current AI defaults and none of them is a choice here.

### Color — OKLCH, cool neutral ground, one signal hue

| Token | Light | Dark | Use |
|---|---|---|---|
| `--ground` | `oklch(0.97 0.006 250)` | `oklch(0.21 0.012 255)` | app background — the table surface |
| `--sheet` | `oklch(0.995 0.004 250)` | `oklch(0.26 0.012 255)` | document/panel surface — the sheet on the table |
| `--ink` | `oklch(0.24 0.02 260)` | `oklch(0.94 0.008 250)` | primary text |
| `--ink-quiet` | `oklch(0.52 0.02 260)` | `oklch(0.70 0.014 255)` | metadata, paths, timestamps |
| `--ink-inverse` | `oklch(0.99 0.003 250)` | `oklch(0.16 0.012 255)` | text on a filled control |
| `--rule` | `oklch(0.90 0.008 255)` | `oklch(0.34 0.014 255)` | 1px separators only |
| `--control-edge` | `oklch(0.64 0.01 255)` | `oklch(0.56 0.014 255)` | control borders (≥3:1 non-text) |
| `--signal` | `oklch(0.62 0.17 255)` | `oklch(0.72 0.15 255)` | selection, focus ring, active tab |
| `--signal-strong` | `oklch(0.50 0.17 255)` | `oklch(0.60 0.16 255)` | the filled primary's own fill |
| `--signal-ink` | `oklch(0.53 0.17 255)` | `oklch(0.72 0.15 255)` | text in the signal hue |
| `--signal-soft` / `-soft-strong` | 11% / 17% signal wash | ditto | selected row, active chip |
| `--stale` | `oklch(0.57 0.16 62)` | `oklch(0.78 0.15 62)` | amber: stale render, unsaved buffer, overdue |
| `--stale-ink` | `oklch(0.47 0.15 62)` | `oklch(0.80 0.14 62)` | the amber as *small* text on either surface |

`--sheet` carries chroma so no surface is pure white; every neutral is tinted toward the
anchor hue. `--stale` is the only warm thing on screen, so an out-of-date render is visible
from across the room.

Only two chromatic tokens exist. `--stale` is the only warm thing on screen, so an out-of-date render is visible from across the room. Body text ≥4.5:1 on `--sheet` in both themes; no gray-on-color text anywhere.

Measured, not assumed — these ratios are computed from the OKLCH values above:

- `--ink` on `--sheet`: **16.45:1** light, **13.03:1** dark. The body-text bar holds with room to spare.
- `--stale` used as *text* (the freshness label) was **2.78:1** in light, below the bar. Its light lightness moved `0.70 → 0.57` for **4.65:1** at the same hue and chroma; dark was already 7.49:1 and is untouched. Amber stays amber, it is simply legible now.
- **The primary button was a recorded trade-off, and is no longer one.** White on `--signal`
  measured **3.68:1** light and **2.49:1** dark. The label is now `--ink-inverse` on
  `--signal-strong` (same hue, one step darker): **5.6:1** light, **6.9:1** dark. `--signal`
  keeps its lightness because it still carries the focus ring and the selection bar, where
  3:1 is the bar and it clears it.

### Type — pair on contrast axis, not two sans-serifs

- **UI / labels / chrome:** Inter Variable, 13px base, `-0.006em` tracking. Utility, not personality.
- **Document prose (Markdown render):** Source Serif 4, 17px / 1.62, measure capped at 68ch. The reading pane is the only place with a serif, and the shift signals "you are now reading content, not chrome."
- **Code / JSON / CSV / paths:** JetBrains Mono, 13px, `tabular-nums`.

Scale: 11 / 13 / 15 / 17 / 21 / 28. Six sizes, no clamp() heroics — this is a tool, not a landing page. Section headings are sentence case, weight 600, never uppercase-tracked eyebrows.

### Layout

Two header rows, because eleven panes in one strip had no hierarchy and clipped at 1100 px.
A **row of five areas** (Files, Search, Papers, Housekeeping, Agent) and, beneath it, the
tabs of the active area. Nothing else is mounted: an area shows only its own panes.

```
┌──────────────────────────────────────────────────────────────────────┐
│ Dossier   [Files][Search][Papers][Housekeeping][Agent]   ⌘K   ◐       │ 44px
│            Capture   Jobs   Identity                                 │ 34px area tabs
├────────────┬───────────────────────────────────┬─────────────────────┤
│ EXPLORER   │  VIEWER / PANE                    │  BUNDLE RAIL        │
│ 260px      │  flex — one document, full focus  │  300px, collapsible │
├────────────┴───────────────────────────────────┴─────────────────────┤
│ API ready · Ready · path · ⌘\ explorer · ⌘/ rail · ?                 │ 28px
└──────────────────────────────────────────────────────────────────────┘
```

Three columns, fixed roles, no floating panels, no nested cards. Both side columns collapse
(`⌘\`, `⌘/`); below 1000 px the rail is a slide-over and below 700 px so is the explorer,
and a closed slide-over is `inert` rather than merely translated off-screen, so it leaves
the tab order with it.

Panels are separated by 1px `--rule` and a change of surface, not by shadow, radius or glass.
`border-radius: 4px` on interactive controls only; panels are square, because the sheets on a
light table are square.

Every pane is one page at `--pane-pad-y`/`--pane-pad-x` with one `h1`, and its heading stays
on screen while the body loads (a skeleton holds the shape, so nothing jumps when the answer
lands).

### Motion

Four named movements, each answering an action: `--dur-1` (90 ms) on a control's state,
`--dur-2` (140 ms) on a slide-over or a skeleton's first paint, a one-shot 400 ms `--stale`
pulse when a background job marks a render stale, and a 1 px press on `:active`. One easing,
`--ease-out` (`cubic-bezier(.2,.6,.2,1)`). No page-load choreography, no scroll reveals, no
hover physics, no `transition: all`, and no animation of a layout property: the panel collapse
is instant because animating a grid track reflows the document every frame.

`prefers-reduced-motion: reduce` sets every animation and transition to 0 ms and removes the
pulse; measured under the reduced-motion context, `.skeleton` computes `animation-duration: 0s`.

### Spacing, targets and states

- One 4 px scale: `--s1` 4 · `--s2` 8 · `--s3` 12 · `--s4` 16 · `--s5` 20 · `--s6` 24 ·
  `--s8` 32 · `--s10` 40 · `--s12` 48 · `--s16` 64. Every padding, margin and gap names a
  step; the 134 off-scale values the gate found were moved onto it.
- Chrome heights are tokens (`--top-h` 78, `--status-h` 28, `--pane-head-h` 42), not numbers
  repeated in subtractions.
- Every control has a 24×24 px target (WCAG 2.5.8) and nine states: rest, hover (gated by
  `@media (hover: hover)` through the pointer media query), `:focus-visible` (2 px ring,
  2 px offset, instant), `:active`, `:disabled` (0.62 opacity + `not-allowed`), loading,
  empty, error, and long content (`min-width: 0` + `overflow-wrap: anywhere`).
- The theme attribute lives on `<html>`, not only on `.app`: `body` sets `color: var(--ink)`,
  and an inherited value is not re-resolved inside a subtree, so a dark `.app` used to keep
  the light ink it inherited. Measured before the fix: 233 text/background pairs under 4.5:1
  in dark; after: 0.

### Copy

Buttons name their effect and keep the name through the flow: "Export to PDF" → "Exporting…" → "Exported to `layout-pdfs-…`". Errors state cause and the next move: *"Word is busy with a dialog — close it and press Re-render."* Empty explorer says *"No files match `resume 2026`. Clear the filter or search all text (⌘K)."* Never "Submit", never "Oops", never a toast that only says "Success".

---

## Product principles (what keeps it uncluttered)

1. **Read is free, write is explicit.** Nothing is written without a keystroke the user aimed. No autosave-over-source, no silent reformatting, no background rewrites.
2. **Never the only copy.** Every destructive or overwriting action routes through `.dossier/trash/` with a timestamped copy. There is no hard delete in the UI.
3. **The folder is the database.** The SQLite index is a cache that can be deleted and rebuilt at any time. No state lives only in the app.
4. **One document at a time in the centre.** Everything that wants to be a second pane becomes a rail item instead.
5. **Actions are declared, not hard-coded.** Every button in the rail is a row in `.dossier/actions.json` (label, command, inputs, outputs, confirm?). Adding a capability is adding a row, which is why this stays an ecosystem rather than a pile of features.
6. **Say what you can't do.** DOCX→Markdown is lossy; PDF→DOCX is extraction, not conversion. Export routes are labelled with their fidelity class (faithful / semantic / extracted) before the user clicks, not after.

---

## Verified environment constraints (measured on this machine, 2026-09-12)

> **Reading rule.** This whole section is a dated snapshot taken on **2026-09-12** and is left
> as written. Anything a later reader measures differently is drift, not a typo — do not
> silently overwrite a number here; add a dated note beside it. The one correction made in this
> section (the DOCX→PDF route, 2026-10-11) is marked inline because it was wrong on the day it
> was written, not merely stale.

| Fact | Receipt | Consequence for the design |
|---|---|---|
| Word installed | `C:\Program Files\Microsoft Office\root\Office16\WINWORD.EXE` exists | DOCX→PDF is available today via Word COM automation. **Corrected 2026-10-11:** the authoritative path is a *private* Word instance (`win32com.client.DispatchEx` + `ExportAsFixedFormat`) in `src/dossier/engine/render.py`, not `docx2pdf` — see `README.md` and `render.py:1-13`. Two divergent paths still exist in code: `src/dossier/convert.py:117-125` still calls `docx2pdf.convert(..., keep_active=True)` and `/api/render` routes through it, while the CLI uses `DispatchEx`. Making one path authoritative is a backend change (worker A's A11); this brief records the intended one. |
| `docx2pdf` present | imports from `…\Python313\Lib\site-packages\docx2pdf\__init__.py` | Present, but **not the primary export route** — `render.py:3-13` exists specifically because `docx2pdf` attaches to a stale registered Word instance. No install needed for the primary route. |
| LibreOffice absent | `glob('C:\Program Files\LibreOffice\program\soffice.exe')` → `[]` | `soffice` is a **fallback**, not the primary path. The published stack research assumed the reverse; that recommendation is overridden. |
| pandoc absent | `shutil.which('pandoc')` → `None` | MD↔DOCX ships via `python-docx` + a bundled writer; pandoc is an optional detected enhancement. |
| `pdftoppm` absent | `shutil.which('pdftoppm')` → `None` | PDF→PNG uses PyMuPDF (`fitz`), already importable. |
| PyMuPDF, python-docx, fastapi, uvicorn, watchfiles, pdfplumber, pypdf, Pillow, jinja2, openpyxl, pandas all import on `python3` (3.13.15) | single import line returned `ALL_OK` | Backend needs no new Python dependencies except the app itself. |
| SQLite 3.50.4 with FTS5 | `create virtual table t using fts5(x)` → `FTS5_OK` | Full-text index needs no extension. |
| Node v24.19.0 / npm 12.0.2, no global vite/react | `node --version`, `npm ls -g` | Frontend builds locally; Vite 8 requires Node ≥22.12 — satisfied. |
| **35.8 GB free on C:** | `GetDiskFreeSpaceExW` | Hard budget. No Electron, no Monaco (≈98 MB unpacked), no Chromium download. CodeMirror + a pinned dependency set only; `node_modules` target under 400 MB and removable after build. |
| Word is the only renderer | — | Export jobs must be serialized (one COM call at a time) and must fail loudly if Word raises a modal dialog. |

---

## Domain overlay: the job-search pane

The folder is a job-search workspace, so the app carries one optional domain pane. **Corrected
2026-10-11:** the enablement gate `.dossier/domain=job-search` described here is implemented
nowhere — a repo-wide search finds that string only in this line, and no module reads it. The
pane's real gate is that `ui/src/App.tsx` renders its jobs/pipeline views against
`/api/jobs`-backed state; it is not conditional on a marker file. Recorded as
intended-not-built rather than deleted, so the next reader knows the marker path was a plan.

- **Pipeline** — reads `job-history.md` (the canonical tracker; the app never becomes the source of truth), shows counts per status, and marks nothing `applied` that the log doesn't already say is applied.
- **Jobs table** — `all_boards_data/all_jobs.json` as a filterable grid: fit, source, work type, pay band, location. **Corrected 2026-10-11:** the record count here was 600; the file now holds **1,789 rows** (2,120,866 B, measured 2026-10-11). The `nz-job-search-coverage-2026-09-12.json` citation is unchanged and was not re-verified.
- **Due list** — runs the existing `followup_cadence.py` and shows urgent/overdue/cold, read-only.
- **Feeds** — read-only adapters for the public board endpoints I verified returning HTTP 200 from this machine today: Greenhouse `boards-api`, Lever `api.lever.co/v0/postings`, Ashby `posting-api`, Himalayas, Remotive, Arbeitnow. Each adapter carries a `policy` field (`official_public` / `partner_only` / `manual_only` / `prohibited`); LinkedIn, Indeed, Glassdoor, SEEK listings and generic Workday portals are registered as `prohibited`/`manual_only` and the runner refuses to execute them. That refusal is a feature of the design, not an omission.

The pane is a *view over existing files plus permitted public endpoints*. It never mutates a resume, never submits an application, and never writes a status the user did not confirm.
