# PLAN — build order

> Reel `DfDlUNVNui4` doc 5. The live checklist is [tasks/WORKLIST.md](../../tasks/WORKLIST.md);
> this is the order the work actually shipped in, and the gate that closed each phase.

| # | Phase | Deliverable | Gate that closed it |
|---|---|---|---|
| 0 | Setup | workspace resolution, config, token, loopback server | `dossier doctor` all ok; `test_the_cookie_alone_authorises_the_api` |
| 1 | Data | folder index (SQLite + FTS5), bundles by stem, trash | `fts_search` ok; 729 files indexed; `never-only-copy` |
| 2 | Diagnose | keywords, identity, fit ranking, the eval instrument | `fit-is-measured`; nDCG@10 0.9078 vs 0.8923 |
| 3 | Documents | template fill, build, verify (source diff, text layer, page) | `base-document`, `layout-clone`, `no-fabrication` |
| 4 | Interface | 12 panes, addressable routes, ⌘K, drafts, the rail | `measure.py` all zeros; `inspect.mjs` 0 findings |
| 5 | Agent contract | 27 modes, 18 gates, briefs, handback validation | `tests/test_matrix.py` (19); `dossier agent adapters --check` |
| 6 | Panel | seven reviewers quoting the line behind each objection | `test_panel.py` (7), quote-verbatim invariant |
| 7 | Polish | density, copy, a11y, performance, antislop | 449 tests; Lighthouse 98–99/100/100; `sloplint` 0 FAIL |

## Standing rule

A phase is closed by a gate, not by a checklist tick. Every row above names the command or test
that would fail if the deliverable regressed.

## Next

1. Commit in reviewed slices — 153 entries are uncommitted and the owner picks the slices.
2. Label the remaining eval rows so the ranker can be measured against something that can lose.
