# Evidence — job-search / Dossier reconciliation, 2026-09-27

Scope: the consolidation request of 2026-09-26 (unify the canonical resume-tailoring
skill, the Dossier application, and all prior job-search sessions into one
LLM-injectable wrapper), audited against live evidence.

Method note: a read-only audit ran first (three parallel subagents: session retrieval,
repo audit, skill/plugin inventory). Corrections and completions applied afterwards are
kept in their own sections, so audit findings and applied fixes are never conflated.
Rows marked *historical* were true at the time of the read-only pass and have since been
superseded by the section that replaces them.

---

## 1. Verification receipts — current state

| Command | Real result |
|---|---|
| `py -3.13 -m pytest -q --junitxml=…` | `tests= 145 failures= 0 errors= 0 skipped= 0 time= 9.356` |
| `.venv/Scripts/dossier.exe agent adapters --check --root .` | all 8 packs `true`, exit 0; on an empty root all 8 `false`, exit 1 |
| `.venv/Scripts/dossier.exe agent manifest --json` | 21 modes / 27 artifacts / 14 gates |
| `.venv/Scripts/dossier.exe doctor --root . --json` | `"verdict": "ready"`, `"blockers": []` |
| `dossier track outcome 1 applied` (no `--confirmed`) | exit 1, `"refused": "drafted-is-not-applied"` |
| doc link audit over all `*.md` | 60 files scanned; the 2 broken links it found were repaired (§7) |

The suite was 143 before this session's two new assertions (§2) and 145 after —
*historical: "143 passed in 13.03s"* was the pre-change figure.

## 2. Contract and documentation defects corrected

- `src/dossier/agent/manifest.py` — artifact `producer` values now resolve to a real
  mode id or engine entry point: `skillgap` → `keywords` (was `jd_skill_gap`),
  `companyresearch` → `build` (was a nonexistent `research` mode), `lessons` → `user`
  (was `aar`), `loop` → `agent.loop.commit` (was `loop`); and `apply` writes
  `job-history.md` (was the phantom `application-tracker.md`, contradicting `track`,
  whose artifact is `job-history.md`).
- `tests/test_matrix.py` — two assertions added so the class cannot regress:
  `test_every_artifact_names_a_real_producer` and `test_apply_writes_the_canonical_tracker`.
  Both fail against the pre-fix manifest; both pass now.
- Generated vendor packs regenerated from source rather than hand-edited: `AGENTS.md`,
  `CLAUDE.md`, `GEMINI.md`, `docs/agent/INJECT.md`, `.cursor/rules/dossier.mdc`,
  `.claude/skills/dossier/SKILL.md`, `docs/PIPELINE.md`, `docs/CONTRACT.md`.
- `docs/agent/INJECT.md` — duplicated H1 removed (hand-written title outside the managed
  block, plus a generated title inside it).
- `src/dossier/agent/adapters.py` — the "90 KB skill document / not reliably executable"
  sentences removed from the generated preamble. `README.md` and `docs/SOURCES.md` had
  carried a conflicting `136 KB` claim for the same object.
- `README.md` — `dossier …` examples replaced with `uv run dossier … --root <folder>`,
  because `dossier` is not on `PATH` (`which dossier` → not found; only
  `.venv/Scripts/dossier.exe` and `run.cmd` exist).
- Shared skill stripped of user-specific values: `generic new-document generator`,
  `Why Northbridge?`, `KiwiSaver`, `Century Gothic`, `043D68`, the `exchange-helper`
  phrase, and an "all 34 patterns" count that enumerated 33. These were verified
  genuinely user-specific rather than merely removed on suspicion — the real base
  document reports `Century Gothic` theme fonts and accent `043D68`
  (`dossier tailor inspect`).
- `docs/SOURCES.md` — duplicated stale size claim removed.
- `PLAN.md` — the original 76-checkbox plan, 0 boxes checked and describing modules
  deleted before the consolidation, moved to `docs/history/PLAN-2026-09-15.md`; a stub
  remains at the old path pointing at the live list.

## 3. Knowledge graph rebuilt (`graphify-out/`)

*Historical:* the repo carried only the legacy Node-era `.graphify/` (5 tracked files,
dated Sep 12 — `169 nodes`, `lastAnalyzedHead: null`), which named deleted modules
(`api_bundle`, `api_export`, `api_files`, `api_jobs`) and held **zero** nodes for
`engine/` or `agent/`. It described an architecture that no longer existed.

Rebuilt with the installed Python `graphifyy` workflow:

- detect: 87 files (70 code, 17 documents), 62,928 words; `skipped_sensitive: 1` —
  `ui/src/tokens.css`, flagged sensitive and therefore excluded from the graph.
- AST pass: 826 nodes / 1772 edges. The Windows process pool failed with
  `BrokenProcessPool` and the extractor fell back to sequential; declared, not hidden.
- Semantic pass (one chunk, dispatched to a subagent as the pipeline requires):
  122 nodes / 78 edges / 3 hyperedges, validated clean — 0 duplicate ids, 0 edges
  missing `confidence_score`, every `file_type` inside the allowed six.
- Result: **987 nodes, 1773 edges, 96 communities, 0 unnamed.**
- Coverage by area: `engine` 195, `agent` 94, `api` 45, `cli` 25, other 552. All 14
  probed modules present: manifest, brief, loop, adapters, workspace, tailor, verify,
  corpus, tracker, negotiate, jd_skill_gap, render, sources, audit.
- Queryable with citations: `graphify query "where is the drafted-is-not-applied gate
  enforced"` → `manifest.py L57`, `engine/tracker.py` (`applied_dates() L148`,
  `cadence() L229`, `parse() L91`, `summary() L173`), `docs/CONTRACT.md`,
  `docs/LESSONS.md`. Highest-degree node: `create_app()` (degree 73).
- Outputs: `graph.json`, `graph.html` (840,006 bytes), `GRAPH_REPORT.md`,
  `manifest.json` (87 files), `cost.json`, `.graphify_labels.json`.

**Graph health warning, surfaced rather than hidden:** 147 dangling-endpoint edges,
4 self-loop edges, 66 collapsed undirected edges. The dangling edges are doc-derived
edges whose target ids do not match the AST naming — the AST/LLM id-mismatch class this
diagnostic exists to catch. The graph is usable and queryable; the warning is not
repaired here.

Legacy `.graphify/` is now superseded but **was not deleted** — it is pre-existing
tracked content this session did not create. Removal is a one-line `git rm -r .graphify`.

## 4. Document pipeline verified end to end

*Historical:* previously reasoned from unit fixtures only, because no base `.docx`
lived in the repo and the live workspace was deliberately left untouched.

Run against a **scratch copy** of a real base document, so the live job-search folder was
never mutated:

- `tailor replace`: `"applied": [ … ], "missed": []` (1 approved change).
- `render`: `{"renderer": "word-private-com", "pages": 2}` — a private Word instance,
  not `docx2pdf`.
- `verify all` with the approved map: **exit 0**; `source-diff` `1 removed, 1 added,
  0 unexpected` with 45 blocks unchanged; `text-layer` 2 pages / 2833 characters with
  the email and phone surviving as literal characters; `rendered-page` 2 pages,
  0 overflow blocks; `"passed": true, "not_visually_verified": false`.
- `verify all` with an **empty** map: **exit 1**, with `unexpected_removed` and
  `unexpected_added` populated — the source-diff gate genuinely refuses an unapproved
  change, rather than merely asserting a rule.
- Visual inspection of both rasterised pages: page 1 clean, no clipping or overlap, and
  the approved edit visible verbatim. Page 2 holds a single orphaned "Languages" block.
- Causal isolation: the **base** document also renders to 2 pages, so the orphaned block
  is a property of the base resume, not an effect of this change.

## 5. Explorer keyboard navigation and accessibility

Verified with real key events via Playwright against a running `dossier serve`, plus
visual inspection of the rendered screenshot. Camofox was running but exposes no
key-press endpoint, so Playwright was the correct instrument for synthesising keys.

- Keyboard reach: the tree was reached with **14 real Tab presses**; no pointer input.
- ArrowDown moved selection none → `approved.json` → `base.docx`; ArrowUp returned;
  exactly **1** element with `aria-selected="true"` at every step; the selected row was
  scrolled into view. Markup is `role="tree"` (`tabindex="0"`) with `role="treeitem"`.
- Focus ring: computed outline `2px solid`, colour derived from `--signal`, matching
  `ui/src/tokens.css:30` (`[tabindex]:focus-visible { outline: 2px solid var(--signal); }`).
  Confirmed visible in the screenshot.
- Overflow: at **1280 and 1920** the document `scrollWidth` equals `clientWidth`, and
  topbar/explorer/center/rail panels all report no content overflow.
- Contrast: DESIGN.md's actual claim — body text ≥4.5:1 on `--sheet` — **holds**:
  16.45:1 light, 13.03:1 dark, computed from the declared OKLCH tokens.

**New findings, outside the card's scope and NOT fixed** (recorded, not acted on):

| Pair | Light | Dark | Note |
|---|---|---|---|
| white on `--signal` (`.primary` button) | 3.68:1 | 2.49:1 | below 4.5:1 for normal text |
| `--stale` used as text (`.stale`) | 2.78:1 | 7.49:1 | light theme only |

`--rule` on `--sheet` measures 1.35:1 / 1.32:1, expected for a 1px decorative separator,
and is not charged as a defect.

Correction of record: an earlier automated contrast probe in this session reported zero
samples and no failures. Its own colour-conversion sanity check failed, which exposed the
probe as broken rather than the UI as clean. The figures above come from computing the
declared OKLCH tokens directly, after that probe was discarded.

## 6. Kanban board reconciled

`hermes kanban --board dossier list` before: 2 done, 2 blocked, all four created
2026-09-15. Both blocked cards had crashed twice with `pid … not alive` and given up
(`effective_limit: 2`, `trigger_outcome: crashed`) without producing any work — a
worker-death signature, not a defect in the work.

- `t_af27ba37` "No git repository initialized" — **premise false**. The repo has 4
  commits (`5d0a5b8`, `cf192a9`, `cb772f9`, `06bb06e`) and 145 tests, not the 15 the card
  body cites. Closed as superseded, evidence recorded as a comment on the card.
- `t_7b047dda` "Verify explorer keyboard nav + accessibility against DESIGN.md" — the
  verification in §5 satisfied every criterion the card named. Closed with receipts.

Result: **4 done, 0 blocked, 0 open.**

## 7. Doc audit and the single live worklist

The doc audit scanned 60 markdown files and 5 relative links, finding 2 broken links —
both in `tasks/WORKLIST.md`, both pointing at an evidence filename that did not exist.
Repaired by renaming this evidence document to the name the worklist already referenced.
Re-run after the fix: 0 broken.

`tasks/WORKLIST.md` is the only live checklist. The original implementation plan is
historical at `docs/history/PLAN-2026-09-15.md`, with a stub left at the old path.
`graft/INDEX.md` and its script source were inspected; the capability is the `scripts/`
module, not a CLI named `graft` (`graft ask` exits 127).

## 8. Open, explicitly not claimed as done

1. **Other-profile skill copies.** `coder`, `designer` and `orchestrator` each hold a
   real 88,579 B copy at `skills/office-productivity/references/resume-tailoring/SKILL.md`
   against the default profile's current file, and none of the three carries the
   `productivity/dossier-workspace` skill that only the default profile has. The 30-line
   alias files beside them are correct pointers, not stale copies. Editing another
   profile's skill tree was **not** authorised in this session, so nothing was changed
   there.
2. **`.graphify/` retirement.** Superseded by `graphify-out/`; left in place (§3).
3. **Graph integrity warning.** 147 dangling-endpoint edges remain unrepaired (§3).
4. **Historical aggregate sub-counts.** The 1,789-row `all_boards_data/all_jobs.json` and
   the 724-member resync zip were cross-checked against `docs/SOURCES.md`, but the
   1,665 / 407 / 831 / 30 / 29 / 131 sub-counts were not re-derived.
5. **Session acceptance register.** A register is being produced separately; until its
   coverage limits are read, session provenance is **not** claimed exhaustive. Title-less
   subagent sessions and non-default profiles were the known blind spots.
6. **`ai-job-search` / `career-ops` imports.** The standing `DO_NOT_INSTALL` verdict from
   session `20260907_191505_681d2d` stands; only provenance and the skill record exist,
   not imports (`docs/SOURCES.md:51-56`).
7. **Plugin surface.** No job-related Hermes plugin exists; only an uninstalled catalog
   record, `hermes-agent/plugin-catalog/job-search.yaml`, which declares no tools, hooks
   or middleware. MCP configuration was left untouched.
8. **Gateway notice.** `hermes kanban` reports that a previous `hermes update` pulled code
   without restarting running gateways. Not actioned: a restart would kill in-flight
   workers on other boards.
9. **Test scope.** `test_matrix.py` asserts the declared contract; it does not validate a
   model's generated prose. No resume or cover letter was generated for delivery in this
   session — the request was an audit, not document production.

## 9. Assessment against the 2026-09-26 request

- **Wrapper (contract + packs + CLI + API + tests): verified working.** 145 tests pass,
  the declared counts match the code, and the gates refuse when they should.
- **All prior job-search sessions folded in: partial.** `docs/LESSONS.md` carries the
  accumulated lessons (19, up from 12 at `cb772f9`) and `docs/SOURCES.md` the source
  provenance, but there is no per-session register yet, so this row stays partial (§8.5).
- **"No gaps, stubs, bugs or mistakes": not claimed.** Concrete code and documentation
  defects were found and fixed (§2); the items in §8 remain open and are labelled so.
- **Privacy check.** No private content was added; user-specific values were stripped from
  the shared skill, and identity references point back at the user's own
  `DEVELOPER-IDENTITY.md` without reproducing its contents.
