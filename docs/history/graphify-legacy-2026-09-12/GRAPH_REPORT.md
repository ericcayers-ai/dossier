# Graph Report - .  (2026-09-11)

## Corpus Check
- Corpus is ~11,343 words - fits in a single context window. You may not need a graph.

## Summary
- 169 nodes · 204 edges · 15 communities detected
- Extraction: 100% EXTRACTED · 0% INFERRED · 0% AMBIGUOUS
- Token cost: 0 input · 0 output
- Edge kinds: contains: 111 · calls: 45 · imports_from: 20 · method: 12 · inherits: 10 · imports: 6


## Input Scope
- Requested: auto
- Resolved: all (source: default-auto)
- Included files: 47 · Candidates: recursive
- Excluded: 0 untracked · 0 ignored · 1 sensitive · 0 missing committed
## God Nodes (most connected - your core abstractions)
1. `FeedAdapter` - 11 edges
2. `_jobs()` - 8 edges
3. `convert()` - 6 edges
4. `audit_workspace()` - 4 edges
5. `Prohibited` - 4 edges
6. `stamp()` - 4 edges
7. `atomic_write()` - 4 edges
8. `extOf()` - 4 edges
9. `load_actions()` - 3 edges
10. `run_action()` - 3 edges

## Surprising Connections (you probably didn't know these)
- None detected - all connections are within the same source files.

## Communities

### Community 6 - "Community 6"
Cohesion: 0.43
Nodes (4): Action, ActionRun, load_actions(), run_action()

### Community 7 - "Community 7"
Cohesion: 0.40
Nodes (2): _free_port(), main()

### Community 11 - "Community 11"
Cohesion: 0.70
Nodes (4): _confirmed_application_dates(), _coverage_sources(), audit_workspace(), build_handoff()

### Community 5 - "Community 5"
Cohesion: 0.24
Nodes (5): Rules, load_rules(), Member, Bundle, resolve_bundle()

### Community 8 - "Community 8"
Cohesion: 0.33
Nodes (1): AppConfig

### Community 3 - "Community 3"
Cohesion: 0.22
Nodes (9): RendererInfo, Route, available_renderers(), routes(), _write_docx_from_markdown(), _text_from(), _csv_to_json(), _json_to_csv() (+1 more)

### Community 9 - "Community 9"
Cohesion: 0.47
Nodes (3): FileRecord, upsert_file(), index_path()

### Community 10 - "Community 10"
Cohesion: 0.47
Nodes (3): canonical_status(), parse_history(), due_items()

### Community 0 - "Community 0"
Cohesion: 0.12
Nodes (13): Job, FeedPolicyError, PermissionError, FeedAdapter, _jobs(), Greenhouse, Lever, Ashby (+5 more)

### Community 13 - "Community 13"
Cohesion: 0.67
Nodes (2): CrawlStats, crawl()

### Community 2 - "Community 2"
Cohesion: 0.20
Nodes (10): PathEscape, ValueError, Conflict, RuntimeError, FileStamp, stamp(), resolve_in_root(), _matches() (+2 more)

### Community 1 - "Community 1"
Cohesion: 0.08
Nodes (2): Tab, Action

### Community 14 - "Community 14"
Cohesion: 0.50
Nodes (4): extOf(), isBinary(), icon(), Viewer()

### Community 16 - "Community 16"
Cohesion: 1.00
Nodes (2): nameOf(), App()

### Community 4 - "Community 4"
Cohesion: 0.21
Nodes (11): FileNode, FileStamp, Member, Bundle, Audit, queryToken, token(), authHeaders() (+3 more)

## Knowledge Gaps
- **3 isolated node(s):** `Tab`, `Action`, `queryToken`
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Community 7`** (2 nodes): `_free_port()`, `main()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 8`** (1 nodes): `AppConfig`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 13`** (2 nodes): `CrawlStats`, `crawl()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 1`** (2 nodes): `Tab`, `Action`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 16`** (2 nodes): `nameOf()`, `App()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **What connects `Tab`, `Action`, `queryToken` to the rest of the system?**
  _3 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Community 0` be split into smaller, more focused modules?**
  _Cohesion score 0.11965811965811966 - nodes in this community are weakly interconnected._
- **Should `Community 1` be split into smaller, more focused modules?**
  _Cohesion score 0.08 - nodes in this community are weakly interconnected._