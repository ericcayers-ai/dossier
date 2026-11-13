# State

Updated 2026-11-14. History lives in `docs/evidence/`; every number below comes from a cold run
executed on this date.

## Vision vs reality

Dossier is a local-first job-search workspace (Python 3.13 + FastAPI + SQLite FTS5 + React 19 +
Vite) where deterministic engine code owns document cloning, verification, corpus building, ranking,
tracking and safety gates, while an injected language model handles judgment modes. Everything
promised in `README.md` (`setup → diagnose → keywords → rewrite → build → verify → apply → prep →
interview → track → followup → negotiate → offer → outcome → upskill → trajectory`) runs locally
and passes end to end (`tests/test_pipeline.py` + `scripts/build_demo_workspace.py`).

## Tree

`master`, HEAD `badd390` plus local 2026-11-12/14 eval-fixture and verification slice (unpushed;
public remote `github.com/ericcayers-ai/dossier` is read-only). Python 3.13 (`.venv`), React 19 +
Vite, MIT-clean PDF stack (`pypdfium2`; `tests/test_licences.py` enforces non-copyleft runtime deps).

## Verified, in one place (2026-11-14)

| gate | command | result |
|---|---|---|
| tests | `.venv\Scripts\python.exe -m pytest -o addopts="" -q -p no:cacheprovider --basetemp=C:/Users/ericc/AppData/Local/Temp/dossier-gate` | **482 passed, 0 failed, 0 skipped** (72.42 s) |
| build | `cd ui && npm run build` | **70 modules**, per-pane chunks (424 ms) |
| UI gate | `.venv\Scripts\python.exe .ui-ux-master\measure.py` | **13 panes × 1440/768/390**: 0 h1 misses, 0 contrast fails, 0 `<24px`, 0 unnamed, 0 overflow, console 0, dark 0, 29/29 focus rings |
| slop | `node C:/Users/ericc/.pi/agent/skills/hallmark/scripts/sloplint.mjs ui/src --scope app` | **0 FAIL**, 2 WARN (waived) |
| cybersafe | `python C:/Users/ericc/.dsh/skills/cybersafe/scripts/cybersafe_scan.py .` | **0 findings** across 552 files |
| full-system | `node C:/Users/ericc/.dsh/tools/full-system.mjs . --quick` | **4/4 pass** (cybersafe, pytest, sloplint, untangle) |
| graph | `graft build && graft check` | **OK** (1,567 nodes, 3,675 edges) |
| adapters | `.venv\Scripts\dossier.exe agent adapters --check --root .` | **8/8 true** |
| doctor | `.venv\Scripts\dossier.exe doctor --root .` | **verdict: ready** (9/9 ok) |

## Live now

- **27 modes, 18 gates, 34 artifacts, 54 unique `/api/*` paths (58 route registrations)** in the
  contract (`dossier agent manifest --json`), plus **13 UI panes in 6 areas**.
- **Eval baseline (`fit-is-measured`)**: `tests/fixtures/eval-workspace/` (23 postings, `corpus_hash`
  `3c8314caac2e`) scores **nDCG@10 0.8596** vs arrival **0.7838**, **Spearman 0.7715**, pinned in CI.

## Not done / Deferred by design

- **No CAPTCHA farm, proxy pool, or `POST /api/scrape/login`** — documented design boundaries.
- **`dossier verify template`** does not inspect Word text boxes or images (`python-docx` limit).
- **Two CLI-only/script API routes** have no UI caller (`GET /api/agent/next`, `GET /api/match/posting`).

## Blocked / Remaining owner decision

- **Owner decision:** confirm whether to rename the 8 engine-vocabulary pane labels (`Capture`,
  `Identity`, `Papers`, `Housekeeping`, `Agent`, `Loop`, `Opportunity`, `Panel`) to plain-language
  names (requires updating `tests/test_e2e_ui.py` in the same commit).
