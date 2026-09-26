# Pipeline

Generated from the contract in `src/dossier/agent/manifest.py`. Do not edit by hand; run `dossier agent adapters`.


<!-- dossier:contract:start -->
## Pipeline

The canonical order. Each mode names its own next step, so a session never has to guess what follows what.

| # | Stage | Intent | Modes |
|---|---|---|---|
| 1 | Setup | Resolve the workspace: identity doc, base resume, corpus, tracker. | `setup`, `corpus`, `rank`, `audit`, `handoff`, `sources` |
| 2 | Diagnose | Find what is broken and rank the fixes. | `diagnose` |
| 3 | Keywords | Extract the posting's real requirements and the gaps against the resume. | `keywords` |
| 4 | Rewrite | Turn supported evidence into XYZ bullets; never invent a metric. | `rewrite` |
| 5 | Build | Clone the base layout into a tailored resume plus a paired cover letter. | `build` |
| 6 | Verify | Diff against the base, render, inspect the page, check the text layer. | `verify`, `render` |
| 7 | Apply | Two-phase approval gates around any live ATS form. | `apply` |
| 8 | Interview prep | Bullet inventory, evidence audit, STAR story bank. | `prep` |
| 9 | Interview | Mock rounds and debriefs against the real claims. | `interview` |
| 10 | Track | Append-only application log; drafted is not applied. | `track` |
| 11 | Follow-up | Deterministic cadence; drafts, never sends. | `followup` |
| 12 | Negotiate | Verbatim-match safety gate, then arithmetic. | `negotiate` |
| 13 | Offer | Clause-by-clause review and questions to ask. Not legal advice. | `offer` |
| 14 | Outcome | Record the real result and mine the pattern. | `outcome` |
| 15 | Upskill | Aggregate recurring genuine gaps across every keyword report. | `upskill` |

## Modes

| Mode | Kind | Stage | What it does | Engine |
|---|---|---|---|---|
| `setup` | deterministic | `setup` | Resolve and report the workspace: identity doc, base resume, corpus, tracker, coverage. | `workspace.resolve` |
| `diagnose` | agent | `diagnose` | Senior-ATS read of the resume: parse safety, weakest line per section, missing signals, five ranked fixes with a before/after. | — |
| `keywords` | hybrid | `keywords` | Requirement extraction and gap classification for one posting (Mode A) or a sampled market survey (Mode B). The mechanical token pass is deterministic. | `jd_skill_gap` |
| `rewrite` | agent | `rewrite` | Google XYZ bullets: X impact, Y metric, Z method. Missing numbers are asked for in one batch, never invented. | — |
| `build` | hybrid | `build` | Clone the base .docx layout in place (Method A), change only the objective and ordering, and emit the paired cover letter in the same pass. | `tailor.build` |
| `verify` | deterministic | `verify` | Source diff the generated document against the base, render it, inspect the page, and check the PDF text layer. Exits non-zero on any failure. | `verify.all` |
| `apply` | hybrid | `apply` | Fill an ATS form after field approval, then stop at a separate submit approval. File uploads are handed to the user. | — |
| `prep` | agent | `prep` | Bullet inventory with evidence, honest fallbacks, spoken introductions, a STAR story bank and a review-question bank. | — |
| `interview` | agent | `interview` | Hiring-manager mock: exactly one question per message, scored, with a debrief. | — |
| `track` | deterministic | `track` | Read the append-only application log, normalize statuses, report counts and the rows that are actionable. | `tracker.summary` |
| `followup` | hybrid | `followup` | Deterministic cadence: 7/7 days chaining, cold after two, pins and retire directives honoured. Drafts only, never sends. | `tracker.cadence` |
| `negotiate` | hybrid | `negotiate` | Verbatim-match safety gate, then arithmetic with the formula shown and a transferability disclaimer. Wage and frequency are never guessed. | `negotiate.roi` |
| `offer` | agent | `offer` | Clause-by-clause walk of an offer or contract plus the questions to ask. Explicitly not legal advice. | — |
| `outcome` | deterministic | `outcome` | Record a real result against the tracker row and archive the artifacts that were actually sent. | `tracker.record_outcome` |
| `corpus` | deterministic | `setup` | Normalize captured board data into one comparable corpus: stable unique ids, work types, facets, sources, dedupe keys, fit carry-forward. | `corpus.build` |
| `rank` | deterministic | `setup` | Deduplicate and rank the corpus by fit, evidence strength, recency and warm-contact signal. A weighted score never hides a disqualifier. | `corpus.rank` |
| `upskill` | deterministic | `upskill` | Count recurring gaps across every keyword report and separate genuinely missing skills from skills merely buried in the resume. | `jd_skill_gap.aggregate` |
| `audit` | deterministic | `setup` | Read-only reconciliation of index, bundles, renders, statuses, dates, event evidence and source limits. | `audit.workspace` |
| `handoff` | deterministic | `setup` | Emit a reconciliation packet for another session. Data, not authority; the bearer token is never included. | `audit.handoff` |
| `render` | deterministic | `verify` | Re-render stale PDFs from their newer DOCX sources through a private Word instance, asserting each output is newer than its source. | `render.stale` |
| `sources` | deterministic | `setup` | Report the board ledger: which sources are public, which are manual-only, which are prohibited, and exactly what the user must supply. | `sources.ledger` |

## Artifacts

The files this contract is built from. The folder is the source of truth; `.dossier/` is derived and disposable.

| Artifact | Path | Role | Producer | Consumers | Required |
|---|---|---|---|---|---|
| identity | `*-IDENTITY.md` | identity | setup | `*` | yes |
| profile | `resume.md` | identity | setup | `diagnose`, `rewrite`, `interview` | yes |
| base | `base.docx` | source | user | `build` | yes |
| posting | `job-posting-*.md` | source | sources | `keywords`, `build`, `apply` | no |
| keywords | `keywords-*.md` | analysis | keywords | `rewrite`, `build`, `upskill` | no |
| skillgap | `*.skillgap.json` | analysis | jd_skill_gap | `upskill` | no |
| diagnosis | `diagnosis*.md` | analysis | diagnose | `rewrite` | no |
| bullets | `bullets-rewritten.md` | analysis | rewrite | `build`, `interview` | no |
| resume_out | `*.docx` | artifact | build | `verify`, `apply` | no |
| render | `*.pdf` | render | render | `verify` | no |
| proof | `*-page-*.png` | proof | render | `verify` | no |
| verification | `verification-*.json` | proof | verify | `audit` | no |
| tracker | `job-history.md` | state | track | `followup`, `audit`, `upskill` | yes |
| followups | `follow-ups.md` | state | followup | `followup` | no |
| storybank | `interview-prep/story-bank.md` | state | prep | `interview`, `negotiate` | no |
| interviewlog | `interview-prep/interview-log.md` | state | interview | `prep` | no |
| negotiation | `negotiation-drafts.md` | state | negotiate | — | no |
| offernotes | `offer-notes.md` | state | offer | — | no |
| applicationdata | `application-data.md` | state | apply | `apply` | no |
| companyresearch | `company_research/*.json` | analysis | research | `build`, `interview` | no |
| corpus | `all_boards_data/all_jobs.json` | state | corpus | `rank`, `audit` | no |
| ranking | `ranked-jobs-*.json` | state | rank | `build` | no |
| coverage | `nz-job-search-coverage-*.json` | state | sources | `audit` | no |
| upskill | `upskill.md` | state | upskill | — | no |
| lessons | `LESSONS.md` | state | aar | `*` | no |
| workspace_state | `.dossier/workspace.json` | state | setup | `*` | no |
| loop | `.dossier/agent-loop.json` | state | loop | `*` | no |
<!-- dossier:contract:end -->
