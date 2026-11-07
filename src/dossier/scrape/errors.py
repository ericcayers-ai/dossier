"""Failure vocabulary for the capture path.

Each class answers a different question for the caller, which is why they are
distinct types rather than one `RuntimeError` with a message:

* `RecipeError` — the workflow is wrong. Fix the file; retrying cannot help.
* `AuthRequired` — the page needs a session the user has not created yet.
* `ChallengeDetected` — the site is asking for a human. Stop; nothing here is
  allowed to answer a challenge.
* `Blocked` — the site refused the request (403/429/robots). Pacing or a session
  may help; evasion is not an option this package offers.
* `Transient` — a timeout, a reset, a 5xx. Retry with backoff.
* `DriverUnavailable` — the engine for this layer is not installed here.

A run that collapses every failure into one exception type cannot report *which*
part of a board is missing, and that is exactly what `partial-is-not-exhaustive`
requires it to do.
"""

from __future__ import annotations


class ScrapeError(RuntimeError):
    """Base class. `RuntimeError` so the CLI turns it into a clean exit, not a traceback."""


class RecipeError(ScrapeError, ValueError):
    """A recipe file that cannot be run as written.

    Also a `ValueError` because the CLI and the API already map that to exit 2 /
    400, which is the right status for "your workflow is malformed".
    """


class AuthRequired(ScrapeError):
    """The capture needs a session that does not exist (or expired)."""


class ChallengeDetected(ScrapeError):
    """The site served a human-verification interstitial. Never solved, only reported."""


class Blocked(ScrapeError):
    """The site refused this request: 401/403/429, or a robots.txt disallow."""


class Transient(ScrapeError):
    """A failure worth retrying: timeout, connection reset, 5xx, empty document."""


class DriverUnavailable(ScrapeError):
    """The browser engine this capture needs is not installed on this machine."""
