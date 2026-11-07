# dossier — architecture

Measured 2026-11-04. Branch `master`.

## Layers

```
CLI (cli.py)          HTTP API (api/app.py)          Agent packs (agent/adapters.py)
        \                    |                          /
         \                   |                         /
          ----  agent/manifest.py  (the contract)  ----
                        |
      +-----------------+------------------+
      |                 |                  |
  engine/*          scrape/*            model.py
  (mechanical)      (capture)           (outbound model, opt-in)
      |                 |                  |
      +--------+--------+------------------+
               |
        safety.py (trash/atomic)   config.py   db.py (SQLite + FTS5)
```

`api/app.py` and `cli.py` import the engine, never the reverse. `manifest.py` imports
nothing from the package, so the contract can be rendered without a workspace.

## The interface

React 19 + Vite, no component library. Five areas (Files, Search, Papers, Housekeeping, Agent)
mount eleven panes; each area renders only its own panes, and the two side panels become
`inert` slide-overs below 1000/700 px. `tokens.css` is the whole vocabulary: OKLCH colour with
two chromatic tokens, six type sizes, a 4 px spacing scale, named chrome heights, two durations
and one easing. Panes share `Pane`-level primitives from `panes/StateViews.tsx` (`Loading`
skeleton, `ErrorState`, `EmptyState`). The theme attribute lives on `<html>` so inherited tokens
resolve in dark. `.ui-ux-master/measure.py` is the mechanical gate over the built app.

## Identity and relevance

`engine/identity.py` builds the target everything else is aimed at: a 15-question
questionnaire stored in `.dossier/identity/answers.json`, merged answer-first over values
mined from the workspace's own documents (each with a file and line), written into the
identity doc's managed block. `score_job` is deterministic arithmetic over that profile
(title family, skills, location/remote, employment, seniority, pay floor, recency) with
one inherited rule: a disqualifier caps the band and is named. Capture filters on the same
number (`--min-match`), and the posting keeps `match: <band> <score>` in its frontmatter.

## Capture path

Three layers, cheapest first, each recording what it did:

1. `feeds.py` — six documented public JSON endpoints (`greenhouse`, `lever`, `ashby`,
   `himalayas`, `remotive`, `arbeitnow`). No browser, no session. Reachable from
   `dossier feeds fetch`; the rows land in `<source>_data/all_jobs.json`, which is the
   shape `engine/corpus.py` already reads.
2. `scrape/browser.py:ObscuraDriver` — the `obscura` binary (Rust/V8) as a subprocess.
   Public pages, JavaScript, robots obeyed by default.
3. `scrape/browser.py:PlaywrightDriver` — Chromium through Playwright. The only layer
   that can hold a session: the user signs in a visible window, `scrape/session.py`
   stores the resulting cookies + localStorage (`0600`, `.dossier/`, never in a handoff).

`scrape/runner.py` sequences them: policy → robots → pace → engine → extract → sanitise
→ write posting + provenance. `scrape/guard.py` resolves the board from the URL host
(not the recipe), asks the one policy predicate, and paces per host.

## Storage

| Store | What | Canonical? |
|---|---|---|
| The folder | Documents, postings, `job-history.md`, corpus JSON | yes |
| `.dossier/index.sqlite3` | FTS5 index of the folder (derived) | no |
| `.dossier/trash/<stamp>/` | Every overwritten file, 30-day default | recovery only |
| `.dossier/scrape/sessions/*.json` | Cookies + localStorage per board | credential-adjacent; local only |
| `.dossier/scrape/runs.jsonl` | Append-only capture log | evidence |
| `.dossier/tree.json` | The user's career DAG | **user-authored, git-ignored** |
| `.dossier/scrape/feeds/*` | Feed capture provenance | evidence |
| `templates/scrapes/*.json` | Shipped capture recipes | templates |

One connection (`db.py:open_db`) is shared by the watch task and every request, WAL with
`busy_timeout=5000`. `files` + `files_fts` are rebuilt by `indexer.crawl`; the mtime+size
check runs before the hash so an unchanged file is not re-read.

## The HTTP surface

39 `/api/*` routes, loopback-bound, authorised by a per-run bearer token delivered as an
`httponly` cookie by `GET /` (the console URL no longer carries it). Mutating routes:
`PUT /api/file`, the tree writes, trash prune/restore, `POST /api/actions` (argv-only,
`shell=False`, cwd pinned inside the root), export, agent commit/ask, and
`POST /api/scrape/capture` (one page per request). `/api/events` is the only streaming
route and is bounded by `?seconds=` (default 300).

## Tests

`tests/test_matrix.py` is the gap net: it parses every declared command, runs every
self-contained one, resolves every engine and gate symbol, and sweeps every GET route.
Adding a mode, a command or a route extends it with no edit. `tests/test_scrape.py` adds
a local fixture site (`tests/fixtures/scrape_site.py`) for the real engines.

## Where a change belongs

- A new deterministic operation → `engine/<area>.py`, a CLI subcommand, a route, a mode.
- A new board → `.dossier/scrapes/<id>.json` (see `docs/SCRAPING.md`); code only if the
  shape is new.
- A new pane → add it to `AREAS` in `ui/src/App.tsx` (an area holds at most three) and give it
  one `h1`, a loading skeleton, an empty state and an error state.
- A new identity question → `engine/identity.QUESTIONS` (id, kind, choices, required); the
  profile, the CLI, the API and the Identity pane all read that one tuple.
- A new rule that must not be softened → a `Gate` in `manifest.py` **and** its enforcer.
- A new derived fact → the engine that owns the source; never a second parser.
