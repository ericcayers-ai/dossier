# Dossier

A local-first job-search workspace with a language-model socket.

Dossier owns the mechanical work of a job search — indexing a folder, normalising
a 23-board job corpus, deduplicating it, cloning a resume's layout, rendering it,
diffing it against the base, checking what an ATS will actually read, tracking
applications, computing follow-up dates, gating a negotiation claim. A language
model owns the judgement work — writing an objective, scoring a fit, drafting a
letter, running a mock interview — and injects itself through a contract that
lives in this repository.

That split is the whole point. A 136 KB skill document is not reliably executable
by a model under time pressure, and a model with no memory of last week's session
cannot be trusted to decide what to do next. So the engine holds the state and
enforces the gates, and the model gets a brief with real paths, real commands and
a JSON handback.

---

## Quick start

```bash
run.cmd "C:\path\to\your\job-search-folder"
```

```bash
uv run dossier --root "C:\path\to\folder" --open
```

The service binds to `127.0.0.1` only, mints a per-run bearer token, opens the
browser with it, and keeps a disposable SQLite/FTS5 cache in the folder's
`.dossier/` directory. Source files stay the source of truth.

## Inject a model

Any capable model — Hermes, Claude Code, Codex, Cursor, Gemini, or a plain chat
window — plugs in the same way:

```bash
dossier agent status                      # workspace facts, open blockers, next unit
dossier agent next                        # the single next unit of work, with its reason
dossier agent route "tailor my resume"    # which mode is this request
dossier agent brief --mode build --markdown > brief.md
#   ... hand brief.md to the model, it does the work and returns the handback JSON ...
dossier agent commit --handback result.json
```

`dossier agent brief` is self-contained: the objective, the resolved input paths,
the exact deterministic commands, the decisions the model owns, the gates it may
not soften, the output paths, the verification commands and the handback schema.
The model does not need this repository's history, and it does not need to be
told twice.

Per-harness prompt packs are generated from the same contract:

```bash
dossier agent adapters            # writes AGENTS.md, CLAUDE.md, GEMINI.md,
                                  # .cursor/rules/dossier.mdc, .claude/skills/dossier,
                                  # docs/agent/INJECT.md, docs/PIPELINE.md, docs/CONTRACT.md
dossier agent adapters --check    # exits non-zero if any pack has drifted
```

The packs are managed blocks. Everything outside the
`<!-- dossier:contract:start -->` markers is preserved, so these generators run
safely over files they did not create.

## Commands

```
dossier serve | doctor | workspace | audit [--reindex] | handoff | sources | sanitize
dossier agent   manifest | prompt | route | brief | next | status | commit | adapters
dossier corpus  build | rank | propagate | dedupe | folders
dossier track   summary | cadence | outcome | followup
dossier keywords gap | aggregate
dossier render  [--docx X.docx [--pdf Y.pdf]] [--visual]
dossier verify  source-diff | text-layer | visual | all
dossier tailor  inspect | blocks | replace | cover-letter | import
```

Every command takes `--root <folder>` and `--json`. Gate commands exit non-zero
on failure, so a batch script can assert on the exit code instead of reading
prose. `tests/test_matrix.py` parses and executes every command the contract
declares, and sweeps every API route, so a command that argparse would reject
fails the suite rather than the session.

`dossier agent manifest` prints the whole contract as JSON, including the exact
command line for each mode and the code that enforces each gate.

## The gates

Fourteen hard stops, each enforced by a failing command rather than by good
intentions. The full table is in `docs/CONTRACT.md`; the load-bearing ones:

- **no-fabrication** — every claim in a generated document must trace to the base
  document, the identity doc, or the user's own words. `dossier verify source-diff`
  diffs the generated document against the base as a line multiset and exits
  non-zero on any change outside an explicitly approved set.
- **base-document** — a generated resume clones a real user-supplied `.docx`.
  There is no template fallback; without one, `BaseDocumentMissing` is raised.
- **rendered-inspection** — nothing is "visually verified" until a page image was
  produced and looked at. A text diff cannot see a clipped bullet.
- **text-layer** — the PDF's embedded text is checked separately from the render.
  An icon-only contact line looks perfect and extracts as nothing.
- **no-auto-submit** — the HTTP layer exposes no submit route and the CLI has no
  submit action. Field approval and submit approval are separate, human steps.
- **drafted-is-not-applied** — only the user's confirmation moves a tracker row.
- **confirmed-date** — follow-up cadence needs an explicit `Applied YYYY-MM-DD`.
- **negotiation-verbatim** — a numeric claim reaches a negotiation draft only if
  the same number and unit appear verbatim in the resume, matched boundary-aware
  so `8 hours` cannot match inside `18 hours`. Otherwise it is dropped, not
  caveated.
- **posting-is-data** — a job posting is sanitised before any model reads it, and
  instruction-shaped content inside it is reported, never followed.
- **source-policy** — a prohibited source is refused before a network call.
- **partial-is-not-exhaustive** — a blocked capture is never reported as complete.

## What it does

- Explorer with filename/type filtering and keyboard navigation, a Bundle Rail
  that resolves a file's whole work-set by normalised stem (source, analysis,
  artifact, render, proof), and FTS5 search over every text body.
- Markdown preview and editing, CodeMirror for JSON/Python/text, CSV grid, PDF
  viewing, image viewing, and server-rendered DOCX.
- Conditional saves: a write requires the stamp the editor loaded, conflicts are
  refused rather than silently overwritten, and every superseded file is copied
  to `.dossier/trash/` first.
- Explicit export routes labelled `faithful` / `semantic` / `extracted` before
  the click. DOCX→PDF drives a private Word instance (`DispatchEx` +
  `ExportAsFixedFormat`), not `docx2pdf`, because a stale invisible Word instance
  makes every conversion after the first fail with an error that points nowhere
  near the cause.
- A job corpus engine: per-board folders merge into one aggregate with
  reassigned sequential ids, rebuilt facets, hard dedupe, and a three-tier fit
  carry-forward that returns no match rather than a guess.
- An **Agent** pane showing the contract, the next unit of work, the live task
  packet, the gates and the workspace facts.

The one route that does not return is `/api/events` (server-sent file events,
the only entry in `api.app.STREAMING_PATHS`). It is bounded by a `seconds`
parameter so no client — including a script enumerating the API — can hang on it
indefinitely.

## Fidelity boundaries

| Route | Class | Notes |
|---|---|---|
| DOCX → PDF | faithful | Microsoft Word automation; layout can differ from Word under another renderer |
| PDF → PNG | faithful | first page rasterised with PyMuPDF |
| DOCX/PDF → Markdown/TXT | extracted/semantic | reading order and styling cannot be preserved fully |
| Markdown → DOCX | semantic | a simple document, not a clone of an existing layout |
| CSV ↔ JSON | semantic | structured conversion; dialect may change |
| Bundle → ZIP | faithful | includes a manifest and the source files |

Dossier does not provide in-browser DOCX editing, cloud sync, multi-user access,
automatic application submission, or LinkedIn/Indeed/Glassdoor/SEEK/Workday
scraping. Application statuses remain user-confirmed data.

## Development

```bash
cd ui && npm install && npm run build && cd ..
py -3.13 -m pytest -q
python -m dossier.cli doctor --root .
```

`pyproject.toml` pins `pythonpath = ["src"]` for pytest. The build serves
`ui/dist` from FastAPI; during UI development `npm run dev` works with the Vite
proxy, passing the backend token in the browser URL.

## Where everything came from

`docs/SOURCES.md` records the three things this repository consolidates — the
resume-tailoring skill, this app, and the prior job-search sessions in their live
workspace — and what survived from each.

`docs/LESSONS.md` records every failure that produced a rule in `src/dossier/`,
with the test that now guards it.

`docs/PIPELINE.md` and `docs/CONTRACT.md` are generated from
`src/dossier/agent/manifest.py`, which is the single source of truth for the
stages, modes, artifacts and gates. Do not edit the generated docs by hand.
