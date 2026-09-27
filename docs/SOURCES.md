# Sources

This repository consolidates three previously separate things. This file records
what they were, what survived from each, and where the survivor lives now — so a
future reader can tell an intentional rule from an inherited accident.

## 1. The resume-tailoring skill

**Was:** `office-productivity/references/resume-tailoring/SKILL.md` (88 KB) plus
`references/job-search-copilot-modes.md` (48 KB), an entry-point alias, and five
standalone helper scripts (`build_job_data.py`, `jd_skill_gap.py`,
`followup_cadence.py`, `negotiation_roi.py`, `verify_docx_layout.py`).

**What survived, and where:**

| Source | Now |
|---|---|
| Document-generation procedure, Method A in-place editing, the table-cell reordering technique | `src/dossier/engine/tailor.py` |
| Visual verification pass, text-layer check, source diff, page-count and overflow rules | `src/dossier/engine/verify.py` |
| Board adapter policy vocabulary and endpoint table | `src/dossier/engine/sources.py` |
| `build_job_data.py` facets, combine, work-type and pay-band derivation | `src/dossier/engine/corpus.py` |
| `jd_skill_gap.py` requirement extraction and three-bucket classification | `src/dossier/engine/jd_skill_gap.py` |
| `followup_cadence.py` cadence, urgency, pins, retire directives | `src/dossier/engine/tracker.py` |
| `negotiation_roi.py` verbatim-match safety gate and arithmetic | `src/dossier/engine/negotiate.py` |
| `verify_docx_layout.py` margin-relative bounding-box check | `src/dossier/engine/verify.py` (`visual`) |
| The 20-plus modes, their inputs and their next steps | `src/dossier/agent/manifest.py` |
| The prose-level judgement each mode requires | `src/dossier/agent/brief.py` (`DECISIONS`) |
| The gates, restated as hard stops with an enforcer | `src/dossier/agent/manifest.py` (`GATES`) |

The helper scripts were **reimplemented in the package**, not imported. The skill
scripts and the package would otherwise be two copies of the same algorithm,
which is exactly how the cadence and the facet builder drift apart.

**What did not survive as executable logic:** prose-only steps. The longer
skill remains the judgement and document-workflow reference; the engine and
its brief own mechanical decisions and gates. The skill remains installed
in the default Hermes profile. Other profiles are separate installations
and are not asserted to be in sync.

## 2. The Dossier app

**Was:** this repository before the consolidation — a local-first document
workspace over a mixed folder: FastAPI service on `127.0.0.1`, per-run bearer
token, SQLite WAL + FTS5 index, Bundle Rail, conditional saves, trash-before-
overwrite, DOCX/PDF rendering, declarative argv-only actions, a read-only Audit
view and a copy-based Sync prompt.

**What survived:** all of it, unchanged in behaviour. The consolidation added a
layer beside it rather than rewriting it. `src/dossier/` kept its module layout;
`api/app.py` gained routes; `ui/` gained one pane.

**What was removed on the second pass**, once the engine held the only
implementation: `domain_jobs.py` (its tracker and corpus parsing duplicated the
engine) and six one-line `api/*.py` re-export stubs that nothing imported
(`actions`, `bundle`, `export`, `files`, `jobs`, `search` — all that was left of
a planned router split). `audit.py` lost its own copy of the board policy table
and its own coverage-file parser, and now reads `engine.sources`; `convert.routes`
now delegates to `engine.render.routes` instead of restating conversion fidelity.

**What was added:** the agent layer (`src/dossier/agent/`), the engine package
(`src/dossier/engine/`), the CLI subcommand tree, and the generated prompt packs.

## 3. Prior job-search sessions and their workspace

**Was:** a live workspace at `<workspace>` —
766 files, 23 captured boards, 1789 corpus rows, 38 tracked applications, 23
archived postings, 38 generated resume/cover-letter pairs, plus dated
`workflow-state-*.md`, `LESSONS.md`, `diagnosis-*.md`, `keywords-*.md`,
`jd-gap-input-*.md`, `ranked-jobs-*.json`, `nz-job-search-coverage-*.json` and a
`scripts/` folder of one-off resync scripts.

**What survived:** the lessons, in `docs/LESSONS.md`, each turned into either a
code rule or a test. The workspace itself was read, not copied — it stays where
it is and Dossier operates on it in place. Its one-off scripts are superseded by
`dossier corpus build`, `dossier corpus propagate`, `dossier render` and
`dossier track cadence`.

The three-tier fit carry-forward, the unique-id guarantee, the private Word
instance and the freshness-counting rule are all in this repository because a
session in that workspace hit the failure first.

## What is deliberately not here

- **No MCP integration.** The board adapters are plain read-only HTTP against
  documented public endpoints, and the `prohibited` list is enforced in code.
- **No scraping of LinkedIn, Indeed, Glassdoor, SEEK or Workday.** Those are
  registered as `prohibited` or `manual_only`; the runner refuses before a
  network call. That refusal is a feature, not a gap.
- **No automatic submission.** The service exposes no submit route and the CLI
  has no submit action. Field approval and submit approval are separate,
  human-owned steps.
- **No generated template fallback for a resume.** Without a real base `.docx`,
  `BaseDocumentMissing` is raised. A rebuild would silently flatten tables.
