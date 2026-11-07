# Design pass — "too much text and subtext" — 2026-11-05

The complaint was visual, so every claim here is a number read from the rendered page or
from a linter run, not an opinion about taste. Register `surface`, mode `Operate`
(`frontend-superskill` §1), spine `impeccable` (`distill` + `clarify`), operator rule
"Omit, Do Not Hide" (`~/.commandcode/taste/taste/taste.md`).

## What was measured, before and after

Instrument: `~/.dsh/scratch/dossier-live-2026-11-05/density.py` — visible words inside
`<main>` per pane, paragraph counts, the longest paragraphs, and the number of `·`/`—`
separators in the rendered text. Same 244-entry workspace copy, same 1440×900 viewport.
The before column is the printed output of the same script run against the pre-pass build;
the after column is `density.json` from the post-pass run (2.2 s settle, so the async task
packet has rendered).

| pane | words before | words after | notes |
|---|---|---|---|
| Folder | 112 | 84 | welcome paragraph removed; the next-unit strip carries the fact |
| Capture | 112 | 57 | lead deleted, recipe/CLI instructions deleted |
| Jobs | **24,882** | **642** | table pages 50 rows at a time |
| Identity | 391 | 339 | lead deleted; 16 field labels remain (they are labels) |
| Build | 49 | 17 | lead deleted |
| Verify | 73 | 34 | lead deleted |
| Audit | 250 | 222 | three copies of the same lead deleted; check details are data |
| Trash | 345 | 330 | retention/CLI sentence shortened; rows are data |
| Sync | 68 | 6 | lead and trailing explanation deleted |
| Loop | **2,805** | **1,094** | 18 gate rows collapsed into `<details>`; system prompt behind a disclosure; manifest summary removed |
| Opportunity | 137 | 103 | lead deleted |
| **total** | **29,224** | **2,928** | **−90 %** |

Separators (`·` / en dash in rendered text): **141 → 8**. The 8 that remain are inside
generated content (the task packet and pay strings), not interface copy.

Other numbers, same build:

| measure | before | after |
|---|---|---|
| `sloplint --scope app` | 2 REFLEX, 11 WARN | **0 REFLEX, 3 WARN** |
| `lint.mjs --app` | 0 FAIL, 5 WARN | 0 FAIL, 5 WARN (all waived, unchanged) |
| `measure.py` (1440/768/390) | all zeros | all zeros (contrast, targets, unnamed, overflow, one `h1`) |
| panes whose `h1` matches its tab label | 5 / 11 | **10 / 11** (Folder keeps the authored empty-state line) |
| console errors / failed requests | 0 | 0 |
| shell interactive | 345 ms | **163 ms** |
| `text-wrap: balance` on display heads | 0 rules | h1 + h2 + trajectory head |
| `::selection` / caret / scrollbar themed | no | yes |

## Which reels told me this, and where each rule landed

The frontend hub's anti-slop floor is assembled from these digests
(`reelkit/DIGESTS.md`); each row below is a rule that was **violated** in this build and is
now applied, with the mechanism that proves it.

| Reel | Rule | Violation found here | How it was fixed | Proof |
|---|---|---|---|---|
| §32 `Dd9R75ej5jv` slide 1 | `text-wrap: balance` is *the* fix for "technically fine, still looks AI-made" | 0 uses in the whole stylesheet | added to `h1, h2` and the trajectory head | `sloplint` F3 gone |
| §51 `DfC3_uyAuWY` tell 3 | a one-line subtext under **every** header is the monotonous rhythm tell | **11 of 11 panes** had `h1` + explanatory sentence | every pane lead deleted | density: 29,224 → 2,928 words |
| §48 `DcrqbqZRVvC` tell 5 | no coloured `border-left` cards | 5 (`agent-next`, blockers, 3 trajectory states) + `.notice` | 1–3 px side stripes replaced by a top hairline or a full 1 px box | `sloplint` "side stripe" WARNs → 0 |
| §48 tell 15 / §32 | inconsistent spacing | `margin: 10px`, `margin-right: 6px` | moved to the 4 px scale | `sloplint` REFLEX → 0 |
| §48 tell 16 / `better-writing` | em-dash habit in prose | 7 (waived, comments only) | unchanged, deliberately | `lint.mjs` `[em-dash]` |
| §49 `DdS5oHtPvcA` tell 5 | the tab title must say where you are | one fixed `<title>Dossier</title>` | `document.title = "<pane> \| Dossier"` on every pane change | measured: `Jobs \| Dossier` → `Build \| Dossier` |
| §49 tell 19 | console full of errors | 0 | 0 | walk listener records 0 |
| `hallmark` F7 | six selectors sharing one container recipe is a "same box" tell | 6 (trajectory toolbar + form) | toolbar flat, form filled and heavier | `sloplint` F7 gone |
| `craft-floor` | theme text selection, caret and scrollbars | all browser defaults | `::selection`, `caret-color`, `scrollbar-color` from the palette | CSS in `tokens.css` |
| `craft-floor` | no middle-dot meta strings (`A · B · C`) | 141 | commas, separate elements, or deleted | density separator count |

## Where the text went

Not deleted and lost — moved to where it answers a question the reader already has:

- **Gates (Loop).** 18 rows × (rule + what is never allowed) were rendered as a table of
  paragraphs. Now: 18 one-line `<summary>` rows; the rule, the "never" and the enforcing
  symbol are one click away, still on screen, still searchable by the browser's own find.
- **System prompt (Loop).** Was always rendered (thousands of words). Now behind a
  `<details>`, with Copy still outside it.
- **Jobs.** 24,882 words was the whole corpus in the DOM. Now 50 rows and a
  "Show 50 more" button; the count line says `Showing 50 of 554` so nobody thinks the
  corpus shrank.
- **Pane leads.** Deleted, not hidden: the pane label and the data say the same thing
  faster. Nothing factual was lost — the two facts worth keeping (the missing `.docx`
  blocker and "Read-only. It never changes a file.") survive as the next-unit strip and a
  one-line note.

## What still reads heavy, measured and not fixed

- **Loop** carries 1,094 visible words, but ~1,000 of them are the generated task packet,
  which is the reason the pane exists.
- **Trash (330), Identity (339) and Audit (222)** are now dominated by data and field
  labels rather than prose; cutting further would delete facts.
- **Opportunity** still has three create/edit forms with their own labels (103 words).
- **`.doc-prose blockquote` keeps a 2 px rule** — a document convention, waived in
  `.ui-ux-master/waivers.md`, not a card.
- **Screenshots were taken and not looked at** by a person or a vision model in this
  session. Every number above is DOM-measured; the visual judgement remains the owner's.

## Reproduce

```powershell
cd ui; npm run build
.venv\Scripts\python.exe .ui-ux-master\measure.py                      # contrast, targets, overflow
node ~/.dsh/skills/hallmark/scripts/sloplint.mjs ui/src --scope app     # 0 FAIL, 0 REFLEX, 3 WARN
node ~/.dsh/skills/taste-skill/scripts/lint.mjs ui/src --app            # 0 FAIL, 5 WARN (waived)
%TEMP%\..\dossier-live-2026-11-05\density.py http://127.0.0.1:8077      # words per pane
.venv\Scripts\python.exe -m pytest -o addopts="" -q                     # 426 passed
```
