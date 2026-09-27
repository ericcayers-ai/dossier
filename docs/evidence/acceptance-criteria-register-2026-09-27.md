# Acceptance-criteria register

> **Redaction note.** This is the register produced by the 2026-09-27 read-only audit of
> the job-search session lineage, copied into the repository so the record survives. Four
> personal specifics were replaced before landing here because a code repository is the
> wrong home for them: three references to the user's neurodivergence disclosure, and two
> to their personal LinkedIn URL. Nothing else was altered; no requirement, session id,
> date or status was changed. The verbatim original remains at
> `%LOCALAPPDATA%\Temp\dossier-audit\register.md`, and the redacted strings are listed
> in the commit that added this file.

Scope: every Hermes session whose **user turns** touch job search, resumes/CVs, job applications, ATS, cover letters, LinkedIn, job boards, interview prep, salary negotiation, or the Dossier application — read directly from the SQLite session stores in read-only mode (`file:...?mode=ro`). Compiled 2026-09-27 (NZST). Read-only audit; no store, skill, profile, cron or memory file was modified.

Evidence rule used throughout: every requirement and session id below is quoted from a `messages.content` row or a `sessions` row in the stores. Nothing is inferred or invented. Where a "requirement" was authored by an **agent** (a subagent delegation brief) rather than typed by the user, it is flagged as such and kept out of the numbered register.

---

## Sessions in scope

30 sessions. `genuine USER turns` counts `role='user'` rows after excluding system-injected wrappers (`[IMPORTANT: Background process…`, `[CONTEXT COMPACTION…`, `[ASYNC DELEGATION…`, `[Your active task list…`, `[System:…`, attachment-only echoes). A session with 1 such turn where that turn is an **agent-authored delegation brief** has **zero genuine user turns** — flagged as `subagent, 0 user turns`.

| session id | date | title | profile | genuine USER turns | topic / in-scope basis |
|---|---|---|---|---|---|
| `20260825_220817_c174c0` | 2026-08-25 | Programs folder audit / memory base | default | 3 | **Cited only as origin of the no-MCP requirement** (`no more signing into these mcps i dont need mcps`). Not a job-search session; deliberately not counted in the 30. |
| `20260826_192045_036ec9` | 2026-08-26 | Humanize resume wording | default | 1 | Attaches `OneDrive/Documents/Documents/Resume Normal Copy.docx` and invokes `/humanizer` — the first resume-text work. |
| `20260827_023310_e8919f` | 2026-08-27 | Auto-tailor resume for Waikato jobs | default | 61 | The originating resume-tailoring session: SJS scrape, base-docx rule, developer-identity doc, skill authoring, 20-industry cap, cover-letter/identity/skill requirements. |
| `20260827_132059_1a632f` | 2026-08-27 | Gather Hermes agent session context and continue all tasks | default | 6 | **Borderline inclusion.** No own user turn names a job term; the resume run is carried in via session replay (78 job-term matches, all in tool output replaying `20260827_023310_e8919f`'s prompt). |
| `20260828_044208_7f5b7b` | 2026-08-28 | expand this from a developer identity to a… | default | 1 | Identity-doc expansion explicitly sourced from `[redacted: personal LinkedIn URL]`. |
| `20260828_044425_6759f7` | 2026-08-28 | Expand developer identity to general identity markdown | default | 3 | Same prompt re-issued 3× (retries); contributes the omit-only-if-unreasonable rule. |
| `20260828_055312_c6e663` | 2026-08-28 | expand the developer identity roadmap with all… | default | 2 | Developer-identity roadmap merge; carries the colour-system block later barred from the shared skill. |
| `20260828_160029_b22eca` | 2026-08-28 | Add health-disclosure info to dev identity doc | default | 6 | Health-disclosure conditionality, "nothing personal in the skill", docx layout-preservation test, redo-all-resumes. |
| `20260828_164736_7672b9` | 2026-08-28 | Tailor resumes for NZ job search | default | 7 | SEEK/Indeed/Trade Me/SJS breadth, remote pass, Trade Me + Indeed MCP-first, LinkedIn export zip. |
| `20260828_164950_1f351f` | 2026-08-28 | (untitled) | default | **0 — subagent, 0 user turns** | Delegation brief from `20260828_164736_7672b9`: SEEK NZ + Indeed NZ + Trade Me Jobs sweep, fit-score, resume per Medium/High fit, `job-history.md`. |
| `20260828_170010_88cb41` | 2026-08-28 | (untitled) | default | **0 — subagent, 0 user turns** | Delegation brief: REMOTE/remote-friendly sweep of SEEK/Indeed/Trade Me/SJS + resumes + `job-history.md`. |
| `20260828_171746_df43c5` | 2026-08-28 | (untitled) | default | **0 — subagent, 0 user turns** | Delegation brief: LinkedIn Jobs (public unauthenticated pages) + fit-scoring + resumes. |
| `20260828_222451_9fc1c5` | 2026-08-28 | Scrape LinkedIn export and update resume tailoring skill | default | 12 | LinkedIn export scrape, one-shot automation, front-loaded intake, single source of truth, ≤20 example resumes, per-board data folders. |
| `20260829_015806_923283` | 2026-08-29 | make the skill /resume-tailoring support… | default | 3 | Cover letter paired with every resume, distinct layouts, then fix `<workspace>`. |
| `20260907_191505_681d2d` | 2026-09-07 | Import AI job search repo into Hermes | default | 2 | Import `MadsLorentzen/ai-job-search` alongside the earlier hand-built skill. |
| `20260911_203039_6edc17` | 2026-09-11 | List job search skills and plugins | default | 20 | "one skill that does absolutely everything"; consolidate ai-job-search + career-ops + 4 ATS personas; widest-scope board sweep, full resync. |
| `20260911_203509_88892f` | 2026-09-11 | (untitled) | default | **0 — subagent, 0 user turns** | Delegation brief: fetch verbatim `dreamJob` resume-diagnoser/recruiter/rewriter/hiring-manager skill files. |
| `20260911_203510_d88f3c` | 2026-09-11 | (untitled) | default | **0 — subagent, 0 user turns** | Delegation brief: extract `career-ops-hq/career-ops` workflow (ATS matching, negotiation, follow-up cadence). |
| `20260911_203510_9263fc` | 2026-09-11 | (untitled) | default | **0 — subagent, 0 user turns** | Delegation brief: fetch `MadsLorentzen/ai-job-search` agent/command/skill definitions verbatim. |
| `20260912_025629_1cd811` | 2026-09-12 | Plan resume tailoring ecosystem app | default | 5 | Dossier app origin: viewer/editor/explorer/exporter ecosystem, integrate into the skill, approval/real-event gates, resync prompt. |
| `20260912_030258_bc5383` | 2026-09-12 | (untitled) | default | **0 — subagent, 0 user turns** | Delegation brief: inventory public job-search skills/plugins/MCP/CLIs/APIs. |
| `20260912_035239_4c86f4` | 2026-09-12 | (untitled) | default | **0 — subagent, 0 user turns** | Delegation brief: Dossier backend slice (root-confined paths, token auth, trash-before-overwrite, WAL+FTS5, feed adapters, board policy hard-block). |
| `20260912_035239_9b60d9` | 2026-09-12 | (untitled) | default | **0 — subagent, 0 user turns** | Delegation brief: Dossier frontend slice (three-column shell, OKLCH tokens, viewer matrix, read-only job pane). |
| `20260915_182840_69312e` | 2026-09-15 | Reconcile triage into native Kanban | default | 17 | **Borderline inclusion.** 454 `dossier` matches, all in tool output (repo listings, `dossier README`, skill catalogs); no user turn names a job or Dossier term. Included because the triage/kanban pass enumerated the Dossier repo as a project. |
| `20260920_032034_7fa620` | 2026-09-20 | Run resume-tailoring workflow and dossier server | default | 2 | In scope on the strength of the user-role resume-tailoring skill invocation in the transcript plus a live Dossier UI build; the 2 typed turns are `continue` and the camofox/screen-clutter complaint. |
| `20260926_172133_c92eb3` | 2026-09-26 | Consolidate resume and dossier into unified job search repo | default | 2 | The consolidation mandate: resume skill + Dossier app + all prior job-search sessions → one LLM-injectable wrapper, consolidated into Dossier. |
| `20260927_194443_f9e0f7` | 2026-09-27 | Consolidate job search automation into new repo | default | 2 | Re-verification pass over all prior sessions, the Dossier repo and the resume skill; subagents-encouraged. |
| `20260927_194709_0c783e` | 2026-09-27 | (untitled) | default | **0 — subagent, 0 user turns** | Delegation brief: read-only retrieval of prior job-search sessions, original acceptance criteria vs claimed completion. |
| `20260927_194709_fef3c7` | 2026-09-27 | (untitled) | default | **0 — subagent, 0 user turns** | Delegation brief: read-only reconciliation of job-related skills/plugins against Dossier contract. |
| `20260927_194709_25f2db` | 2026-09-27 | (untitled) | default | **0 — subagent, 0 user turns** | Delegation brief: read-only Dossier repo audit, CLI/test receipts, acceptance matrix. |
| `20260927_210200_e3ea51` | 2026-09-27 | (untitled) | default | **0 — subagent, 0 user turns** | Delegation brief: produce this register. |

Per-profile in-scope counts: **default 30, coder 0, designer 0, orchestrator 0.** Total genuine user turns across in-scope sessions: **166**.

---

## Acceptance criteria

Status vocabulary: `stated` (stands as last stated), `later corrected` (a later user turn changed it), `superseded` (a later user turn replaced it outright). Rows 1–59 are user-stated. Rows are numbered in first-appearance order.

| # | Requirement as the user stated it | First session | Date | Status |
|---|---|---|---|---|
| 1 | "keep my exact style of writing the resume" (attaching `Resume Normal Copy.docx` and invoking the humanizer) | `20260826_192045_036ec9` | 2026-08-26 | stated |
| 2 | "look for all jobs for me … and then automatically tailor my resume to each one" | `20260827_023310_e8919f` | 2026-08-27 | stated |
| 3 | "follow strict rules to keep my writing sound exactly like me without the ai-isms and with my tone and style of writing" | `20260827_023310_e8919f` | 2026-08-27 | stated |
| 4 | "make sure the resume follows the quota for the resume tailor skill too" | `20260827_023310_e8919f` | 2026-08-27 | stated |
| 5 | "focus on using the normal copy as the base reference to work from" | `20260827_023310_e8919f` | 2026-08-27 | stated |
| 6 | "these generalized json files will be limited to a max of 20 industries or work types etc" | `20260827_023310_e8919f` | 2026-08-27 | stated |
| 7 | "github projects consist of all the subfolders i have under programs/ do a subagent deep dive to get and attain a general memory of what kind of software developer i would be. then use that as the context" | `20260827_023310_e8919f` | 2026-08-27 | stated |
| 8 | "create a generalized md file that can be used as a summary of who i am as a software developer using ai. this file can be used whenever on behalf of the resumegenerator" | `20260827_023310_e8919f` | 2026-08-27 | stated |
| 9 | "make sure this developer identity includes all my projects, and takes into account that my learning i do throughout my course at waikato teaches me the modular basics to systems and development" | `20260827_023310_e8919f` | 2026-08-27 | stated |
| 10 | "make sure you have reviewed these resumes using all the skills available online for resume tailoring and creating please. then also make sure you have considered my identity document too" | `20260827_023310_e8919f` | 2026-08-27 | stated |
| 11 | "check through absolutely all resume documents in my documents folder, no limit in scope" | `20260827_023310_e8919f` | 2026-08-27 | stated |
| 12 | "treat absolutely everything you find as aditional context, and the normal copy be the tailoring base" | `20260827_023310_e8919f` | 2026-08-27 | stated |
| 13 | "make sure the workflow of this entire conversation is properly made into that skill" | `20260827_023310_e8919f` | 2026-08-27 | stated |
| 14 | "export this skill for me so i can have the file" | `20260827_023310_e8919f` | 2026-08-27 | **superseded** |
| 15 | "implement everything from humanizer into this skill as well. so this skill does everything" | `20260827_023310_e8919f` | 2026-08-27 | stated |
| 16 | "make sure that the skill requires a user to hand in an example resume as a docx for it to use to register the tone and style of writing of the user" | `20260827_023310_e8919f` | 2026-08-27 | stated |
| 17 | "will generate those resumes copying the exact same layout as the original resume docx same font and design and everything" | `20260827_023310_e8919f` | 2026-08-27 | stated |
| 18 | "also visually check that the text all fits on one page and things arent hanging out the edge or obscured etc. text look clean etc" | `20260827_023310_e8919f` | 2026-08-27 | stated |
| 19 | "for job search websites if they have an mcp or something to sign in and automatically work with their job search system then prioritize that please" | `20260827_023310_e8919f` | 2026-08-27 | **later corrected** |
| 20 | "also scan the user's entire linkedin profile and then contacts and everything" | `20260827_023310_e8919f` | 2026-08-27 | stated |
| 21 | "make it so with the call of that skill everything will be automated and done instantly" | `20260827_023310_e8919f` | 2026-08-27 | stated |
| 22 | "have it also ask whether or not you want to paste a memory md (give the user a valid prompt to give to any llm that keeps memory about the user to provide everything)" | `20260827_023310_e8919f` | 2026-08-27 | stated |
| 23 | "expand this from a developer identity to a general identity md file. look at all of this: [redacted: personal LinkedIn URL]" | `20260828_044208_7f5b7b` | 2026-08-28 | stated |
| 24 | "if the thing is really irrelevant or really unsure just ommit, otherwise be very comprehensive and only ommit if unreasonable" | `20260828_044425_6759f7` | 2026-08-28 | stated |
| 25 | "make sure that developer identity document has the fact [redacted: personal health detail] etc" | `20260828_160029_b22eca` | 2026-08-28 | **later corrected** |
| 26 | "make it very conditional whether or not to mention it. depends on the job and the user if they want to. also within that resume skill make it so any health conditions (keep it very generalized) can be added but only considered conditionally" | `20260828_160029_b22eca` | 2026-08-28 | stated |
| 27 | "make sure this skill doesnt have anything personal to me in it. and do a live test on the entire skill now" | `20260828_160029_b22eca` | 2026-08-28 | stated |
| 28 | "the base to tailor from is called normal copy, and my developer identity (make sure that is included in the skill but generalized too)" | `20260828_160029_b22eca` | 2026-08-28 | stated |
| 29 | "make sure when these resumes are generated as well that all it does is replace the text in the docx but the styles format and layout arent changed and it is verified there is no text overflow etc" | `20260828_160029_b22eca` | 2026-08-28 | stated |
| 30 | "find all my generated resumes and redo them so they match everything the skill offers" | `20260828_160029_b22eca` | 2026-08-28 | stated |
| 31 | "continue using the latest updated resume tailoring skill with all my <workspace> and <home>\OneDrive\Documents\Documents files please. generate more resumes perhaps" | `20260828_164736_7672b9` | 2026-08-28 | stated |
| 32 | "i want to look through seek nz, indeed, trademe jobs, literally all available main job searches" | `20260828_164736_7672b9` | 2026-08-28 | stated |
| 33 | "go through all job search sites including sjs indeed and trademe and seek etc for remote jobs please" | `20260828_164736_7672b9` | 2026-08-28 | stated |
| 34 | "ensure that i use the `https://github.com/giussepe198/trademe-mcp` as well as any other available mcp as first priority like indeed mcp protocol etc" (verbatim, minus the `@url:` markup around the link) | `20260828_164736_7672b9` | 2026-08-28 | **later corrected** |
| 35 | "if there are any gaps or things you have learnt, (keep generalized) then update the skill please" | `20260828_164736_7672b9` | 2026-08-28 | stated |
| 36 | "Do all the linkedin scraping now please … make sure the skill is working so it can do everything one shot absolutely automatically with no errors" | `20260828_222451_9fc1c5` | 2026-08-28 | stated |
| 37 | "whenever the skill is invoked it will firstly immediately request for everything it needs" | `20260828_222451_9fc1c5` | 2026-08-28 | stated |
| 38 | "assess my identity docs and without puttiing anything personal, keeping it generalized … and make sure the skill asks for all these forms of stuff from the start" | `20260828_222451_9fc1c5` | 2026-08-28 | stated |
| 39 | "remove it so theres a single source of truth. also make sure everything in the folder is rebuilt given all the context of the linkedin stuff and all the jobs etc" | `20260828_222451_9fc1c5` | 2026-08-28 | stated |
| 40 | "yes please do this fresh job search now making sure that nothing is redundant etc maybe up to 20 example resumes" | `20260828_222451_9fc1c5` | 2026-08-28 | stated |
| 41 | "make sure that in this skill job search would be done either broad industries, remote, local, based of linkedin data etc" | `20260828_222451_9fc1c5` | 2026-08-28 | stated |
| 42 | "in the skill it would be advised to manually (as human) audit the output resumes etc" | `20260828_222451_9fc1c5` | 2026-08-28 | stated |
| 43 | "make sure that the skill makes it so sjs_data with all its files are gathered, and using the exact same layout a folder with all data gathered from all job search sites" | `20260828_222451_9fc1c5` | 2026-08-28 | stated |
| 44 | "now in my case make sure all job boards data is gathered and filled please" | `20260828_222451_9fc1c5` | 2026-08-28 | stated |
| 45 | "make the skill /resume-tailoring support generating a cover letter alongside each resume that is generated please. the cover letter should be using the similar style as the resume but both layouts are distinct" | `20260829_015806_923283` | 2026-08-29 | stated |
| 46 | "i want you to purposely go through this entire repo and import it into hermes agent alongside everything from the repo and everything i had in my skill i worked on with you from earlier" (`MadsLorentzen/ai-job-search`) | `20260907_191505_681d2d` | 2026-09-07 | stated |
| 47 | "my final outcome i would like is to call one skill that pretty much lets you do absolutely everything for me" | `20260911_203039_6edc17` | 2026-09-11 | stated |
| 48 | "consolidate within these skills, the following items in entirety: [MadsLorentzen/ai-job-search] [career-ops-hq/career-ops] … and anything else you might find online. dont be limited in scope" (bracketed = `@url:` links in the original; the same turn enumerates THE DIAGNOSER, THE RECRUITER, THE REWRITER, THE HIRING MANAGER) | `20260911_203039_6edc17` | 2026-09-11 | stated |
| 49 | "audit everything and make sure this resume tailoring skill actually has absolutely everything please. like if i call the skill in a chat everything should be available" | `20260911_203039_6edc17` | 2026-09-11 | stated |
| 50 | "run the job search on absolutely everything using camofox browser and using everything from that skill. all jobs that could be applicable to me. run the entire workflow" | `20260911_203039_6edc17` | 2026-09-11 | stated |
| 51 | "as many nz job boards as possible and as many listings please that ccould work for me, even retail or something" | `20260911_203039_6edc17` | 2026-09-11 | stated |
| 52 | "make sure as you do this that your scope is everything. the widest scope possible, the all in one" | `20260911_203039_6edc17` | 2026-09-11 | stated |
| 53 | "run afull and entire resync on all information to make sure everything from everything is upto doate" | `20260911_203039_6edc17` | 2026-09-11 | stated |
| 54 | "consider the entire skill and plugins making sure you dont miss a thing" | `20260911_203039_6edc17` | 2026-09-11 | stated |
| 55 | "Make me a rough app that serves as a general viewer and interactor and file editer and viewer and explorer and exporter etc like a full comprehensive easy to use not cluttered ecosystem" | `20260912_025629_1cd811` | 2026-09-12 | **superseded** (purpose redefined by #58) |
| 56 | "Make use of all skill hubs and make sure to utilize as many skills and plugins as you may need in designing and planning" | `20260912_025629_1cd811` | 2026-09-12 | stated |
| 57 | "once all of that is completed then tell me and then we will move on to implementing the entire thing, no questions asked" / "implement all phases now go" | `20260912_025629_1cd811` | 2026-09-12 | stated |
| 58 | "also as an extra requirement make sure this app and how it works is integrated into the skill itself" | `20260912_025629_1cd811` | 2026-09-12 | stated |
| — | *the four guard-rail bullets the user listed under #58, quoted verbatim:* "Application submission requires your review and explicit approval." · "Follow-ups require a confirmed application date." · "Interview, offer, negotiation, and outcome workflows require a real event." · "Some boards were blocked, stale, paused, or unavailable; those limits are documented and need to be requested manually." | `20260912_025629_1cd811` | 2026-09-12 | stated |
| — | "Have the app support some prompt or skill to give back to the ai that the skill knows about for updating and well resyncing all records and all data gathered ingeneral." | `20260912_025629_1cd811` | 2026-09-12 | stated |
| 59 | "Consolidate everything from the resume tailoring skill and the dossier app and all my previous hermes agent sessions relating to job searches and this repo into a new repo which automates and handles all of it as a kind of wrapper that you hermes agent or any other llm can inject itself into to do everything" | `20260926_172133_c92eb3` | 2026-09-26 | stated |
| 60 | "dossier is what id like everything to be cohesively consolidated into" | `20260926_172133_c92eb3` | 2026-09-26 | stated |
| 61 | "Do it all yourself, use skills whenever you need to. be ingenious go" | `20260926_172133_c92eb3` | 2026-09-26 | stated |
| 62 | "make sure there are no gaps stubs bugs or mistakes go" | `20260926_172133_c92eb3` | 2026-09-26 | stated |
| 63 | "look at all previous hermes agent sessions and browse through dossier repo and resume tailoring skill and any skills or plugins job related and make sure everything has been met" | `20260927_194443_f9e0f7` | 2026-09-27 | stated |
| 64 | "subagents when beneficial please" | `20260927_194443_f9e0f7` | 2026-09-27 | stated |
| 65 | "ahem that just cluttered up my whole screen, also im not sure if you were actually getting much from camofox" (i.e. browser automation must not spam the desktop and must demonstrably produce data) | `20260920_032034_7fa620` | 2026-09-20 | stated |
| 66 | "no more signing into these mcps i dont need mcps" — recorded outside the job-search line but the standing rule the shared skill must respect | `20260825_220817_c174c0` | 2026-08-25 | stated (see contradiction C1) |

**Register total: 66 user-stated acceptance criteria** (rows 1–66; the two un-numbered rows are verbatim sub-clauses of #58 and its resync companion, counted inside the #58 group rather than separately).

### Agent-authored constraints — NOT user-stated, excluded from the 66

These appear only in **subagent delegation briefs** (the user never typed them). They are recorded because they were treated as binding requirements by the builds, and because two of them contradict user statements:

- `20260828_164950_1f351f` / `20260828_170010_88cb41` / `20260828_171746_df43c5`: "fit-score every listing", "generate new tailored resumes (.docx) for every Medium/High-fit job that doesn't already have one", "Also produce/update a job-history.md log".
- `20260912_035239_4c86f4` (Dossier backend): "root-confined paths, token auth, conditional writes with mtime+sha256 conflict detection, trash-before-overwrite/delete, SQLite WAL+FTS5", "public-feed adapters for Greenhouse/Lever/Ashby/Himalayas/Remotive/Arbeitnow **with policy hard-block for prohibited LinkedIn/Indeed/Glassdoor/SEEK/Workday**".
- `20260912_035239_9b60d9` (Dossier frontend): "no hardcoded fake job/document data", "Optional job pane reading backend `/api/jobs`, `/api/jobs/list`, `/api/jobs/due` **read-only**", "cool-neutral OKLCH light/dark tokens exactly from DESIGN.md".
- `20260911_203510_d88f3c`: extract `negotiation-roi.mjs`, `verify-ats.mjs`, `followup-cadence.mjs` logic for reimplementation.

---

## Corrections and contradictions

**C1 — MCP is required, then not allowed (three-way).**
`20260827_023310_e8919f` (2026-08-27): "for job search websites if they have an mcp … then prioritize that please". `20260828_164736_7672b9` (2026-08-28): "ensure that i use the trademe-mcp as well as any other available mcp as first priority like indeed mcp protocol etc". Against that, `20260825_220817_c174c0` (2026-08-25) records the user's own rule "no more signing into these mcps i dont need mcps", which the assistant logged as "your preference — **no MCPs** (I removed all 19; won't re-add unless you ask)". The later Dossier backend brief `20260912_035239_4c86f4` compounds it by hard-blocking "LinkedIn/Indeed/Glassdoor/SEEK/Workday". Three positions, never reconciled in any user turn.

**C2 — Health disclosure: required, then made conditional.**
`20260828_160029_b22eca` first: "make sure that developer identity document has the fact [redacted: personal health detail] etc"; then in the same session: "make it very conditional whether or not to mention it. depends on the job and the user if they want to. also within that resume skill make it so any health conditions (keep it very generalized) can be added but only considered conditionally". The first statement is dead; #26 governs.

**C3 — Export/copy the skill, then delete the copy.**
`20260827_023310_e8919f` (2026-08-27): "export this skill for me so i can have the file"; `20260828_222451_9fc1c5` (2026-08-28): "remove it so theres a single source of truth". Row 14 is superseded by row 39.

**C4 — What Dossier is.**
`20260912_025629_1cd811` (2026-09-12) framed the app as a generic document workspace — "a general viewer and interactor and file editer and viewer and explorer and exporter … a full comprehensive easy to use not cluttered ecosystem" — and the two build briefs that followed (`20260912_035239_4c86f4`, `20260912_035239_9b60d9`) kept it job-agnostic (read-only job pane, "no hardcoded fake job/document data"). `20260926_172133_c92eb3` (2026-09-26) then said: "Consolidate everything from the resume tailoring skill and the dossier app … dossier is what id like everything to be cohesively consolidated into" — Dossier is now the job-search wrapper itself. Row 55 is superseded by rows 59–60.

**C5 — Resume layout must be frozen; the cover letter's must not be.**
`20260828_160029_b22eca`: for resumes "all it does is replace the text in the docx but the styles format and layout arent changed"; `20260829_015806_923283`: the cover letter uses "the similar style as the resume but both layouts are distinct". Not a reversal (different artifact) but the two rules are stated with opposite polarity and must not be applied to the same document type.

**C6 — Widest scope vs "not cluttered".**
`20260911_203039_6edc17` (2026-09-11): "your scope is everything. the widest scope possible, the all in one" and "as many nz job boards as possible … even retail or something". `20260912_025629_1cd811` (2026-09-12), one day later, specs the UI as "not cluttered". Both are live; the register records the tension rather than a winner.

**C7 — Board policy: user wants the boards, the design blocks them.**
Rows 32/33/40–41/51 ask for SEEK NZ, Indeed, Trade Me, SJS, LinkedIn and "as many nz job boards as possible". The agent-authored Dossier backend brief `20260912_035239_4c86f4` instead mandates a "policy hard-block for prohibited LinkedIn/Indeed/Glassdoor/SEEK/Workday" with public feeds only (Greenhouse/Lever/Ashby/Himalayas/Remotive/Arbeitnow). No user turn ever revoked the user's own board list, and no user turn ever approved the hard-block.

**C8 — "drafted vs applied" is not a verbatim user requirement.**
The prior audit's spine states "drafted vs applied must be distinct and only user confirmation moves a row to applied". The closest user statements are `20260912_025629_1cd811`: "Application submission requires your review and explicit approval" and "Follow-ups require a confirmed application date" / "Interview, offer, negotiation, and outcome workflows require a real event". The stricter framing ("A CV or cover letter drafted alone is not yet an application") appears in imported repo material (`MadsLorentzen/ai-job-search`, quoted in `20260907_191505_681d2d` and in orchestrator store `20260921_215256_b90d71`), not in a user turn. Treat the user-level rule as "explicit approval + a real event", and the drafted/applied split as imported design policy.

**C9 — "user-specific colour/font/accent values must not be baked into the shared skill" is a derived rule, not a quote.**
The user's actual words are `20260828_160029_b22eca` "make sure this skill doesnt have anything personal to me in it" and `20260828_222451_9fc1c5` "without puttiing anything personal, keeping it generalized". The concrete hex values (`Primary: #ff964f`, `Accent: #ffe3ba`, `Background: #141210`) live in the identity docs (`20260827_023310_e8919f`, `20260828_055312_c6e663`); the user never named colour or font as the thing to strip.

---

## Coverage limits

### Searches actually run

1. `SELECT name,type FROM sqlite_master` on all four stores, then `PRAGMA table_info(sessions)` / `PRAGMA table_info(messages)` to discover the real columns (`sessions`: id, title, started_at, profile_name, parent_session_id, message_count, …; `messages`: id, session_id, role, content, display_kind, timestamp, active, compacted, …).
2. Read-mode comparison on the default store: `mode=ro` gave 1,237 sessions / 210,784 messages; `mode=ro&immutable=1` gave 1,237 / 210,769. Both were used to check that `-wal` content was not being lost. **`mode=ro` (WAL-aware) was used for all findings**, since `immutable=1` omits 15 committed messages. Read-only is enforced by SQLite in both modes; nothing was written.
3. Broad keyword sweep over **all `role='user'` rows in all four stores**: `resume|résumé|cvs?|ats|cover letter|linkedin|job board|job ?search|job appl|interview prep|salary negotiation|dossier|seek\.com|indeed|greenhouse|workday|lever|job description|tailor` → 156 candidate sessions (default 136, coder 12, orchestrator 8, designer 0).
4. Tightened sweep requiring a strong term (`resume[- ]tailor|résumé|cover letter|job application|job search|ats|linkedin|dossier|interview|cv\.docx|job description|job board|salary negotiat|recruiter|seek\.co|greenhouse|workday|applied to|application tracker|career|employment|position at|job ad`) → default 86 candidate sessions; **displayed the matched snippets for every one of them** and classified each by hand.
5. Session-**title** sweep for the same vocabulary across all four stores (`resume|résumé|cv|job|career|dossier|ats|linkedin|cover letter|hiring|recruit|apply|application`) to catch sessions whose user turns are terse ("continue") but whose title names the topic.
6. Per-session genuine-user-turn extraction with system-wrapper filtering (`[IMPORTANT:`, `[CONTEXT COMPACTION`, `[ASYNC DELEGATION`, `[Your active task list`, `[System:`, `<html`, attachment echoes) for all 30 in-scope sessions and 8 borderline/excluded sessions.
7. Assistant/tool-side corroboration (`regex` count + snippet) for borderline sessions `20260827_132059_1a632f` (78 hits), `20260915_182840_69312e` (606 hits, 454 of them `dossier`), `20260920_032034_7fa620` (369), `20260921_174108_162967` (8), `20260913_150750_deaa42` (16), `20260922_202745_1cb001` (9), `20260826_190705_c916e0` (0).
8. Spine-verification grep for `non-?mcp|no mcp|auto-?submit|never submit|draft`, and a focused read of `20260825_220817_c174c0` user+assistant rows, to test the prior audit's spine claims against real strings — which is how C1, C8 and C9 were found.
9. Every one of the 20 session ids supplied by the prior audit was re-queried by primary key: **all 20 exist** in `default/state.db` with the stated topics and parent links. None was missing.

### Stores read, and stores not read

| store | path | readable | size at read time |
|---|---|---|---|
| default | `<home>\AppData\Local\hermes\state.db` | yes | ≈1,239 sessions / ≈210,800 messages (live store; the count moved by 1–2 during the audit) |
| coder | `…\profiles\coder\state.db` | yes | 204 sessions / 19,427 messages |
| designer | `…\profiles\designer\state.db` | yes | 66 sessions / 1,542 messages |
| orchestrator | `…\profiles\orchestrator\state.db` | yes | 221 sessions / 14,413 messages |

**No session store was missing or unreadable.** `<home>\AppData\Local\hermes\profiles\.deleted\` exists and was **not** read (out of scope). `projects.db` and `verification_evidence.db` exist in each profile directory and were **not** read — they are not message stores. Read-only means uncommitted `-wal` frames are included but nothing was checkpointed, vacuumed or altered.

### Explicitly NOT classified as in scope (with the reason)

- `20260921_174108_162967` — 8 job-term matches, all inside skill-catalog dumps in tool output.
- `20260913_150750_deaa42` — matches are `session_search` output replaying `20260911_203039_6edc17`.
- `20260922_202745_1cb001` — "dossier" in the generic sense: "Produce a read-only dossier on the candidate external skill xr-interface-architect". Unrelated to the Dossier app.
- `20260826_190705_c916e0` — single `seek.co` match came from a GitHub skill list; zero job-search content.
- `20260916_204530_eabbb8`, `20260916_211314_1e0f2e`, `20260919_190004_4c8f4e`, `20260917_020316_638de6`, `20260914_014506_4c38d6`, `20260926_172549_ad59ae`, `20260922_025038_138977` — matches only `applied to` / `seek.co` / `dossier` inside compaction blocks, async-delegation notices or unrelated repo text.
- **12 `cron_d68f8f98e5cd_*` "Morning briefing" sessions** (Sep 01–27) load the `office-productivity` hub whose description names resume/CV/ATS/LinkedIn, so they show up in any keyword sweep. They are automated cron runs: **zero genuine user turns**. Left out of the 30.
- **coder:** 0 in scope. Its 12 candidates are task-titled engineering sessions where `resume`/`tailor` appear incidentally.
- **designer:** 0 in scope. Title-sweep false positives only: `D2.2 Apply the D1.3 failure-state copy spec…` (`20260920_211911_8aac69`, `20260920_212014_623b05`, `20260921_002821_d83378`).
- **orchestrator:** 0 in scope. False positive: `Fix quota guard repair breaker (C1/C3) — hard-cap 3, resume-after-restore only` (`20260921_215256_b90d71`) — "resume" is a verb, though that session's tool output does quote imported ai-job-search material (`/Users/ericc/ai-job-search-final-small-segments/098.txt`).

### Sessions included but flagged borderline (so they are visible, not silently added)

- `20260827_132059_1a632f` — no user turn names a job term; included because the job-search run is replayed and continued inside it.
- `20260915_182840_69312e` — no user turn names a job or Dossier term; included because its triage/kanban pass enumerates the Dossier repo as a project. **A reader who applies the strict keyword-in-user-turn rule would drop both of these, making the count 28.**
- `20260920_032034_7fa620` — the two typed turns are `continue` and a complaint; scope rests on the user-role resume-tailoring skill invocation in the transcript.

### What could still be missed

- **Sessions deleted before this audit.** Only the live DBs were read; the single default store holds ≈1,239 sessions against the ≈1,231 the prior audit cited, so anything already pruned is unrecoverable here.
- **Non-message stores.** Hermes `memories/`, `cron/` job definitions, kanban boards and skill files were deliberately not read (out of scope), so a requirement recorded only as a memory entry or cron prompt would not appear. The `no MCPs` memory entry is known only because the assistant quoted it in `20260825_220817_c174c0`.
- **The Dossier repo and skill files were not read**, per the task's read-only boundary — so whether the built artifacts actually satisfy rows 1–66 is out of this register's remit (statuses here record what the *user said*, not whether it shipped).
- **Compaction loss.** User turns older than a compaction boundary survive only as summaries; several borderline sessions are exactly that shape, and any requirement stated pre-compaction inside them is not recoverable as a verbatim string.
- **Attachment-only turns.** A user turn that was nothing but a file or a URL with no surrounding text was filtered as an echo; one of those could carry an implied requirement.
- **The 13 subagent sessions** hold agent-authored briefs only. Their content is quoted where it constrains the build, but it is not user testimony and is excluded from the 66.
