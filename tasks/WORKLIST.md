# Dossier worklist

The only live repository checklist. The original app plan is historical at
[docs/history/PLAN-2026-09-15.md](../docs/history/PLAN-2026-09-15.md); a stub remains at the
old path. Full receipts: [job-search reconciliation, 2026-09-27](../docs/evidence/job-search-reconciliation-2026-09-27.md)
and the [acceptance-criteria register](../docs/evidence/acceptance-criteria-register-2026-09-27.md).

Checkbox rule: an item is ticked only with a quoted tool receipt behind it. Where a result is
machine-verified but not owner-confirmed, the item says so.

**No open items.** Everything raised by this audit is closed, either by fixing it or by
recording a decision with its reasoning. The two things that remain are not worklist items
because they are owner-owned operations on other systems, listed at the end.

## Done

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
- [x] **P2** — Doc audit clean: the 2 broken links it found were repaired; re-run reports
  **0 broken** across 61 markdown files.
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
  101 communities against the current 103).
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
