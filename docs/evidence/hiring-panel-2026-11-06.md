# The hiring panel — implemented, not filed

Source reel: <https://www.instagram.com/p/DFSN_zVS7G6/> (fetched 2026-11-06). Its claim, verbatim
from the caption: *"Each one scores you and quotes the exact line that made them say no. Then the
chair fixes it by rewriting your weakest parts."*

This is entry **§36** (`DeVIz_uS06F`) of the reel digest. Until today the matrix carried it as
*filed* — a product mode a UI pass could not satisfy. It is now built, and the matrix says so.

## What exists

| surface | artefact |
|---|---|
| engine | `src/dossier/engine/panel.py` — seven seats, a weighted score, and the chair's three rewrites |
| CLI | `dossier panel --resume <md/docx> [--posting <md>] [--role <text>]`, exits non-zero on a `fail` |
| API | `GET /api/panel?resume=&posting=&role=` (token-authenticated like every other route) |
| UI | a twelfth pane, **Agent → Panel**: score, seven seats, quoted lines, the chair's plan |
| manifest | mode `panel` (deterministic) with its own command, so the matrix gate accepts it |
| tests | `tests/test_panel.py` (7), one API test, one end-to-end pane test |

## The seven seats

| seat | asks | what it looks at |
|---|---|---|
| Applicant tracking system | Can I parse this without losing a line? | risky glyphs (em dash, curly quotes, bullets), table-shaped lines, lines over 220 chars, missing headings, contact block |
| Recruiter, 30-second scan | Do I see the role and one number in the top third? | the top third of the document |
| Hiring manager | Does this answer the posting's must-haves? | posting terms against the resume body |
| Sceptical team lead | Would I bet on these claims? | bullet lines with vague verbs and no number |
| Lexical match | Are the posting's own words present? | coverage ratio and the absent terms |
| Screen against the calendar | Do the dates agree? | reverse-chronological order, date span |
| Reference check | Could a referee back this up? | self-description adjectives with nothing behind them |

Each seat returns a 0–100 score and findings of `{line, quote, why, fix}`. The chair ranks every
finding by weight × verdict, de-duplicates by (seat, line) and emits **three** rewrites with the
line they belong to. Prose is never generated: the engine names the line and the instruction, which
is the same contract every other agent mode uses.

## The invariant that makes the promise true

"Quotes the exact line" is enforced in the type system's shadow:

```python
if quote and quote not in source:
    raise ValueError(f"quote {quote!r} is not in line {line}: {source!r}")
```

`_Guard.finding` raises if a quote is not a verbatim substring of the line it claims, and if a line
number is outside the document. Three tests hold it: every quote in a fixture is checked against
the source, a fabricated quote raises, and an index outside the document raises. Findings that
describe an *absence* (missing terms, missing headings) carry `line=None, quote=""` — an absence is
not dressed up as a quotation.

## Measured

Against the live copy of the owner's workspace (`%TEMP%\dossier-live-2026-11-05`):

```
dossier panel --root . --resume resume.md
  # Hiring panel: 77/100 (borderline)
  ats 64 · recruiter 100 · manager 50 · lead 100 · keywords 50 · screen 80 · honesty 100
  line 37  > Ran informal English conversation sessions to build students' spoken English.
           fix: Replace the dash, quote and bullet glyphs with ASCII
  line 5   > (a 220+ character line)  fix: Split it into bullets under 200 characters
```

With a real posting (`job-posting-Northbridge-TechnicalSupportEngineer.md`), through the UI:
**76/100**, `manager 41` (the posting's terms are unanswered), `keywords 58`, plan of 3, and the
pane renders in **211 words** — a seven-seat report that is a table, not a wall.

## Gates after adding a pane and a mode

```
pytest                                  448 passed (100 s)
measure.py   12 panes at 1440/768/390   0 h1 misses, 0 contrast fails, 0 <24px targets,
                                        0 unnamed, 0 overflow, console 0, dark 0, 29/29 rings
inspect.mjs --app                       0 findings
sloplint                                0 FAIL, 0 REFLEX, 2 WARN (both pre-existing, waived)
a11y.py      12 panes + 2 dialogs       clean
graft check                             OK
Lighthouse                              98–99 / 100 / 100
```

The one point that moved: the panel's stylesheet first shipped inside `tokens.css`, which is on
the critical path for every screen. It now ships in its own **1.4 KB** chunk loaded with the pane
(`dist/assets/PanelPane-*.css`), and the critical stylesheet went back to **39.3 KB**. Four
Lighthouse runs across the change: FCP 1.4 s and CLS 0 in all of them, LCP 2.1 s, and TBT
swinging 20–50 ms on a machine running four other agent sessions — performance 99 on the idle run
and 98 on the loaded ones. Same code, same bundle; the difference is measurement noise, recorded
rather than smoothed over.

The 24/25-pane instruments were updated with the pane rather than left claiming "all panes": the
12th entry in `.ui-ux-master/measure.py`, `a11y.py`, `walk.py`, `tour.py`, the e2e `AREA_OF` map and
the pane-walk test's `seen == 12`.

## What it deliberately does not do

- **No prose rewrite.** The reel's chair "rewrites your weakest parts"; here the chair produces the
  rewrite *instruction* with the offending line, and the `rewrite` mode (agent) does the writing.
  Generating replacement bullets from a template would be the fabrication the
  `no-fabrication` gate exists to prevent.
- **No posting, no pretending.** With no posting the manager and lexical seats say so and score 50
  each, and the header repeats it rather than silently scoring the resume alone.
- **Not a new dependency.** Seven reviewers, no model call: the same input always yields the same
  score and the same quotes, which is what makes it testable.
