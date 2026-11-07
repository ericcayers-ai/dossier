# Handoff

2026-11-07. What a fresh session needs. Detail: `docs/STATE.md` and the receipts in
`docs/evidence/`.

## Where this stands

`master`, **head moves with the 2026-11-07 slices** (they land on top of `9b3b77b`; nothing is
pushed). The owner's ask this session was *"how do i even use this thing, fix it so it just works
for the layman… hone them in on the frontend side"*; the answer is the **Start here** pane and the
plain-language pass, receipt in `docs/evidence/ux-layman-2026-11-07/README.md` (before/after
screenshots at 1440 and 390, one instrument both ways, contrast on every new label).

- **449 passed, 1 failed** — the failure is `test_no_tracked_file_carries_personal_contact_details`,
  pre-existing (5 tracked files carry the owner's name or the New Zealand phone prefix) and untouched by this pass.
- **13 panes in 6 areas**, 27 modes, 18 gates, 54 unique API paths (58 registrations); every one answers (34 ok, 18 refused with a
  sentence, 4 skipped with a reason, **0 × 5xx**).
- **The hiring panel** (reel §36) is built: seven reviewers, each scoring and **quoting the exact
  line**, plus a chair's three rewrites. `engine/panel.py`, `dossier panel`, `GET /api/panel`,
  pane Agent → Panel.
- **Saving from the UI works**: it never did. `mtime_ns` is past `2**53`, so the browser rounded
  the stamp by ~100 ns and every save was a false 409. `matches()` now compares content exactly
  and the mtime within 1 µs.
- **⌘K is a launcher**: 12 panes with no query, places ranked above files, Enter navigates.
- **GET routes stay cheap**: `/api/render` serves cache only and answers 409 with the POST that
  builds it; `/api/convert/routes` states a conversion's fidelity class before the click.

## The five commands that matter

```powershell
.venv\Scripts\python.exe -m pytest -o addopts="" -q -p no:cacheprovider   # 449 passed, 1 pre-existing failure
.venv\Scripts\python.exe .ui-ux-master\measure.py            # 13 panes, all zeros
cd ui; npm run build                                         # per-pane chunks
.venv\Scripts\python.exe docs\evidence\ux-layman-2026-11-07\capture.py --label after   # the UX receipt
.venv\Scripts\dossier.exe agent adapters --check --root .    # generated docs in sync
.venv\Scripts\dossier.exe doctor --root .                    # environment capabilities
```

Scratch instruments (not in the repo): `%TEMP%\..\tour.py`, `friction.py`, `sweep.py`,
`retrieval.py`, `hammer.py`, `a11y.py`, `measure.py` receipts land in
`.ui-ux-master/receipts/` and `~/.dsh/scratch/dossier-live-2026-11-05/receipts/`.

## Traps this repo has already paid for

- **A manifest change does not regenerate the docs.** Run `dossier agent adapters` — it rewrites
  `docs/CONTRACT.md`, `docs/PIPELINE.md`, `GEMINI.md`, `.cursor/rules/dossier.mdc`,
  `.claude/skills/dossier/SKILL.md`, `docs/agent/INJECT.md`.
- **`mtime_ns` cannot survive JSON.** Never compare a nanosecond timestamp that passed through
  JavaScript; compare content and treat the time as a hint.
- **A pane's CSS belongs beside its chunk**, not in `tokens.css` — every rule added there rides on
  the first paint.
- **Restart the server after a Python change** before believing a UI measurement: a green probe
  against a stale process measures the old code.
- **Chrome lays 33.6 px rows, not 33.** Rounding the explorer's row height accumulated 437 px of
  scroll error; the height stays fractional.
- **`pytest` needs `-o addopts=""` and a short `--basetemp`** or it fails on path length.

## 2026-11-07 — the eval set's missing labels, proposed

15 grades (the 5 null rows + the 10 lowest-scored) are written to
`docs/evidence/fit-eval-proposed-grades-2026-11-07.json`, each with a justification read off the
captured posting text, and laid out in `docs/evidence/fit-eval-proposals-2026-11-07.md`. The gold
set and the slack are untouched; **the owner confirms the grades**. Measured on the honest labels:
`nDCG@10 0.7283` against `arrival 0.7838` — the ranker loses to arrival order, Spearman rises to
0.591. Read `docs/evidence/orchestrate-2026-11-07.md` for the commands and the gate caveat: the
suite is red here for one environment reason (Playwright's browsers are not installed, `7 failed,
427 passed, 16 errors`, all `BrowserType.launch`).

## Next action

1. Commit in reviewed slices (the owner picks them).
2. Confirm the 15 proposed eval grades in
   `docs/evidence/fit-eval-proposed-grades-2026-11-07.json`, then re-record the baseline yourself
   and fix `score_job` — the ranker, not the slack.
