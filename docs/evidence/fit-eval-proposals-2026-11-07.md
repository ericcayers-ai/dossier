# The eval set's missing rows, proposed — 2026-11-07

`docs/evidence/fit-eval-labels-2026-11-05.json` carries 23 rows, **5 strong / 13 possible /
0 unlikely / 0 skip**, so `nDCG@10 0.9078` cannot be lost: every labelled row is a positive and
the ranker is only ever asked to agree with itself. `docs/STATE.md` "Next action" step 2 names the
fix: label the 5 null rows and the 10 lowest-scored rows.

Those **15 grades are proposed here and nowhere else**. The gold set is untouched, no threshold
moved, no baseline was written, and nothing was committed — the owner confirms, amends or rejects
each line.

- Proposal: `docs/evidence/fit-eval-proposed-grades-2026-11-07.json` (same shape as a labels
  file, so `dossier identity eval --labels <it>` reads it directly)
- Gold set: `docs/evidence/fit-eval-labels-2026-11-05.json` — **unchanged**
- Thresholds: `evaluation.NDCG_SLACK` / `SPEARMAN_SLACK` — **unchanged**

The proposal's name deliberately avoids `.gitignore:89` (`docs/evidence/*-labels-*.json`), which is
where the gold set itself sits: `git ls-files docs/evidence/fit-eval-labels-2026-11-05.json`
returns nothing, so the labels every number here is measured against are **on disk only, never
committed**. Changing that is the owner's call, not this run's — but a session that clones this
repo cannot reproduce any of these numbers without the file.

## How the 15 were chosen

The 5 rows whose `grade` was `null`, plus the 10 rows carrying a tracker grade with the lowest
score (ties broken by title). Every grade below is read off the captured posting text and the
identity's own hard filters in `DEVELOPER-IDENTITY.md` — none is inferred from the score it is
meant to check.

## The 15 proposals

| score/band | row | tracker said | proposed | evidence for the proposal |
|---:|---|---|---|---|
| 36 unlikely | Cashier Team Member — The Warehouse, Cambridge (PT) | *null* | **skip** | Its only match is the string "retail" in a role-family list; the posting is in-store cashiering, no software/photo/translation content |
| 32 unlikely | Software Engineer - Intern — Aderant | *null* | **skip** | Posting: "4 **final year** undergrads or recent graduates", in-office Auckland CBD; he is a second-year in Ngāruawāhia |
| 32 unlikely | Test Automation Engineer - Intern — Aderant | *null* | **unlikely** | "Currently studying … a degree in Computer Science", "basic knowledge" of C#/Python is enough — but in-office Auckland CBD |
| 32 unlikely | Trade Service Team Member (Drive-Through) — Mitre 10 Taupo | *null* | **skip** | Posting: "Must have a current full NZ driver's licence", plus forklift/yard work — the identity's hard filter |
| 25 unlikely | Part-Time Retail Assistant — AS Colour, Sylvia Park | *null* | **skip** | "Part-time role (10 hours per week)", Mount Wellington, Auckland — wrong occupation and wrong city |
| 32 unlikely | AI Development Intern — Energyline | possible | **unlikely** | "An internship between November 2026 and February 2027" prototyping AI tooling fits him, but Christchurch Central with no licence |
| 32 unlikely | Data Science Intern — Xtracta | possible | **unlikely** | "Competent programming ability, ideally with Python", but the work is client extraction-issue documentation at Penrose, Auckland, in person |
| 32 unlikely | Source URL: …LIC summer-intern-evaluating… | possible | **possible** (provisional) | LIC summer internship is a real target, but this capture is a 137-byte stub — no posting text, "location unknown" — recapture before trusting it |
| 21 unlikely | Summer Internship — Accelerating Genetic Gain Through Simulation — LIC | strong | **strong** | "Basic programming experience (Python preferred)" on a Python simulation model, genetics only *desirable*; the 21 and its "location unknown"/"reads senior" reasons are capture gaps |
| 14 unlikely | Retail Assistants Christmas — Farmers | possible | **skip** | Christmas team members who "work late nights, weekends", festive-season retail across all Farmers stores |
| 14 unlikely | Sales Assistant — The Outlet (Te Rapa) — Ngahuia | possible | **skip** | "27 hours per week (Monday, Tuesday, Wednesday, Sunday)" retail sales at The Outlet |
| 11 unlikely | Christmas Team Member (Nightfill) — The Warehouse, Te Rapa | possible | **skip** | Fixed-term nightfill/stock work, "$25.42 per hour", 7am–3.30pm shifts |
| 11 unlikely | Christmas Team Member (Shopfloor/Checkout) — Cambridge | possible | **skip** | The same festive-retail programme, shopfloor and checkout |
| 11 unlikely | Seasonal Department Fixed Term Team Member — Mitre 10 Cambridge | possible | **skip** | A 40-hour Tuesday-to-Saturday roster selling outdoor furniture and BBQs |
| 0 unlikely | PhotoCentre Operator — Harvey Norman, Wellington | possible | **unlikely** | "Edit and restore images … using … Photoshop" is his photo-retouching target, but the role is "Permanent Full time" in Wellington while he is enrolled at Waikato |

Six rows move from the tracker's `possible` to `skip`: they are **wrong work**, not unavailable
work. If any of them is work he would take for the money, say so and it goes back.

## What the numbers say (measured, not estimated)

Same workspace and same instrument as the original receipt: a copy of the owner's folder with the
23 archived postings at `%TEMP%\dossier-live-2026-11-05`.

```text
$ dossier identity eval --root <ws> --labels docs/evidence/fit-eval-labels-2026-11-05.json
graded 18 of 23 row(s)
                           nDCG@10      P@10  slots P@10  recall@25  spearman
  identity score            0.9078       1.0         0.8        1.0    0.5011
  arrival order             0.8923       1.0         1.0        1.0   -0.3945
  grades: strong 5, possible 13, unlikely 0, skip 0; from {'tracker': 18, ...}
```

That reproduces `fit-eval-baseline-2026-11-05.json` exactly, so the instrument is the same one.

```text
$ dossier identity eval --root <ws> --labels docs/evidence/fit-eval-proposed-grades-2026-11-07.json
graded 15 of 23 row(s)
                           nDCG@10      P@10  slots P@10  recall@25  spearman
  identity score              0.45       0.2         0.1        1.0    0.1872
  arrival order             0.5873       0.2         0.2        1.0    0.0224
  grades: strong 1, possible 1, unlikely 4, skip 9; from {'agent': 15}
```

```text
$ # what-if: gold 18 + these 15 = all 23 graded, gated against the recorded baseline
graded 23 of 23 row(s)
                           nDCG@10      P@10  slots P@10  recall@25  spearman
  identity score            0.7283       0.6         0.6        1.0     0.591
  arrival order             0.7838       0.8         0.8        1.0    -0.383
  judged rows in the first 10: 10
gate fit-is-measured: FAIL — nDCG@k dropped to 0.7283 from 0.9078 (allowed drift 0.02)
```

**The ranker loses to arrival order once the labels include negatives** (0.7283 against 0.7838).
Spearman rises (0.5011 → 0.591), so the score does track grade better than before; what fails is
the *top of the list*. Two defects the rows name themselves:

1. **A cashier role scores 36 and lands in the top five** because `score_job` awards points for the
   string "retail" appearing in a role-family list and for "internship wording present". Neither is
   a signal that the work is his work.
2. **A Hamilton Python simulation internship scores 21** because the capture left its location
   `unknown` and the scorer then reads the role as senior. The posting says "basic programming
   experience (Python preferred)" and "genetics … desirable" — an intern-level brief.

The gate failing is the point, not a regression to be silenced: a measurement that cannot fail was
not a measurement. **Do not lower the thresholds.** The ranker is what should move.

## What this is not

- Not a new gold set, and not a baseline write.
- Not a ranking change: `score_job` was not touched.
- Not complete: 8 rows stay on tracker provenance (`not_covered` in the JSON). The most valuable
  next one is *Summer Intern – Machine Learning for Animal Assessment* (LIC, score 32, band
  unlikely) where the tracker says **strong** — the same capture-gap shape as the row above.

## The owner's next action

Read the 15 lines, edit any grade in the JSON, then re-run
`dossier identity eval --labels <confirmed file>` and `--write-baseline` **yourself** once the set
is one you believe. Until then `fit-eval-baseline-2026-11-05.json` stays the recorded baseline.
