# Handoff

2026-11-16. What a fresh session needs. Detail: `docs/STATE.md`, `docs/SCOPE-LEDGER.md`, and
`docs/evidence/`.

## Where this stands

`master`, HEAD carrying the 2026-11-14 verification slice plus the 2026-11-16 pane rename; the push
and this pass's gates are recorded in `docs/FINISH-LOG-2026-11-16.md`. All 482 tests, UI build,
13-pane Playwright UI measurement, sloplint, cybersafe scan (0 findings), `graft check`,
`agent adapters --check`, `doctor`, and `full-system.mjs --quick` are green from cold runs on
2026-11-14.

- **Eval fixture and `score_job` fix landed:** the 23-posting evaluation workspace is committed under
  `tests/fixtures/eval-workspace/` with `docs/evidence/fit-eval-baseline-2026-11-12.json`
  (`nDCG@10 0.8596` > arrival `0.7838`, `Spearman 0.7715`).
- **Cybersafe 0 findings:** scrubbed 19 zero-width characters (`CS-09`) from 9 archived fixture
  postings while preserving `corpus_hash == 3c8314caac2e`.
- **Measure race fixed:** `.ui-ux-master/measure.py` now waits for `main h1` visibility after pane
  clicks in both light and dark loops.

## The five commands that matter

```powershell
.venv\Scripts\python.exe -m pytest -o addopts="" -q -p no:cacheprovider --basetemp=C:/Users/ericc/AppData/Local/Temp/dossier-gate
.venv\Scripts\python.exe .ui-ux-master\measure.py
cd ui; npm run build
.venv\Scripts\dossier.exe agent adapters --check --root .
.venv\Scripts\dossier.exe doctor --root .
```

## Traps this repo has already paid for

- **A manifest change does not regenerate the docs.** Run `dossier agent adapters` after changing
  `src/dossier/agent/manifest.py`.
- **`mtime_ns` cannot survive JSON.** Compare content hashes and treat timestamps as hints.
- **A pane's CSS belongs beside its chunk**, not in `tokens.css`.
- **Restart the server after a Python change** before believing a UI measurement.
- **`pytest` needs `-o addopts=""` and a short `--basetemp`** on Windows/OneDrive.

## Next action

1. Pane labels are plain task words as of 2026-11-16 (`Find roles`, `Saved roles`, `Preferences`,
   `Write CV`, `Check CV`, `Health check`, `Deleted`, `Handoff`; ids and routes unchanged), and
   `master` is pushed to `origin`. Receipt: `docs/FINISH-LOG-2026-11-16.md`. Nothing is queued.
