# TRD — technical requirements

> Reel `DfDlUNVNui4` doc 1. Merged into [ARCHITECTURE.md](../ARCHITECTURE.md) on 2026-11-06;
> that file is the authority and this is the requirements list it satisfies.

## Stack

- **Python 3.13** in `.venv`; FastAPI + uvicorn for the local service; SQLite (FTS5) for the
  index; `python-docx` for templates; Word or LibreOffice for DOCX→PDF; PyMuPDF for page checks.
- **React 19 + Vite** for the UI: 12 panes, one bundle, per-pane lazy chunks, no UI framework,
  no CSS-in-JS.
- One contract file, `src/dossier/agent/manifest.py`, generates the docs, the CLI surface, the
  vendor prompt packs and the gate list.

## Hard requirements

| # | Requirement | Where it is enforced |
|---|---|---|
| 1 | Nothing leaves the machine | no outbound client except the capture the user starts; `telemetry.py` measured 0 external hosts |
| 2 | Loopback + per-run token on every route | `api/app.py` middleware; `test_every_declared_api_route_is_behind_the_token` |
| 3 | The folder is the source of truth | `safety.py` `resolve_in_root`, `PathEscape` → 400 |
| 4 | Every overwrite is recoverable | `trash_then_write` → `.dossier/trash/`, 30-day cap, `never-only-copy` gate |
| 5 | A write is never lost or torn | `atomic_write`: per-path mutex, unique temp, bounded rename retry, 1 µs mtime tolerance |
| 6 | A GET never does slow work | `/api/render` serves cache and 409s to `POST /api/render` |
| 7 | A generated document is verified, not assumed | `engine/verify.py` source-diff + text-layer + visual gates |
| 8 | No fabrication | `no-fabrication` gate + the panel's quote-verbatim invariant |

## Non-functional targets (measured 2026-11-06)

- First load **106 KiB**; Lighthouse **98–99 / 100 / 100**; FCP 1.4 s, LCP 2.1 s, CLS 0.
- Search p50 **8 ms** on 729 indexed files.
- Suite **449 tests** in ~100 s (under load, 498 s); every gate green.

## Out of scope

Desktop packaging (no `src-tauri`), GPU work, multi-user auth, mobile builds.
