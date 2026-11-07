# Trajectory Tree Implementation Plan

## Goal
Add a local-first, full-stack career trajectory DAG to Dossier, with validated sequential links, read-only synchronization from the workspace's job tracker/corpus/artifacts, CLI/API access, an interactive React pane, and a trajectory agent contract.

## Architecture
`.dossier/tree.json` is the canonical per-workspace graph. `engine.tree` validates node/link invariants and writes through Dossier's atomic-write plus trash-backup safety helpers. Sync is an explicit, repeatable user action: it reads `job-history.md`, `all_boards_data/all_jobs.json`, and exact-name artifact siblings, never edits the resume corpus, and never infers an `applied` state from generated files. The API and CLI delegate to the same engine. The React pane consumes the API, groups nodes by type, permits explicit node/link writes, and copies a structured next-branch packet without applying it.

## Constraints
- Preserve all existing 14 manifest safety gates unchanged.
- Every linked parent must be `complete` before its child can be `active` or `complete`; all parents are required.
- Reject cycles, missing endpoints, duplicate links, invalid dates, and parent dates later than child dates.
- Keep source corpus, `job-history.md`, DOCX, and PDF artifacts read-only; only write Dossier's `.dossier/tree.json` with a prior trash backup.
- No MCP, external login, application submission, new dependency, fabricated evidence, or synthetic resume template.
- Canonical corpus is `all_boards_data/all_jobs.json` (measured at 1,789 rows); no top-level `all_jobs.json` exists.
- Use unique exact normalized tracker-to-corpus matches; leave non-matches as separate history opportunities. Attach only real files referenced by tracker rows or exact sibling names.

## Ordered tasks
1. **Tree engine + tests:** define node/state/link schema, atomic persistence, validation, DAG traversal, ASCII/Mermaid export, status, and idempotent source sync. Add focused tests first and keep every write in a temporary test workspace.
2. **API + CLI:** add authenticated GET graph/export and POST node/link/sync endpoints; add `tree status|add|link|view|sync` CLI actions. Extend API/CLI contract tests and preserve bounded-stream behavior.
3. **Agent contract:** register the `trajectory` stage/mode and `.dossier/tree.json` artifact; regenerate all eight managed prompt packs from the manifest and verify zero drift.
4. **Corpus/artifact integration:** test counts, stable IDs, exact artifact paths, ambiguous/no-match handling, and repeat-sync preservation of manual nodes. Run once against a temporary copy/fixture; do not write to the canonical resume folder.
5. **React pane:** add topbar navigation, grouped branching display, type/state/date-aware node form, link form with prerequisite feedback, ASCII/Mermaid export, source sync, and Generate Next Branch clipboard action. Use existing theme tokens and add narrow-viewport overflow handling.
6. **End-to-end + audit:** exercise experience → touchpoint → meeting → opportunity → milestone via API/CLI; assert both exports; run backend suite (at least 160 passing), UI `npm run build`, adapter check (8/8 true), full CLI/API matrix, and static gap sweep. Verify light/dark rendering and horizontal overflow in a real browser. Update `tasks/WORKLIST.md`, `docs/LESSONS.md`, and task-local state with receipts and any explicit blockers.

## Current evidence
- Baseline backend suite: passed; 149 collected tests (no failures).
- Baseline adapters: all 8 current packs `true`.
- `dossier doctor --root .`: `ready`.
- Corpus: 1,789 rows in `<workspace>/all_boards_data/all_jobs.json`.
- Tracker: 38 parsed rows; exact normalized title/employer matching links 17 uniquely to corpus rows, leaving 21 separate tracker opportunities.
- `_preview/`: 20 cover-letter PDFs and no resume PDFs; tracker-named resume/cover-letter DOCX files exist elsewhere in the canonical root. All sources remain read-only.
- Existing untracked `.mcp.json` is user-owned and will not be touched.
