# dossier — scope ledger

Tracks items discovered beyond the handoff and items deliberately left undone.

## Found beyond the handoff

- **Zero-width characters in eval fixture (`tests/fixtures/eval-workspace/job-posting-*.md`)** — `cybersafe_scan.py` flagged 19 `CS-09-ZERO-WIDTH-SMUGGLING` findings across 9 captured posting fixtures. Stripped all zero-width/directional characters; `cybersafe_scan.py` now reports 0 findings across 552 files while preserving `corpus_hash` (`3c8314caac2e`).
- **`.ui-ux-master/measure.py` lazy-pane heading race** — Fixed the intermittent `1440 Panel -> h1 []` race by waiting for `main h1` to become visible after clicking `.pane-btn` in both light and dark loops.
- **`graft/` context graph drift** — Rebuilt stale graph (180 changed, 2 removed symbols) so `graft check` passes (`1567` nodes, `3675` edges).
- **Eval fixture & `score_job` calibration verified in gate** — Verified the uncommitted `tests/fixtures/eval-workspace/` (23 graded postings), `docs/evidence/fit-eval-baseline-2026-11-12.json` (`nDCG@10 0.8596` vs arrival `0.7838`, `Spearman 0.7715`), and `identity.score_job` fixes (`_GENERIC_TITLE_TOKENS`, `_INTERNSHIP_WORD`, `_YEARS_EXPERIENCE`, `location_known`) in the full 482-test suite.

## Deliberately not done

- **Plain-language pane rename** — **done 2026-11-16.** The eight engine-vocabulary labels are now
  `Find roles`, `Saved roles`, `Preferences`, `Write CV`, `Check CV`, `Health check`, `Deleted`,
  `Handoff`, with ids and routes unchanged. `tests/test_e2e_ui.py` and `.ui-ux-master/measure.py`
  click the new labels in the same commit, so the pin moved with the rename instead of being
  loosened. Receipt: `docs/FINISH-LOG-2026-11-16.md`.
- **Automated CAPTCHA solver / proxy pool** — Requires paid owner key (`DOSSIER_SOLVER_KEY`); excluded by design (`challenge-is-explicit` + `session-is-the-users`).
- **`POST /api/scrape/login`** — Omitted by design because browser sign-in requires an interactive local window (`dossier scrape login`).
- **Splitting `src/dossier/cli.py`** — 1,680 lines; no failing test or defect justifies the behaviour risk of refactoring CLI wiring.
