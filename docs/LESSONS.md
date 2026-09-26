# Lessons

Every entry is something that actually failed on real data. Each one is now
either a rule in `src/dossier/` or a test in `tests/` — if you delete the code,
delete the entry; if you find a new failure, add both.

Read this before changing the engine.

---

## 1. Job records must carry unique ids

**Expected:** filtering the jobs pane would reduce the rendered rows to the
matching set.
**Actual:** the counter updated to the filtered count while the table body kept
the wrong rows, because 1789 records shared only 1669 distinct ids and the UI
keyed rows on the duplicated id.
**Why:** the builder used `setdefault("id", i)`, so ids inherited from earlier
board exports survived. The collision was invisible until a filter changed the
rendered list length.
**Rule:** `corpus.build_facets` always reassigns sequential ids, and every board
folder is re-id'd on combine.
**Test:** `test_build_facets_always_reassigns_unique_ids`.

## 2. A fit score must never be carried across a shared listing URL

**Expected:** propagating scores from the ranking view onto the aggregate would
fill in the missing fits.
**Actual:** several sources publish many distinct roles behind one listing URL
(`careers.farmers.co.nz/jobdetails`, `nz.indeed.com/viewjob`). Keying on URL
alone would have copied one posting's score onto unrelated rows.
**Why:** a URL is a location, not an identity.
**Rule:** `corpus.match_row` resolves by unique url, then unique title+employer,
then title inside its own url group — and returns no match rather than a guess.
**Test:** `test_propagate_fit_never_guesses_across_a_shared_listing_url`.

## 3. Do not drive Word PDF export through `docx2pdf` on this host

**Expected:** re-rendering PDFs from their newer DOCX sources would succeed for
every pair.
**Actual:** the first file converted and the remaining 17 failed with
`AttributeError: Open.SaveAs`.
**Why:** `docx2pdf` attaches to any registered Word instance, and a stale
invisible `WINWORD.EXE` left by an earlier run made `Documents.Open` return a
non-document. The visible-instance state was invisible in the error text.
**Rule:** `render.export_pdf` uses `DispatchEx` for a private instance,
`ExportAsFixedFormat`, and always quits.
**Test:** `test_available_renderers_is_honest_about_absence`; the private-instance
path is exercised whenever a real render runs.

## 4. Verify index freshness numerically before claiming a workspace is synced

**Expected:** files rewritten during a session would be picked up by the live
watcher and re-indexed.
**Actual:** a probe file left the indexed count unchanged and Word-rewritten PDFs
kept stale index mtimes, so the audit still reported 37 out-of-date renders after
they had been rebuilt. A service restart re-indexed everything correctly.
**Why:** Word's replace-by-rename write pattern was not reflected as a change
event. The root cause was never established; a count-based probe was too coarse
to say whether the watcher or the write pattern was at fault.
**Rule:** freshness is proven by comparing each row's `mtime_ns` against
`os.stat` on disk, never by trusting the watcher. `dossier audit` reads state;
`dossier audit --reindex` refreshes it explicitly.
**Open item:** the residual watcher question is still open. Do not describe the
watcher as reliable.

## 5. A coverage snapshot must be resolved, not hard-coded

**Expected:** the audit's source ledger would read current coverage.
**Actual:** it read a hard-coded `nz-job-search-coverage-2026-09-12.json`, so the
ledger, the freshness check and the fit-coverage check all reported stale data
while newer snapshots sat beside it.
**Rule:** `sources.coverage` and `audit._newest_coverage_file` resolve the newest
dated file and accept both published schemas.
**Test:** `test_ledger_separates_policies_and_names_what_the_user_must_supply`.

## 6. Bound a crawl by the responses you actually get

**Expected:** a board's pagination controls describe all current result pages.
**Actual:** one board advertised past page 31 and another through page 11; the
next requested pages returned HTTP 404. An earlier unbounded 34-page crawl hit
the execution guard, and a first bounded batch was misread as empty because its
response snapshot field had not been parsed.
**Why:** stale pagination links survive a shrunken result set, and the browser
response shape was assumed instead of checked.
**Rule:** a source is bounded by observed successful pages, per-page assertions
are non-empty, and a partial capture is never reported as exhaustive.

## 7. `drafted` is not `applied`

**Expected:** the tracker reflects reality.
**Actual:** 38 tracked rows, all `drafted`, and no application was ever submitted
— which is correct, and exactly the state a careless summariser would round up to
"38 applications sent."
**Rule:** only the user's confirmation moves a row, and only an explicit
`Applied YYYY-MM-DD` starts a cadence. Both are enforced in
`tracker.record_outcome`, and the second is why `track` mode has a `confirmed-date`
gate.
**Tests:** `test_record_outcome_refuses_to_mark_applied_without_confirmation`,
`test_cadence_will_not_run_without_a_confirmed_date`.

## 8. A text diff is not a layout check

**Expected:** identical extracted text meant the document was fine.
**Actual:** reusing each block's own trailing blank paragraph instead of cloning
a uniform separator left an uneven, visibly cramped gap — after the block that
landed last lost its separator. Every text check passed.
**Why:** whitespace position is not text content.
**Rule:** `tailor.reorder_cell_blocks` clones one blank paragraph as the
separator, and no render is described as "visually verified" without a rendered
page image being inspected.
**Test:** `test_visual_check_catches_text_past_the_margin`.

## 9. An unverifiable number must be dropped, not caveated

**Expected:** the negotiation mode reports achievements with their estimated
value.
**Actual:** a story-bank figure whose exact value and unit did not appear
verbatim in the resume could have been carried into a sentence the user would say
out loud to an employer.
**Why:** a caveat does not survive contact with a real conversation.
**Rule:** `negotiate.verify_claim` drops the claim silently, boundary-aware so
`8 hours` does not match inside `18 hours` and `60%` does not match inside `160%`.
And wage and frequency are never guessed.
**Tests:** `test_verify_claim_is_boundary_aware`,
`test_negotiate_reports_uncalculable_rather_than_guessing_a_wage`.

## 10. A prompt file must not embed live state

**Expected:** a generated `AGENTS.md` would verify as current on the next check.
**Actual:** `dossier agent adapters --check` reported every pack stale the moment
after it was written, because the managed block embedded the workspace's own file
count — and writing the packs changed that count.
**Why:** a committed document that contains a number the repository changes is
wrong by construction, and can never verify.
**Rule:** `adapters._core` derives the block from the manifest and the workspace
path only. Live facts are fetched by running `dossier agent status`.
**Test:** `test_adapters_write_every_pack_and_verify`.

## 11. `all` is not the builtin once you define a function with that name

**Expected:** a verification report would say whether every check passed.
**Actual:** `TypeError: all() missing 2 required positional arguments`.
**Why:** `verify.all` shadows the builtin inside its own module, so the summary
line called the verification entry point instead of the builtin.
**Rule:** `verify._all_ok` spells the fold out. Avoid module-level names that
shadow a builtin you also use.

## 12. Reading is not running

**Expected:** an inherited batch generator "looks fine on disk."
**Actual:** a generator that imported its job list from a sibling module crashed
on run after that sibling was renamed — while appearing intact.
**Rule:** a generator is self-contained, and it is executed once and its count
checked before anything it produces is shown to a user. `dossier` commands work
the same way: gate commands exit non-zero, so assert on the exit code rather than
reading prose.
**Test:** `tests/test_matrix.py` executes every command the contract declares.

## 13. An engine function name is not a command line

**Expected:** a brief's "run these first" commands would run.
**Actual:** 6 of 21 modes handed the model a command argparse rejects —
`dossier jd_skill_gap` (it is `dossier keywords gap`), `dossier tracker cadence`
(it is `dossier track cadence`), `dossier tailor build` (it is
`dossier tailor replace`). The command was being derived from the `engine` field
by splitting on a dot and hoping.
**Why:** the two are different things. `tracker.cadence` names a function;
`dossier track cadence` names a command line, and the mapping between them is a
decision, not a transformation.
**Rule:** each mode declares its own `command` in `MODE_COMMANDS`, with `<...>`
marking a value the caller must supply, and the brief marks a command `runnable`
only when it has no placeholder.
**Test:** `test_every_declared_command_parses`,
`test_every_self_contained_command_runs`.

## 14. A gate that names code which does not exist is decoration

**Expected:** the manifest's `engine` and `enforced_by` fields would point at the
code doing the enforcing.
**Actual:** `tailor.build`, `corpus.build`, `audit.workspace`, `render.stale`,
`negotiate.roi`, `audit.handoff` and a bare `jd_skill_gap` all named symbols that
were never written under those names. A reader following the contract landed
nowhere.
**Rule:** engine references are full paths from the package root
(`engine.corpus.combine`, `agent.workspace.resolve`, `audit.build_handoff`) and a
test resolves every one of them.
**Test:** `test_every_declared_engine_symbol_exists`,
`test_every_gate_enforcer_symbol_resolves`.

## 15. An unbounded stream is a trap for every other client

**Expected:** a script enumerating the API would get an answer from each route.
**Actual:** it hung forever on `/api/events`, whose loop never ends. The route was
fine for the one UI that knew about it and fatal for anything else, including the
test that was supposed to be checking the API surface.
**Rule:** `/api/events` is bounded by a `seconds` parameter (default 300),
declared in `STREAMING_PATHS`, and covered by its own test rather than the sweep.
**Test:** `test_the_streaming_route_is_declared_and_bounded`.

## 16. `AppConfig.create` describes a layout; it does not create it

**Expected:** `dossier audit --root <new folder>` would audit.
**Actual:** `sqlite3.OperationalError: unable to open database file`, because
`.dossier/` did not exist yet. `create_app` had always called `ensure()` first, so
the bug only lived on the command line — which is exactly where a person meets it
first.
**Rule:** `cli._open_index` calls `ensure()` and crawls once when the index is
empty.
**Test:** `test_every_self_contained_command_runs`.

## 17. Two copies of one rule drift

**Expected:** one answer per question.
**Actual:** the repository held four pairs of the same rule: `domain_jobs` and the
engine both parsed the tracker and loaded the corpus; `audit.SOURCE_POLICIES`
restated `engine.sources.POLICIES`; `convert.routes` and `engine.render.routes`
each declared conversion fidelity; the workspace resolver and the importer each
re-implemented "is this the user's base document?".
**Why:** each pair was written at a different time by a different path, and
nothing compared them.
**Rule:** one implementation per rule — `engine.tracker`, `engine.corpus`,
`engine.sources`, `engine.render`, `engine.tailor` — with the older surface
delegating to it or removed. `domain_jobs` and six unreferenced `api/*` re-export
stubs were deleted outright.
**Test:** `test_every_declared_engine_symbol_exists` plus the engine suites.

## 18. A prerequisite named for something nothing resolves is a permanent lie

**Expected:** the Build mode would stop telling a model it needs a base document
once the workspace had one.
**Actual:** it declared `needs=("base.docx",)`. The resolver's keys are
`base`, `resume`, `docx`, `posting`, `root`, `identity`, `offer`, `outcome`,
`user` — so `base.docx` matched nothing and reported itself unresolved forever,
in a workspace that already had `base-resume.docx`.
**Why:** the value was written as a filename where the field wanted a key, and
nothing compared the two lists.
**Rule:** `manifest.NEED_KEYS` is the closed set, `MANIFEST.USER_SUPPLIED` marks
the ones only the user holds, and a test rejects any other value.
**Test:** `test_every_declared_need_is_a_known_key`.

## 19. The section a model is told to run first should not be below the fold

**Expected:** a rendered brief with one of each section.
**Actual:** an edit left two identical `## Inputs you may open` sections, and the
`## Run these first` block sat under forty lines of resolved file paths — so on a
real screen the commands were off the bottom of a scrollable card. A duplicated
heading hides a section silently; nobody re-reads a rendered packet to notice.
**Rule:** the commands render immediately after the workspace facts, and tests
assert both section uniqueness and that order.
**Test:** `test_the_rendered_brief_has_no_duplicate_section`,
`test_the_commands_come_before_the_file_list`.
