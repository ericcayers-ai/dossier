# Finish log — 2026-11-16

One pass, four deliverables. Every claim below has the command that produced it. Branch `master`,
repo `C:\Users\ericc\OneDrive\Desktop\Programs\dossier`.

## 1. The eight pane labels are plain task words

- [x] **Renamed `label` only; every `id`, area and hash route is unchanged.** Commit `6361695`.

  | pane `id` | was | is | route (unchanged) |
  |---|---|---|---|
  | `capture` | Capture | **Find roles** | `#/search/capture` |
  | `jobs` | Jobs | **Saved roles** | `#/search/jobs` |
  | `identity` | Identity | **Preferences** | `#/search/identity` |
  | `build` | Build | **Write CV** | `#/papers/build` |
  | `verify` | Verify | **Check CV** | `#/papers/verify` |
  | `audit` | Audit | **Health check** | `#/housekeeping/audit` |
  | `trash` | Trash | **Deleted** | `#/housekeeping/trash` |
  | `sync` | Sync | **Handoff** | `#/housekeeping/sync` |

  The set is chosen against what each pane holds, not from the candidate list: `Saved roles` because
  the Jobs pane is "every job Dossier has saved, plus what you have applied to", not applications
  only; `Handoff` because the Sync pane's own sentence is "Hand this session to another AI in one
  paste"; `Health check` because the Audit pane's own sentence is "A health check of the folder".
  Areas (`Search`, `Papers`, `Housekeeping`) and the five unrenamed panes are untouched.

- [x] **The visible heading moves with the label**, because the pane headings already equal their tab
  labels (measured in `docs/evidence/live-walk-2026-11-05.md:29-30`). `ui/src/App.tsx:72-74` plus one
  `h1` per pane: `CapturePane.tsx:49`, `JobsPane.tsx:76`, `IdentityPane.tsx:110`, `BuildPane.tsx:77`,
  `VerifyPane.tsx:37`, `AuditPane.tsx:13,17,25`, `TrashPane.tsx:72,76,90`, `SyncPane.tsx:12,16,39`.

- [x] **The two label maps that duplicated pane names moved too**, or the rename would have split
  the vocabulary: `ui/src/panes/StartPane.tsx:25-26` (the landing page's `Open …` buttons) and
  `ui/src/panes/NextStep.tsx:49-50` (the next-unit strip's button). `JobsPane.tsx:101`'s empty state
  told the reader to use "Search / Capture"; it now says "Search / Find roles".

- [x] **The pin moved with the labels; it was not weakened.** `tests/test_e2e_ui.py` clicks and
  asserts the new names in `AREA_OF`, in the four pane walk-throughs, in the deep-link and back-button
  tests, and in `test_every_pane_keeps_its_heading_and_never_renders_blank`'s twelve-pane map. All
  eight new labels appear in that file. `.ui-ux-master/measure.py:28-33` (the 13-pane × 3-width UI
  gate) uses the same labels.

- [x] **Docs that name a pane label were updated:** `docs/design/APP-FLOW.md` (navigation map),
  `docs/ARCHITECTURE.md:105` ("the Preferences pane"), `docs/STATE.md` (the open owner decision is
  replaced by the decision made), `docs/SCOPE-LEDGER.md` (the row moves out of *deliberately not
  done*), `docs/HANDOFF.md` (next action), `docs/TEMPLATES.md` (Write CV pane, twice),
  `docs/IDENTITY.md:94` ("Preferences / Matches tab"), `docs/SOURCES.md:53-54`, and `DESIGN.md:102`
  (the layout sketch's pane row).

  Dated receipts were deliberately **not** rewritten: `docs/evidence/*`, `.ui-ux-master/audit*.md`,
  `handoff.md` and `scope.md` record what was measured on their own dates, and editing the labels
  inside them would make the receipt disagree with the build it measured. The repo already works
  this way (`tasks/WORKLIST.md:34-37`). `docs/AUDIT-2026-11-04.md` names no pane label (it says
  "8 panes"), so it needed no edit.

## 2. The six trajectory checkboxes reconcile against HEAD

- [x] **All six ticked with the commit and the command behind each.** Commit `a776d66`, in
  `tasks/WORKLIST.md` § *Trajectory work (committed at `c043aa0`)*. Feature commit `c043aa0`;
  measured against `HEAD` = `45eeaa0`.

  ```text
  $ git show HEAD:src/dossier/engine/tree.py        -> 640 lines; upsert_node, link_nodes,
      to_ascii, to_mermaid, sync, generate_next_packet, _artifact_path, _proposed_tracker_branch
  $ pytest ... -k test_tree                         -> 43 passed, 439 deselected (2.46 s)
  $ git show HEAD:src/dossier/api/app.py            -> if view == "trajectory":
  $ git show HEAD:src/dossier/cli.py                -> trajectory = add("tree", "career trajectory DAG")
  $ git show HEAD:src/dossier/agent/manifest.py     -> Stage("trajectory", ...) +
      Artifact("trajectory_tree", ".dossier/tree.json", ...)
  $ git ls-tree -r --name-only HEAD ui/src/trajectory -> TrajectoryPane.tsx, trajectory.css
  $ dossier agent adapters --check --root .         -> 8/8 true
  ```

  The end-to-end box is
  `tests/test_tree_api.py::test_api_creates_nodes_links_and_exports_an_experience_to_milestone_path`
  (six nodes, five links, the blocked → actionable transition, every label in the ASCII export,
  `mermaid.count("-->") == 5`).

- [x] **One box carries a stated caveat instead of a false tick.** "Canonical corpus integration
  confirmed in `<workspace>/.dossier/tree.json` (1,810 nodes)": the *integration* is committed and
  tested (`test_sync_imports_all_jobs_and_unique_tracker_rows_without_marking_applied`,
  `test_sync_uses_exact_tracker_artifact_names_and_leaves_sources_read_only`,
  `test_sync_builds_prospective_sequence_for_uniquely_matched_tracker_jobs_only`), but the 1,810-node
  artifact was measured in a job-search workspace outside this checkout — `dir .dossier\tree.json`
  here returns *File Not Found* — so that number is not re-derived and the box says so.

## 3. `master` pushed to `origin`

- [x] **Pushed.** Both remotes point at `https://github.com/ericcayers-ai/dossier.git`.

  ```text
  $ git push origin master
  To https://github.com/ericcayers-ai/dossier.git
     badd390..a776d66  master -> master
  ```

  `git rev-parse origin/master` → `a776d66c9f892677edec7614647f8f71d6aa7569`, which is the
  worklist commit. This log is one commit after it and is pushed on top in the same pass.
  Note: this checkout's configured upstream for `master` is the `dossier` remote (same URL), whose
  tracking ref is stale locally; the pushed remote is current.

## 4. Gates

- [x] **pytest, cold, after every code and doc edit of this pass:**

  ```text
  $ .venv\Scripts\python.exe -m pytest -o addopts="" -q -p no:cacheprovider \
      --basetemp=C:/Users/ericc/AppData/Local/Temp/dossier-gate
  482 passed, 2 warnings in 79.85s (0:01:19)
  ```

  Observed but not a failure: the Word COM thread prints `Windows fatal exception: code 0x800706be`
  while `tests/test_api.py::test_a_get_never_converts_and_the_post_owns_the_build` runs the render
  path. The test passes and the count is the full 482.

- [x] **UI build:** `cd ui && npm run build` → exit 0, 70 modules, 517 ms, per-pane chunks.

- [x] **UI measurement (13 panes × 1440/768/390, plus dark, focus and reduced motion):**

  ```text
  $ .venv\Scripts\python.exe .ui-ux-master\measure.py
  1440px: panes without exactly one h1=0, contrast fails=0, <24px targets=0, unnamed controls=0, overflowed elements=0
  768px:  panes without exactly one h1=0, contrast fails=0, <24px targets=0, unnamed controls=0, overflowed elements=0
  390px:  panes without exactly one h1=0, contrast fails=0, <24px targets=0, unnamed controls=0, overflowed elements=0
  console: 0
  dark contrast fails=0; focus stops=29, without a ring=0, off-screen=0
  reduced motion: {'skeleton_animation': '0s'}
  ```

  The script starts and stops its own uvicorn server; nothing was left running.

- [x] **Agent adapters:** `dossier agent adapters --check --root .` → 8/8 `true`.

## Not done, on purpose

- **Not committed:** the pre-existing dirty paths (`.ui-ux-master/measure.json`, the `p5` and
  `docs/evidence` screenshots, and `docs/DECISIONS.md`, which carries another pass's uncommitted
  work). The measurement and e2e runs regenerated those receipts and wrote new ones named after the
  new labels; they are left in the working tree, not folded into this pass's commits.
- **Pre-existing drift left alone:** `docs/design/APP-FLOW.md` still omits the `Start` row and still
  says "eleven flat tabs" / "twelve panes" where `App.tsx` has 6 areas and 13 panes;
  `docs/ARCHITECTURE.md:28-30` still says "five areas … eleven panes". Renaming labels did not make
  those counts more or less true, and fixing them was outside this pass.
- **A `DECISIONS.md` entry for the rename is not written here** because that file's diff belongs to
  another pass. The decision is recorded in `docs/STATE.md` § *Decided 2026-11-16* and above.
