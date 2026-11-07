# Reel adoption notes - 2026-10-27

Sources: four Instagram reels digested 2026-10-27 plus the WASCAPE request. Full rationale:
`<home>\.dsh\handoffs\2026-10-27-reel-widescope\HANDOFF.md` and `PROJECT-DECISIONS.md`.
Owner-approved browser default: `obscura` v0.2.5 (see `~/.pi/agent/AGENTS.md`).

Status: notes only. Nothing below is implemented yet.

## Verdict

**D ADOPT.** An eval set built from the workspace's own tailoring requests, plus citation verification
on every claim the tool emits about the user's CV - a claim that cites no source span is dropped.
**A ADAPT.** obscura for review-surface screenshots into `docs/evidence/`, parity-checked first.
**B**: no - this is an original concept, and its "layout clone" refers to the user's own .docx
(`README.md:111`). C and E do not apply.

## By source

| Source | Applies | How it would be implemented here | Gate |
|---|---|---|---|
| A - obscura browser | yes | The review surface is the local app served by `src/dossier/api/app.py` (opened by `run.cmd`). Screenshots belong in `docs/evidence/` beside the dated notes already there. Before switching, capture the same page with the current path and record a content-parity number - the repo's own rule is that a render claim needs a rendered page (`src/dossier/engine/verify.py:146`). | `dossier verify visual` |
| B - replica parity method | no | Nothing is cloned from an upstream product: the base is the user's own .docx and has no template fallback (`README.md:111`, gate `base-document`). | none |
| C - measured render loop | no | Rendering already has a numeric check (`margin_tol` in `src/dossier/engine/verify.py`); no rubric file or frame loop is wanted. | none |
| D - eval sets / guardrails / cited retrieval | yes | Citation check: extend the existing provenance gate (`source_diff`, `src/dossier/engine/verify.py:36`) and the verbatim-claim gate (`verify_claim`, `src/dossier/engine/negotiate.py:125`) into new file: `src/dossier/engine/citations.py`, proven by new file: `tests/test_citations.py`. Eval set: 20 examples from the postings and handbacks the engine already commits (`commit`, `src/dossier/agent/loop.py:213`) in new file: `src/dossier/eval/tailoring_eval.py`. | `uv run pytest -q tests/test_citations.py tests/test_tailoring_eval.py` |
| E - WASCAPE | no | No 3D capture, no streaming delivery. | none |

## Rejected, with reason

- **B replica parity** - no upstream product; the "clone" is the user's own document, and `no-fabrication` already governs it.
- **C rubric caps** - the visual gate is a page-margin and page-count check, not a quality rubric; a rubric would score what a person must read.
- **E WASCAPE** - nothing in this repo captures or delivers scenes.
- **A as a replacement engine** - obscura is for receipt screenshots only; the app's own render/verify path stays authoritative.
- **An eval set built from synthetic jobs** - the value is in real requests, so a fabricated set would score nothing real.

## First step

Write new file: `tests/test_tailoring_eval.py` with the 20-example set assembled from the workspace's
own stored tailoring requests, then run `uv run pytest -q tests/test_tailoring_eval.py` and let the
regression gate fail before any scoring code is written.

## Not verified here

No stored tailoring requests were read for this note, so the 20-example set is a target size, not a
measured sample. The obscura/screenshot parity number was not produced - nothing was captured, run or
installed.

## Prior backlog, consolidated (2026-10-27)

Older owner requests that belong to this project, with the status the reconciled ledger recorded.
Source: `<home>\.dsh\handoffs\2026-10-27-reel-widescope\PRIOR-BACKLOG-BY-PROJECT.md`
(derived from `dm-context-ledger.md`, the 2026-10-26 run reports and `fullinstadmNOTES.md`).
Statuses are 2026-10-26/27 receipts, not re-verified today: re-run this repo's gate before calling
anything done.

| # | Item | Status |
|---|---|---|
| A5 | Plugin or own ecosystem | DECIDED: own ecosystem (D1) - zero references to Learning Studio, and the owner's own line is that Dossier is what everything should be consolidated into |
| A7 | Consolidate the resume-tailoring skill, Dossier and the prior Hermes job-search sessions into one LLM-injectable wrapper | CONSOLIDATE-INTO-DOSSIER - the skill is parked at `~/.dsh/skills-archive/2026-10-08-parked/.../resume-tailoring/` (SKILL.md 1,284 lines); upstream MadsLorentzen/ai-job-search is MIT, a prompt and workflow pack rather than an app |
| A7 next | Copy the skill into dossier/skills/, then run dossier agent adapters --check | OPEN - the next step the ledger records |
| - | Trajectory Tree | DONE as recorded - commits f8a1f8b and c043aa0, suite at 269 |

### Prior sessions on this project
- dsh 2026-09-11 - planned the resume-tailoring ecosystem app, 10 files touched.
- hermes 2026-09-11 - implemented the backend slice of the Dossier app, 31 files touched.
- hermes 2026-09-26 - consolidated resume and dossier into the unified job-search repo, 42 files touched.
- dsh 2026-09-27 - consolidated job-search automation into the new repo, 19 files touched.

### What this means for the reel work above
The citation verifier and the eval set sit on the tailoring loop that A7 is about to move, so they
land after the skill copy or they get written against paths that move. A5 has already answered the
packaging question: own ecosystem, no Learning Studio plugin.
