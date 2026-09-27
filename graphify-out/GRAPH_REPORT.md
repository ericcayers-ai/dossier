# Graph Report - dossier  (2026-09-27)

## Corpus Check
- 87 files · ~71,439 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 7 file(s) not represented in the graph (top: .mdc 2, (none) 2, .cmd 1)

## Summary
- 999 nodes · 1786 edges · 101 communities (47 shown, 54 thin omitted)
- Extraction: 96% EXTRACTED · 4% INFERRED · 0% AMBIGUOUS · INFERRED: 79 edges (avg confidence: 0.87)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `52d046a4`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- tailor.py
- loop.py
- corpus.py
- cli.py
- test_matrix.py
- test_engine.py
- manifest.py
- test_agent.py
- render.py
- Generated Per-Harness Prompt Packs
- create_app
- convert.py
- parse
- feeds.py
- graft-hooks.cjs
- safety.py
- App.tsx
- package.json
- test_cli.py
- negotiate.py
- bundles.py
- compilerOptions
- api.ts
- dependencies
- compilerOptions
- app.py
- actions.py
- _make_resume
- extOf
- pathlib
- Job-Search Domain Pane
- Modes Table: Kind, Reads, Writes, Gates, Next
- main.tsx
- The Model Socket: Markdown Packet plus JSON Handback
- rendered-inspection Gate
- graft
- devDependencies
- scripts
- Never the Only Copy
- main.tsx Module Entry
- Lesson 3: Do Not Drive Word PDF Export Through docx2pdf
- Lesson 7: drafted Is Not applied
- Lesson 17: Two Copies of One Rule Drift
- tsconfig.json
- Gates Enforced in Code, Never Softened
- Actions Are Declared, Not Hard-Coded
- Bundle Rail
- Say What You Can't Do (fidelity classes)
- The Folder Is the Database
- Read Is Free, Write Is Explicit
- negotiation-verbatim Gate
- partial-is-not-exhaustive Gate
- SQLite WAL + FTS5 Index
- Lesson 15: An Unbounded Stream Is a Trap for Every Other Client
- test_propagate_fit_never_guesses_across_a_shared_listing_url
- test_scan_posting_stops_at_a_heading_written_as_prose
- test_record_outcome_writes_and_trashes_a_backup
- test_the_primary_font_is_resolved_not_guessed
- test_the_date_expectation_is_a_resume_shape_not_a_letter_shape
- test_margins_come_from_the_documents_own_geometry
- test_dedupe_collapses_one_posting_captured_with_two_employer_labels
- Modes the Engine Completes Without a Model
- Modes That Need Model Judgement
- graft ask --source Crux
- graft callers: Exact Edges and Blast Radius
- Querying a Node Beats Reading Source
- graft grep: Exhaustive Find
- graft map: Orientation
- graft MCP Server Surface
- Pick the One Tool That Fits
- Per-Turn Token-Savings Tally
- The Six graft Tools
- graft skeleton: A File's API
- Per-Folder bundles.json Rules
- OKLCH Cool-Neutral Token Set
- The Interface Is a Light Table
- base-document Gate
- layout-clone Gate
- no-auto-submit Gate
- posting-is-data Gate
- token-never-leaks Gate
- Consolidation Deliverable Marked PARTIAL
- 35.8 GB Disk Budget
- 127.0.0.1 Bind with Per-Launch Bearer Token
- Root Confinement
- Lesson 1: Job Records Must Carry Unique Ids
- Lesson 2: A Fit Score Must Not Cross a Shared Listing URL
- Lesson 5: A Coverage Snapshot Must Be Resolved, Not Hard-Coded
- Lesson 11: A Module Function Named all Shadows the Builtin
- Lesson 16: AppConfig.create Describes a Layout, It Does Not Create It
- Lesson 19: The Section a Model Is Told to Run First Should Not Be Below the Fold
- Artifacts Table: Path, Role, Producer, Consumers
- Each Mode Names Its Own Next Step
- Three Consolidated Origins
- dossier
- Acceptance Register for Historical Sessions
- brief.py
- workspace.py
- jd_skill_gap.py
- pytest
- ledger

## God Nodes (most connected - your core abstractions)
1. `create_app()` - 73 edges
2. `_make_workspace()` - 24 edges
3. `resolve()` - 23 edges
4. `build_parser()` - 20 edges
5. `parse()` - 17 edges
6. `resolve_in_root()` - 16 edges
7. `compilerOptions` - 16 edges
8. `Workspace` - 15 edges
9. `_emit()` - 15 edges
10. `AppConfig` - 15 edges

## Surprising Connections (you probably didn't know these)
- `Prohibited and Manual-Only Sources` --semantically_similar_to--> `Job-Search Domain Pane`  [INFERRED] [semantically similar]
  docs/SOURCES.md → DESIGN.md
- `Injected Contract Pipeline Order` --semantically_similar_to--> `Canonical Fifteen-Stage Order`  [INFERRED] [semantically similar]
  .claude/skills/dossier/SKILL.md → docs/PIPELINE.md
- `The Model Socket: Markdown Packet plus JSON Handback` --semantically_similar_to--> `dossier agent brief: Self-Contained Packet`  [INFERRED] [semantically similar]
  docs/agent/INJECT.md → README.md
- `Never the Only Copy` --semantically_similar_to--> `never-only-copy Gate`  [INFERRED] [semantically similar]
  DESIGN.md → docs/CONTRACT.md
- `Never the Only Copy` --semantically_similar_to--> `No Hard Delete`  [INFERRED] [semantically similar]
  DESIGN.md → docs/history/PLAN-2026-09-15.md

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Fourteen Hard-Stop Gates** — docs_contract_no_fabrication_gate, docs_contract_base_document_gate, docs_contract_layout_clone_gate, docs_contract_rendered_inspection_gate, docs_contract_text_layer_gate, docs_contract_posting_is_data_gate, docs_contract_no_auto_submit_gate, docs_contract_drafted_is_not_applied_gate, docs_contract_confirmed_date_gate, docs_contract_negotiation_verbatim_gate, docs_contract_source_policy_gate, docs_contract_partial_is_not_exhaustive_gate, docs_contract_never_only_copy_gate, docs_contract_token_never_leaks_gate [EXTRACTED 1.00]
- **Prompt Packs Generated from One Manifest** — readme_adapter_packs, agents_dossier_contract_block, claude_dossier_contract_block, gemini_dossier_contract_block, claude_skills_dossier_skill_pack, docs_agent_inject_vendor_packs, docs_contract_contract_document [EXTRACTED 1.00]
- **The Tailoring Pipeline Flow** — docs_pipeline_stage_order, docs_pipeline_artifacts_table, docs_pipeline_next_step_declared, docs_contract_modes_table, docs_contract_contract_document [INFERRED 0.85]

## Communities (101 total, 54 thin omitted)

### Community 0 - "tailor.py"
Cohesion: 0.07
Nodes (57): copy, _verify(), _has_pymupdf(), apply_replacements(), BaseDocumentMissing, _bottom_rule(), CloneResult, cover_letter() (+49 more)

### Community 1 - "loop.py"
Cohesion: 0.22
Nodes (19): _candidate(), commit(), _load(), next_unit(), _postings_without_analysis(), Path, The cross-session work loop. A model injected into this workspace has no memory…, The single next unit of work, with the reason it was chosen. (+11 more)

### Community 2 - "corpus.py"
Cohesion: 0.07
Nodes (42): importlib, platform, sqlite3, aggregate_hash(), board_folders(), build_facets(), build_index(), combine() (+34 more)

### Community 3 - "cli.py"
Cohesion: 0.12
Nodes (37): argparse, ArgumentParser, socket, _agent(), _audit(), build_parser(), _corpus(), _doctor() (+29 more)

### Community 4 - "test_matrix.py"
Cohesion: 0.06
Nodes (36): docx, fastapi_testclient, shlex, test_api_contract_and_audit(), test_api_path_escape(), agent_brief(), argv_for(), build_workspace() (+28 more)

### Community 6 - "manifest.py"
Cohesion: 0.09
Nodes (38): _contract_doc(), _core(), _cursor_frontmatter(), packs(), _pipeline_doc(), Path, Emit the agent contract as vendor prompt packs. Every harness reads the same…, Write `body` between managed markers, preserving everything outside them.… (+30 more)

### Community 7 - "test_agent.py"
Cohesion: 0.08
Nodes (30): parametrize, _make_workspace(), Path, Tests for the injectable agent layer., A duplicated heading silently hides a whole section behind a scrollbar — the…, `Run these first` has to be reachable on the first screenful, or the section a…, The keywords mode writes `<posting-stem>.skillgap.json`. Accepting only a…, test_adapters_write_every_pack_and_verify() (+22 more)

### Community 8 - "render.py"
Cohesion: 0.18
Nodes (21): available_renderers(), export_pdf(), _has_pywin32(), pdf_pages(), pdf_to_png(), Path, RuntimeError, _pymupdf() (+13 more)

### Community 9 - "Generated Per-Harness Prompt Packs"
Cohesion: 0.05
Nodes (45): Dossier Contract Block (AGENTS.md), Graft Block (AGENTS.md), Dossier Contract Block (CLAUDE.md), Ask the Engine, Do Not Re-Derive It, Dossier Skill Pack (generated contract), graft Repo Context Graph, Dossier Design Brief, Injecting Any Model into Dossier (+37 more)

### Community 10 - "create_app"
Cohesion: 0.08
Nodes (6): create_app(), do_search(), events(), tree(), tree_node(), search()

### Community 11 - "convert.py"
Cohesion: 0.11
Nodes (27): csv, io, shutil, available_renderers(), convert(), _csv_to_json(), _json_to_csv(), Path (+19 more)

### Community 12 - "parse"
Cohesion: 0.15
Nodes (23): date, Pattern, jobs_due(), append_followup(), applied_dates(), cadence(), _compute(), _directives() (+15 more)

### Community 13 - "feeds.py"
Cohesion: 0.12
Nodes (16): adapter(), Arbeitnow, Ashby, FeedAdapter, FeedPolicyError, Greenhouse, Himalayas, Job (+8 more)

### Community 14 - "graft-hooks.cjs"
Cohesion: 0.12
Nodes (24): best(), entry(), { execFileSync }, fromPkg(), fs, globalRoot(), newer(), path (+16 more)

### Community 15 - "safety.py"
Cohesion: 0.18
Nodes (21): os, export(), get_file(), put_file(), raw(), render(), verify_summary(), atomic_write() (+13 more)

### Community 16 - "App.tsx"
Cohesion: 0.09
Nodes (4): Action, AuditPane(), Tab, Audit

### Community 17 - "package.json"
Cohesion: 0.10
Nodes (19): ag-grid-community, ag-grid-react, @codemirror/commands, @codemirror/lang-json, @codemirror/lang-markdown, @codemirror/lang-python, @codemirror/language, @codemirror/state (+11 more)

### Community 18 - "test_cli.py"
Cohesion: 0.14
Nodes (15): Path, CLI surface tests. The CLI is the seam an injected model actually calls, so its…, test_agent_adapters_writes_then_verifies(), test_agent_brief_markdown_contains_the_run_these_first_section(), test_agent_commit_accepts_a_real_handback(), test_agent_commit_rejects_a_bad_handback(), test_agent_next_reports_the_blocking_unit(), test_corpus_build_reports_duplicate_ids_as_a_failure() (+7 more)

### Community 19 - "negotiate.py"
Cohesion: 0.16
Nodes (21): analyze(), analyze_paths(), _any_variant_in_text(), build_draft_paragraph(), compute_calculation(), extract_quantified_claims(), format_number(), _number_variants() (+13 more)

### Community 20 - "bundles.py"
Cohesion: 0.19
Nodes (19): hashlib, bundle(), Bundle, classify_role(), load_rules(), Member, Path, resolve_bundle() (+11 more)

### Community 21 - "compilerOptions"
Cohesion: 0.11
Nodes (17): compilerOptions, allowJs, allowSyntheticDefaultImports, esModuleInterop, isolatedModules, jsx, lib, module (+9 more)

### Community 22 - "api.ts"
Cohesion: 0.14
Nodes (16): agentApi, AgentContract, AgentGate, AgentMode, AgentStatus, AgentUnit, api, authHeaders() (+8 more)

### Community 23 - "dependencies"
Cohesion: 0.13
Nodes (15): dependencies, ag-grid-community, ag-grid-react, @codemirror/commands, @codemirror/lang-json, @codemirror/lang-markdown, @codemirror/lang-python, @codemirror/language (+7 more)

### Community 24 - "compilerOptions"
Cohesion: 0.14
Nodes (13): compilerOptions, allowImportingTsExtensions, lib, module, moduleDetection, moduleResolution, noEmit, skipLibCheck (+5 more)

### Community 25 - "app.py"
Cohesion: 0.16
Nodes (14): asyncio, FastAPI, fastapi_responses, fastapi_staticfiles, mimetypes, ai_handoff(), audit(), auth() (+6 more)

### Community 26 - "actions.py"
Cohesion: 0.33
Nodes (7): Action, ActionRun, load_actions(), run_action(), subprocess, sys, test_action_uses_argv_and_requires_confirmation()

### Community 27 - "_make_resume"
Cohesion: 0.20
Nodes (10): _make_resume(), Path, test_apply_replacements_only_touches_the_named_paragraph(), test_apply_replacements_refuses_to_write_over_the_base(), test_cover_letter_is_a_distinct_one_paragraph_flow(), test_import_base_copies_without_touching_the_original(), test_layout_spec_reads_the_real_document(), test_replacements_report_a_miss_instead_of_silently_doing_nothing() (+2 more)

### Community 28 - "extOf"
Cohesion: 0.24
Nodes (10): App(), CodeEditor(), Explorer(), extOf(), flatten(), icon(), isBinary(), nameOf() (+2 more)

### Community 29 - "pathlib"
Cohesion: 0.12
Nodes (18): collections, datetime, json, pathlib, re, secrets, Read-only reconciliation of a workspace. Every fact here comes from an engine…, Deterministic engines. Each module here does one class of mechanical work and… (+10 more)

### Community 30 - "Job-Search Domain Pane"
Cohesion: 0.33
Nodes (6): Job-Search Domain Pane, source-policy Gate, Proving-Ground Folder (read-mostly), No MCP Integration, Prior Job-Search Workspace (<workspace>), Prohibited and Manual-Only Sources

### Community 31 - "Modes Table: Kind, Reads, Writes, Gates, Next"
Cohesion: 0.40
Nodes (5): Injected Contract Pipeline Order, Modes Table: Kind, Reads, Writes, Gates, Next, Lesson 13: An Engine Function Name Is Not a Command Line, Lesson 18: A Prerequisite Named for Something Nothing Resolves Is a Permanent Lie, Canonical Fifteen-Stage Order

### Community 32 - "main.tsx"
Cohesion: 0.40
Nodes (4): react, react-dom, ui_src_agent, ui_src_tokens

### Community 33 - "The Model Socket: Markdown Packet plus JSON Handback"
Cohesion: 0.50
Nodes (4): The Model Socket: Markdown Packet plus JSON Handback, Why a Brief Instead of the Full Reference, dossier agent brief: Self-Contained Packet, Engine Owns Mechanics, Model Owns Judgement

### Community 34 - "rendered-inspection Gate"
Cohesion: 0.50
Nodes (4): rendered-inspection Gate, text-layer Gate, Lesson 8: A Text Diff Is Not a Layout Check, Verify the Real-Folder DOCX to PDF to Image to Text-Layer Pipeline

### Community 35 - "graft"
Cohesion: 0.50
Nodes (3): npx, graft, @nanonets/graft

### Community 36 - "devDependencies"
Cohesion: 0.50
Nodes (4): devDependencies, @types/react, @types/react-dom, typescript

### Community 37 - "scripts"
Cohesion: 0.50
Nodes (4): scripts, build, dev, preview

### Community 38 - "Never the Only Copy"
Cohesion: 0.67
Nodes (3): Never the Only Copy, never-only-copy Gate, No Hard Delete

### Community 39 - "main.tsx Module Entry"
Cohesion: 0.67
Nodes (3): Three-Column Fixed-Role Shell, main.tsx Module Entry, Vite Root Mount div

### Community 40 - "Lesson 3: Do Not Drive Word PDF Export Through docx2pdf"
Cohesion: 0.67
Nodes (3): Measured Environment Constraints, Word Is the Only Renderer, Lesson 3: Do Not Drive Word PDF Export Through docx2pdf

### Community 41 - "Lesson 7: drafted Is Not applied"
Cohesion: 0.67
Nodes (3): confirmed-date Gate, drafted-is-not-applied Gate, Lesson 7: drafted Is Not applied

### Community 42 - "Lesson 17: Two Copies of One Rule Drift"
Cohesion: 0.67
Nodes (3): Lesson 17: Two Copies of One Rule Drift, Helper Scripts Reimplemented, Not Imported, Removed Duplicate Surfaces

### Community 96 - "brief.py"
Cohesion: 0.14
Nodes (17): dataclasses, Brief, build(), _deterministic_commands(), _harness_note(), _inputs(), _prerequisites(), Path (+9 more)

### Community 97 - "workspace.py"
Cohesion: 0.24
Nodes (18): ArtifactHit, _corpus_state(), _coverage_state(), _external_base_candidates(), _hit(), _is_base_document(), _load_json(), _newest() (+10 more)

### Community 98 - "jd_skill_gap.py"
Cohesion: 0.20
Nodes (15): aggregate(), analyze(), classify(), _extract_tokens(), _line_is_non_req_header(), _line_is_req_header(), _line_is_section_boundary(), Path (+7 more)

### Community 99 - "pytest"
Cohesion: 0.25
Nodes (6): pytest, actions(), run_action(), start_watcher(), config(), fixture

### Community 100 - "ledger"
Cohesion: 0.50
Nodes (5): coverage(), ledger(), Path, Latest coverage snapshot with a freshness verdict, newest file wins., Per-source policy plus whatever the newest capture actually recorded.

## Ambiguous Edges - Review These
- `Evidence: 2026-09-27 Audit / Reconciliation` → `Dossier Worklist`  [AMBIGUOUS]
  tasks/WORKLIST.md · relation: references

## Knowledge Gaps
- **127 isolated node(s):** `path`, `fs`, `{ pathToFileURL }`, `{ execFileSync }`, `path` (+122 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 459 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **54 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **What is the exact relationship between `Evidence: 2026-09-27 Audit / Reconciliation` and `Dossier Worklist`?**
  _Edge tagged AMBIGUOUS (relation: references) - confidence is low._
- **Why does `create_app()` connect `create_app` to `pytest`, `cli.py`, `test_matrix.py`, `manifest.py`, `convert.py`, `parse`, `safety.py`, `bundles.py`, `app.py`, `actions.py`?**
  _High betweenness centrality (0.060) - this node is a cross-community bridge._
- **Why does `convert()` connect `convert.py` to `app.py`, `create_app`, `safety.py`?**
  _High betweenness centrality (0.008) - this node is a cross-community bridge._
- **Why does `layout_spec()` connect `tailor.py` to `cli.py`?**
  _High betweenness centrality (0.007) - this node is a cross-community bridge._
- **Are the 2 inferred relationships involving `create_app()` (e.g. with `AppConfig` and `PathEscape`) actually correct?**
  _`create_app()` has 2 INFERRED edges - model-reasoned connections that need verification._
- **What connects `path`, `fs`, `{ pathToFileURL }` to the rest of the system?**
  _127 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `tailor.py` be split into smaller, more focused modules?**
  _Cohesion score 0.06502732240437159 - nodes in this community are weakly interconnected._