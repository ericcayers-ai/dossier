# What is still to do — measured 2026-11-09

Read-only inventory. Every row below was re-measured today at `HEAD` = `4e9c0e0`; the tree was
clean before and is clean after (`git status --porcelain` → 0). Scratch instruments live in
`~/.dsh/scratch/dossier-live-2026-11-05/`; the live job-search workspace they used to run against
(`%TEMP%\dossier-live-2026-11-05`) **no longer exists**, which is itself item B1.

## The gate, as it stands

```text
$ .venv/Scripts/python.exe -m pytest -o addopts="" -q -p no:cacheprovider --basetemp=…\dossier-gate
1 failed, 449 passed, 2 warnings in 134.51s (0:02:14)

$ .venv/Scripts/dossier.exe doctor --root .          -> verdict: ready, 9/9 ok
$ .venv/Scripts/dossier.exe agent adapters --check   -> 8/8 true
$ .venv/Scripts/python.exe .ui-ux-master/measure.py  -> 13 panes × 1440/768/390 all zeros,
                                                        console 0, dark 0, 29/29 focus rings
$ node ~/.pi/agent/skills/hallmark/scripts/sloplint.mjs ui/src --scope app
                                                     -> 0 FAIL, 2 WARN (both waived)
$ graft build && graft check                         -> 1516 nodes, 3571 edges; check OK
$ .venv/Scripts/dossier.exe audit --root .           -> 0 fail, 1 attention (coverage)
```

So: **one red test, and it is the only red one.** The 7 Playwright failures and 16 errors recorded
on 2026-11-07 are gone — the browsers are installed and `tests/test_e2e_ui.py` is green.

## A. The red test (owner data decision, 5 files)

`tests/test_safety.py::test_no_tracked_file_carries_personal_contact_details` →
`AssertionError` naming exactly:

```text
['.github\ISSUE_TEMPLATE\config.yml: <account handle>', 'CODE_OF_CONDUCT.md: <account handle>',
 'CONTRIBUTING.md: <account handle>', 'docs\evidence\fit-eval-2026-11-05.md: ericcayers',
 'tests\test_panel.py: <NZ dialling prefix> ']
```

Two ways out, and only the owner can pick: replace the contact with a role address in the three
housekeeping files and a placeholder in the receipt, **or** delete the assertion. Deleting the gate
is the wrong default — it is the invariant that keeps a receipt generated from a real workspace
from being published with somebody's phone number in it.

## B. The ranker is worse than arrival order, and cannot currently be re-measured

### B1 — the eval corpus was in `%TEMP%` and is gone

`docs/evidence/fit-eval-baseline-2026-11-05.json` records `corpus_hash 4f7da8256384` and **no
rows**; `docs/evidence/fit-eval-labels-2026-11-05.json` has the 23 keys, titles and grades but not
the posting text. `%TEMP%\dossier-live-2026-11-05` (the root both files were produced from) does
not exist. Consequence: `dossier identity eval --root <that path>` cannot be reproduced, and a
corpus with a different hash cannot honestly be compared against the recorded baseline.

Fix, and it must precede B2: archive the 23 postings (or one `all_jobs.json`) as a repo fixture and
point the eval at it, so `fit-is-measured` is reproducible from the repo alone.

### B2 — `score_job` loses to no ranking at all

On the honest labels (gold 18 + the 15 proposed = 23 graded) the last recorded run was

```text
identity score   nDCG@10 0.7283   Spearman 0.591
arrival order    nDCG@10 0.7838   Spearman -0.383
```

`graded 23 of 23` fails `fit-is-measured` (`nDCG@k dropped to 0.7283 from 0.9078`). The recorded
0.9078 was inflated by 0 negatives in the gold set, so the honest number is the 0.7283. The work is
in `src/dossier/engine/identity.py::score_job` (weights + title-family matching), not in
`evaluation.NDCG_SLACK`. The 15 proposed grades still need the owner's confirmation
(`docs/evidence/fit-eval-proposed-grades-2026-11-07.json`).

## C. Feed rows carry no description, so requirement extraction has nothing to read (new)

Measured live today against a real board, in a throwaway root:

```text
$ dossier feeds fetch greenhouse --board vercel --root %TEMP%\dossier-ingestFt1y
complete: greenhouse - 87 of 87 records -> …\greenhouse_data\all_jobs.json
$ 87 rows; row keys: description, employer, id, location, pay, source, title, url, work_type
$ rows[0]['description'] -> ''
```

Cause, both halves in `src/dossier/feeds.py`: `ENDPOINTS["greenhouse"]` has no `?content=true`
(the API returns a 6,930-character `content` field only with it), and `_jobs()` reads
`item["description"]`, which Greenhouse never sends. The same shape applies to `lever`
(`descriptionPlain`) and `ashby` (`descriptionHtml`). Until this is fixed, `keywords` / `upskill` /
`match` judge a posting by its **title alone**, which is most of why the fit score is weak (B2).
Rate-limited correctly today; `complete: 87 of 87` proves the fetch and the honesty ledger.

## D. Nothing runs the six-step pipeline end to end

`docs/PROJECT.md`'s job is ingest → filter → tailor → letter → track. The pieces exist and each is
tested in isolation; there is no test and no receipt that runs all six over one workspace and then
asks the tracker "what did I apply to, with which variant, and what is next". `test_pipeline_from`
(`tests/test_agent.py:76`) asserts a *mode chain*, not a job pipeline. Also: the repo root is a
workspace with no `*-IDENTITY.md`, no base `.docx`, no tracker and 0 postings
(`dossier agent status` → three blockers), so there is currently **no live instance** of the
product on this machine at all.

## E. The coverage artifact has no producer

`manifest.py:591` declares `Artifact("coverage", "nz-job-search-coverage-*.json", …, producer
"sources")` and `audit` reports it as `[attention] No coverage snapshot. Source freshness is
unproven.` Nothing under `src/` ever writes that glob — `engine/sources.coverage` and
`agent/workspace._coverage_state` only read it. Every workspace therefore shows the attention row
forever, and `agent/loop.py:145` can name a stale-coverage target that no command can satisfy.
The fix is small: have `scrape run` / `feeds fetch` write the run's own numbers
(source, items, `complete`, failures, date) to that filename.

## F. The reel matrix is 8 entries behind

```text
$ grep -c '^## ' ~/.pi/agent/reelkit/DIGESTS.md   -> 149 headings, entries run to §119
$ grep -c '^| ' docs/evidence/reel-matrix-2026-11-06.md  -> 119 (111 rows + header/rule)
```

§112–§119 (Beamer, CDMs, Unslop, "most powerful prompt", gamedev skills, Craft Anything, Roblox
skills, the Fujifilm agent) have no row. Reading them, seven look N/A to this repo and one
(§114 Unslop) is already honoured by `sloplint` — but that is a judgement, and the matrix's own rule
is that its rows equal the digest's entries. Also note the digest is being edited by other sessions
while this is written, so re-measure at the end of the pass, not the start.

## G. Documentation drift since 2026-11-07

- `docs/STATE.md` still dates itself 2026-11-06/07, quotes `HEAD c043aa0` in the Tree section, and
  lists "commit in reviewed slices" as next action 1 — the tree is clean at `4e9c0e0` over 28
  commits, so that action is done.
- STATE says the remote returns 404; `git remote -v` has `origin
  https://github.com/ericcayers-ai/dossier.git`, `master` has **no upstream** and nothing has ever
  been pushed. Publishing is an unmade owner decision, not a broken remote.
- STATE/HANDOFF quote `449 passed, 1 failed` — still exactly right — but attribute it to the last
  pass rather than to today.
- `graft/` was stale by two panes (`StartPane.tsx`); rebuilt and green now.

## H. Decisions only the owner can make

| id | the decision | why it is still open |
|---|---|---|
| plain-language names | rename `Capture/Identity/Papers/Housekeeping/Agent/Loop/Opportunity/Panel` and the six area labels, or keep the engine's vocabulary | `tests/test_e2e_ui.py` clicks those labels, so the rename and the gate change must land in one commit |
| #143 | plugin vs its own ecosystem | recorded 2026-11-06, never answered |
| #186 | one wrapper repo over the tailoring skill + the app + the Hermes job-search sessions | same shape; the evidence to decide it exists (23 postings, 38 tracker rows, 18 gates) |
| #005 | persona fine-tune as the backend | contradicts `docs/PROJECT.md` (judgement belongs to whichever model is injected); needs an amend of PROJECT.md or a close |
| #010 | scraping that survives bot defence | contradicts the declared non-goal; the honest version is more public feeds |
| #129 | "incorporate all this" | unactionable until the source list is named |

## I. Deferred by design, not gaps (verify before re-opening)

Captcha farm / proxy pool / fingerprint spoofing beyond `challenge.STEALTH_INIT_SCRIPT`; the solver
needs a key only the owner can buy. No `POST /api/scrape/login` (a server route cannot wait for a
person). `verify template` cannot scan text boxes or images for placeholders (`python-docx` exposes
neither). Two routes have no UI call site on purpose (`GET /api/agent/next`,
`GET /api/match/posting`).

## J. Hygiene, ranked last

- `src/dossier/cli.py` is 1,680 lines / 82 KB; 14 files exceed 24 KB. A split is a behaviour-risk
  refactor with no failing test to justify it — do not start it casually.
- 2,232 B of duplicate content, inside a gitignored generated cache under
  `docs/history/graphify-legacy-2026-09-12/`. Nothing to reclaim outside it (`untangle-scan` → 0 B
  dead).
- **A gate run dirties the tree**: `tests/test_e2e_ui.py` rewrites six tracked screenshots in
  `docs/evidence/e2e-*.png` and `measure.py` rewrites `.ui-ux-master/receipts/**`. Expected by
  design (they are receipts), but "clean tree" is only true before a run.
- `measure.py` races: it sleeps 350 ms after a pane click and can sample before a lazy pane chunk
  paints. Reproduced once today — `1440 Panel -> h1 []` — and absent on the immediate rerun. The
  instrument should `wait_for_selector("h1")`, or it will keep producing a false red on the pane
  that loads last.

## What was not checked today

Lighthouse (disk at 8.2 GB of 931 GB, and the score wobbles 98–99 under five concurrent sessions);
`inspect.mjs` / `a11y.py` / `tour.py` (they need a served build; `measure.py` covers the same
768/390 and contrast ground); any board other than Greenhouse; `dossier verify all` on a real
document (no base `.docx` on this machine).
