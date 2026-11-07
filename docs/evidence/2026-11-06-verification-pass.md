# Verification pass — 2026-11-06

Run with the `project-verification` skill: its own gate first, then independent instruments,
then triage, then this receipt. Every figure below is a command run in this repository on
2026-11-06; the receipts the instruments write are named beside each one.

## 0. The contract, before touching anything

1. **Outside judge** — the repo's own gate (`pytest`, `dossier doctor`, `dossier agent adapters
   --check`) plus five instruments that do not read code: a route sweep, a real-browser journey,
   a density/a11y pass, a concurrent-write storm, and a retrieval probe.
2. **Pass condition** — `pytest` ≥ 448 green; `sweep` **0 × 5xx** with no unexplained skip; the
   journey with 0 console errors and 0 failed requests; `measure.py` all zeros across 12 panes;
   0 lost writes and 0 conflicts over 40 concurrent saves; retrieval provenance 100 % and an
   uncovered query returning 0 rather than an error.
3. **Known-bad control** — the sweep itself fired before the fix (`POST /api/actions` → 500) and
   the stamp test fails on any changed content, which is why "0 findings" here means "the check
   ran", not "the check stopped matching".
4. **Not running** — no commit, no publish, no deploy; nothing outside this repo and its scratch
   workspace (`%TEMP%\dossier-live-2026-11-05`); the other four agent sessions on this machine were
   left alone.

## 1. Orientation

- Branch `master`, HEAD `c043aa0`, **152 entries uncommitted** (the owner slices; the tree is
  dirty by design and that is stated, not hidden).
- A server was running on 127.0.0.1:8077 against the scratch copy of the workspace, restarted
  after every Python change (see the trap in §6).
- Read: `AGENTS.md`/`CLAUDE.md`, `docs/STATE.md`, `docs/HANDOFF.md`, `tasks/WORKLIST.md`, the last
  receipt.

## 2. The repo's own gate

| command | result |
|---|---|
| `.venv\Scripts\python.exe -m pytest -o addopts="" -q` | **449 passed**, 168 s |
| `.venv\Scripts\dossier.exe doctor --root .` | every capability `ok` (docx_write, docx_to_pdf, pdf_text_layer, pdf_to_image, fts_search, capture_public, capture_authenticated) |
| `.venv\Scripts\dossier.exe agent adapters --check --root .` | every generated document `true` (8 of 8) |
| `cd ui && npm run build` | built in 522 ms, per-pane chunks |
| `.venv\Scripts\python.exe .ui-ux-master\measure.py` | 12 panes at 1440/768/390: 0 h1 misses, 0 contrast fails, 0 targets < 24 px, 0 unnamed controls, 0 overflow, console 0, dark 0, 29/29 focus rings |
| `inspect.mjs --app` / `sloplint` / `a11y.py` / `graft check` | 0 findings / 0 FAIL 0 REFLEX / clean / OK |

## 3. The five instruments

| # | instrument | receipt | result |
|---|---|---|---|
| 1 | **Route sweep** — every declared `/api/*` route called in-process against a seeded workspace with the app's own token | `receipts/sweep.json` | **34 ok, 18 refused (4xx with a sentence), 4 skipped with a reason, 0 × 5xx** over 54 unique paths (58 registrations; 56 rows after HEAD/OPTIONS are dropped) |
| 2 | **Journey** — `tour.py`, 24 steps in a real browser at 1440/768/390 plus a headed PDF run | `visual-2026-11-06/` | console **0**, HTTP ≥ 400 **0**, every pane one `h1` |
| 3 | **Density / copy** — `measure.py` word and control counts per pane | `tour.json` | landing 62 words · Loop 221 · Trash 153 · Panel 50 (empty) / 211 (run) · 0 `(s)` in user-facing strings |
| 4 | **Write-path storm** — `hammer.py`: 8 clients × 5 concurrent `PUT /api/file` | `friction.json` | **40 writes, 40 × 200, 0 × 500, 0 × 409** |
| 5 | **Performance / a11y** — Lighthouse desktop + `a11y.py` | `lighthouse10.json`, `a11y.json` | **98 / 100 / 100**, FCP 1.4 s, LCP 2.1 s, CLS 0; a11y clean on 12 panes and 2 dialogs |

## 4. Retrieval (the repo has a knowledge index)

| check | result |
|---|---|
| 1. Capability | `/api/health` reports **729 indexed** files |
| 2. Provenance | 50 of 50 search hits resolve to a real file on disk, 0 unresolvable |
| 3. Refusal | an uncovered token returns **200 with 0 results** — an answer, not an error and not a wrong file |
| 4. Evaluation | nDCG@10 **0.9078** vs baseline 0.8923, Spearman 0.5011 vs −0.3945 (`fit-eval-2026-11-05.md`); 18 gradable rows, all positive — the gold set cannot yet lose, which is stated in `STATE.md` Next action |
| 5. Failure surfacing | a failed document names its extractor's error, not "1 failed" (`extract.py` `meta["error"]`, surfaced by the sweep's 4xx bodies) |
| 6. Latency | p50 **8 ms**, p95 17 ms after the fix below (was p95 287 ms) |
| 7. Hardware sizing | **N/A** — no GPU, no model in this repo |

## 5. Feature-gap triage

Every declared route against a call site in `ui/src` (the sweep counts first-party `.ts/.tsx`
mentions of the route or its last segment):

| route | status | verdict |
|---|---|---|
| `GET /api/agent/next` | 200, no call site | **reachable another way** — the landing strip reads `GET /api/agent/status`, whose payload carries `next`; `agent/next` is the CLI-shaped twin |
| `GET /api/match/posting` | 422 without a `rel`, no call site | **API-only by design** — a single-posting probe for scripts; the app scores through `GET /api/identity/match` |
| the other 54 | 34 ok, 18 refused, 4 skipped | every one has a call site or a named reason for the skip |

## 6. Findings, and what was done

| # | finding (the command that showed it) | class | fix |
|---|---|---|---|
| 1 | `POST /api/actions` with `{}` → **500** (`sweep.py`) | product defect | body validated: missing `id`/`rel` → **400 with a sentence**, unknown id → 404. The sweep now records 0 × 5xx |
| 2 | the sweep's first run reported **52 × 401** | **instrument defect** | the bearer token is per app instance; the harness now builds the config with the token it sends. Fixed before any conclusion was drawn |
| 3 | `"resume"` took **255 ms** per query (`retrieval.py`) | product defect | a query whose path matches already fill the page no longer pays for bm25 over every body match: **255 → 4–16 ms** |
| 4 | `GET /api/render` converted DOCX on a cache miss (`CONVENTIONS.md:33`) | convention violated | GET serves **cache only** and answers **409** naming `POST /api/render`, which builds; the client does GET → POST → GET; `GET /api/convert/routes` states the fidelity class |
| 5 | a DOCX stated no fidelity class (`DESIGN.md:165`) | convention violated | the Viewer reads the class from the engine and prints "Server render · faithful fidelity" above the frame |
| 6 | `STATE.md` 206 lines, `HANDOFF.md` 143 (`CONVENTIONS.md:66`) | convention violated | both rewritten: **76** and **57** lines, history moved into the receipts |
| 7 | the browser showed "fidelity unknown" and no frame after the render split | **not a product defect** | the server was still running the pre-change code — the skill's own trap. Restarted, then: caption "faithful fidelity", iframe present, 3 GETs (probe, preflight, iframe) |

`docs/CONTRACT.md` had no `panel` row before this pass: adding a manifest mode does not regenerate
the generated documents. `dossier agent adapters` rewrote six managed blocks; `--check` now
returns `true` for all seven.

## 7. Negative controls

- The route sweep **fired** on a known-bad request (`{}` → 500) and stopped firing after the fix.
- `tests/test_safety.py::test_a_stamp_rounded_by_javascript_still_matches` asserts that a *changed*
  file still conflicts (different sha256, different size, a 10 ms move), so the relaxed comparison
  cannot silently accept a stale write.
- `tests/test_api.py::test_a_get_never_converts_and_the_post_owns_the_build` asserts the **409** on a
  cold cache before asserting the 200 after the POST — the failure path is exercised, not assumed.

## 8. Not checked

- **No commit, no push, no deploy.** Nothing was published; the tree stays as the owner slices it.
- **Not run**: `POST /api/scrape/run` (launches a real browser session), `GET /api/export` (writes
  outside the root), `POST /api/agent/ask` (needs a configured model API), `POST /api/tree/links`
  (needs two existing node ids) — four skips, each named in `sweep.json`.
- **No GPU/desktop verification**: `desktop-verify` / `agent-desktop` (§95 of the reel digest) does
  not apply — `ls src-tauri` returns nothing; this is a web/service app.
- **The eval gold set cannot lose yet** (18 positive grades): the ranker's quality is measured, its
  discrimination is not.
- **Lighthouse under load**: 98 on three runs, 99 on one; FCP/LCP/CLS identical, TBT 20–50 ms while
  four other sessions run. Reported as a range.

---

# Addendum — the per-entry re-read, by five subagents

The first half of this pass verified by instrument. This half answers the other question: *was the
reel digest actually gone through, and was every document considered?* Both were done by reading,
in parallel, and the arithmetic is checkable.

## Who read what

| child | scope | output | entries |
|---|---|---|---|
| `chunk1` | `DIGESTS.md` lines 15–360 | `digest-chunk1-2026-11-06.md` | §1–§34 (34) |
| `chunk2` | lines 361–720 | `digest-chunk2-2026-11-06.md` | §34–§45 (12) |
| `chunk3` | lines 721–1080 | `digest-chunk3-2026-11-06.md` | §46–§78 (33) |
| `chunk4` | lines 1081–1420 | `digest-chunk4-2026-11-06.md` | §79–§95 (17) |
| `docs` | every file under `docs/` not covered by the earlier two audits | `docs-audit-3-2026-11-06.md` | 48 documents |

**Completeness was checked by id, not by counting rows** (the skill's own rule): the union of the
four chunks' entry numbers is `1…95`, 95 distinct, **no gaps**. `grep -c '^## ' DIGESTS.md` = 111 =
95 entries + 16 sub-sections, and the matrix carries 111 rows.

## What the re-read changed

29 of the 95 entry verdicts were sharpened; 15 were rewritten in the matrix (each now carries
`· re-read 2026-11-06 by the chunk scouts`). The substantive ones are the N/A → honoured moves,
because a *transferable* rule had been dismissed with the rest of a reel's domain:

| § | the rule that transfers | verdict now |
|---|---|---|
| 4 | a specialist persona with declared inputs and a handback | honoured — the manifest's 27 modes each declare reads/writes/gates |
| 9, 13 | written design guidelines before pixels | honoured — `DESIGN.md` + `.ui-ux-master/` + the rendered-page check |
| 12 | prefer free public catalogues and a local engine | honoured — `SOURCES.md:136` chose the local engine over the paid path |
| 43 | nothing closed, modified or deleted without approval | honoured — trash-before-overwrite, `never-only-copy` |
| 52 | local BM25 with quoted tokens, one server not two | honoured — `db.py` FTS5, tokens quoted as phrases |
| 84 | deterministic gates over a swarm that can talk itself into a verdict | honoured — gates are code in `manifest.py` |
| 87 | the model proposes, code holds the veto | honoured — "Gates that are never softened" in `brief.py` |
| 88 | one manifest is the source, every surface generated | honoured — docs, CLI, packs all read the manifest |
| 91 | generated output is accepted by a render-and-compare gate | honoured — `verify.visual` |
| 20 | a chair that scores and names the weakest parts | **applied** — the panel's chair |
| 55 | six documents exist before code | honoured — `docs/design/` (and filled in below) |

## Findings the documents scout produced, and the fixes

| finding | fix |
|---|---|
| `docs/design/` held six **unfilled prompt templates** ("Three adjectives, one anti-reference.") | all six rewritten with real content drawn from the canonical docs — 635 → 1,746 words |
| `docs-audit-2.md` **did not exist**, though `request-coverage-2026-11-06.md` cited it | the citation now points at `docs-audit-3-2026-11-06.md`, which covers those five documents and all 42 the first audit missed |
| `STATE.md` and `HANDOFF.md` said **56 routes** | measured **54 unique paths / 58 registrations**; both corrected |
| `SOURCES.md:146` named a gate `challenge-is-a-blocker` | the gate is `challenge-is-explicit`; corrected |
| this receipt said adapters checked **7 of 7** | the command prints **8** keys; corrected |
| `atomic-write-2026-11-06.md` said **7 tests** in `test_safety.py` | **8** now; corrected |
| `AUDIT-2026-11-04.md` carried stale counts with no date warning | marked as a dated snapshot, with `CONTRACT.md` named as the authority |

Every one of those was a *number in a document that disagreed with the code* — the class of defect
the skill calls out as "one value, one source".

## Not checked in this half

- The chunk scouts read and grepped; they did not run the UI. The browser claims in this receipt
  come from the instruments in the first half (`tour.py`, `measure.py`, `inspect.mjs`, Lighthouse).
- `§96`+ do not exist yet: the digest stood at 111 headings when this pass read it.

## Addendum 2 — stub sweep

A "no stubs" claim needs a mechanical check, so: every `pass`, `TODO`, `FIXME`, `NotImplementedError`
and "coming soon" in the first-party code.

```
grep -rnE "TODO|FIXME|XXX|NotImplementedError|^\s*pass\s*$" src/dossier --include=*.py   # 11 hits, all `pass`
grep -rnE "TODO|FIXME|coming soon|not implemented" ui/src --include=*.tsx --include=*.ts   # 0 hits
```

The eleven `pass` statements, read one by one, are three kinds and none is a stub:

- **an exception class** — `class RendererUnavailable(RuntimeError): pass` (`engine/render.py:87`);
- **a best-effort branch with its reason in a comment** — the stdio reconfigure (`cli.py:1654`), the
  trash prune log (`safety.py:641`), the render cache unlink (`scrape/browser.py:205`), the
  optional `playwright` probe (`browser.py:459`), the guard cache on a read-only workspace
  (`scrape/guard.py:146`), the Windows chmod (`scrape/session.py:251`);
- **an intentional no-op inside a branch** — `engine/identity.py:356` (a `Label: value` line keeps
  the value, so there is nothing to strip), `identity.py:789` (an unparseable date earns no recency
  bonus), `tailor.py:131` (`defusedxml` absent → fall through to the DOCTYPE/ENTITY check),
  `scrape/challenge.py:184` (a navigating page is not a failure).

No `NotImplementedError`, no `TODO`, no "coming soon" anywhere in `src/dossier` or `ui/src`.

## Addendum 3 — the flaky gate, fixed

`tests/test_api.py::test_a_get_never_converts_and_the_post_owns_the_build` passed alone and failed
in a pair with `test_matrix.py`. Not flakiness in the test: **`POST /api/render` let a converter
exception escape** (`convert.py:128` → Word COM), so the route answered with an unhandled
traceback rather than a status. Word is an external process; under load it refuses.

| before | after |
|---|---|
| converter raises → unhandled exception (500-shaped) | **503** with `the DOCX renderer could not run: …`; the cache stays empty so the next GET still answers **409** and a retry is honest |
| the test skipped whenever the machine's Word was busy | one deterministic test monkeypatches `convert` to raise and asserts **503 + sentence + 409**; the real conversion test is opportunistic and says so |

That is the skill's rule applied literally: *fix the instrument when the instrument is wrong, and a
skip needs its reason on the record.*
