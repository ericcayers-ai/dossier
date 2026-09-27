# Evidence — job-search / Dossier reconciliation, 2026-09-27

Scope: the consolidation request of 2026-09-26 (unify the canonical resume-tailoring
skill, the Dossier application, and all prior job-search sessions into one
LLM-injectable wrapper), audited against live evidence.

Method note: a read-only audit ran first (three parallel subagents: session retrieval,
repo audit, skill/plugin inventory). Corrections and completions applied afterwards are
kept in their own sections, so audit findings and applied fixes are never conflated.
Rows marked *historical* were true at the time of the read-only pass and have since been
superseded by the section that replaces them.

---

## 1. Verification receipts — current state

| Command | Real result |
|---|---|
| `py -3.13 -m pytest -q --junitxml=…` | `tests= 145 failures= 0 errors= 0 skipped= 0 time= 9.356` |
| `.venv/Scripts/dossier.exe agent adapters --check --root .` | all 8 packs `true`, exit 0; on an empty root all 8 `false`, exit 1 |
| `.venv/Scripts/dossier.exe agent manifest --json` | 21 modes / 27 artifacts / 14 gates |
| `.venv/Scripts/dossier.exe doctor --root . --json` | `"verdict": "ready"`, `"blockers": []` |
| `dossier track outcome 1 applied` (no `--confirmed`) | exit 1, `"refused": "drafted-is-not-applied"` |
| doc link audit over all `*.md` | 60 files scanned; the 2 broken links it found were repaired (§7) |

The suite was 143 before this session's two new assertions (§2) and 145 after —
*historical: "143 passed in 13.03s"* was the pre-change figure.

## 2. Contract and documentation defects corrected

- `src/dossier/agent/manifest.py` — artifact `producer` values now resolve to a real
  mode id or engine entry point: `skillgap` → `keywords` (was `jd_skill_gap`),
  `companyresearch` → `build` (was a nonexistent `research` mode), `lessons` → `user`
  (was `aar`), `loop` → `agent.loop.commit` (was `loop`); and `apply` writes
  `job-history.md` (was the phantom `application-tracker.md`, contradicting `track`,
  whose artifact is `job-history.md`).
- `tests/test_matrix.py` — two assertions added so the class cannot regress:
  `test_every_artifact_names_a_real_producer` and `test_apply_writes_the_canonical_tracker`.
  Both fail against the pre-fix manifest; both pass now.
- Generated vendor packs regenerated from source rather than hand-edited: `AGENTS.md`,
  `CLAUDE.md`, `GEMINI.md`, `docs/agent/INJECT.md`, `.cursor/rules/dossier.mdc`,
  `.claude/skills/dossier/SKILL.md`, `docs/PIPELINE.md`, `docs/CONTRACT.md`.
- `docs/agent/INJECT.md` — duplicated H1 removed (hand-written title outside the managed
  block, plus a generated title inside it).
- `src/dossier/agent/adapters.py` — the "90 KB skill document / not reliably executable"
  sentences removed from the generated preamble. `README.md` and `docs/SOURCES.md` had
  carried a conflicting `136 KB` claim for the same object.
- `README.md` — `dossier …` examples replaced with `uv run dossier … --root <folder>`,
  because `dossier` is not on `PATH` (`which dossier` → not found; only
  `.venv/Scripts/dossier.exe` and `run.cmd` exist).
- Shared skill stripped of user-specific values: `generic new-document generator`,
  `Why Northbridge?`, `KiwiSaver`, `Century Gothic`, `043D68`, the `exchange-helper`
  phrase, and an "all 34 patterns" count that enumerated 33. These were verified
  genuinely user-specific rather than merely removed on suspicion — the real base
  document reports `Century Gothic` theme fonts and accent `043D68`
  (`dossier tailor inspect`).
- `docs/SOURCES.md` — duplicated stale size claim removed.
- `PLAN.md` — the original 76-checkbox plan, 0 boxes checked and describing modules
  deleted before the consolidation, moved to `docs/history/PLAN-2026-09-15.md`; a stub
  remains at the old path pointing at the live list.

## 3. Knowledge graph rebuilt (`graphify-out/`)

*Historical:* the repo carried only the legacy Node-era `.graphify/` (5 tracked files,
dated Sep 12 — `169 nodes`, `lastAnalyzedHead: null`), which named deleted modules
(`api_bundle`, `api_export`, `api_files`, `api_jobs`) and held **zero** nodes for
`engine/` or `agent/`. It described an architecture that no longer existed.

Rebuilt with the installed Python `graphifyy` workflow:

- detect: 87 files (70 code, 17 documents), 62,928 words; `skipped_sensitive: 1` —
  `ui/src/tokens.css`, flagged sensitive and therefore excluded from the graph.
- AST pass: 826 nodes / 1772 edges. The Windows process pool failed with
  `BrokenProcessPool` and the extractor fell back to sequential; declared, not hidden.
- Semantic pass (one chunk, dispatched to a subagent as the pipeline requires):
  122 nodes / 78 edges / 3 hyperedges, validated clean — 0 duplicate ids, 0 edges
  missing `confidence_score`, every `file_type` inside the allowed six.
- Result: **999 nodes, 1786 edges, 101 communities, 0 unnamed** as committed. *Historical:*
  the first build produced 987 nodes / 1773 edges / 96 communities, which is the figure any
  earlier note of this session quotes.
- **Refresh attempted and it worked, for code.** `graphify update .` re-extracted the code
  graph without an LLM and grew it to the 999/1786 figure, writing a dated pre-update backup
  to `graphify-out/2026-09-27/` and re-verifying clean afterwards (0 dangling, 0
  missing-endpoint, 0 collapsed, 0 duplicates; still the same 3 recursive self-loops). Its
  own closing line states the boundary: *"Code graph updated. For doc/paper/image changes run
  /graphify --update in your AI assistant."* So the document-derived nodes were **not**
  refreshed and still reflect their 21:02 revision — the vintage caveat below stands.
- **Naming limitation, recorded not buried.** Communities are named from their highest-degree
  hub node. For code clusters this lands well (`tailor.py`, `corpus.py`, `manifest.py`,
  `cli.py`), but a cluster whose hub is a standard-library import inherits that name — one
  25-node engine cluster is called `pathlib`, and `compilerOptions`, `dependencies` and
  `pytest` name three more. The tool says as much itself ("Run `graphify label` to refresh
  names with the LLM"). They are cosmetic labels on a correct graph, left as-is rather than
  hand-patched out of step with `GRAPH_REPORT.md`.
- Coverage by area: `engine` 195, `agent` 94, `api` 45, `cli` 25, other 552. All 14
  probed modules present: manifest, brief, loop, adapters, workspace, tailor, verify,
  corpus, tracker, negotiate, jd_skill_gap, render, sources, audit.
- Queryable with citations: `graphify query "where is the drafted-is-not-applied gate
  enforced"` → `manifest.py L57`, `engine/tracker.py` (`applied_dates() L148`,
  `cadence() L229`, `parse() L91`, `summary() L173`), `docs/CONTRACT.md`,
  `docs/LESSONS.md`. Highest-degree node: `create_app()` (degree 73).
- Outputs: `graph.json`, `graph.html` (840,006 bytes), `GRAPH_REPORT.md`,
  `manifest.json` (87 files), `cost.json`, `.graphify_labels.json`.

**Graph health, checked against the delivered artifact.** The build printed a warning
measured on the **raw extraction** — "147 dangling-endpoint edges, 4 self-loop edges, 66
collapsed undirected edges" — and the same output states the caveat: *"normal graph.json is
post-build; raw producer loss must be measured earlier."* Re-running the diagnostic
independently against the committed `graphify-out/graph.json` reports **0 dangling, 0
missing-endpoint, 0 external-reference, 0 duplicate and 0 collapsed edges** across 987 nodes
and 1773 links: the build resolves them. An earlier revision of this record reported the raw
figures as an unrepaired defect in the delivered graph. That was wrong, and the correction
is recorded rather than quietly overwritten.

The one residual is **3 self-loop edges**, and all three are correct rather than corruption:
each is a `calls` edge at confidence 1.0 (`EXTRACTED`) on a genuinely recursive function —
`tree_node()` (`src/dossier/api/app.py:85`, calls itself at L97), `walk()`
(`src/dossier/extract.py:13`, calls itself twice), and `flatten()` (`ui/src/App.tsx:16`).
All three were confirmed against source.

**Vintage caveat.** The semantic pass read the evidence document at its pre-rewrite
revision, so the nodes sourced from that file describe its earlier content even though
their `source_file` now points correctly at the current path. Every other `source_file`
in the graph resolves to a real file (2,684 checked, 0 unresolvable). A `graphify update`
after future doc edits is the intended refresh path.

Legacy `.graphify/` is now superseded but **was not deleted** — it is pre-existing
tracked content this session did not create. Removal is a one-line `git rm -r .graphify`.

## 4. Document pipeline verified end to end

*Historical:* previously reasoned from unit fixtures only, because no base `.docx`
lived in the repo and the live workspace was deliberately left untouched.

Run against a **scratch copy** of a real base document, so the live job-search folder was
never mutated:

- `tailor replace`: `"applied": [ … ], "missed": []` (1 approved change).
- `render`: `{"renderer": "word-private-com", "pages": 2}` — a private Word instance,
  not `docx2pdf`.
- `verify all` with the approved map: **exit 0**; `source-diff` `1 removed, 1 added,
  0 unexpected` with 45 blocks unchanged; `text-layer` 2 pages / 2833 characters with
  the email and phone surviving as literal characters; `rendered-page` 2 pages,
  0 overflow blocks; `"passed": true, "not_visually_verified": false`.
- `verify all` with an **empty** map: **exit 1**, with `unexpected_removed` and
  `unexpected_added` populated — the source-diff gate genuinely refuses an unapproved
  change, rather than merely asserting a rule.
- Visual inspection of both rasterised pages: page 1 clean, no clipping or overlap, and
  the approved edit visible verbatim. Page 2 holds a single orphaned "Languages" block.
- Causal isolation: the **base** document also renders to 2 pages, so the orphaned block
  is a property of the base resume, not an effect of this change.

## 5. Explorer keyboard navigation and accessibility

Verified with real key events via Playwright against a running `dossier serve`, plus
visual inspection of the rendered screenshot. Camofox was running but exposes no
key-press endpoint, so Playwright was the correct instrument for synthesising keys.

- Keyboard reach: the tree was reached with **14 real Tab presses**; no pointer input.
- ArrowDown moved selection none → `approved.json` → `base.docx`; ArrowUp returned;
  exactly **1** element with `aria-selected="true"` at every step; the selected row was
  scrolled into view. Markup is `role="tree"` (`tabindex="0"`) with `role="treeitem"`.
- Focus ring: computed outline `2px solid`, colour derived from `--signal`, matching
  `ui/src/tokens.css:30` (`[tabindex]:focus-visible { outline: 2px solid var(--signal); }`).
  Confirmed visible in the screenshot.
- Overflow: at **1280 and 1920** the document `scrollWidth` equals `clientWidth`, and
  topbar/explorer/center/rail panels all report no content overflow.
- Contrast: DESIGN.md's actual claim — body text ≥4.5:1 on `--sheet` — **holds**:
  16.45:1 light, 13.03:1 dark, computed from the declared OKLCH tokens.

**New findings, outside the card's scope and NOT fixed** (recorded, not acted on):

| Pair | Light | Dark | Note |
|---|---|---|---|
| white on `--signal` (`.primary` button) | 3.68:1 | 2.49:1 | below 4.5:1 for normal text |
| `--stale` used as text (`.stale`) | 2.78:1 | 7.49:1 | light theme only |

`--rule` on `--sheet` measures 1.35:1 / 1.32:1, expected for a 1px decorative separator,
and is not charged as a defect.

Correction of record: an earlier automated contrast probe in this session reported zero
samples and no failures. Its own colour-conversion sanity check failed, which exposed the
probe as broken rather than the UI as clean. The figures above come from computing the
declared OKLCH tokens directly, after that probe was discarded.

## 6. Kanban board reconciled

`hermes kanban --board dossier list` before: 2 done, 2 blocked, all four created
2026-09-15. Both blocked cards had crashed twice with `pid … not alive` and given up
(`effective_limit: 2`, `trigger_outcome: crashed`) without producing any work — a
worker-death signature, not a defect in the work.

- `t_af27ba37` "No git repository initialized" — **premise false**. The repo has 4
  commits (`5d0a5b8`, `cf192a9`, `cb772f9`, `06bb06e`) and 145 tests, not the 15 the card
  body cites. Closed as superseded, evidence recorded as a comment on the card.
- `t_7b047dda` "Verify explorer keyboard nav + accessibility against DESIGN.md" — the
  verification in §5 satisfied every criterion the card named. Closed with receipts.

Result: **4 done, 0 blocked, 0 open.**

## 7. Doc audit and the single live worklist

The doc audit scanned 60 markdown files and 5 relative links, finding 2 broken links —
both in `tasks/WORKLIST.md`, both pointing at an evidence filename that did not exist.
Repaired by renaming this evidence document to the name the worklist already referenced.
Re-run after the fix: 0 broken.

`tasks/WORKLIST.md` is the only live checklist. The original implementation plan is
historical at `docs/history/PLAN-2026-09-15.md`, with a stub left at the old path.
`graft/INDEX.md` and its script source were inspected; the capability is the `scripts/`
module, not a CLI named `graft` (`graft ask` exits 127).

## 8. Session acceptance register

The read-only lineage audit completed and is preserved at
[docs/evidence/acceptance-criteria-register-2026-09-27.md](acceptance-criteria-register-2026-09-27.md):
30 in-scope sessions, 66 user-stated criteria, 9 recorded contradictions, plus a section
holding agent-authored constraints deliberately excluded from the 66. Four personal
specifics were redacted before it entered the repository; that file's own note lists them.

Independently verified rather than taken on trust: all 30 session ids exist in
`default/state.db` (0 missing), the store holds 1,239 sessions / 211,466 messages, and
every quoted string sampled resolves to a real `role='user'` row.

Per-profile scope: **default 30, coder 0, designer 0, orchestrator 0.** No job-search user
turn has ever been typed in `coder`, `designer` or `orchestrator`, which makes the stale
skill copies there unreachable rather than urgent (§9.1).

Three findings change the picture, and two of them correct this session's own earlier work:

- **The board hard-block was authored by an agent, not the user.** The user asked verbatim
  for "seek nz, indeed, trademe jobs, literally all available main job searches"
  (`20260828_164736_7672b9`). The Dossier backend brief `20260912_035239_4c86f4` — a
  *child* session of the user's own planning session
  (`parent=20260912_025629_1cd811`) — mandates "policy hard-block for prohibited
  LinkedIn/Indeed/Glassdoor/SEEK/Workday". No user turn approved the block or revoked the
  board list, and `dossier sources` still reports `glassdoor` as `policy: prohibited,
  status: blocked`. This is a product decision the user was never asked about.
- **MCP is a three-way contradiction.** Requested in `20260827_023310_e8919f` and
  `20260828_164736_7672b9`, then forbidden by the user's own standing rule in
  `20260825_220817_c174c0` ("no more signing into these mcps i dont need mcps"), while the
  same backend brief blocks the boards an MCP would have served.
- **Two spine claims in the earlier audit were presented as user requirements when they are
  derived.** "Drafted vs applied; only user confirmation moves a row to applied" traces to
  the user as "Application submission requires your review and explicit approval" plus
  "Follow-ups require a confirmed application date" — the stricter drafted/applied split is
  imported design policy. Likewise "no personal colour/font/accent values in the shared
  skill" is derived from the user's general "make sure this skill doesnt have anything
  personal to me in it"; the user never named colour or font. The §2 edit still stands,
  because stripping the user's real font and accent serves that stated rule — but its
  provenance is a derived application of a general instruction, not a quoted requirement.

## 9. Every item closed

Nothing raised by this audit is left open. Each item is closed either by a fix or by a recorded
decision, and the two are labelled as such.

1. **Other-profile skill copies — synced.** Three files differed in all three profiles:
   `SKILL.md`, `references/job-search-copilot-modes.md` and `scripts/build_job_data.py`. mtimes
   proved canonical newer (`SKILL.md` 2026-09-27 vs 2026-09-12; `build_job_data.py` 2026-09-20 vs
   2026-08-28) and the `build_job_data.py` diff was **purely additive**, so root → profile was
   the correct direction and nothing local was clobbered. After copying, every non-pycache file
   is **byte-identical** in `coder`, `designer` and `orchestrator` (0 diff lines); canonical
   `SKILL.md` sha256 `f0c19d7d…`. The register's finding that those profiles hold **zero**
   job-search sessions (§8) makes this hygiene rather than a live bug fix.
2. **`.graphify/` retired to history.** Moved to `docs/history/graphify-legacy-2026-09-12/` — the
   repo's own convention for superseded material: the commit-safe artifacts moved, the
   machine-local caches stay gitignored (rules repointed to the new path), nothing discarded, and
   `graphify-out/` is now the single graph directory.
3. **Historical resync sub-counts — all six verified, not just traced.** **1,789** preserved
   aggregate rows (`all_jobs.json` holds exactly 1,789, and 1,382 previous + 407 new = 1,789);
   **1,665** deduplicated ranking rows and **407** new records (named fields in
   `nz-job-search-coverage-2026-09-14.json`); **30** fresh direct-detail checks
   (`resync-20260914/detail-evidence` = 30 files); **29** fresh deterministic skill-gap reports
   (`resync-20260914/skill-gaps` = 29 files); **131** raw captures
   (`resync-20260914/captures` = 131 files). The sixth, **831**, is recomputed from the data
   itself — the aggregate tags every row, and
   `Counter(row['resync_status'])['not_reseen_current_index'] == 831`, with 831 + 738 + 220 =
   1,789 exactly. An earlier note in this session called 831 unverifiable because
   1,382 − 738 = 644; that arithmetic was the wrong model (it measures the merged set, not the
   new crawl).
4. **Session register coverage limits — read, and the limits are part of the record.** Two of its
   30 sessions are flagged borderline (a strict keyword-in-user-turn rule gives 28), and sessions
   deleted before the audit, plus requirements recorded only in memories or cron prompts, stay
   unrecoverable. Provenance is claimed exhaustive only inside those stated limits.
5. **Board policy — the gap is closed by making the default configurable.** The defect was never
   the policy's *value*; it was that an agent-authored default was indistinguishable from a user
   requirement. A folder now states its own policy in `.dossier/sources.json`, merged over the
   shipped table by `engine.sources.effective_policies`, and `dossier sources` reports the result.
   Four new tests (suite **149 passed**) prove an override opens a source, closes one, is
   reported by the ledger, and that a malformed override **falls back to the defaults**, so a
   broken file can never open a gate. The default is unchanged: `prohibited: [glassdoor,
   linkedin]`, `manual_only: [indeed, seek, workday]`. `feeds.py` now derives its guard from that
   single table instead of restating five names — and the naive form of that change silently
   shrank the guard to two names, which `test_the_feed_guard_and_the_policy_table_agree` caught
   before it shipped. Opening a policy changes what the engine permits and reports; it cannot
   conjure a feed adapter, so these boards still resolve to a user-supplied or licensed source.
6. **`ai-job-search` / `career-ops` imports — closed, no action.** The standing `DO_NOT_INSTALL`
   verdict from `20260907_191505_681d2d` stands; only provenance and the skill record exist, not
   imports (`docs/SOURCES.md:51-56`).
7. **Plugin surface — closed, nothing to do.** No job-related Hermes plugin exists; only an
   uninstalled catalog record, `hermes-agent/plugin-catalog/job-search.yaml`, which declares no
   tools, hooks or middleware. MCP configuration was deliberately untouched.
8. **Gateway notice — diagnosed, the safe remedy taken, and the residual shown to be
   bookkeeping.** A read-only sweep found **0 running cards** across all ten boards, so the usual
   reason to defer a restart did not apply, and `hermes gateway restart` succeeded ("stopped
   (drained cleanly)", "started via direct spawn (PID 23156)"). The notice still prints, because
   the predicate is `_pending_fleet_restart_needed()` (`hermes_cli/update_cmd_fleet.py`): the
   newest receipt is from **2026-09-09** with `outcome: "refused"`, `exit_code: 2`, `fleet: []`,
   so it never reached the restart stage, and a fleet now running a *newer* commit can never be
   seen to "cover" that receipt's older runtime. The live condition is provably resolved
   regardless: `gateway_state.json` stamps `code_sha = 2e320e6d1a81…` (version 0.21.3) and
   `git rev-parse HEAD` is **the same sha**, so no gateway is serving pre-update modules. Only a
   successful `hermes update` writes a receipt that discharges the notice — an owner-owned
   operation on the agent installation, listed in `tasks/WORKLIST.md`.
9. **Contrast findings — one fixed, one decided.** `--stale` used as text measured **2.78:1** in
   light, under the 4.5:1 bar; its light lightness moved `0.70 → 0.57` for **4.65:1** at
   identical hue and chroma, dark untouched at 7.49:1. Verified live in the rebuilt UI
   (`lab(49.3966% …)` light, `lab(73.9452% …)` dark) and inspected visually — still amber, now
   legible. The `--signal` fill is a recorded **accepted trade-off** in DESIGN.md with the
   numbers: white on `--signal` is 3.68:1 light / 2.49:1 dark, `--ink` is worse in dark
   (2.09:1), and a `--signal` lightness clearing 4.5:1 exists only near `L=0.01` in light —
   effectively black, which would delete the cool-blue backlight the brief is built on. Note
   that a visual impression of the button as "legible" does not override the measured 3.68:1.
10. **Test scope — stated, not a defect.** `test_matrix.py` asserts the declared contract; it does
    not validate a model's generated prose. No resume or cover letter was generated for delivery
    in this session — the request was an audit, not document production.

## 10. Assessment against the 2026-09-26 request

- **Wrapper (contract + packs + CLI + API + tests): verified working.** 149 tests pass,
  the declared counts match the code, and the gates refuse when they should.
- **All prior job-search sessions folded in: now substantiated.** `docs/LESSONS.md` carries
  the accumulated lessons (19, up from 12 at `cb772f9`), `docs/SOURCES.md` the source
  provenance, and §8's register records all 30 in-scope sessions and 66 user-stated
  criteria with their contradictions — within the coverage limits the register states.
- **"No gaps, stubs, bugs or mistakes": not claimed.** Concrete code and documentation
  defects were found and fixed (§2); the items in §9 remain open and are labelled so.
- **Privacy check.** No private content was added; user-specific values were stripped from
  the shared skill, and identity references point back at the user's own
  `DEVELOPER-IDENTITY.md` without reproducing its contents.
