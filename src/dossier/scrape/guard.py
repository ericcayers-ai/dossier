"""The capture guard: which board, may it be fetched, and how fast.

Two questions are answered here, in this order, before a socket opens.

**Which board is this?** A recipe declares a `source`, but a declaration is not
evidence: a recipe for `linkedin.com` could declare `source: "web"` and walk
around the board's policy. So the source is *resolved from the URL host* and a
recipe may only name a source whose policy is at least as permissive — the host
wins whenever the two disagree.

**May it be fetched at all?** `engine.sources.assert_allowed` is the one
predicate the ledger and every fetch already share. A host that resolves to a
`prohibited` or `manual_only` board is refused here, before `httpx` is imported
for a robots check and before any browser starts.

Then the slower questions: robots.txt (obeyed by default, RFC 9309 semantics —
a 5xx or an unreachable robots.txt is a *disallow*, not a shrug) and a per-host
delay. Both are recorded in the run record so a receipt can show what was
respected rather than asserting it.
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

from ..engine.sources import (POLICIES, SourceRefused, assert_allowed,
                              effective_policies, permitted)

#: The policy name a URL the user supplied is filed under when no known board
#: matches its host. It is fetchable because the user named the page; it is not a
#: licence to crawl a board, because the host map below is consulted first.
USER_SUPPLIED = "web"

#: Host suffix -> board name in `engine.sources.POLICIES`. Longest suffix wins, so
#: `nz.linkedin.com` and `linkedin.com` resolve to the same board, and
#: `api.greenhouse.io` does not accidentally match an unrelated host.
HOST_SOURCES: dict[str, str] = {
    "linkedin.com": "linkedin",
    "indeed.com": "indeed",
    "indeed.co.nz": "indeed",
    "glassdoor.com": "glassdoor",
    "glassdoor.co.nz": "glassdoor",
    "seek.co.nz": "seek",
    "seek.com.au": "seek",
    "myworkdayjobs.com": "workday",
    "workday.com": "workday",
    "greenhouse.io": "greenhouse",
    "lever.co": "lever",
    "ashbyhq.com": "ashby",
    "himalayas.app": "himalayas",
    "remotive.com": "remotive",
    "arbeitnow.com": "arbeitnow",
    "remoteok.com": "remoteok",
    "remoteok.io": "remoteok",
    "jobicy.com": "jobicy",
    "weworkremotely.com": "weworkremotely",
}

#: Domains that are the user's own machine. A capture of localhost is a developer
#: fixture, never a board, and obscura refuses private addresses unless told not to.
PRIVATE_HOSTS = ("localhost", "127.0.0.1", "::1", "0.0.0.0")

ROBOTS_CACHE = ".dossier/scrape/robots.json"
ROBOTS_TTL_SECONDS = 24 * 60 * 60
ROBOTS_USER_AGENT = "Dossier/0.1 (+local-first job-search workspace; user-initiated capture)"


def host_of(url: str) -> str:
    return (urlparse(url).hostname or "").casefold()


def is_private(url: str) -> bool:
    host = host_of(url)
    return host in PRIVATE_HOSTS or host.endswith(".local") or host.rsplit(".", 1)[-1].isdigit()


def board_for(url: str) -> str | None:
    """The policy-table board this URL belongs to, if any."""
    host = host_of(url)
    if not host:
        return None
    matches = [suffix for suffix in HOST_SOURCES if host == suffix or host.endswith("." + suffix)]
    if not matches:
        return None
    return HOST_SOURCES[max(matches, key=len)]


def resolve_source(url: str, declared: str = "", root: Path | str | None = None) -> str:
    """The source a capture is filed under, resolved from the URL, not the recipe.

    A declared source is honoured only when it names the same board the host
    resolves to, or when it names a board the workspace has explicitly opened and
    the host belongs to it. When the host resolves to nothing known, the declared
    source is kept if the workspace's own table has an entry for it (so a user can
    add a board to `.dossier/sources.json`); otherwise the URL is filed under
    `web`, the user-supplied policy.
    """
    declared = (declared or "").strip().casefold()
    board = board_for(url)
    if board:
        # The host decides. A recipe cannot relabel a board it does not own. `web`
        # is not a relabel: it is the absence of a claim, so it defers to the host.
        if declared and declared not in (board, USER_SUPPLIED):
            raise SourceRefused(
                f"{url} is a {board} page, but the recipe declares source "
                f"{declared!r}. A capture is filed under the board its host "
                "resolves to; fix the recipe instead of relabelling the URL.")
        return board
    table = effective_policies(root)
    if declared and (declared in table or declared == USER_SUPPLIED):
        return declared
    return USER_SUPPLIED


def assert_capture_allowed(url: str, declared: str = "", root: Path | str | None = None) -> str:
    """Refuse a capture before any network call. Returns the resolved source."""
    source = resolve_source(url, declared, root)
    assert_allowed(source, root)
    return source


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _robots_cache(root: Path) -> dict:
    try:
        data = json.loads((root / ROBOTS_CACHE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _write_robots_cache(root: Path, cache: dict) -> None:
    path = root / ROBOTS_CACHE
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(cache, indent=2), encoding="utf-8")
    except OSError:
        # The cache is an optimisation. A read-only workspace must still capture.
        pass


def robots_allowed(url: str, root: Path | str, *, user_agent: str = ROBOTS_USER_AGENT,
                   http=None, timeout: float = 10.0, cache: bool = True) -> dict:
    """Whether robots.txt permits this exact URL, with the reason and its source.

    Obeyed by default and answered per *path*, not per host: a board can allow its
    listing pages and disallow every profile page, and a capture that ignored the
    difference would be exactly the behaviour this gate exists to prevent.

    RFC 9309 semantics for an unreachable file: a 4xx means "no rules", a 5xx or
    a timeout means "assume disallow". Guessing the permissive interpretation from
    a broken robots.txt is how an agent ends up crawling a site that said no.
    """
    root = Path(root)
    parsed = urlparse(url)
    origin = f"{parsed.scheme}://{parsed.netloc}"
    robots_url = origin + "/robots.txt"
    cached = _robots_cache(root).get(origin) if cache else None
    stale = True
    if cached:
        try:
            age = (_now() - datetime.fromisoformat(cached["fetched_at"])).total_seconds()
            stale = age > ROBOTS_TTL_SECONDS
        except (KeyError, TypeError, ValueError):
            stale = True

    if cached and not stale:
        body, status = cached.get("body"), cached.get("status")
    else:
        if http is None:
            import httpx
            http = httpx.Client(follow_redirects=True, timeout=timeout,
                                headers={"User-Agent": user_agent})
        try:
            response = http.get(robots_url)
            status, body = response.status_code, response.text
        except Exception as exc:  # noqa: BLE001 - any transport failure is "unreachable"
            return {"allowed": False, "origin": origin, "robots_url": robots_url,
                    "reason": f"robots.txt could not be read ({type(exc).__name__}: {exc}); "
                              "an unreachable robots.txt is treated as disallow",
                    "fetched": False}
        if cache:
            table = _robots_cache(root)
            table[origin] = {"fetched_at": _now().isoformat(), "status": status,
                             "body": body[:200_000]}
            _write_robots_cache(root, table)

    if status in (401, 403):
        return {"allowed": False, "origin": origin, "robots_url": robots_url,
                "status": status, "reason": f"robots.txt answered {status}"}
    if status >= 500:
        return {"allowed": False, "origin": origin, "robots_url": robots_url,
                "status": status,
                "reason": f"robots.txt answered {status}; a server error is treated as disallow"}
    if status >= 400:
        return {"allowed": True, "origin": origin, "robots_url": robots_url,
                "status": status, "reason": f"no robots.txt ({status})"}

    parser = RobotFileParser()
    parser.parse((body or "").splitlines())
    agent = user_agent.split("/")[0].split()[0] if user_agent else "*"
    allowed = parser.can_fetch(agent, url) and parser.can_fetch("*", url)
    reason = ("robots.txt permits this path" if allowed
              else "robots.txt disallows this path for a generic crawler")
    return {"allowed": allowed, "origin": origin, "robots_url": robots_url,
            "status": status, "reason": reason,
            "crawl_delay": parser.crawl_delay(agent) or parser.crawl_delay("*")}


def workspace_robots_override(root: Path | str | None, source: str) -> bool | None:
    """A workspace's explicit `"robots": false` for one source, or None.

    Only an explicit boolean counts. A malformed value is ignored, because a typo
    must never be able to open a gate.
    """
    if root is None:
        return None
    try:
        table = json.loads((Path(root) / ".dossier" / "sources.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    entry = table.get(source) if isinstance(table, dict) else None
    value = entry.get("robots") if isinstance(entry, dict) else None
    return value if isinstance(value, bool) else None


#: Per-host pacing. Module-level because a recipe loop and a single capture run in
#: the same process; the clock is the real one, and tests pass `sleep=None` to skip.
_LAST_CALL: dict[str, float] = {}


def pace(url: str, delay_ms: int, *, sleep=time.sleep, clock=time.monotonic) -> float:
    """Wait so that consecutive requests to one host are at least `delay_ms` apart.

    Returns the number of seconds actually waited, so a run record can show the
    pacing instead of claiming it. Serial by design: two concurrent workers would
    multiply the request rate against the same host, which is the thing pacing
    exists to bound.
    """
    if delay_ms <= 0:
        return 0.0
    host = host_of(url) or "?"
    last = _LAST_CALL.get(host)
    now = clock()
    wait = 0.0 if last is None else max(0.0, delay_ms / 1000.0 - (now - last))
    if wait and sleep is not None:
        sleep(wait)
    _LAST_CALL[host] = clock()
    return round(wait, 3)


def describe_policy(root: Path | str | None = None) -> dict:
    """The capture-relevant slice of the board table, for `scrape status`."""
    table = effective_policies(root)
    return {
        name: {"policy": entry["policy"], "permitted": permitted(name, root),
               "detail": entry.get("detail", "")}
        for name, entry in sorted(table.items())
    }


__all__ = ["HOST_SOURCES", "PRIVATE_HOSTS", "USER_SUPPLIED", "POLICIES",
           "assert_capture_allowed", "board_for", "describe_policy", "host_of",
           "is_private", "pace", "resolve_source", "robots_allowed",
           "workspace_robots_override"]
