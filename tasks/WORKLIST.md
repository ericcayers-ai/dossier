# Dossier worklist

The only live repository checklist. The original app plan is historical at
[docs/history/PLAN-2026-09-15.md](../docs/history/PLAN-2026-09-15.md); a stub remains at
the old path. Full receipts: [job-search reconciliation, 2026-09-27](../docs/evidence/job-search-reconciliation-2026-09-27.md).

Checkbox rule: an item is ticked only with a quoted tool receipt behind it. Where a
result is machine-verified but not owner-confirmed, the item says so.

## Done

- [x] **P1** — Contract drift: five `ARTIFACTS` producers named code that does not exist,
  and `apply` wrote a phantom `application-tracker.md`. Receipt: `py -3.13 -m pytest -q
  --junitxml=…` → `tests= 145 failures= 0 errors= 0 skipped= 0`; `agent manifest --json`
  now resolves every producer to a real mode or engine entry point.
- [x] **P1** — Two regression tests added so the class cannot return
  (`test_every_artifact_names_a_real_producer`, `test_apply_writes_the_canonical_tracker`);
  both fail against the pre-fix manifest. Suite went 143 → 145.
- [x] **P1** — Generated packs regenerated from source; duplicated H1 in
  `docs/agent/INJECT.md` removed. Receipt: `agent adapters --check --root .` → all 8 packs
  `true`; on an empty root all 8 `false`, exit 1.
- [x] **P1** — Shared skill stripped of user-specific values (`Century Gothic`, `043D68`,
  `Why Northbridge?`, `KiwiSaver`, `exchange-helper`) and the 33-of-34 pattern count fixed.
  Verified genuinely user-specific against the real base: `tailor inspect` reports
  `"primary_font": "Century Gothic"`, `"primary_accent": "043D68"`.
- [x] **P1** — `PLAN.md` superseded (0 of 76 boxes checked, described deleted modules);
  moved to `docs/history/PLAN-2026-09-15.md`.
- [x] **P1** — Code-context graph rebuilt as `graphify-out/`. Receipt: 987 nodes, 1773
  edges, 96 communities, 0 unnamed; `engine` 195 + `agent` 94 + `api` 45 nodes;
  `graphify query "where is the drafted-is-not-applied gate enforced"` returns
  `manifest.py L57` and `engine/tracker.py` with line numbers. Graph health warning (147
  dangling-endpoint edges) is recorded, not hidden.
- [x] **P2** — Real document cycle verified end to end on a scratch copy of a real base:
  `tailor replace` (1 applied, 0 missed) → `render` (`word-private-com`, 2 pages) →
  `verify all` exit 0 (`0 unexpected`, `"passed": true`), and exit 1 against an empty
  approved map. Pages inspected visually.
- [x] **P2** — Explorer keyboard nav and a11y verified live with real key events:
  14 Tabs to reach the tree, ArrowDown/Up move selection, exactly one `aria-selected`
  row, 2px solid `--signal` focus ring, no overflow at 1280/1920, body-text contrast
  16.45:1 light / 13.03:1 dark against DESIGN.md's 4.5:1 bar.
- [x] **P2** — Both blocked Dossier kanban cards reconciled and closed; both had crashed
  twice with `pid … not alive`. Board now `4 done, 0 blocked, 0 open`, with evidence
  comments on each card.
- [x] **P2** — Doc audit: 60 markdown files, 5 relative links, 2 broken (both here) —
  repaired; re-run reports 0 broken.
- [x] **P1** — Session acceptance register completed and preserved at
  [docs/evidence/acceptance-criteria-register-2026-09-27.md](../docs/evidence/acceptance-criteria-register-2026-09-27.md).
  Receipt: 30 in-scope sessions, 66 user-stated criteria, 9 contradictions, plus the
  agent-authored constraints held separately; independently verified — all 30 session ids
  exist in `default/state.db` (0 missing), store = 1,239 sessions / 211,466 messages, and
  every sampled quote resolves to a real `role='user'` row. Per-profile scope: default 30,
  coder 0, designer 0, orchestrator 0. Four personal specifics redacted before it entered
  the repo, listed in that file's own note.

## Open

- [ ] **P2** — Authorise (or decline) syncing the three other-profile copies. `coder`,
  `designer` and `orchestrator` each hold a real 88,579 B
  `skills/office-productivity/references/resume-tailoring/SKILL.md`, and none carries
  `productivity/dossier-workspace`. Receipt: byte counts from live `find`; the 30-line
  alias files beside them are correct pointers, not stale. The register lowers the stakes:
  those three profiles hold **zero** job-search sessions. Remaining: an explicit decision,
  because another profile's skill tree was outside this session's authority — and with no
  job work there, declining is a reasonable answer.
- [ ] **P2** — Retire the legacy `.graphify/` directory (5 tracked files, Sep 12) now that
  `graphify-out/` is canonical. Receipt: `.graphify/graph.json` still lists deleted
  `api_*.py` stubs and has no `engine/` or `agent/` nodes. Remaining: deletion is
  destructive to pre-existing tracked content, so it waits on the owner — `git rm -r
  .graphify` is the whole job.
- [x] **P2** — Graph integrity: **no repair was needed.** Receipt:
  `graphify diagnose multigraph --graph graphify-out/graph.json` → 987 nodes, 1773 links,
  `dangling_endpoint_edges: 0`, `missing_endpoint_edges: 0`, `collapsed …: 0`,
  `exact_duplicate_edges: 0`. The 147 dangling / 4 self-loop / 66 collapsed figures printed
  during the build were measured on the **raw extraction** — the same output says so
  ("normal graph.json is post-build; raw producer loss must be measured earlier") — and the
  build resolves them. An earlier version of this list called that an unrepaired defect in
  the delivered graph; that was wrong. The 3 residual self-loops are `calls` edges at
  confidence 1.0 on genuinely recursive functions (`tree_node()` `api/app.py:85`,
  `walk()` `extract.py:13`, `flatten()` `ui/src/App.tsx:16`), each confirmed against source.
- [x] **P3** — Re-derive the historical resync sub-counts. Receipt: **five of six recomputed
  exactly** from the artifacts — 1,789 aggregate rows (`all_jobs.json` = 1,789 rows and
  1,382 + 407 = 1,789), 1,665 ranking rows and 407 new records (named fields in
  `nz-job-search-coverage-2026-09-14.json`), 30 detail checks
  (`resync-20260914/detail-evidence` = 30 files), 29 skill-gap reports
  (`resync-20260914/skill-gaps` = 29 files), 131 captures
  (`resync-20260914/captures` = 131 files). Also recounted: `NZ-JobSearch-Resync-2026-09-14.zip`
  = **724 members, 0 directory entries** — exact.
- [ ] **P3** — One resync figure stays unverified: **831** "prior rows not re-seen in current
  readable indexes". Receipt: defined in the resync summary of `20260911_203039_6edc17`,
  but the ledger's arithmetic gives 1,382 − 738 = 644, so 831 counts against readable
  indexes specifically. Remaining: reproduce that narrower count, or leave it labelled.
- [ ] **P1** — Board policy the user never approved. The user asked verbatim for "seek nz,
  indeed, trademe jobs, literally all available main job searches"; the engine instead
  hard-blocks exactly those (`dossier sources` → `glassdoor` `prohibited`, SEEK/Indeed
  manual-only). Receipt: the block is mandated in the *agent-authored* build brief
  `20260912_035239_4c86f4`, a child session of the user's own planning session
  (`parent=20260912_025629_1cd811`), and no user turn approved or revoked it. Remaining: an
  owner decision — this is product behaviour, not an audit fix.
- [ ] **P3** — Decide on the two new contrast findings from §5 of the evidence file
  (white on `--signal` 3.68:1 light / 2.49:1 dark; `--stale` as text 2.78:1 in light).
  Receipt: computed from the declared OKLCH tokens in `ui/src/tokens.css`. Remaining:
  these are outside DESIGN.md's stated bar, so they are a design decision, not a defect
  to silently fix.
- [ ] **P3** — Refresh the graph's evidence-document nodes on the next `graphify update`.
  Receipt: the semantic pass read that file before its final revision, so those nodes
  describe earlier content; their `source_file` paths are correct and every other
  `source_file` in the graph resolves (2,684 checked, 0 unresolvable). Remaining: run
  `graphify update <path>` after doc edits land.
- [ ] **P3** — Gateway restart is now **safe but not taken**. Receipt: a read-only sweep of
  all ten boards finds **0 running cards** (no `running` status anywhere), and the gateway
  process is alive (PID 47568, `orchestrator` PID 7680). Remaining: an owner call, because
  the restart also bounces the messaging and cron side of the gateway — the in-flight-worker
  reason to defer it no longer applies.
