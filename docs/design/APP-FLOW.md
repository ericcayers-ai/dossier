# APP-FLOW

> Reel `DfDlUNVNui4` doc 2. Merged into [ARCHITECTURE.md](../ARCHITECTURE.md) § The interface on
> 2026-11-06; the pane list is generated from `ui/src/App.tsx` and must match it.

## Phases

1. **Entry** — cold load lands on one screen that says what to do next: the engine's next unit,
   its reason, its blockers, and one button that goes there (`NextStep`).
2. **Core loop** — capture a posting → diagnose the resume → extract requirements → tailor a
   document → verify it → apply → track → follow up.
3. **Return** — a reload restores the pane and the open document (`#/<area>/<pane>`), unsaved
   edits survive as drafts behind an explicit prompt, and search (`⌘K`) finds either a file or a
   place.

## Navigation map

```
Files        └ Folder
Search       ├ Capture · Jobs · Identity
Papers       ├ Build · Verify
Housekeeping ├ Audit · Trash · Sync
Agent        ├ Loop · Opportunity · Panel
```

Two levels, because eleven flat tabs clipped at 1100 px. `⌘K` lists all twelve panes with no
query and ranks places above files, so any screen is one keystroke and one Enter away.

## Every pane carries the same four states

Loading (a skeleton, never a spinner), ready, empty (what this place is, one next action) and
failed (a sentence and a retry). `test_every_pane_keeps_its_heading_and_never_renders_blank`
walks all twelve and fails if a pane loses its `h1`.

## Trust boundaries the flow must not cross

- Nothing is written without a keystroke; no autosave over the source.
- Every overwrite lands in `.dossier/trash/` first.
- No submit, send or publish action exists anywhere in the flow.
