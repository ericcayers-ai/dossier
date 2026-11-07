# Capture — automated research across bot-resistant boards

A board is captured by exactly one of three layers, and the run record says which.

| Layer | Engine | Holds a session | Use it for |
|---|---|---|---|
| 1 | Public JSON feed (`feeds.py`) | no | a board with a documented read-only endpoint |
| 2 | `obscura fetch` | no | a public page, or one that needs JavaScript |
| 3 | Playwright + Chromium | **yes** | content behind the user's own sign-in |

Start at layer 1 and drop down only for a reason. The layers share the policy check, the
robots check, the per-host pace, the extractor, the sanitiser and the posting format, so a
capture looks the same in the archive whichever engine produced it.

## The commands

```text
dossier feeds list                                     # which boards, which policy
dossier feeds fetch greenhouse --board <slug> --root <ws>
dossier scrape status      --root <ws>                  # recipes, sessions, engines, due
dossier scrape recipes     --root <ws>                  # every recipe, and every broken one
dossier scrape login       --source <board> --url <sign-in page> --root <ws>
dossier scrape session-import --source <board> --cookies cookies.txt --url <page> --root <ws>
dossier scrape capture <url>                          # one page, archived as a posting
dossier scrape run --recipe <id> --root <ws>
dossier scrape run --due --root <ws>                    # every recipe whose cadence elapsed
```

Every command takes `--json`. Exit code `0` means complete, `1` means partial or refused
for an action the user must take, `2` means the request itself was wrong.

## Signing in, and what is stored

`dossier scrape login --source <board> --url <sign-in page>` opens a **visible** browser
window. You sign in yourself; Dossier types nothing and never sees a password. When you
confirm (or when `--selector` matches an element that only exists once signed in), it
saves what the browser was given: cookies and localStorage, as Playwright's
`storage_state`.

Structural guarantees, all in `scrape/session.py`:

- `save()` rebuilds the record from `cookies` and `origins` **only**. Any other key —
  password, username, token, profile dump — is dropped before anything is written, and the
  dropped names are recorded in the session metadata.
- Only `user-login` and `imported-cookies` may create a session. There is no automated
  method, so no code path can submit a credential.
- An empty jar is refused: a file that claims to be a session but holds nothing makes an
  unauthenticated capture look authenticated.
- A jar is never attached to a host its cookies do not cover (`assert_session_domain`), and
  an expired jar is reported as expired — the fix is a human action, not a retry.
- Files are written `0600` under `.dossier/scrape/sessions/`, which is git-ignored and
  never part of a handoff packet.

A cookie export from your own browser works too:
`dossier scrape session-import --source <board> --cookies cookies.txt --url <page>`. The
parser keeps `#HttpOnly_` lines, which is where the session cookie usually is.

## bot-resistant boards

Resistance is met with a real session, stealth browser configuration, honest pacing, patience
and — when the workspace asks for it — a solver. Every step is recorded, so "how did this page
arrive" always has an answer.

- **Policy first.** `scrape/guard.py` resolves the board from the URL host and asks the
  single predicate the ledger uses (`engine/sources.permitted`). A refused board never
  opens a socket. The owner opens one with a recorded write rather than by editing code:
  `dossier sources --open linkedin` (policy `user_supplied` by default, `--policy` to
  choose, `--close` to go back to the shipped default). The change lands in
  `.dossier/sources.json` through the trash.
- **robots.txt** is obeyed per path by default. A 4xx means "no rules"; a 5xx or an
  unreachable robots.txt means **disallow** (RFC 9309). `--no-robots` exists, and the run
  record shows it was asked for.
- **Pacing.** Requests to one host are at least `delay_ms` apart (default 1500 ms), serial
  by design. The wait is measured and reported, not assumed.
- **A challenge is answered by policy, and recorded.** The gate is now
  `challenge-is-explicit`: detection, the policy applied and whether it cleared all go into
  the posting's frontmatter, the run log and the `challenge` block of the result. The policy
  is `auto` unless the workspace says otherwise:

| policy | what runs |
|---|---|
| `block` | detect, stop, report (the old behaviour) |
| `await` | keep the page open and poll — many interstitials clear on their own |
| `stealth` | one retry with a stealth context |
| `stealth-await` | stealth, then poll |
| `solve` | ask the configured solver for a token and inject it |
| `auto` | plain → stealth+wait → visible window (if allowed) → solver (if configured) |

Configured in `.dossier/scrape.json`, per board or globally, or per command:

```json
{
  "challenge": "auto",
  "visible": false,
  "sources": {"linkedin": {"challenge": "stealth-await"}}
}
```

- **Stealth** is a browser configuration, not a claim: `navigator.webdriver` removed,
  `languages`/`platform`/`plugins`/`hardwareConcurrency` made consistent, `window.chrome`
  present, the notification-permission quirk patched, a real UA and `Pacific/Auckland`, and
  `bypass_csp` so an injected token survives. obscura gets `--stealth`. It does not make a
  sign-in unnecessary and it does not defeat a real check on its own.
- **A visible window** is the human-in-the-loop answer: `visible: true` in the workspace
  config (or `--headed`) lets `auto` open Chromium and wait up to 90 s while you complete a
  real check. It is off by default because a headless run must not block for 90 s on a
  challenge that will never clear.
- **The solver** is a paid third-party service (2captcha-compatible). It is used only when
  the policy is `solve` (or `auto` *and* a key is present), only when the page exposes a
  site key, and the key is read from `DOSSIER_SOLVER_KEY` in the environment — never from a
  repo or a workspace file, never printed. `DOSSIER_SOLVER_URL` overrides the endpoint.
- **A 401/403/429 is a `Blocked`**, raised immediately and never retried. Only a timeout,
  a reset or a 5xx is `Transient` and retried, with backoff.
- **What is still not here**: no CAPTCHA farm, no proxy pool, no fingerprint spoofing beyond
  the signals above, and no ability to read another person's session. `challenge-is-explicit`
  makes that a *recorded choice*, not a hidden one.

## Writing a recipe

A recipe is the site-specific part and nothing else. Copy `templates/scrapes/listing-template.json`
into `.dossier/scrapes/`, keep the same `id` to override a shipped one, then:

```json
{
  "id": "acme-listing",
  "source": "web",
  "start_url": "https://acme.example/careers",
  "auth": "public",
  "list": {"item": "article.role", "link": "h2 a", "title": "h2",
           "company": ".company", "location": ".location"},
  "detail": {"content": "main", "remove": ["[class*=cookie]"]},
  "pagination": {"mode": "next-link", "selector": "a[rel=next]", "max_pages": 3},
  "limits": {"max_items": 25, "delay_ms": 1500, "timeout_s": 30, "retries": 2},
  "cadence_hours": 24,
  "wait_until": "networkidle"
}
```

- `pagination.mode` is `none`, `query` (needs `param`) or `next-link` (needs `selector`).
- `auth: "required"` makes the session mandatory: without one the run is an `AuthRequired`
  blocker naming `dossier scrape login`.
- `cadence_hours` makes the recipe *due* after that long; `dossier scrape run --due` reads
  it, which is how "ongoing research" stays a scheduled decision instead of a daemon.
- Unknown keys, unparsable selectors and a missing slug are errors before any request.
  A breaking typo must not silently mean "one page, reported as complete".

Check the selectors against the live page before trusting a run:

```text
dossier scrape capture <listing-url> --selector 'article.role' --no-screenshot --json
```

## What a capture writes

- `job-posting-<source>-<slug>.md` — frontmatter (`source`, `url`, `captured_at`,
  `driver`, `title`, `session`, `robots`, `screenshot`, `resolved_url`) then the extracted
  text, sanitised on the way in (`posting-is-data`). The filename prefix is what
  `engine/sources.is_posting` recognises, so the rest of the pipeline treats it as a
  posting automatically.
- `.dossier/scrape/captures/<stem>.json` — provenance: driver, robots verdict, policy row,
  session source, elapsed ms, the sanitiser's findings and a sha256 of the archived
  Markdown.
- `.dossier/scrape/runs.jsonl` — one line per run, including partial ones and their reason.
- `.dossier/scrape/screenshots/<date>/<source>-<hash>.png` when a screenshot was taken.
- An overwrite goes through `.dossier/trash/` first (`never-only-copy`).

Re-running is cheap and idempotent: a URL already archived is a duplicate and is skipped;
`--refresh` re-captures it (trashing the old file).

## Reading a run

`complete: true` means every listing page loaded, every listed item was captured and
nothing was cut off. Anything else is `complete: false` with:

- `failures[]` — stage (`list`/`detail`), URL, exception type and message;
- `truncated` — `--limit` cut the list;
- `capped` — `--pages` stopped while the board still had another page;
- `reason` — one sentence a human can act on.

Report those verbatim. A count of captured rows is not coverage.

## Limits this system does not hide

- A board that never stops challenging, with no session, no visible window allowed and no
  solver key, still ends as an honest blocker naming the phases that were tried. `auto` is
  not a promise; it is a ladder with a recorded outcome.
- obscura renders long-tail CSS differently from Chromium and is not always faster. It also
  cannot dump a page AND screenshot it in one pass (`-s` suppresses the dump), so an obscura
  capture records no image; ask for `--driver playwright` when a screenshot is the receipt.
- `--headed` on a server with no interactive desktop does nothing useful; sign in and work
  through a challenge on the machine you actually use.
- The run log is local. A second machine has no capture history until it runs.
