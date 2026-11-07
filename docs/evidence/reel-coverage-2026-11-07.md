# Reel digest → Dossier: the 2026-11-07 delta

Pass 2026-11-07. The full sweep was already done and receipted on 2026-11-06 —
`docs/evidence/reel-matrix-2026-11-06.md`, **111 rows**, one per `##` heading in
`<home>/.pi/agent/reelkit/DIGESTS.md`, every entry carrying a verdict and a reason. That
file is not rewritten here; this one adds the entries ingested since, and re-checks the count so
the older receipt cannot be claimed as complete coverage it no longer has.

## The count, measured

```text
$ grep -c '^## ' DIGESTS.md                      # 126   (was 111 on 2026-11-06)
$ grep -cE '^\| (§[0-9]+|S[0-9]+) \|' docs/evidence/reel-matrix-2026-11-06.md   # 111
```

126 − 111 = **15 headings ingested since**, and they resolve exactly: six entries `§96`–`§101` plus
nine of their sub-headings (2 + 2 + 1 + 2 + 1 + 1). The table below therefore has six entry rows and
six sub-heading rows, the latter each covering one or both of "Named tools" / "Fit for this
machine". Nothing was reclassified, and no earlier verdict is re-opened.

Commands run, in the corpus's own interpreter, corpus read-only:

```text
$ ./venv/Scripts/python.exe rq.py project dossier      # 10 saved items for this project
$ ./venv/Scripts/python.exe rq.py verdict viable       # §88 §91 §92 §93 §96 §97 §99
$ ./venv/Scripts/python.exe rq.py verdict implemented  # §90 §95 §100 §101
$ ./venv/Scripts/python.exe rq.py search evaluation     # no dossier hit
$ ./venv/Scripts/python.exe rq.py search label          # no dossier hit
$ ./venv/Scripts/python.exe rq.py search "ranking score"   # no match
$ ./venv/Scripts/python.exe rq.py search "resume fit"      # no match
```

The searches are the ones that matter for this run's subsystem (the fit evaluation and its labels):
nothing in the digest addresses relevance labelling, nDCG or ranker evaluation, so no verdict in
the corpus bears on the work done today.

## The fifteen new headings

| §n | title | applies to dossier? | verdict applied |
|---|---|---|---|
| §96 | `HAL-X-AI/THX-02`, a 4.54B "decision model" (not a reel) | no — a router/classifier model, not a document tool | recorded: viable but unverified; nothing adopted, nothing to adopt here |
| S §96 | Named tools / Fit for this machine | no — no install in this repo | none |
| §97 | AnyScene — a 3D city block from one sentence | no — Blender scene generation, a different project's lane | recorded: viable; `fal` is paid, so nothing here (order §5: no spend) |
| S §97 | Named tools / Fit for this machine | no — overlaps superskills, not dossier | none |
| §98 | "prompt engineering was the biggest waste of time" | no — a comment-to-DM funnel with one defensible sentence | recorded: no-action |
| S §98 | Fit for this machine | no | none |
| §99 | Atomic Agent — a local-first agent with a GAIA number | no — it is a harness, and Pi already is the harness here | recorded: viable, rejected as a replacement; installer never run |
| S §99 | Named tools / Fit for this machine | no | none |
| §100 | "four output formats" (writing, diagram, HTML, explainer) | no — already folded into `karpathy-superskill` | implemented elsewhere; nothing for dossier |
| S §100 | Fit for this machine | no | none |
| §101 | "skill finder" install-and-verify walkthrough | no — already implemented as `capability-management` discipline | implemented elsewhere; nothing for dossier |
| S §101 | Fit for this machine | no | none |

No new entry names dossier, its evaluation, its ranking or its scraping, so no verdict in the
corpus bears on the labelling work done today and no earlier verdict is re-opened. Of the four
`implemented` verdicts, §90 and §95 are the matrix's `N/A` (a `tradingagents` duplicate, and
`agent-desktop`, which the digest itself rules out for a web/service app: `ls src-tauri` → absent);
§100 and §101 were applied as skills outside this repo. **Work list addition: none.**
