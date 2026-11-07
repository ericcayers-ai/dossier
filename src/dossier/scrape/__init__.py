"""Automated capture for boards a public JSON feed cannot serve.

Three layers, cheapest first. A capture always starts at the top and only drops
to the next layer for a reason the run record names.

1. **The public feeds** (`dossier.feeds`) — a documented read-only JSON endpoint.
   No browser, no session, no ambiguity about what is being fetched.
2. **obscura** (a Rust/V8 headless engine, invoked as a subprocess) — the page an
   endpoint does not publish, or a page that needs JavaScript. No Python browser
   dependency, and it obeys robots.txt by default.
3. **Playwright + Chromium** — the only layer that can hold a real signed-in
   session. The user signs in themselves in a visible window; Dossier stores the
   resulting cookies and localStorage, never a password, and reuses them headless.

What this package deliberately does not do: solve a challenge, defeat a
fingerprint check, rotate proxies to evade a block, or read another person's
session. A challenge is detected, recorded and reported as a blocker — the
`partial-is-not-exhaustive` gate stays true because a blocked capture is never
counted as coverage.

Gates this package enforces:

* `source-policy` — the board is resolved from the URL host, not trusted from a
  recipe, and refused before a socket opens (`guard.resolve_source`).
* `session-is-the-users` — a session exists only from the user's own sign-in or
  the user's own cookie export, is refused for a host its cookies do not belong
  to, and can never contain a password (`session.SessionStore`).
* `posting-is-data` — captured text is sanitised at ingestion, exactly like an
  archived posting file (`engine.sources.sanitize`).
* `never-only-copy` — an overwrite goes through `.dossier/trash/`
  (`safety.trash_then_write_text`).
* `partial-is-not-exhaustive` — a run reports `complete=False` whenever a page,
  an item or a requested page count did not arrive (`runner.RunRecord.complete`).
"""

from .errors import (AuthRequired, Blocked, ChallengeDetected, DriverUnavailable,
                     RecipeError, ScrapeError, Transient)
from .recipes import Recipe, discover, load, validate
from .runner import capture_url, run_recipe, status
from .session import SessionStore, import_netscape_cookies

__all__ = [
    "AuthRequired", "Blocked", "ChallengeDetected", "DriverUnavailable",
    "RecipeError", "ScrapeError", "Transient",
    "Recipe", "discover", "load", "validate",
    "capture_url", "run_recipe", "status",
    "SessionStore", "import_netscape_cookies",
]
