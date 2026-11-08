# State

2026-11-06. The current truth about this repo. History lives in `docs/evidence/`; every number
below is a command whose receipt is named.

## Tree

`master`, HEAD `4e9c0e0` plus the 2026-11-09 publish-gate commit, published at
`github.com/ericcayers-ai/dossier` (public). Python 3.13 (`.venv`), React 19 + Vite.
`pyproject.toml` sets `addopts = "-q"`, so a scoped run needs `-o addopts=""`.

**2026-11-09: the suite is fully green and the licence is coherent.** `456 passed, 0 failed`;
playwright is installed; `pymupdf` (AGPL) is no longer a runtime dependency — PDF work runs on
PDFium (`pypdfium2`) and `tests/test_licences.py` fails if a runtime dependency ever turns
copyleft. `.github/workflows/ci.yml` runs the gate. Receipt: `publish-gate-2026-11-09.md`.

## Verified, in one place

| gate | command | result (2026-11-06) |
|---|---|---|
| tests | `.venv\Scripts\python.exe -m pytest -o addopts="" -q` | **449 passed** (168 s) |
| build | `cd ui && npm run build` | built, per-pane chunks, 39.3 KB critical CSS |
| UI gate | `.venv\Scripts\python.exe .ui-ux-master\measure.py` | 12 panes: 0 h1 misses, 0 contrast fails, 0 <24px targets, 0 unnamed, console 0, dark 0, 29/29 focus rings |
| layout | `inspect.mjs --app --widths 1440,768,390` | 0 findings |
| slop | `sloplint ui/src --scope app` | 0 FAIL, 0 REFLEX |
| a11y | `a11y.py` (12 panes + 2 dialogs) | clean |
| graph | `graft check` | OK |
| performance | Lighthouse (desktop) | 98–99 / 100 / 100, FCP 1.4 s, LCP 2.1 s, CLS 0 |
| routes | `sweep.py` (scratch) | 34 ok, 18 refused with a sentence, 4 skipped with a reason, **0 × 5xx** |
| retrieval | `retrieval.py` (scratch) | 729 indexed, 50/50 hits resolve, uncovered query → 0 results, p50 8 ms |
| journey | `tour.py` (scratch) | 24 steps, console 0, HTTP ≥400 0 |
| save path | `tests/test_safety.py` | `PUT /api/file` 200; JS-rounded stamp accepted |
| features | `dossier agent adapters --check` | every generated doc in sync |

**2026-11-07 re-measure: the gate is red on this machine, for one environment reason.**
`7 failed, 427 passed, 16 errors`; all 23 raise `BrowserType.launch: Executable doesn't exist`
for `chromium_headless_shell-1248` — Playwright's browsers are not installed here. The 7 are
`tests/test_scrape.py`, the 16 are `tests/test_e2e_ui.py`; nothing outside the browser path fails.
`playwright install` is the fix and it is a download, so it waits for the owner.
Receipt: `orchestrate-2026-11-07.md`.

**2026-11-07, later: Playwright is installed and the browser suites pass.** Re-measured after the
layman pass (a `df` check first — the run below started with the volume at 100 % and aborted with
`OSError: [Errno 28]` in `test_template`/`test_trash_retention`; deleting 96 stale
`%TEMP%\dossier-e2e-*` workspaces freed 11 GB and the same command then ran clean):

| gate | command | result (2026-11-07) |
|---|---|---|
| tests | `.venv\Scripts\python.exe -m pytest -o addopts="" -q -p no:cacheprovider` | **449 passed, 1 failed** in 135 s — the failure is `test_safety.py::test_no_tracked_file_carries_personal_contact_details`, pre-existing on `master` and listed under *Next action* |
| browser suite | `… pytest tests/test_e2e_ui.py` | **16 passed** in 60 s |
| UI gate | `.ui-ux-master\measure.py`, extended with the new pane | **13 panes × 1440/768/390: 0 h1 misses, 0 contrast fails, 0 <24px targets, 0 unnamed, 0 overflow, console 0, dark 0, 29/29 focus rings** |
| slop | `sloplint ui/src --scope app` | 0 FAIL, 2 WARN (both waived) |
| before/after | `docs/evidence/ux-layman-2026-11-07/capture.py` | 20 screenshots, 2 metric files, console 0 |

Receipts (26 `.md` in `docs/evidence/`): `2026-11-06-verification-pass.md` (the acceptance pass, with
its per-entry subagent addendum and the stub sweep),
`request-coverage-2026-11-06.md` (every owner request → evidence),
`ui-coverage-2026-11-06.md`, `reel-matrix-2026-11-06.md` (**111 rows = 111 digest headings**),
`hiring-panel-2026-11-06.md`, `atomic-write-2026-11-06.md`, `perf-split-2026-11-06.md`,
`skills-audit-2026-11-06.md`, `docs-audit-2026-11-06.md`, `docs-audit-3-2026-11-06.md` (all 42 uncovered documents),
`digest-chunk{1..4}-2026-11-06.md` (the four line-range reads that cover §1–§95).

## Live now

- **27 modes, 18 gates, 34 artifacts, 54 unique `/api/*` paths (58 route registrations)** in the contract
  (`dossier agent manifest --json`), including `panel` — seven reviewers, each scoring and
  quoting the exact line behind its objection.
- **13 UI panes in 6 areas** (2026-11-07): **Start** · Start here | **Files** · Folder |
  **Search** · Capture, Jobs, Identity | **Papers** · Build, Verify | **Housekeeping** · Audit,
  Trash, Sync | **Agent** · Loop, Opportunity, Panel. `Start here` is the default destination
  (`#/start/start`) and states the loop as four steps with the engine's own next unit above them.
  The twelve older panes and every address are unchanged. Receipt:
  `docs/evidence/ux-layman-2026-11-07/README.md`.
- `dossier panel`, `GET|POST /api/render`, `GET /api/convert/routes`, queued `?dir=` + search with
  path matches first.

## Not done

- **No CAPTCHA farm, no proxy pool, no fingerprint spoofing** beyond
  `scrape/challenge.STEALTH_INIT_SCRIPT`. The solver needs a paid key only the owner can supply.
- **`POST /api/scrape/login` does not exist.** Signing in stays a CLI action that opens a real
  window, because a server route cannot wait for a person.
- **`dossier verify template` does not scan text boxes or images** for placeholders
  (`python-docx` exposes neither); the leftover gate catches what it can read.
- **Two routes have no UI call site, on purpose**: `GET /api/agent/next` (the status route the
  landing strip reads already carries `next`) and `GET /api/match/posting` (a single-posting probe
  for scripts; the app scores through `/api/identity/match`).
- **`CONVENTIONS.md:66`**: this file and `HANDOFF.md` were over their 120-line cap; both were
  trimmed on 2026-11-06 and the session logs moved into the receipts.

## Blocked / environment

- Disk: **17 GB free** at the last check (it was 9.9 GB). Treat a large build as conditional on a
  fresh `df`. `cleanup.ps1` reclaims little by itself; `npm cache clean --force` and
  `uv cache clean` freed ~9 GB here.
- `uv sync` without `--all-extras` uninstalls the extras; `*.dist-info\licenses` carries the
  Windows ReadOnly bit and fails an uninstall mid-way (clear it first).
- `obscura --screenshot` suppresses `--dump`; the driver writes the dump with `-o` instead.
- Five other agent sessions run concurrently on this box; a Lighthouse TBT reading under load is
  not the engine's own.

## Next action

1. **Decide whether the workbench's own names change.** `Capture`, `Identity`, `Papers`,
   `Housekeeping`, `Agent`, `Loop`, `Opportunity`, `Panel` are pinned by `tests/test_e2e_ui.py`, so
   the 2026-11-07 pass added a plain-language front door instead of renaming them. The proposed
   plain map is in `docs/evidence/ux-layman-2026-11-07/README.md`; acting on it means editing the
   gate in the same commit. Since 2026-11-09 the `Start here` pane is inside both gates, so all 13
   panes are measured (STATE used to claim 13 while `measure.py` walked 12).
2. **The contact-details invariant is green.** Fixed 2026-11-09 by scrubbing 93 occurrences of
   real employer names, home paths and a phone fixture across 37 files, and by narrowing the test's
   needle from the GitHub account handle to the personal identifiers it is actually for.
3. **Confirm the 15 proposed eval grades** — written 2026-11-07 at
   `docs/evidence/fit-eval-proposed-grades-2026-11-07.json` (one justification per row, tracker's
   prior grade beside it); the gold set is **unchanged** and no threshold moved. On the honest
   labels the ranker loses to arrival order (**nDCG@10 0.7283 against 0.7838**), so the next fix is
   `score_job`, not the slack. The eval workspace lived in `%TEMP%` and is gone, so the 23 postings
   must be archived as a fixture before the number can be reproduced. Re-record the baseline
   yourself once the set is one you believe.
