# Backend schema

> Reel `DfDlUNVNui4` doc 4. Merged into [ARCHITECTURE.md](../ARCHITECTURE.md) § Storage on
> 2026-11-06; this file is the table list as the code actually declares it.

## On disk

```
<root>/                      the user's folder — the source of truth
  .dossier/                  derived, disposable
    index.sqlite3            files + FTS index (WAL)
    trash/                   every overwritten file, timestamped (30-day cap)
    cache/render/            DOCX→PDF renders, keyed by the source's sha256
    identity/                parsed identity state
    tree.json                the user's career DAG
    actions.json feeds.json  user configuration
```

`AppConfig.create(root)` fixes these paths and the per-run token
(`src/dossier/config.py`); deleting `.dossier/` loses no user document.

## Tables (`src/dossier/db.py`)

| table | columns | notes |
|---|---|---|
| `files` | `rel` PK, `ext`, `size`, `mtime_ns`, `sha256`, `kind`, `stem_key`, `role`, `meta_json`, `indexed_at`, `extract_error` | one row per indexed file; `rel` is the path relative to the root, which is why `resolve_in_root` guards every read and write |
| `files_fts` | virtual FTS5 over (`rel` UNINDEXED, `body`) | `unicode61` tokenizer; `search()` quotes each token as a phrase so a typed `"` or `OR` cannot error |

Two indexes: `files_stem` on `stem_key` (bundle grouping) and the FTS table. Search answers a
**path** match first (wildcards escaped through `ESCAPE '\'`) and body matches after it.

## Invariants

- `sha256` + `size` decide a write precondition; `mtime_ns` is a hint within 1 µs, because a
  nanosecond timestamp cannot survive JSON (it is past `2**53`).
- `extract_error` is reported, never swallowed: a file the extractor cannot read is a named row,
  not a silent absence.
- No table stores document content the user did not put in the folder; `body` is extracted text
  of a file that already exists on disk.
