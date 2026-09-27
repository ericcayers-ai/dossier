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

## Open

- [ ] **P2** — Authorise (or decline) syncing the three other-profile copies. `coder`,
  `designer` and `orchestrator` each hold a real 88,579 B
  `skills/office-productivity/references/resume-tailoring/SKILL.md`, and none carries
  `productivity/dossier-workspace`. Receipt: byte counts from live `find`; the 30-line
  alias files beside them are correct pointers, not stale. Remaining: an explicit
  decision, because another profile's skill tree was outside this session's authority.
- [ ] **P2** — Retire the legacy `.graphify/` directory (5 tracked files, Sep 12) now that
  `graphify-out/` is canonical. Receipt: `.graphify/graph.json` still lists deleted
  `api_*.py` stubs and has no `engine/` or `agent/` nodes. Remaining: deletion is
  destructive to pre-existing tracked content, so it waits on the owner — `git rm -r
  .graphify` is the whole job.
- [ ] **P2** — Repair the 147 dangling-endpoint edges in the new graph (doc-derived edges
  whose targets do not match AST ids). Receipt: `graphify diagnose` health warning from
  the build. Remaining: an id-reconciliation pass; the graph is usable meanwhile.
- [ ] **P3** — Re-derive the historical resync sub-counts (1,665 / 407 / 831 / 30 / 29 /
  131) against the 1,789-row `all_boards_data/all_jobs.json` and the 724-member zip.
  Receipt: only the 1,789 and 724 totals were confirmed. Remaining: a full pass; they are
  currently labelled historical, not verified.
- [ ] **P3** — Read the session acceptance register's coverage limits before any claim of
  exhaustive session provenance. Receipt: the register is being produced separately;
  title-less subagent sessions and non-default profiles were the known blind spots.
  Remaining: adjudicate its coverage section against this worklist.
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
- [ ] **P3** — Confirm the gateway notice `hermes kanban` prints ("a previous
  `hermes update` pulled new code but did not restart running gateways"). Receipt: the
  warning appears on every kanban invocation. Remaining: owner-scheduled, since a restart
  would kill in-flight workers on other boards.
