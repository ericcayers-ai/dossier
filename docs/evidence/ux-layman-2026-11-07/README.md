# The layman pass — 2026-11-07

The owner's words: *"how do i even use this thing, fix it so it just works for the layman please.
focus on the goals of the actual app and hone them in on the frontend side please."*

The app's goal, from `docs/PROJECT.md`: capture a posting → diagnose the resume → extract
requirements → tailor a document that clones the user's own layout → verify → apply → track →
follow up. A layman's version of that is three sentences long: **"I found a job. Show me whether I
fit, give me the tailored document, and tell me what to do next."**

Before this pass the app could do all of it and answered none of it on screen.

## The instrument

One script, `capture.py`, was run twice — once against the committed UI (`--label before`), once
against this pass (`--label after`) — over two workspaces rebuilt from scratch on each run: a
populated job-search folder (126 files, 4 postings, a base resume, a `.docx` template) and an empty
folder, which is what a first-time user opens. Four screens at 1440 and 390, plus the empty folder.
Every number below is read from the rendered page in Chromium (`before-metrics.json`,
`after-metrics.json`); the screenshots are the same run, kept as the record.

```
.venv\Scripts\python.exe docs\evidence\ux-layman-2026-11-07\capture.py --label before|after
```

## What the audit found

**Destinations.** Five top-level areas and twelve panes — seventeen places, three of which the
first-run user can even see ("Folder" plus the area strip). The vocabulary is the engine's:
`Capture`, `Identity`, `Build`, `Verify`, `Audit`, `Trash`, `Sync`, `Loop`, `Opportunity`, `Panel`,
`Housekeeping`, and in the chrome `Rail`, `Explorer`, `Bundle rail`, `recipe`, `challenge`,
`artefacts`, `blockers`, `sessions`. Two of the chrome controls were labelled **"Files"** and
**"Rail"** and sat directly beside the pane **"Folder"**.

**The first screen was a dead end.** Both first-run screenshots show the same thing: an `<h1>`
reading *"Put the folder on the light table."*, the engine's card *"Waiting on you: Setup"*, and one
button, **"Open Folder"** — which navigates to the pane you are already on. The page that explains
what to do was never reachable from the page that says what to do. On an empty folder the screens
were 30 words and one dead button; nothing said "put your resume in this folder" in a form a
stranger could act on.

**The three things a layman needs were three different panes, none of them the landing page.**
Fit is on `Jobs`/`Identity`, the tailored document is on `Build` (which asked for a workspace-relative
path and a `.docx` with `{{placeholders}}` the user had never been told to make), and "what now" was
on a card in the folder pane.

**Smaller, measured defects** in the "before" shots: the explorer header read `1 files` for one
file; the landing stat row painted a fourth, empty grey tile behind three counts; the header at
390 px cut the area strip mid-word.

## The map, in plain words

The e2e suite (`tests/test_e2e_ui.py`) *is* the contract: it clicks `.area-btn` by the labels
`Files`, `Search`, `Papers`, `Housekeeping`, `Agent`, clicks all twelve `.pane-btn` labels, asserts
`#/papers/verify` deep-links, and requires `.area-btn[aria-current]` to read exactly `Papers`. So
renaming the workbench's areas or panes would have rewritten the gate that proves the app works —
an owner decision, not a front-end tidy-up. **Nothing was renamed and nothing was removed. Six
areas now, one of them new:**

| area | in plain words | panes |
|---|---|---|
| **Start** (new, first) | what to do next, and how far along you are | Start here |
| Files | your folder | Folder |
| Search | find and save job ads | Capture · Jobs · Identity |
| Papers | make and check a document | Build · Verify |
| Housekeeping | housekeeping (audit, trash, sync) | Audit · Trash · Sync |
| Agent | the engine's own contract | Loop · Opportunity · Panel |

Inside each pane the heading is unchanged (the tests assert it) and one sentence now says what the
pane is for:

| pane | the sentence now under the heading |
|---|---|
| Start here | Dossier turns one job ad into one tailored document you can send, then keeps track of what you sent. |
| Your folder | Everything Dossier reads is here. Pick a file on the left to open it… |
| Capture | Save one job ad from a link, or a whole board. The copy stays in this folder. |
| Jobs | Every job Dossier has saved, plus what you have applied to and what is due a follow-up. |
| Identity | What you are looking for. Dossier judges how well a job fits against these answers, not against a guess. |
| Build | Fill your own resume with one job's details. Dossier copies your file and replaces the placeholders, so the layout never changes. |
| Verify | Check a document before you send it: layout kept, text readable, pages rendered. |
| Audit | A health check of the folder: what is missing, what is out of date, and which job boards Dossier may read. |
| Sync | Hand this session to another AI in one paste. Nothing is sent anywhere unless you paste it. |
| Loop | The engine's own contract: which jobs Dossier finishes itself and which need a model. |

Chrome vocabulary that was renamed (no test depends on it): `Rail` → **Related files**, `Explorer`
→ **Your files**, footer `⌘\ explorer` / `⌘/ rail` → `⌘\ file list` / `⌘/ related files`, the rail's
empty state `Select a file.` → *"Open a document to see the files that belong with it."*

## What changed

- **`ui/src/panes/StartPane.tsx`** (new, 112 lines) — the front door and the app's default
  destination (`#/start/start`). It reads two routes that already existed (`/api/workspace`, the
  folder resolver; `/api/identity`) and states the loop as **four numbered steps** with a state word
  each (`Done` / `Next` / `Not yet`), the engine's own counts (`126 files`, `1 job ad saved`), and a
  button per step. Above them sits the engine's answer to "what now" — the same `.welcome-next` card
  as before, one filled primary button, one reason. Below them, **This folder**: the path Dossier is
  reading, "nothing leaves this machine", and a disclosure with the exact command to open a
  different folder (`run.cmd "C:\path\to\your job search"`), because the folder is chosen at launch
  and there is no route to change it at runtime.
- **A blocking notice on first run.** When the folder holds no document the engine can clone, the
  pane says so once, in one sentence, including the naming rule the engine actually applies
  (`is_base_document`: the file name must contain "resume" or "cv"). That rule was previously only
  discoverable by reading `tailor.py`.
- **`ui/src/App.tsx`** — the `Start` area and pane, `start` as the default and as the base-URL
  address; the "No document open" strip is no longer rendered on Start with no tabs open; the
  Files empty state is now *"Your folder"* with the folder's real `.docx` list (or a notice that
  there is none) instead of a metaphor; every pane/area/hash in `AREAS` is otherwise byte-identical.
- **Purpose lines** on the ten panes above (`p.pane-purpose`), one sentence each, no subtext added
  under any nav bar.
- **`ui/src/panes/CapturePane.tsx`** — the one page form is now URL + one button; `Source`,
  `Challenge`, the saved-session switch and the engine inventory moved into a single disclosure
  ("Advanced: which page reader, and saved sessions"). Visible fields to save one job ad: **6 → 3**.
- **`ui/src/panes/VerifyPane.tsx`** — the three path fields are datalists over the folder's real
  files, so a document is picked from a list instead of typed from memory.
- **`ui/src/panes/NextStep.tsx`** — kept, and moved onto Start; its count row was removed because
  the four steps now state those numbers once.
- **`ui/src/panes/Explorer.tsx`** — `1 files` → `count()` from `lib/copy.ts` (`1 file`).
- **`ui/src/tokens.css`**, **`ui/src/agent.css`** — `.start-pane` / `.steps` / `.step` (rows, not
  cards), `.pane-purpose`, and the 390 px header now fits: the search field keeps its accessible
  name and gives its width to the six areas.

Nothing in `src/dossier/` changed. No API route, engine call, gate or test was touched.

## Before and after, same instrument, same fixtures

```
screen                   areas    words in main   fields   primaries   areas clipped @390
01 start                 5 → 6     34 → 140       0 → 0    1 → 1       6 → 6
02 capture               5 → 6     57 →  66       6 → 3    1 → 1       6 → 6
03 build                 5 → 6     29 →  50       2 → 2    1 → 1       6 → 6
04 jobs                  5 → 6     44 →  61       1 → 1    0 → 0       6 → 6
05 first run (empty)     5 → 6     30 → 149       0 → 0    1 → 1       6 → 6
console errors           0         0
```

Read honestly: **words went up, and that is the trade this pass made.** The landing page now spends
140 words on four steps and one blocking fact where it spent 34 on a metaphor and a button that
went nowhere; each working pane carries one extra sentence saying what it is for. What went *down*
is what a person has to work out or type: fields to fill before a job ad is saved (**6 → 3**), panes
whose purpose is unexplained (10 → 0), and chrome controls named after internal structures
(`Rail`, `Explorer` → 0). Where a screen asks for nothing, it still asks for nothing (Build: 2
fields, most of a primary button).

The `areas clipped @390` column is a pre-existing 6 px overflow inside the horizontally scrollable
area strip; this pass measured it before changing the header and kept it from getting worse.

## Contrast on the new labels

Computed in-page (WCAG 2.1, resolved through every translucent layer) in the same run, at 1440 and
390, in both themes' default light:

| label | ratio | AA body (4.5) |
|---|---|---|
| `.area-btn` (inactive) | 5.46 | pass |
| `.area-btn.active` | 14.97 | pass |
| `.pane-btn.active` | 16.16 | pass |
| `main h1` | 16.16 | pass |
| `.pane-purpose` (new) | 5.46 | pass |
| `.brand` | 16.16 | pass |
| `.search-trigger` | 5.46 | pass |

No new colour token was introduced; the purpose line uses the existing `--ink-quiet`.

## What a newcomer does in the first 60 seconds

1. `run.cmd "C:\path\to\my job search"` — the app opens on **Start here**, not a file browser.
2. The first thing under the heading is either the engine's next unit with one button, or, on an
   empty folder, the blocking fact: *"No resume to build from yet… its name needs to contain
   'resume' or 'cv'."*
3. **The four steps** say how far along the search is: folder, what you want, job ads, a tailored
   document — each with a state word and a button that goes to the pane that does it.
4. Paste a job link on `Capture` and press **Scrape page** (one field, one button; everything else
   is behind *Advanced*).
5. `Build` fills the folder's real `.docx` list; `Verify` picks documents from datalists instead of
   asking for typed paths.

## Not done, with the reason

- **Area and pane names are still the engine's** (`Capture`, `Identity`, `Papers`, `Housekeeping`,
  `Agent`, `Loop`, `Opportunity`, `Panel`). They are pinned by `tests/test_e2e_ui.py`; renaming them
  means rewriting the gate, which is the owner's call. The map above is the proposal if that call is
  ever made.
- **No folder picker.** The root is fixed at launch (`AppConfig.create(root)`), and adding a route
  to re-point it is an API change, out of scope for a front-end pass. Start states the command
  instead.
- **`Start` adds a sixth area** rather than removing any. Capability-preserving was the constraint;
  a genuine reduction (e.g. folding `Housekeeping` into one "Maintenance" pane, or moving
  `Loop`/`Opportunity`/`Panel` behind one "Advanced" area) is possible but changes the tested
  addresses.
- The 6 px area-strip overflow at 390 px predates this pass and is unchanged.
