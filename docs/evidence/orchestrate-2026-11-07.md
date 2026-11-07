# Orchestrated run — dossier — 2026-11-07

Order `[[ORDER-ID: dossier-20261107]]`, received in full with its `[[END-OF-ORDER]]` sentinel.
Owner's instruction for this run: label the 15 unlabelled eval rows, propose a grade for each with a
line of evidence, write the proposals to their own file, **do not** overwrite the gold set, **do not**
change a threshold, **do not** commit. Done, and measured.

## What closed

**The eval set's missing labels, proposed.** `docs/evidence/fit-eval-labels-2026-11-05.json` has 23
rows and **0 negatives**, so `nDCG@10 0.9078` could not be lost. The 15 rows `docs/STATE.md` names
(the 5 null rows plus the 10 lowest-scored rows) now each carry a proposed grade, a one-line
justification read off the captured posting text, and the tracker's prior grade beside it:

- `docs/evidence/fit-eval-proposed-grades-2026-11-07.json` — 15 graded rows + the 8 rows left on
  tracker provenance, in a shape `dossier identity eval --labels` reads directly.
- `docs/evidence/fit-eval-proposals-2026-11-07.md` — the same 15 as a table, with the numbers below.

The gold set, the baseline and `evaluation.NDCG_SLACK` / `SPEARMAN_SLACK` are untouched.

## Commands and output tails

```text
$ .venv/Scripts/dossier.exe identity eval --root %TEMP%\dossier-live-2026-11-05 \
      --labels docs/evidence/fit-eval-labels-2026-11-05.json
graded 18 of 23 row(s)
  identity score            0.9078       1.0         0.8        1.0    0.5011
  arrival order             0.8923       1.0         1.0        1.0   -0.3945
  grades: strong 5, possible 13, unlikely 0, skip 0; from {'tracker': 18, ...}
exit=0                      # reproduces fit-eval-baseline-2026-11-05.json exactly
```

```text
$ .venv/Scripts/dossier.exe identity eval --root %TEMP%\dossier-live-2026-11-05 \
      --labels docs/evidence/fit-eval-proposed-grades-2026-11-07.json
graded 15 of 23 row(s)
  identity score              0.45       0.2         0.1        1.0    0.1872
  arrival order             0.5873       0.2         0.2        1.0    0.0224
  grades: strong 1, possible 1, unlikely 4, skip 9; from {'agent': 15}
```

```text
$ # what-if only: gold 18 + these 15 = all 23 graded, gated against the recorded baseline
graded 23 of 23 row(s)
  identity score            0.7283       0.6         0.6        1.0     0.591
  arrival order             0.7838       0.8         0.8        1.0    -0.383
gate fit-is-measured: FAIL — nDCG@k dropped to 0.7283 from 0.9078 (allowed drift 0.02)
exit=1                      # the merged labels were a temp file, deleted; nothing was recorded
```

**Before → after, on the honest labels: the product loses to arrival order (0.7283 against 0.7838).**
Spearman rises 0.5011 → 0.591, so the score does rank grade better than before; what breaks is the
top of the list. The rows say why: a cashier role scores 36 and sits in the top five because
`score_job` counts the string "retail" as a role-family match and "internship wording present" as a
signal, while a Hamilton Python simulation internship scores 21 because its capture left the
location `unknown`. The gate failing is the measurement working, not a regression to silence.

## The gate

```text
$ .venv/Scripts/python.exe -m pytest -o addopts="" -q
7 failed, 427 passed, 2 warnings, 16 errors in 195.16s
$ .venv/Scripts/python.exe -m pytest -o addopts="" -q --ignore=tests/test_e2e_ui.py
7 failed, 427 passed, 2 warnings in 130.49s
```

All 23 are one environment cause, named by Playwright itself:

```text
playwright._impl._errors.Error: BrowserType.launch: Executable doesn't exist at
  ...\ms-playwright\chromium_headless_shell-1248\chrome-headless-shell-win64\chrome-headless-shell.exe
  Please run the following command to download new browsers: playwright install
```

The 7 failures are `tests/test_scrape.py`'s Playwright cases; the 16 errors are
`tests/test_e2e_ui.py`'s. No test outside the browser path failed. `playwright install` is a
download, and the order forbids one without the owner, so the gate is reported red, not repaired.
**This run's own changes are documents only** — no `src/`, `tests/` or `ui/` file was touched, so
these 23 cannot be attributed to it. `docs/STATE.md`'s "449 tests green" was measured on 2026-11-06
in an environment that had the browsers; it is now restated as measured today.

## Reel digest — the delta, audited

`docs/evidence/reel-coverage-2026-11-07.md`. `grep -c '^## ' DIGESTS.md` → **126** against the 111
rows in `reel-matrix-2026-11-06.md`: 15 headings ingested since, resolving exactly to `§96`–`§101`
plus nine sub-headings. Ran `rq.py project dossier`, `verdict viable`, `verdict implemented` and four
searches (`evaluation`, `label`, `ranking score`, `resume fit`). None of the new entries touches
dossier; **no verdict to apply, no work-list addition**. The four `implemented` verdicts were already
applied or are the matrix's `N/A`.

## Untangle pass — numbers recorded, no change made

```text
$ node ~/.dsh/tools/untangle-scan.mjs . --json
files 561 · 14,260,908 B · codeFiles 104 (1,251,693 B) · docFiles 176 (856,994 B) · testRatio 0.25
deadBytes 0 · dupBytes 2,232 · reclaimable 2,232
```

The only reclaimable bytes are a duplicated AST cache inside
`docs/history/graphify-legacy-2026-09-12/` — history, which this pass may not delete. Also skipped
deliberately: **the tree carries 159 uncommitted paths from earlier sessions whose slices the owner
has not yet chosen**, so a structural edit now would land inside someone else's uncommitted change.
Phase 0 of the skill wants a green gate first, and today's gate is red for the browser reason above.

## Obsolescence and the other open items — verified, not edited

- **Not superseded.** No `CONSOLIDATION`/`ARCHIVE`/`legacy` note names a successor for dossier; the
  repo is live (`docs/STATE.md`, HEAD `c043aa0`). No `ARCHIVE-DECISION-2026-11-07.md` is warranted.
- **`tasks/WORKLIST.md:159,169,174,177,179,180`** still `[ ]` for the trajectory tree, whose code
  landed at `f8a1f8b` / `c043aa0`. Confirmed open; **not edited** — outside this run's slice.
- **`tasks/WORKLIST.md:102-104`** still reads "unverified — no receipt, no implementation" where
  `:72` records the panel built 2026-11-06. Confirmed; **not edited** — same reason.
- **A7 skill copy** into `dossier/skills/`: `ls -d skills` → absent. Confirmed open; not this slice.
- **Slice plans for the 159 dirty paths**: not produced. The owner is the one who picks slices
  (`docs/STATE.md` "Next action" 1), and producing them here would be advice, not verification.

## Nothing was committed, nothing was staged

`git status --porcelain` shows the pre-existing dirty tree plus this run's four new documents
(`docs/evidence/fit-eval-proposed-grades-2026-11-07.json`, `fit-eval-proposals-2026-11-07.md`,
`reel-coverage-2026-11-07.md`, `orchestrate-2026-11-07.md`) and the two edited docs
(`docs/STATE.md`, `docs/HANDOFF.md`). No `git add`, no commit, no push.
