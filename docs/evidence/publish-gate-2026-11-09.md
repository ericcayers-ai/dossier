# Publish gate — 2026-11-09

Order: *"do all cybersecurity checks and make sure its all prod ready… licensing of everything is ok
and nothing confidential or private is leaked and then … push to the repo publically"*. This is the
receipt: what was measured, what was found, what was changed, and what is still the owner's call.

Working tree at the start: clean, `HEAD` = `4e9c0e0`. Suite at the start: **449 passed, 1 failed**.

## 1. The gate after this pass

```text
$ .venv/Scripts/python.exe -m pytest -o addopts="" -q -p no:cacheprovider
456 passed, 2 warnings in 124.55s            # was 449 passed, 1 failed
$ python ~/.dsh/skills/cybersafe/scripts/cybersafe_scan.py .      → 518 files, 0 findings
$ .venv/Scripts/dossier.exe doctor --root .                       → verdict: ready, 9/9
$ .venv/Scripts/dossier.exe agent adapters --check --root .       → 8/8 true
$ cd ui && npm ci && npm run build                                → built, per-pane chunks
$ cd ui && npm audit --omit=dev                                   → 0 vulnerabilities
$ pytest tests/test_licences.py                                    → 3 passed
$ graft build && graft check                                       → 1516 nodes, OK
```

## 2. Found and fixed — privacy

`git grep` over history and tracking found one real leak, and it was not in the working tree:

| where | what it exposed | fix |
|---|---|---|
| `.verification/tailoredresumes-before.json` (added `5d0a5b8`, deleted later) | the owner's home path, surname, **23 real applications** with employer, role, month, cover-letter filenames and PDF sha256s | purged from every commit before the first push (see §5) |
| `.agent_state/` (3 tracked files) | local agent scratch naming the real workspace | untracked, `.gitignore`d |
| 8 tracked docs + `.ui-ux-master/measure.py` | `<home>` — local username and harness layout | scrub script; `measure.py` now derives `REPO` from `__file__` and the temp dir from `tempfile` |
| 11 tracked files | real employer names used as fixtures and quoted in receipts | replaced with neutral names (`Northbridge`, `Harbourline`, …), consistently, so tests still pass |
| `tests/test_panel.py`, `tests/test_safety.py` | a `+64` phone fixture tripping the repo's own invariant | placeholder phone without the `+64` prefix |
| `.ui-ux-master/handoff.md` | home paths in a working note | scrubbed |

93 occurrences across 37 files. `tests/test_safety.py::test_no_tracked_file_carries_personal_contact_details`
now passes, and its needle list was narrowed from the GitHub account handle to the personal
identifiers (real name, mailbox, phone, LinkedIn) — the account is the published identity of the
repository, so linking to it in `CONTRIBUTING.md` is not a leak. Recorded in the test's docstring.

`docs/evidence/fit-eval-labels-2026-11-05.json` (23 real postings + 20 tracker rows) was already
gitignored and stays that way; the tracked proposal file that quoted two employers was scrubbed.

## 3. Found and fixed — licensing

| package | licence | verdict |
|---|---|---|
| `pymupdf` (PyMuPDF) | **AGPL-3.0-or-Artifex-commercial** | **P0**: it was a *runtime* dependency of an MIT repository |
| `pypdfium2` (PDFium) | BSD-3-Clause / Apache-2.0 | adopted as the default PDF engine |
| 10 others | MIT / BSD / Apache / PSF / MPL-2.0 | permissive; judged mechanically |

Changes: `pymupdf` moved out of `dependencies` into the optional `pymupdf` extra; PDF text, page
geometry and rasterising moved to `render.text_layout` / `render.pdf_to_png`, which use PDFium and
only fall back to PyMuPDF when it is installed; `extract.py` and `convert.py` no longer import it;
`doctor.py` reports `pymupdf` as optional. New `THIRD-PARTY.md` states the AGPL consequence plainly
(a bundled or hosted application needs the AGPL or the commercial licence; the source repository
does not convey a combined work). New `tests/test_licences.py` fails if a runtime dependency ever
becomes copyleft, and asserts PyMuPDF is only an extra.

Also fixed: `ui/package-lock.json` declared `ag-grid-community`, `ag-grid-react` and `pdfjs-dist`,
none of which were in `package.json`, imported, or installed — a `npm ci` on the published repo
would have pulled three unused packages. `vite` and `@vitejs/plugin-react` moved to
`devDependencies`, and `"latest"` pinned to `^6.1.1`.

## 4. Found and fixed — security

Two reviewers read `api/app.py`, `safety.py`, `config.py`, the scrape layer and the client. Verified
good: bearer/cookie auth on every `/api/*` route (including the SSE generator), path containment on
every file path (`resolve_in_root`), parameterised SQL with quoted FTS terms, `no-auto-submit`,
session store refusing an empty or cross-host jar, solver key dropped before returning, no
`dangerouslySetInnerHTML` anywhere in the client.

| sev | finding | fix |
|---|---|---|
| P0 | the client appended the bearer token to `/api/raw`, `/api/render` and `/api/events` as `?token=` — address bar, history, `Referer`, access log. `token-never-leaks` was enforced only for the CLI | `withToken` deleted, the `?token=` bootstrap removed, the server no longer accepts a query token; the `SameSite=Lax` cookie already authorises all three. New test asserts a query token is 401 |
| P1 | `/api/raw` served any workspace file inline on the app's own origin — an `.html`/`.svg` in the folder ran as first-party script with full API authority, chainable to `actions.py` command execution | markup is now `Content-Disposition: attachment` with `X-Content-Type-Options: nosniff` and `Content-Security-Policy: sandbox; frame-ancestors 'none'`. New test covers html, svg and a plain file |
| P1 | a `.cmd`/`.bat` obscura shim runs through `cmd /c`, which re-parses the line; a captured URL containing `&` forks a command (measured: the URL truncates at the `&`) | an argument carrying a cmd metacharacter is refused on the shim path only, with a sentence naming the `.exe`; the `.exe` path passes argv untouched. New test |
| P2 | token compared with `!=` | `secrets.compare_digest` |
| P2 | no security headers at all | `nosniff`, `Referrer-Policy: no-referrer`, `frame-ancestors 'none'` on every response |
| P2 | mutating `GET /api/export` accepted with no `Origin` | recorded, not changed: it writes only inside the workspace root, and moving it to POST is an API contract change |
| P2 | unbounded `await_seconds`, no request-body cap | recorded, not changed in this pass |

## 5. The push

The public history must not contain the `.verification/` inventory, so history was rewritten before
the first push (`git filter-branch` over `--index-filter`, all refs), a `pre-public` branch and a
bundle kept the original locally, and every reachable blob was then re-scanned with
`dossier-leak-sweep.py` and `git grep` for: private keys, AWS/GitHub/OpenAI/Anthropic/Google/Slack/
Stripe patterns, JWTs, `password=`/`api_key=` assignments, emails, NZ phone numbers, the owner's
name, home paths, and the real workspace folder name. Result: **0 secrets, 0 personal contact
details, 0 home paths** in the reachable object set.

Also added `.github/workflows/ci.yml` — the suite, the adapter drift check, the licence gate and the
contact-details invariant run on GitHub Actions, so the gate is not a claim made by the author.

## 6. Still open after this pass (unchanged by it)

1. The 15 proposed eval grades still need the owner's confirmation, and the eval corpus must be
   archived into the repo before `score_job` can be re-measured — the workspace it ran against was
   in `%TEMP%` and is gone (see `open-items-2026-11-09.md`).
2. Feed rows still carry an empty `description` for the board-scoped sources, so requirement
   extraction reads titles only.
3. The coverage artifact has no producer.
4. The plain-language pane rename is still a decision, now with the `Start here` pane inside both
   gates (`measure.py` and `test_e2e_ui.py` previously skipped it — 12 of 13 panes were measured
   while STATE claimed 13).
