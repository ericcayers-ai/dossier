# dossier — decisions

Append-only. One entry per decision that constrains later work; each states what it cost.

2026-10-11 — the manifest is the single source

`agent/manifest.py` owns modes, gates, artifacts and the pipeline; docs, CLI help, API
payloads and vendor packs are generated from it. Cost: a contract change requires
`dossier agent adapters` plus a regenerated diff, and a hand edit to a managed block fails
`--check`.

2026-10-11 — gates are code, not prose

Every gate names the symbol that enforces it, and `tests/test_matrix.py` resolves that
symbol. Cost: a new gate needs a real enforcer, so "we should be careful" cannot become a
gate.

2026-10-12 — the board policy table is conservative by default

`engine/sources.POLICIES` refuses LinkedIn and Glassdoor outright and treats Indeed, Seek
and Workday as manual-only. A workspace can amend one row in `.dossier/sources.json`
without editing code. Cost: the default path cannot fetch several boards the owner may be
entitled to; opening one is a deliberate, recorded act.

## 2026-11-04 — `user_supplied` is a policy, not an exemption

A URL the user names is fetchable, because naming a page is the instruction. The host is
resolved first (`scrape/guard.HOST_SOURCES`), so a LinkedIn URL still meets the prohibited
row. Cost: a new board needs a host-map row or an entry in `sources.json`.

## 2026-11-04 — three capture layers, cheapest first

Feeds → obscura → Playwright+Chromium. obscura is the default because it is installed,
fast and robots-aware; Playwright is the only engine that can hold a session. Cost: two
engines to keep working, and `uv sync --extra browser` on a new machine for the
authenticated path.

## 2026-11-04 — a session is the user's, structurally

`SessionStore.save` rebuilds the record from `cookies` and `origins` only, refuses any
method that is not a user sign-in or a user cookie export, refuses an empty jar, and
refuses to attach a jar to a host its cookies do not cover. Cost: an automated login is
impossible by design, so a board that demands a bot check cannot be captured at all.

## 2026-11-04 — a challenge is a blocker (SUPERSEDED the same day by `challenge-is-explicit`)

The first pass refused to answer an interstitial at all. Kept as a record of the
default that was replaced, and of why: a person sitting in front of the machine
asked for the page.

## 2026-11-04 — `complete` is a computation, not an exit code

A run is complete only when every listing page and every item arrived and nothing was
truncated by `--limit` or `--pages`; otherwise `complete: false` with the reason and the
failed URLs. Cost: a `--limit` run is always "partial", even when the user wanted one item.

## 2026-11-04 — recipes are JSON, validated strictly

Unknown top-level keys are errors, selectors are parsed with the real CSS parser, and a
broken workspace recipe is reported instead of being replaced by the shipped one with the
same id. Cost: a recipe written against an older schema fails loudly instead of running.

## 2026-11-04 — capture state lives under `.dossier/`

Sessions, the run log, screenshots and feed provenance are in `.dossier/scrape/`, which is
git-ignored and disposable. Cost: the run log is local evidence, not a shared record; a
second machine starts with no history.

## 2026-11-04 — the console URL carries no token

`GET /` sets the `httponly` cookie the API accepts, so `_serve` prints a bare URL. Cost:
`--open` relies on the cookie path, verified by `tests/test_api.py`.

## 2026-11-04 — a challenge is answered by policy, and it is recorded

Supersedes `challenge-is-a-blocker`. `challenge-is-explicit` requires every run to record the
detection, the policy applied and whether it cleared; `block` is now one selectable policy.
`auto` escalates plain → stealth+wait → a visible window (opt-in via `"visible": true` or
`--headed`) → a solver, which is used only with `DOSSIER_SOLVER_KEY` in the environment —
never from a workspace file, so a solver account cannot be copied with a repo. obscura also
taught us that `--screenshot` suppresses `--dump`: the driver writes the dump with `-o` and
leaves images to Playwright. Cost: the tool can now be pointed at a hostile page; the
mitigations are that the key and the window are explicit, and the receipt names what ran.

## 2026-11-04 — a user template is a first-class build input

`dossier tailor template` fills the user's own `.docx` and never rebuilds it. Cost: there
are now two build paths (base clone, template fill) and two verification shapes; the
template path deliberately does not run a source diff, because a filled field is a
legitimate difference.

## 2026-11-04 — the leftover gate refuses to write

A strict template fill with `{{…}}` remaining writes nothing; a partial draft needs
`--allow-leftovers`.

## 2026-11-04 — the identity is answer-first, mined, and scored in the open

The questionnaire beats document mining (`.dossier/identity/answers.json` over `*-IDENTITY.md`
/ `resume.md` / `job-history.md`), every mined value carries a file and line, and a field with
neither is absent rather than defaulted (`identity-grounded`). `score_job` is arithmetic over
that profile, normalised by the signals the profile actually supplies, with a disqualifier
capping the band and being named. Cost: a sparse or historical profile scores low and says
so — the first real attempt mined "what I applied for" and returned customer-support roles
for a CS student, which is the correct answer to the wrong question. A capture's
`--min-match` filters on the same number and records `filtered: true` with the score, so a
filtered run reports `complete: false` rather than archiving everything and calling it a
shortlist.

## 2026-11-09 — publishing this repository

The repository is public at `github.com/ericcayers-ai/dossier`. Four decisions were made to make
that honest, each with a receipt in `docs/evidence/publish-gate-2026-11-09.md`:

- **Personal job-search data is not repository content.** 93 occurrences of real employer names,
  absolute home paths and a phone fixture were replaced across 37 tracked files, `.agent_state/` was
  untracked, and the deleted `.verification/tailoredresumes-before.json` — which listed 23 real
  applications with cover-letter filenames and sha256s — was purged from every commit before the
  first push. The graded labels file stays gitignored: it is the owner's data, not the repo's.
- **`pymupdf` is not a runtime dependency.** It is AGPL-3.0-or-commercial, which does not sit
  coherently beside an MIT `LICENSE`. PDF text, geometry and rasterising moved to PDFium
  (`pypdfium2`, BSD-3-Clause/Apache-2.0) behind `render.text_layout` / `render.pdf_to_png`; PyMuPDF
  is an optional extra and a test-only fixture tool. `tests/test_licences.py` now fails if a
  runtime dependency turns copyleft.
- **The bearer token never travels in a URL.** The client appended `?token=` to `/api/raw`,
  `/api/render` and `/api/events`; the server accepted it. Both halves are gone — the HttpOnly
  `SameSite=Lax` cookie authorises those requests already — because a URL credential reaches the
  address bar, history, `Referer` and the access log, which is exactly what `token-never-leaks`
  forbids.
- **A markup file in the workspace is not executable application code.** `/api/raw` serves HTML,
  SVG and XML as an attachment inside `Content-Security-Policy: sandbox`, with `nosniff`, because
  otherwise any page a capture dropped into the folder would run with the app's own API authority.

Two findings were recorded and deliberately not changed in this pass: `GET /api/export` mutates on a
GET and accepts a missing `Origin` (it writes only inside the workspace root), and `await_seconds`
plus request-body size are unbounded (a loopback-only threat model). Both are listed in the receipt.
