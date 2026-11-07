# Dossier worklist

The only live repository checklist. The original app plan is historical at
[docs/history/PLAN-2026-09-15.md](../docs/history/PLAN-2026-09-15.md); a stub remains at the
old path. Full receipts: [job-search reconciliation, 2026-09-27](../docs/evidence/job-search-reconciliation-2026-09-27.md)
and the [acceptance-criteria register](../docs/evidence/acceptance-criteria-register-2026-09-27.md).

Checkbox rule: an item is ticked only with a quoted tool receipt behind it. Where a result is
machine-verified but not owner-confirmed, the item says so.

## Open items

**Corrected 2026-11-05: the Trajectory Tree is committed.** The note that stood here said
"one open item: the Trajectory Tree work is uncommitted". That was true against
`HEAD` = `701c1fd`, and it stopped being true at `f8a1f8b` and `c043aa0`. Measured today
on `c043aa0 feat(tree): wire the trajectory DAG into the CLI, the API and the agent
manifest`:

```text
$ git show HEAD:src/dossier/engine/tree.py | wc -l
640
$ git show HEAD:src/dossier/cli.py | grep -c tree
17
$ git show HEAD:src/dossier/api/app.py | grep -c tree
38
$ git show HEAD:src/dossier/agent/manifest.py | grep -c tree
7
$ git ls-tree -r --name-only HEAD tests | grep -c tree
4
$ git ls-tree -r --name-only HEAD ui/src/trajectory | wc -l
2
```

A worklist that keeps saying "uncommitted" after the commit makes the next session redo
work that is already on disk, so the stale paragraph is replaced rather than kept. The
historical receipts below stay as written — they record what was measured on those dates,
and each one now sits beside the state that supersedes it.

Measured 2026-10-11 against `HEAD` = `701c1fd1ef230b7b2f0c817e5dc600866267284a` (branch
`master`), which was accurate then: that revision contained **zero** occurrences of the
feature.

```text
$ git show HEAD:src/dossier/agent/manifest.py | Select-String trajectory | Measure-Object -Line
0
$ git show HEAD:src/dossier/cli.py | Select-String tree | Measure-Object -Line
0
$ git show HEAD:src/dossier/api/app.py | Select-String trajectory | Measure-Object -Line
0
```

Untracked paths the feature depended on in that revision (all of them are in `HEAD` now —
verified with `git ls-tree -r --name-only HEAD` on 2026-11-05):

| Path | Bytes | In `HEAD` on 2026-10-11 | In `HEAD` today |
|---|---|---|---|
| `src/dossier/engine/tree.py` | 32,416 | no | yes, 640 lines |
| `tests/test_tree.py` | 15,637 | no | yes |
| `tests/test_tree_api.py` | 9,698 | no | yes |
| `tests/test_tree_cli.py` | 2,278 | no | yes |
| `tests/test_tree_contract.py` | 1,312 | no | yes |
| `tasks/plan.md` | 4,044 | no | yes |
| `ui/src/trajectory/TrajectoryPane.tsx` | 14,891 | no | yes |
| `ui/src/trajectory/trajectory.css` | 7,848 | no | yes |
| `docs/evidence/trajectory-tree-corpus-baseline-2026-10-01.json` | 1,171 | no | yes |

**Superseded.** That commit decision has since been made: `f8a1f8b` and `c043aa0` carry the
feature, and `git show HEAD:<path>` returns every file in the table.

Plan: [tasks/plan.md](plan.md).

**Built 2026-11-06: the seven-reviewer hiring panel.** Filed 2026-10-12 as a product mode outside the contract; implemented as `engine/panel.py` (seven deterministic seats, each scoring and quoting the line behind its objection, plus a chair's three rewrites), CLI `dossier panel`, route `GET /api/panel` and the Agent → Panel pane. The original filing note is kept below because its measurement is what justified building it. Instagram
reel `DeVIz_uS06F` ("7 CLAUDES REJECT YOUR RESUME", 36 s, Roblox-style 3D explainer,
ingested 2026-10-12; frames in `reelkit/reels/DeVIz_uS06F/frames/`, digest in
`reelkit/DIGESTS.md` §36) shows a Claude skill invoked as `/hiring-panel my-resume...`
that runs seven agents over one resume: one as the robot ATS gatekeeper (`THE ROBOT
GATEKEEPER`, `INTAKE` → `HUMAN`, `ATS` card), one as the hiring manager, then five
independent readers (`5 READERS, 5 VIEWS`, panels `1`–`5` badged `ATS` / `APPLICANT` /
`HR`), before rewriting the resume with every mistake fixed (`EVERY MISTAKE FIXED`,
`MISTAKES 6`, `PRINT`).

Nothing can be copied or installed from it: **no repo, URL or licence appears in any of the
40 frames**, and the reel's own call to action is "comment ... and I'll DM you the link".

Measured absence, 2026-10-12, working tree:

```text
$ .venv/Scripts/dossier.exe agent manifest --json              -> 22 modes, no panel mode
$ Select-String -Path src/**/*.py -Pattern hiring-panel        -> 0 matches
$ Select-String -Path src/**/*.py -Pattern rejection           -> 0 matches
$ Select-String -Path src/**/*.py -Pattern persona             -> 0 matches
$ Select-String -Path src/dossier/agent/manifest.py -Pattern panel -> 0 matches
$ Select-String -Path src/**/*.py -Pattern hiring              -> 1 match: manifest.py:258,
  the `interview` mode's own description ("Hiring-manager mock: exactly one question per
  message, scored, with a debrief.")
```

The nearest existing modes are `diagnose` (one senior-ATS read of the resume) and
`interview` (one question per message). Neither runs a multi-persona independent read, and
neither emits a corrected document.

**Status: unverified — no receipt, no implementation, no upstream source.** Filed rather
than actioned because the request was "into dossier if not already", and it is not already.
Any implementation would have to add a mode to `manifest.MODES` with both an engine symbol
and a real command line, regenerate the eight adapter packs, and extend
`tests/test_matrix.py` — and it must not soften `no-fabrication` or `layout-clone`, which is
precisely what a "rewrite the resume to fix everything the panel found" step risks doing.

**Update, same day — built as a DSH skill rather than a Dossier mode.**
`~/.dsh/skills/hiring-panel/SKILL.md` (global, so it applies in this repo too) reproduces
the seven reads and, importantly, produces the corrected draft *through* `dossier agent
route` → `rewrite` / `build` instead of around them, so `no-fabrication` and
`layout-clone` still bind. Receipt: `reelkit/skillforge.py --verify` → 45 skill(s), 45 OK,
0 FAIL. The model-facing proof (`dsh headless` from a foreign cwd) **failed on provider
quota** — `QUOTA: Insufficient Balance` — so "served to a model" is not verified.
**Nothing in `src/dossier/` changed**: this item stays open if you want the engine itself
to own the mode.

## Trajectory work (committed at `c043aa0`)

The receipts below were recorded in the working tree while the feature was uncommitted, and
are kept because the measurements are real. They reproduce from `HEAD` today.

**Re-measured 2026-11-05.** `HEAD` is `c043aa0` (`f8a1f8b` and `c043aa0` are the two tree
commits), and the committed revision contains the feature:

```text
$ git show HEAD:src/dossier/agent/manifest.py | grep -c tree
7
$ git show HEAD:src/dossier/api/app.py | grep -c tree
38
$ git show HEAD:src/dossier/cli.py | grep -c tree
17
$ git show HEAD:src/dossier/engine/tree.py | wc -l
640
```

The dirty tree still verifies green. Tree gate (41 tests, exit 0):

```text
$ uv run --with pytest python -m pytest tests/test_tree.py tests/test_tree_api.py tests/test_tree_cli.py tests/test_tree_contract.py --basetemp=C:/dossier-pytest-temp -q -p no:warnings
.........................................          [100%]   exit 0
```

Falsification check — omitting `tests/test_tree_contract.py` drops the count to 39 (exit 0),
confirming the suite executes exactly its arguments. Agent surfaces:

```text
$ uv run dossier agent manifest --root .             -> exit 0; 22 modes; `trajectory`
  mode/stage and the `trajectory_tree` → `.dossier/tree.json` artifact registered
$ uv run dossier agent adapters --check --root .     -> exit 0; 8/8 packs `true`, 0 `false`
```

No checkbox above is ticked by this re-measurement: the receipt still requires a committed
revision, and the owner commit decision (`"Awaiting an owner commit decision."`, WORKLIST.md:45)
stands. Full receipt:
[autofix2-2026-10-25](../docs/evidence/autofix2-2026-10-25.md).

- [ ] Engine DAG core, tests, safe tree writes, deterministic ASCII/Mermaid, unique tracker
  matching, exact-path artifacts, and read-only source sync. Receipt (dirty tree only): focused
  tree/API/CLI/contract tests passed (41/41 passing in tree test suite; 190/190 passing across
  full repository test suite); canonical-copy probe imported **1,789 jobs + 38 tracker records**,
  linked 17 exact tracker records, kept 21 separate, reported zero ambiguity. Evidence:
  `docs/evidence/trajectory-tree-corpus-baseline-2026-10-01.json` (untracked, 1,171 B, dated
  2026-10-01) — that file holds six checks (`corpus-row-count`, `tracker-row-count`,
  `tracker-exact-match`, `artifact-read-only-projection`, and two `status: manual` entries). It
  supports 1,789 / 38 / 17 / 21; it does **not** contain a SHA-256 check and does **not**
  contain a "119 artifacts" figure, so neither claim is carried here.
- [ ] Authenticated API endpoints and CLI tree actions implemented. `GET /api/tree` remains the
  filesystem view; `GET /api/tree?view=trajectory` serves the graph. In the dirty tree,
  `src/dossier/api/app.py:116` reads `if view == "trajectory":`; at `HEAD` the string
  `trajectory` occurs 0 times in that file. Targeted run receipt: `test_tree_api.py` 6/6 passed,
  `test_tree_cli.py` 2/2 passed.
- [ ] Manifest registers `trajectory` stage/mode and `.dossier/tree.json` artifact without
  modifying the existing 14 safety gates. All **8/8 adapter packs** checked `true` with 0 drift
  (`uv run dossier agent adapters --check --root .`).
- [ ] UI add/link/sync/exports and Generate Next Branch packet implemented in `ui/src/trajectory/`.
  Frontend typecheck and build verified clean with zero TypeScript errors (`npm run build` -> `tsc -b && vite build` exit 0). The whole directory is untracked.
- [ ] Full-stack end-to-end sequential flow verified: Experience -> Touchpoint (inbound email) -> Meeting (screen) -> Opportunity (tailored job) -> Milestone (outcome) with deterministic ASCII and Mermaid graph TD exports.
- [ ] Canonical corpus integration confirmed in `<workspace>/.dossier/tree.json` (1,810 nodes — measured 2026-10-11, file 1,373,953 B). The 1,789 jobs figure is independently confirmed (`all_boards_data/all_jobs.json` parses to 1,789 rows, 2,120,866 B). The 21 unmatched tracker records / 119 artifacts / 0 stubs breakdown and the "source file SHA-256 values were unchanged" claim were **not** re-verified by the C pass and are not carried here.

## Historical resolved items

- [x] **P1** — Contract drift: five `ARTIFACTS` producers named code that does not exist, and
  `apply` wrote a phantom `application-tracker.md`. Receipt: `agent manifest --json` now
  resolves every producer to a real mode or engine entry point.
- [x] **P1** — Regression tests so the class cannot return
  (`test_every_artifact_names_a_real_producer`, `test_apply_writes_the_canonical_tracker`).
- [x] **P1** — Generated packs regenerated from source; duplicated H1 in
  `docs/agent/INJECT.md` removed. Receipt: `agent adapters --check --root .` → all 8 packs
  `true`; on an empty root all 8 `false`, exit 1.
- [x] **P1** — Shared skill stripped of user-specific values (`Century Gothic`, `043D68`,
  `Why Northbridge?`, `KiwiSaver`, `exchange-helper`) and the 33-of-34 count fixed. Verified
  genuinely user-specific: `tailor inspect` reports `"primary_font": "Century Gothic"`,
  `"primary_accent": "043D68"`.
- [x] **P1** — `PLAN.md` superseded (0 of 76 boxes checked, described deleted modules); moved
  to `docs/history/PLAN-2026-09-15.md`.
- [x] **P1** — Code-context graph rebuilt as `graphify-out/`, then refreshed. Receipt:
  `graphify diagnose multigraph` → **1032 nodes, 1821 edges, 0 dangling, 0 missing-endpoint,
  0 collapsed, 0 duplicate**; `engine` + `agent` + `api` modules all present;
  `graphify query "where is the board policy enforced"` → `policy()` `engine/sources.py:77`.
  *Historical:* the figures moved as the graph was refreshed (987/1773/96 first build →
  999/1786 code refresh → 1032/1821 once the documents were re-extracted), and the "147
  dangling-endpoint edges" an earlier note reported were raw-extraction figures the build
  resolves.
- [x] **P1** — Session acceptance register completed and preserved at
  [docs/evidence/acceptance-criteria-register-2026-09-27.md](../docs/evidence/acceptance-criteria-register-2026-09-27.md).
  Receipt: 30 in-scope sessions, 66 user-stated criteria, 9 contradictions, agent-authored
  constraints held separately; independently verified — all 30 session ids exist (0 missing),
  store = 1,239 sessions / 211,466 messages, sampled quotes resolve to real `role='user'`
  rows. Per-profile scope: default 30, coder 0, designer 0, orchestrator 0.
- [x] **P2** — Real document cycle verified end to end on a scratch copy of a real base:
  `tailor replace` (1 applied, 0 missed) → `render` (`word-private-com`, 2 pages) →
  `verify all` exit 0 (`0 unexpected`, `"passed": true`), and exit 1 against an empty approved
  map. Both pages inspected visually.
- [x] **P2** — Explorer keyboard nav and a11y verified live with real key events: 14 Tabs to
  reach the tree, ArrowDown/Up move selection, exactly one `aria-selected` row, 2px solid
  `--signal` focus ring, no overflow at 1280/1920.
- [x] **P2** — Both blocked Dossier kanban cards reconciled and closed; both had crashed twice
  with `pid … not alive`. Board: `4 done, 0 blocked, 0 open`, with evidence comments.
- [x] **P2** — Doc audit clean: the 2 broken links it found were repaired. Corrected
  2026-10-11: the file count was wrong. The repository holds **72** markdown files outside
  `ui/node_modules/`, `.venv/` and `graphify-out/` (45 gitignored `graft/`, 3 `.agent_state/`,
  8 `docs/history/`, 16 in the working tree proper) — no denominator gives 61, and no markdown
  link checker exists anywhere in the repo. Re-verified positively by hand on 2026-10-11: all
  **10** relative links in the 13 binding docs resolve to existing paths, **0 broken**
  (`AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, `README.md`, `DESIGN.md`, `docs/CONTRACT.md`,
  `docs/PIPELINE.md`, `docs/SOURCES.md`, `docs/LESSONS.md`, `docs/agent/INJECT.md` carry none;
  `PLAN.md` carries 3, `tasks/WORKLIST.md` carries 5, `README.md` carries 2). That half of the
  claim stands.
- [x] **P2** — Legacy `.graphify/` retired to `docs/history/graphify-legacy-2026-09-12/`.
  Nothing discarded — its commit-safe artifacts moved, its machine-local caches stay
  gitignored at the new path, and `graphify-out/` is now the single graph directory.
- [x] **P2** — Three stale profile skill copies synced from canonical. Receipt: `SKILL.md`,
  `references/job-search-copilot-modes.md` and `scripts/build_job_data.py` differed in all
  three profiles (mtimes proved canonical newer; the `build_job_data.py` diff was purely
  additive); after copying, every non-pycache file is **byte-identical** in `coder`,
  `designer` and `orchestrator` (0 diff lines), canonical `SKILL.md` sha256 `f0c19d7d…`.
- [x] **P2** — Graph integrity: **no repair was needed.** Receipt:
  `graphify diagnose multigraph --graph graphify-out/graph.json` → `dangling_endpoint_edges: 0`,
  `missing_endpoint_edges: 0`, `collapsed …: 0`, `exact_duplicate_edges: 0`. The 147 dangling /
  4 self-loop / 66 collapsed figures printed during the build were measured on the **raw
  extraction** — the same output says so ("normal graph.json is post-build; raw producer loss
  must be measured earlier"). An earlier version of this list called that an unrepaired defect
  in the delivered graph; that was wrong. The 3 residual self-loops are `calls` edges at
  confidence 1.0 on genuinely recursive functions (`tree_node()` `api/app.py:85`, `walk()`
  `extract.py:13`, `flatten()` `ui/src/App.tsx:16`), each confirmed against source.
- [x] **P3** — Historical resync sub-counts, **all six now verified**. Five recomputed from the
  artifacts: **1,789** aggregate rows (`all_jobs.json` = 1,789 and 1,382 + 407 = 1,789),
  **1,665** ranking rows and **407** new records (named ledger fields), **30** detail checks
  (`resync-20260914/detail-evidence` = 30 files), **29** skill-gap reports
  (`…/skill-gaps` = 29 files), **131** captures (`…/captures` = 131 files). **831** recomputed
  from the data itself: `Counter(all_jobs.json[*]['resync_status'])['not_reseen_current_index']
  == 831`, and 831 + 738 + 220 = 1,789 exactly. Also recounted:
  `NZ-JobSearch-Resync-2026-09-14.zip` = **724 members, 0 directory entries**.
- [x] **P1** — Board policy gap closed by making the default **configurable instead of
  buried**. The user asked verbatim for "seek nz, indeed, trademe jobs, literally all available
  main job searches" (`20260828_164736_7672b9`); the block came from the *agent-authored* brief
  `20260912_035239_4c86f4` (a child of the user's own planning session), and no user turn
  approved or revoked it. Now a folder states its own policy in `.dossier/sources.json`, which
  `engine.sources.effective_policies` merges over the shipped table. Receipts: four new tests,
  suite **149 passed**; a malformed override falls back to the defaults (a broken override can
  never open a gate); `dossier sources --root .` still returns the unchanged default
  (`prohibited: [glassdoor, linkedin]`, `manual_only: [indeed, seek, workday]`). The guard in
  `feeds.py` is now **derived from that one table** rather than restating five names — and
  writing it the lazy way silently shrank the guard to two names, which the new
  `test_the_feed_guard_and_the_policy_table_agree` caught before it shipped.
- [x] **P3** — Contrast findings resolved. `--stale` used as text was **2.78:1** in light, below
  the 4.5:1 bar; its light lightness moved `0.70 → 0.57` for **4.65:1** at the same hue and
  chroma, dark untouched at 7.49:1. Verified live in the rebuilt UI
  (`lab(49.3966% …)` in light, `lab(73.9452% …)` in dark) and inspected visually — still reads
  as amber, still legible. The `--signal` fill case is recorded in DESIGN.md as an **accepted
  trade-off**, with the numbers: white on `--signal` is 3.68:1 light / 2.49:1 dark, `--ink` is
  worse in dark (2.09:1), and a lightness that clears 4.5:1 exists only near `L=0.01` in light
  — i.e. black, which would delete the cool-blue backlight the brief is built on.
- [x] **P3** — Graph refresh after the doc edits: **both halves done.** `graphify update .`
  re-extracted the code graph without an LLM (→ 999 / 1786, dated backup written, health clean),
  and its own closing line states it covers code only — so the document half was refreshed the
  way that line prescribes, via a subagent extraction over the five changed documents. Final
  committed graph: **1032 nodes, 1821 edges, 103 communities, 0 unnamed**, with `graphify
  diagnose multigraph` reporting **0 dangling, 0 missing-endpoint, 0 collapsed, 0 duplicate**
  and only the 3 recursive self-loops. The merge's own 2 collapsed same-endpoint pairs were
  deduped rather than reported, and the stale label signature file was removed (it described
  101 communities against the current 103). Counts re-measured 2026-10-11:
  `graphify-out/graph.json` (1,093,848 B) parses to `nodes=1032 links=1821`, and
  `graphify-out/.graphify_labels.json` holds 103 keys with 0 empty values.
  **Do not cite `docs/graph.json`** — that path does not exist. The only 128,765-byte file of
  that name is the retired legacy graph at
  `docs/history/graphify-legacy-2026-09-12/graph.json`, which holds `nodes=169 links=204`.
  **Provenance limit:** `graphify-out/graph.json` records
  `built_at_commit = 722e2f0690ba83cf98a52d6bd039aa114a733f91`, while `HEAD` is
  `701c1fd1ef230b7b2f0c817e5dc600866267284a`; three later commits (`98376b5`, `3071e61`,
  `701c1fd`) edited the figures. The artifact therefore cannot be regenerated from the commit
  its own stamp names — the stamp is a vintage note, not a reproducibility guarantee.
- [x] **P3** — Gateway restart: **taken**, after a read-only sweep found **0 running cards**
  across all ten boards. Receipt: `hermes gateway restart` → "stopped (drained cleanly)",
  "started via direct spawn (PID 23156)"; board still readable afterwards.

## Closed by decision, not by code change

These are complete. They are recorded here because the decision matters, not because work
remains.

- **The gateway version warning is bookkeeping, not a live fault.** `hermes gateway status`
  still prints the mixed-`sys.modules` notice after the restart. Diagnosis: the predicate is
  `_pending_fleet_restart_needed()` (`hermes_cli/update_cmd_fleet.py`), and the newest receipt
  is from **2026-09-09** with `outcome: "refused"`, `exit_code: 2`, `fleet: []` — so it never
  reached the restart stage, and a fleet now running a *newer* commit can never be seen to
  "cover" that receipt's older runtime. The live gateway's own stamp proves the real condition
  is resolved: `gateway_state.json` records `code_sha = 2e320e6d1a81…` (version 0.21.3) and
  `git rev-parse HEAD` is **the same sha**. Only a successful `hermes update` run writes a
  fresh receipt that discharges the notice — a separate, owner-owned operation (see below).
- **Four hub-named communities left as-is.** `pathlib` (a 25-node engine cluster),
  `compilerOptions`, `dependencies` and `pytest` took a standard-library or manifest symbol as
  their hub, so the label is uninformative. `graphify` says the fix is an LLM labelling pass
  ("Run `graphify label`"); hand-patching the names would put `graph.json` out of step with
  `GRAPH_REPORT.md` for a cosmetic gain. Recorded, not buried.
- **`--signal` on the primary button** — see the contrast item above; documented in DESIGN.md
  with the computed numbers as a deliberate taste-and-identity trade-off.

## Owner-owned operations on other systems (not worklist items)

- **`hermes update`** would discharge the version notice and repair the embedded SQLite
  runtime, but on this install it is a large operation: the app is **~8.9k commits behind**
  and `codex_models.py` carries a **local patch** that a pull would need re-applied. Not run
  here — it changes the user's agent installation, not the Dossier repo.
- **New, unrelated to Dossier but surfaced by this work:** `hermes kanban` reports the host
  interpreter's **SQLite 3.50.4 is vulnerable to the WAL-reset corruption bug** affecting
  `kanban.db`. Hermes's own remedy is "upgrade to SQLite 3.51.3+ (or backports 3.50.7 /
  3.44.6); Hermes-managed installs can repair the embedded runtime with `hermes update`."
  Flagged because board integrity is at stake, not fixed because it shares the same
  owner-owned upgrade above.

## Intake 2026-11-06 — six Dossier items that were sitting in another workspace's queue

Source: `~/OneDrive/Documents/deepseek-harness/default-workspace/reelkit/DM-2026-11-05/ACTION-QUEUE.md`
(a DM backlog digest produced by a different session on 2026-11-05; `BOARD.md` lists Dossier as
"project priority 1"). Recorded here because a backlog that lives only in another workspace's
folder is a backlog this repo cannot act on. Nothing below is confirmed as wanted — three rows
contradict a declared non-goal and are recorded as such.

| id | the ask, as worded | status against this repo |
|---|---|---|
| #005 | Use a persona fine-tune as Dossier's backend to imitate the owner's writing | **conflict, not a task.** A voice model is not the product; `docs/PROJECT.md` puts judgement work behind `agent/manifest.py` so any injected model can do it. A persona backend would be a second judge with no evidence trail. Needs an owner decision, not a build. |
| #010 | Automated scraping that "survives bot defence and can sign in" | **contradicts a declared non-goal.** `docs/PROJECT.md`: "Defeating a bot check, paying for a scraper service, or reading another person's session. A challenge is detected and reported; that is the whole feature." The honest version of this ask is *more sources that do not fight back*, which `feeds.py` + recipes already cover. |
| #016 | "Work on dossier more" | standing order; this session's pass is the current discharge. |
| #129 | "Incorporate all this into the dossier repo" | **unactionable as written** — "all this" is not named. Needs the source list before it can become a row. |
| #143 | Reconsider whether Dossier becomes a plugin or its own ecosystem | **open architecture decision**, recorded here as needing an owner call: today it is a local app + CLI + injected-agent contract, and the contract is the asset (`agent/manifest.py`, 18 gates). |
| #186 | Consolidate the resume-tailoring skill, the app and the Hermes job-search sessions into one wrapper repo | **open decision**, same shape as #143. The evidence to decide it exists: 23 archived postings, 38 tracker rows, 18 gates. |
| #187 / #189 | "Jake's resume" (twice) | not about this app; no Dossier action. |

Decision needed from the owner: keep the three conflicts (#005, #010) as non-goals and close
them, or amend `docs/PROJECT.md` first. Nothing here was implemented on the assumption that the
DM list outranks the repo's own contract.
