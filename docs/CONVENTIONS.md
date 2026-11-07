# dossier — conventions

## Ask the engine

Never re-derive in prose what a command already answers. `dossier doctor` before
promising a capability, `dossier sources` before naming a board, `dossier agent status`
before guessing the next step. If a gate fails, report the failure; do not route around it.

## Code

- Python 3.13, standard library first. A new dependency needs a sentence in
  `pyproject.toml` saying what it replaces or why nothing smaller works.
- Modules in `src/dossier/engine/` own one rule and export it; a second copy of a rule is
  the failure `docs/LESSONS.md` §17 records. Before writing a helper, grep for the rule.
- One canonical predicate per gate. `engine/sources.permitted` is the only answer to
  "may this board be fetched"; `scrape/guard.resolve_source` is the only answer to
  "which board is this URL".
- Comments explain a decision and its cost, not the syntax. A comment that restates the
  next line is deleted.
- Errors carry the fix: `AuthRequired` names the `dossier scrape login` command,
  `RecipeError` names the offending key and the accepted set.
- Never swallow an exception into an empty result. `Blocked`, `ChallengeDetected` and
  `AuthRequired` propagate; only `Transient` is retried.

## CLI and API

- Subcommands group by noun with an action (`scrape status`, `feeds fetch`, `track
  cadence`). Every leaf accepts `--root` and `--json`.
- Exit codes are the contract: `0` complete, `1` partial or refused for a user action,
  `2` the request itself was wrong. Gates exit non-zero so a batch can assert on the code.
- A new route is added to `tests/test_matrix.py`'s sweep automatically; a route that
  answers 500 on a bare workspace fails the suite.
- A GET route never performs a slow operation. Capture is a POST, one page per request.

## Data and files

- Every overwrite goes through `safety.trash_then_write*`. Direct `write_text` is for
  `0600` session state under `.dossier/` only, never for a user document.
- Posting text is sanitised at ingestion (`engine.sources.sanitize`), whether it came from
  a file, a feed or a browser.
- Frontmatter a machine writes is frontmatter a machine reads: `runner._frontmatter_value`
  parses exactly the keys `_posting_markdown` writes.
- Generated documents are never templated from scratch; the base `.docx` is the layout.

## Tests

- A bug is reproduced by a failing test first. `tests/fixtures/scrape_site.py` exists so a
  capture test drives a real origin instead of a mock that cannot disagree with it.
- A test that needs a browser skips with the install command in the reason, never passes
  vacuously.
- Assert on the *invariant*, not a count: `len(manifest.GATES) == 14` broke when a gate
  was added for a real reason; "no original gate was removed" is the invariant.
- Fixture data is built per test in `tmp_path`; nothing test-authored is written into the
  repo.

## The contract

- `manifest.py` is edited once and the packs are regenerated: `dossier agent adapters`,
  then `dossier agent adapters --check`. A hand-edited managed block is a drift bug.
- A mode's `engine` names code, its `command` names a command line. Declare both.
- A gate without a `_by` that resolves is decorative; `test_matrix` fails it.

## Docs

- `STATE.md` and `HANDOFF.md` are the only files an agent re-reads after a compaction.
  Keep each under 120 lines and current at every checkpoint.
- A receipt records the command, the exit code and the counted result — not a claim.
