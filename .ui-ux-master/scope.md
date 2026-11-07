# Scope — every frontend surface (P0)

Measured 2026-11-04 against the built app (`ui/dist`), driven in Chromium at 1440×900,
768×900 and 390×844. The app is a **local-first workbench**: register `surface`, mode
`Operate`. Success is a person finishing a task — capture a board, build a document, track an
application — not a visitor being persuaded.

| Surface | Route | Source | Mode | Notes |
|---|---|---|---|---|
| Shell (header, areas, status bar) | `/` | `App.tsx`, `tokens.css` | Operate | two-row header, 5 areas, 11 panes |
| Folder (explorer, viewer, tabs, bundle rail) | pane `files` | `panes/Explorer.tsx`, `Viewer.tsx`, `BundleRail.tsx` | Operate + Read | the reading surface |
| Search palette | overlay | `panes/Palette.tsx` | Operate | ⌘K |
| Capture | pane `capture` | `panes/CapturePane.tsx` | Operate | one page / one recipe |
| Jobs | pane `jobs` | `panes/JobsPane.tsx` | Operate | 5 tabs: postings, pipeline, due, ranked, feeds |
| Identity | pane `identity` | `panes/IdentityPane.tsx` | Operate | questionnaire + matches |
| Build (provide a template) | pane `build` | `panes/BuildPane.tsx` | Operate | fill + verify |
| Verify | pane `verify` | `panes/VerifyPane.tsx` | Operate | 3 gates |
| Audit | pane `audit` | `panes/AuditPane.tsx` | Read | checks + source ledger |
| Trash | pane `trash` | `panes/TrashPane.tsx` | Operate | restore + prune |
| Sync | pane `sync` | `panes/SyncPane.tsx` | Read | handoff packet |
| Agent (loop) | pane `agent` | `panes/AgentPane.tsx` | Operate | contract, handback, packs |
| Opportunity tree | pane `trajectory` | `trajectory/TrajectoryPane.tsx` | Operate | DAG editor |
| Keyboard shortcuts | overlay | `App.tsx` | Read | `?` |
| Conflict / save banners | inline | `App.tsx` | Operate | alertdialog |

State inventory before the pass: 11 panes, 8 of which had a loading state, 7 an empty state,
8 an error state, and 4 dropped their `h1` while loading. Two overlays, one alertdialog, one
toast-less status line.

Current-state screenshots: `.ui-ux-master/receipts/p0/` (the browser audit captured 22,
before the pass) and `.ui-ux-master/receipts/p5/` (33 after it, 11 panes × 3 widths, plus
`dark-1440.png`).
