# Dossier — design brief

**One-line job of this app:** open any file in a working folder, understand it in context, change it, and move it forward — without leaving the folder or opening five programs.

**Subject grounded:** the proving-ground folder is `<workspace>` — 374 files, 22.9 MB: 108 `.json`, 85 `.pdf`, 73 `.md`, 62 `.docx`, 37 `.png`, 5 `.py`, 2 `.csv`, 1 `.zip`. The app is general-purpose; this folder is what it must survive on day one.

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
├─ Ayers_Resume_Northbridge_TechnicalSupportEngineer_Sep2026.docx        (artifact)
├─ Ayers_Resume_..._CoverLetter.docx                                   (artifact)
├─ Ayers_Resume_..._Sep2026.pdf  +  _CoverLetter.pdf                   (render)
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
| `--sheet` | `oklch(1 0 0)` | `oklch(0.26 0.012 255)` | document/panel surface — the sheet on the table |
| `--ink` | `oklch(0.24 0.02 260)` | `oklch(0.94 0.008 250)` | primary text |
| `--ink-quiet` | `oklch(0.52 0.02 260)` | `oklch(0.70 0.014 255)` | metadata, paths, timestamps |
| `--rule` | `oklch(0.90 0.008 255)` | `oklch(0.34 0.014 255)` | 1px separators only |
| `--signal` | `oklch(0.62 0.17 255)` | `oklch(0.72 0.15 255)` | selection, focus ring, active tab — cool blue, the backlight |
| `--stale` | `oklch(0.57 0.16 62)` | `oklch(0.78 0.15 62)` | amber: render older than its source, unsaved buffer, overdue follow-up |

Only two chromatic tokens exist. `--stale` is the only warm thing on screen, so an out-of-date render is visible from across the room. Body text ≥4.5:1 on `--sheet` in both themes; no gray-on-color text anywhere.

Measured, not assumed — these ratios are computed from the OKLCH values above:

- `--ink` on `--sheet`: **16.45:1** light, **13.03:1** dark. The body-text bar holds with room to spare.
- `--stale` used as *text* (the freshness label) was **2.78:1** in light, below the bar. Its light lightness moved `0.70 → 0.57` for **4.65:1** at the same hue and chroma; dark was already 7.49:1 and is untouched. Amber stays amber, it is simply legible now.
- **Known limit, accepted on purpose.** White on the `--signal` fill (`.primary`) is **3.68:1** light and **2.49:1** dark, and `--ink` is worse in dark (**2.09:1**). A `--signal` lightness that clears 4.5:1 for the label exists only near `L=0.01` in light — effectively black — which would delete the cool-blue backlight this brief is built on. The filled primary button therefore stays as it is: a taste-and-identity trade-off, not an oversight. Changing it means a much darker `--signal` in both themes, which also carries the focus ring and the selection highlight.

### Type — pair on contrast axis, not two sans-serifs

- **UI / labels / chrome:** Inter Variable, 13px base, `-0.006em` tracking. Utility, not personality.
- **Document prose (Markdown render):** Source Serif 4, 17px / 1.62, measure capped at 68ch. The reading pane is the only place with a serif, and the shift signals "you are now reading content, not chrome."
- **Code / JSON / CSV / paths:** JetBrains Mono, 13px, `tabular-nums`.

Scale: 11 / 13 / 15 / 17 / 21 / 28. Six sizes, no clamp() heroics — this is a tool, not a landing page. Section headings are sentence case, weight 600, never uppercase-tracked eyebrows.

### Layout

```
┌──────────────────────────────────────────────────────────────────────┐
│  ⌘K search            <workspace> ▸ layout-pdfs-2026-09-12       │ 44px
├────────────┬───────────────────────────────────┬─────────────────────┤
│ EXPLORER   │  VIEWER / EDITOR                  │  BUNDLE RAIL        │
│ 260px      │  flex — one document, full focus  │  300px, collapsible │
│            │                                   │                     │
│ tree       │  ┌ tab tab tab ─────────────────┐ │  source             │
│ filters    │  │                              │ │  analysis           │
│ saved      │  │  pdf / md / grid / code      │ │  artifact           │
│ views      │  │                              │ │  render ⚠ stale     │
│            │  └──────────────────────────────┘ │  proof              │
│            │                                   │  ── actions ──      │
│            │                                   │  open in Word       │
│            │                                   │  re-render PDF      │
│            │                                   │  export…            │
├────────────┴───────────────────────────────────┴─────────────────────┤
│ path · 4.2 KB · modified 2m ago · indexed          [job pane] [logs]  │ 28px
└──────────────────────────────────────────────────────────────────────┘
```

Three columns, fixed roles, no floating panels, no nested cards, no dashboard grid of identical tiles. Both side columns collapse to give the document the full width (`⌘\` and `⌘/`). The centre pane is always exactly one document — tabs, not tiles, because comparing two documents is a rare case served by a second window, not by permanently halving the reading area.

Panels are separated by 1px `--rule` and a change of surface, not by shadow, radius, or glass. `border-radius: 4px` on interactive controls only; panels are square, because the sheets on a light table are square.

### Motion

Almost none, and all of it functional: 120ms ease-out on panel collapse, 90ms on tab change, a 400ms `--stale` amber pulse *once* when a background job marks a render out of date. No page-load choreography, no scroll reveals, no hover physics. `prefers-reduced-motion: reduce` removes the pulse and shortens transitions to 0ms.

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

| Fact | Receipt | Consequence for the design |
|---|---|---|
| Word installed | `C:\Program Files\Microsoft Office\root\Office16\WINWORD.EXE` exists | DOCX→PDF is available today via `docx2pdf` (COM). |
| `docx2pdf` present | imports from `…\Python313\Lib\site-packages\docx2pdf\__init__.py` | No install needed for the primary export route. |
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

The folder is a job-search workspace, so the app carries one optional domain pane — off by default, enabled when `.dossier/domain=job-search`:

- **Pipeline** — reads `job-history.md` (the canonical tracker; the app never becomes the source of truth), shows counts per status, and marks nothing `applied` that the log doesn't already say is applied.
- **Jobs table** — `all_boards_data/all_jobs.json` (600 records, 8 sources verified in `nz-job-search-coverage-2026-09-12.json`) as a filterable grid: fit, source, work type, pay band, location.
- **Due list** — runs the existing `followup_cadence.py` and shows urgent/overdue/cold, read-only.
- **Feeds** — read-only adapters for the public board endpoints I verified returning HTTP 200 from this machine today: Greenhouse `boards-api`, Lever `api.lever.co/v0/postings`, Ashby `posting-api`, Himalayas, Remotive, Arbeitnow. Each adapter carries a `policy` field (`official_public` / `partner_only` / `manual_only` / `prohibited`); LinkedIn, Indeed, Glassdoor, SEEK listings and generic Workday portals are registered as `prohibited`/`manual_only` and the runner refuses to execute them. That refusal is a feature of the design, not an omission.

The pane is a *view over existing files plus permitted public endpoints*. It never mutates a resume, never submits an application, and never writes a status the user did not confirm.
