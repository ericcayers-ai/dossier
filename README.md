# Dossier

Dossier is a local-first document workspace for a mixed folder. It keeps the file explorer, text editors, rendered documents, exports, and related work artifacts in one view.

## Launch

From this folder:

```text
run.cmd "C:\path\to\folder"
```

Or:

```text
uv run dossier --root "C:\path\to\folder" --open
```

The service binds to `127.0.0.1` only. The launcher creates a per-run token, opens the browser with a token URL, and stores a local SQLite/FTS5 cache under the selected folder's `.dossier` directory. The cache is disposable and the selected source files remain the source of truth.

## What it does

- Explorer with filename/type filtering and keyboard navigation.
- Markdown preview/editing, CodeMirror editing for JSON/Python/text, CSV preview, browser PDF viewing, image viewing, and server-rendered DOCX viewing.
- Bundle Rail grouping source, analysis, artifact, render, and proof files by configurable normalized stems.
- Full-text search backed by SQLite FTS5.
- Conditional saves: writes require the file stamp loaded by the editor; conflicts are refused instead of silently overwriting another change. Existing files are copied to `.dossier/trash/` before overwrite.
- Explicit semantic/faithful/extracted export routes. DOCX/PDF rendering uses Microsoft Word through `docx2pdf` when available, with LibreOffice as a detected fallback. PDF pages rasterize through PyMuPDF.
- Declarative, argv-only actions with no `shell=True`.
- Optional read-only job-search pane over existing job records and policy-gated public feeds.
- **Audit** view: read-only checks for index/bundle coverage, stale renders, submission approval, confirmed application dates, real event evidence, and blocked/manual/unavailable source limits.
- **Sync prompt** view: generates a copyable, source-grounded reconciliation packet for an AI session to resync records. It never includes the local bearer token and repeats the approval/date/event/manual-source safeguards.

## Fidelity boundaries

| Route | Class | Notes |
|---|---|---|
| DOCX → PDF | faithful | Microsoft Word automation where installed; layout can differ from Word if another renderer is used |
| PDF → PNG | faithful | first page rasterized with PyMuPDF |
| DOCX/PDF → Markdown/TXT | extracted/semantic | reading order and styling cannot be preserved fully |
| Markdown → DOCX | semantic | creates a simple document, not a clone of an existing layout |
| CSV ↔ JSON | semantic | structured data conversion; dialect/formatting may change |
| Bundle → ZIP | faithful | includes a manifest and source files |

Dossier does not provide in-browser DOCX editing, cloud sync, multi-user access, automatic application submission, or LinkedIn/Indeed/Glassdoor/SEEK/Workday scraping. Application statuses remain user-confirmed data.

## Development

```text
cd ui
npm install
npm run build
cd ..
py -3.13 -m pytest -q
```

The build serves `ui/dist` from FastAPI. During UI development, `npm run dev` can be used with the Vite proxy configuration; pass the backend token in the browser URL when the backend requires authentication.
