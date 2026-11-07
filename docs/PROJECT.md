# dossier — project

## What it is

A local-first job-search workspace. You point it at a folder; it indexes the folder,
finds the postings, resumes and letters in it, and runs the loop a job search actually
is: capture postings → diagnose the resume → extract requirements → tailor a document
that clones your own layout → verify it → apply → track → follow up → negotiate → learn
from the outcomes.

The folder is the source of truth. `.dossier/` holds derived state and disposable
caches, and can be deleted at any time without losing a user document.

## The one idea

Mechanical work is deterministic code in `src/dossier/engine/`; judgement work is
performed by whichever model injects itself through the contract declared once in
`src/dossier/agent/manifest.py`. Docs, the CLI, the HTTP API, the vendor prompt packs
and the tests all read that manifest, so no surface can quietly disagree with another.

## Who uses it

- The owner, in a browser (the local app) or a terminal (`dossier …`).
- An agent (Pi, Codex, Claude Code, Cursor), through `dossier agent brief` → work →
  `dossier agent commit`, which rejects a handback that claims work it cannot evidence.

## Success criteria

1. A claim about a document is checkable: `dossier verify all` exits non-zero when the
   render, the text layer or the source diff disagrees.
2. A capture is honest: a blocked board, an expired session, a challenge or a limit is
   reported as `complete: false` with the reason, never counted as coverage.
3. Every overwrite is recoverable from `.dossier/trash/`.
4. Adding a board is a JSON recipe, not a code change.
5. A fresh agent session can act correctly after reading two small files
   (`STATE.md`, `HANDOFF.md`) and one command (`dossier agent next`).

## Non-goals

- Hosting anyone's data. The HTTP service binds `127.0.0.1` and requires a per-run token.
- Submitting an application. Two approval gates exist; there is no submit action.
- Defeating a bot check, paying for a scraper service, or reading another person's
  session. A challenge is detected and reported; that is the whole feature.
- Being a general document manager. It is a job-search loop with a document workspace
  attached.

## Where things live

| Need | Path |
|---|---|
| The contract (modes, gates, artifacts) | `src/dossier/agent/manifest.py` |
| Mechanical work | `src/dossier/engine/` |
| Capture (feeds, browser, recipes) | `src/dossier/feeds.py`, `src/dossier/scrape/` |
| The local service | `src/dossier/api/app.py` |
| The UI | `ui/` (React + Vite; `ui/dist` is built by `run.cmd`) |
| Tests and the command/route matrix | `tests/` |
| Durable state per workspace | `.dossier/` (git-ignored) |
| Continuity for agents | `docs/STATE.md`, `docs/HANDOFF.md` |
