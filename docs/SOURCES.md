# Sources

This repository consolidates three previously separate things. This file records
what they were, what survived from each, and where the survivor lives now — so a
future reader can tell an intentional rule from an inherited accident.

## 1. The resume-tailoring skill

**Was:** `office-productivity/references/resume-tailoring/SKILL.md` (88 KB) plus
`references/resume-tailoring/references/job-search-copilot-modes.md` (48 KB), an entry-point
alias, and five standalone helper scripts (`build_job_data.py`, `jd_skill_gap.py`,
`followup_cadence.py`, `negotiation_roi.py`, `verify_docx_layout.py`). Both sizes check out
against the parked copy (90,483 B and 48,656 B, measured 2026-10-11).

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
its brief own mechanical decisions and gates.

> **Corrected 2026-10-11.** This paragraph used to read "The skill remains installed in the
> default Hermes profile." It does not. `<dsh-home>\skills\office-productivity`
> does not exist; the only copy on this machine is parked at
> `<dsh-home>\skills-archive\2026-10-08-parked\parked\dsh_global\office-productivity\`
> (SKILL.md 7,090 B there; the 90,483-byte resume-tailoring SKILL.md sits under
> `references/resume-tailoring/`). Other profiles are separate installations and are not
> asserted to be in sync. No engine behaviour depends on the skill being installed — this is a
> provenance note, not a runtime dependency.

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

**Was:** a live workspace at `<resume-corpus-root>` —
766 files, 23 captured boards, 1789 corpus rows, 38 tracked applications, 23
archived postings, 38 generated resume/cover-letter pairs, plus dated
`workflow-state-*.md`, `LESSONS.md`, `diagnosis-*.md`, `keywords-*.md`,
`jd-gap-input-*.md`, `ranked-jobs-*.json`, `nz-job-search-coverage-*.json` and a
`scripts/` folder of one-off resync scripts.

> **Measurement note (2026-10-11).** The sentence above is past-tense and is kept as written;
> the other figures verify. The **766** file count matches no counting convention measurable
> today: the same folder holds **770** files recursively including hidden entries, **728**
> excluding `.dossier/`, and **707** excluding `.dossier/` and `_preview/`. Treat 766 as a
> historical count taken at the time, not a current one — the sentence already says "Was:".

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

  **Provenance, so this is not mistaken for a user requirement.** The user asked
  for these boards by name — "i want to look through seek nz, indeed, trademe
  jobs, literally all available main job searches" (session
  `20260828_164736_7672b9`) — and requested the widest possible coverage in
  `20260911_203039_6edc17`. The block itself originates in an agent-authored
  build brief (`20260912_035239_4c86f4`, the Dossier backend slice), not in a
  user turn: no session records the user approving the block or withdrawing the
  board list. The exclusion is a conservative default chosen because those sites
  forbid automated collection, and it is a decision the owner has not been asked
  to confirm. It is now a *configurable* default rather than a buried one: a workspace
  states its own policy in `.dossier/sources.json`, which
  `engine.sources.effective_policies` merges over the shipped table, and `dossier
  sources` reports the result. A missing or malformed file falls back to the
  defaults, so a broken override can never open a gate. Opening a policy changes
  what the engine permits and reports; it cannot conjure a feed adapter, so these
  boards still resolve to a user-supplied posting, export or licensed source. The
  reason to keep the default is legal, not technical.
- **No automatic submission.** The service exposes no submit route and the CLI
  has no submit action. Field approval and submit approval are separate,
  human-owned steps.
- **No generated template fallback for a resume.** Without a real base `.docx`,
  `BaseDocumentMissing` is raised. A rebuild would silently flatten tables.

## 4. The capture layers (2026-11-04)

Three layers fetch a board, cheapest first, and the run record names the one used. The
narrative, the recipe schema and the refusal vocabulary are in `docs/SCRAPING.md`; this
section records only where each layer came from.

| Layer | Code | Origin |
|---|---|---|
| Public JSON feeds | `feeds.py` | the six endpoints survived the 2026-09-26 consolidation; **no caller existed until 2026-11-04**, when `dossier feeds` was wired to the corpus shape |
| obscura subprocess | `scrape/browser.py:ObscuraDriver` | `~/.dsh/tools/obscura/` v0.2.5, installed 2026-10-27 from reel `De9kMGeShp9`; chosen because it obeys robots by default and needs no Python browser dependency |
| Playwright + Chromium | `scrape/browser.py:PlaywrightDriver` | the `browser` extra in `pyproject.toml`; the only engine that can hold the user's session |
| Session store | `scrape/session.py` | new. Cookies + localStorage only; never a password |
| Recipes | `scrape/recipes.py`, `templates/scrapes/` | new. Site specificity as data, validated before a request |
| Runner | `scrape/runner.py` | new. Policy → robots → pace → engine → extract → sanitise → write |

Two constraints are inherited rather than invented: `source-policy` (a prohibited board is
refused before a network call, `engine/sources.assert_allowed`) and
`partial-is-not-exhaustive` (a partial capture is never reported as coverage,
`engine/sources.coverage`). The capture layer reuses both predicates rather than restating
them, and adds two gates of its own — `session-is-the-users` and `challenge-is-explicit` —
because a browser can reach content a JSON endpoint cannot.

A URL the user names is filed under the `user_supplied` policy row (`web`). That row
authorises *that page*, not a crawl: `scrape/guard.HOST_SOURCES` resolves a known board from
the host first, so a LinkedIn URL still meets the prohibited row no matter what a recipe
declares.
