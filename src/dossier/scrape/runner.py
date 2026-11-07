"""The runner: one capture, one recipe, and the honest report of what arrived.

A capture is a sequence of small decisions, each recorded:

1. **Which board, and may it be fetched** — `guard.assert_capture_allowed`, before
   any socket. A prohibited board stops here, not after a 403.
2. **May this path be read** — robots.txt, per URL, obeyed by default.
3. **Which engine** — obscura for a public page, Playwright when a session is in
   play, and the record says which one produced the bytes.
4. **How fast** — a per-host delay, waited, not merely intended.
5. **What arrived** — the list, then each item's detail page, extracted to text.
6. **What was written** — `job-posting-<source>-<slug>.md`, sanitised on the way
   in (`posting-is-data`), through `.dossier/trash/` when it replaces a file
   (`never-only-copy`), with the provenance needed to re-check it later.

The one rule that shapes the report: **`complete` is not "it exited zero"**. It is
true only when every requested page loaded, every listed item was captured and
nothing was silently truncated. A blocked board, an expired session, a challenge,
a selector that matched nothing, or a `--limit` that cut the list short all
produce `complete=False` with the reason named — `partial-is-not-exhaustive`.

Runs are idempotent and resumable: a posting already captured for a URL is skipped
as a duplicate (unless `--refresh`), so a recipe that fails at item 17 of 25 costs
one re-run, not 25 refetches.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse

from ..engine import sources as source_engine
from ..safety import trash_then_write_text
from . import browser, guard, recipes
from .errors import (AuthRequired, Blocked, ChallengeDetected, DriverUnavailable,
                     RecipeError, ScrapeError, Transient)
from .extract import links, meta_description, page_title, text as html_text
from .session import SessionStore

POSTING_PREFIX = "job-posting-"
RUN_LOG = ".dossier/scrape/runs.jsonl"
SCREENSHOT_DIR = ".dossier/scrape/screenshots"
PROVENANCE_DIR = ".dossier/scrape/captures"
DEFAULT_DELAY_MS = 1500


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(moment: datetime | None = None) -> str:
    return (moment or _now()).isoformat(timespec="seconds")


def slug_for(value: str, limit: int = 60) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "-", (value or "").casefold()).strip("-")
    return (cleaned[:limit].strip("-") or "untitled")


def _posting_name(source: str, title: str, url: str) -> str:
    stem = slug_for(title) if title else slug_for(urlparse(url).path.rsplit("/", 1)[-1])
    return f"{POSTING_PREFIX}{slug_for(source, 20)}-{stem}.md"


def _frontmatter_value(path: Path, key: str) -> str | None:
    """Read one frontmatter line without a YAML dependency.

    The posting format is written by this module, so the reader can be exact: a
    `key: value` line between the leading `---` fences. Anything else is ignored
    rather than guessed at.
    """
    try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            first = handle.readline().strip()
            if first != "---":
                return None
            for line in handle:
                if line.strip() == "---":
                    return None
                name, _, value = line.partition(":")
                if name.strip() == key:
                    return value.strip()
    except OSError:
        return None
    return None


def _posting_index(root: Path) -> dict[str, Path]:
    """Every archived posting, keyed by the URL in its frontmatter."""
    index: dict[str, Path] = {}
    for path in sorted(root.glob(f"{POSTING_PREFIX}*.md")):
        url = _frontmatter_value(path, "url")
        if url:
            index[url] = path
    return index


def _screenshot_path(root: Path, source: str, url: str) -> Path:
    stamp = _now().strftime("%Y%m%d")
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:10]
    return root / SCREENSHOT_DIR / stamp / f"{slug_for(source, 20)}-{digest}.png"


def _session_state(root: Path, source: str, url: str) -> tuple[dict | None, dict]:
    """The stored session for this host, or a refusal that names the fix."""
    store = SessionStore(root)
    state = store.assert_session_domain(source, url)
    return state, store.meta(source) or {}


def _fetch_once(root: Path, url: str, *, source: str, driver: str, headless: bool,
                timeout_s: float, wait_until: str, selector: str, screenshot: bool,
                session: bool, robots: bool | None, delay_ms: int, allow_private: bool,
                storage_dir: Path | None = None, user_agent: str = "",
                stealth: bool = False, await_clear_s: float = 0.0,
                solve: bool = False) -> dict:
    """One page: policy, robots, pacing, engine, extraction — in that order."""
    resolved = guard.assert_capture_allowed(url, source, root)
    # The session is keyed by the name the user chose (or the resolved board when
    # they named none). Policy is keyed by the resolved board; a session is keyed
    # by what the user called it, so `--source fixture --session` finds the jar it
    # imported even though the policy row for that URL is `web`.
    session_key = (source or resolved).strip().casefold()
    private = guard.is_private(url)

    robots_report: dict = {"checked": False}
    if robots is not False:
        report = guard.robots_allowed(url, root)
        robots_report = {"checked": True, **{k: report[k] for k in
                                             ("allowed", "reason", "robots_url", "status")
                                             if k in report}}
        if not report["allowed"]:
            raise Blocked(f"robots.txt does not permit {url}: {report['reason']}")

    waited = guard.pace(url, delay_ms)

    state, meta = (None, {})
    if session:
        state, meta = _session_state(root, session_key, url)

    shot = _screenshot_path(root, resolved, url) if screenshot else None
    request = browser.Fetch(
        url=url,
        selector=selector,
        wait_until=wait_until,
        timeout_s=timeout_s,
        screenshot=shot,
        session_state=state,
        session_source=session_key if state else "",
        headless=headless,
        allow_private=allow_private or private,
        user_agent=user_agent,
        storage_dir=storage_dir,
        stealth=stealth,
        await_clear_s=await_clear_s,
        solve=solve,
    )
    fetched = browser.capture(request, driver)

    body = html_text(fetched.html)
    return {
        "url": url,
        "final_url": fetched.final_url,
        "status": fetched.status,
        "driver": fetched.driver,
        "elapsed_ms": fetched.elapsed_ms,
        "title": fetched.title or page_title(fetched.html),
        "description": meta_description(fetched.html),
        "text": body,
        "html": fetched.html,
        "screenshot": fetched.screenshot,
        "session": {"used": bool(state), "source": session_key, "method": meta.get("method")} if state else {"used": False},
        "robots": robots_report,
        "policy": {"source": resolved, "policy": source_engine.policy(resolved, root)},
        "challenge": fetched.challenge or {},
        "paced_ms": int(waited * 1000),
        "notes": fetched.notes,
    }


class ChallengeBlocked(ChallengeDetected):
    """A challenge survived every phase the policy allowed.

    Carries the phase record so the run reports *how* it was answered, not merely
    that it failed — the difference between "the site said no" and "we tried the
    supported answers and each one was refused".
    """

    def __init__(self, message: str, record: dict):
        super().__init__(message)
        self.record = record


def _fetch_with_challenge_policy(root: Path, url: str, *, policy: str, source: str,
                                 driver: str, headless: bool, timeout_s: float,
                                 wait_until: str, selector: str, screenshot: bool,
                                 session: bool, robots: bool | None, delay_ms: int,
                                 allow_private: bool, user_agent: str = "",
                                 await_seconds: float | None = None,
                                 storage_dir: Path | None = None,
                                 allow_visible: bool | None = None) -> dict:
    """Try the phases the policy allows, in order, and record each one.

    `auto` is deliberately the widest: a plain attempt, then stealth plus a wait,
    then a *visible* window (a person can complete a real check), then the solver if
    the environment holds a key. Each phase that fails is recorded with its reason, so
    a page that never becomes readable is reported with the whole trail rather than a
    bare timeout.
    """
    from .challenge import (AWAIT_SECONDS_HEADED, AWAIT_SECONDS_HEADLESS,
                            allow_visible as visible_configured, solver_config)

    await_headless = await_seconds if await_seconds is not None else AWAIT_SECONDS_HEADLESS
    await_headed = max(await_headless, AWAIT_SECONDS_HEADED)
    visible = visible_configured(root) if allow_visible is None else allow_visible
    attempts: list[dict] = []
    playwright_available = browser.available()["playwright"]["available"]

    def run(label: str, **overrides) -> dict | None:
        try:
            page = _fetch_once(
                root, url, source=source, driver=overrides.pop("driver", driver),
                headless=overrides.pop("headless", headless), timeout_s=timeout_s,
                wait_until=wait_until, selector=selector, screenshot=screenshot,
                session=session, robots=robots, delay_ms=delay_ms,
                allow_private=allow_private, user_agent=user_agent,
                storage_dir=storage_dir, **overrides)
        except ChallengeDetected as exc:
            attempts.append({"phase": label, "outcome": "challenged", "detail": str(exc)[:300]})
            return None
        except ScrapeError as exc:
            # A block or a session problem is not the challenge ladder's business;
            # re-raising keeps the failure class the caller already handles.
            attempts.append({"phase": label, "outcome": type(exc).__name__, "detail": str(exc)[:300]})
            raise
        page["challenge"] = {**(page.get("challenge") or {}), "policy": policy,
                             "resolved_by": label, "attempts": list(attempts)}
        attempts.append({"phase": label, "outcome": "ok"})
        if not page["challenge"].get("detected") and not any(
                attempt["outcome"] == "challenged" for attempt in attempts):
            # Nothing was challenged: do not dress an ordinary page up as a resolved
            # one. `attempts` stays in the run log; the page record stays clean.
            page["challenge"] = {}
        return page

    if policy == "block":
        page = run("plain")
        if page:
            return page
        raise ChallengeBlocked(
            f"{url}: a human-verification interstitial and the policy is 'block'", 
            {"policy": policy, "attempts": attempts})

    if policy == "await":
        page = run("wait", await_clear_s=await_headless)
    elif policy == "stealth":
        page = run("stealth", stealth=True)
    elif policy == "stealth-await":
        page = run("stealth+wait", stealth=True, await_clear_s=await_headless)
    elif policy == "solve":
        page = run("solver", await_clear_s=await_headless, solve=True)
    else:  # auto
        page = (run("plain")
                or run("stealth+wait", stealth=True, await_clear_s=await_headless)
                or (run("visible", driver="playwright", stealth=True, headless=False,
                        await_clear_s=await_headed) if visible and playwright_available else None)
                or (run("solver", driver="playwright", stealth=True,
                        await_clear_s=min(await_headless, 10), solve=True)
                    if solver_config()["configured"] else None))
    if page:
        return page
    raise ChallengeBlocked(
        f"{url}: the interstitial survived every phase of challenge policy {policy!r} "
        f"({len(attempts)} attempt(s)). Set DOSSIER_SOLVER_KEY and policy 'solve', or "
        "open the page yourself and import the resulting cookies.",
        {"policy": policy, "attempts": attempts})


def _fetched(root: Path, url: str, *, source: str, driver: str, headless: bool,
             timeout_s: float, wait_until: str, selector: str, screenshot: bool,
             session: bool, robots: bool | None, delay_ms: int, allow_private: bool,
             storage_dir: Path | None = None, user_agent: str = "",
             challenge: str = "auto", await_clear_s: float | None = None) -> dict:
    """One page, with the workspace's challenge policy applied to it."""
    from .challenge import effective_policy

    policy = effective_policy(root, source, override=challenge)
    return _fetch_with_challenge_policy(
        root, url, policy=policy, source=source, driver=driver, headless=headless,
        timeout_s=timeout_s, wait_until=wait_until, selector=selector,
        screenshot=screenshot, session=session, robots=robots, delay_ms=delay_ms,
        allow_private=allow_private, user_agent=user_agent, await_seconds=await_clear_s,
        # An explicit `--headed` is the caller saying a window is acceptable; that is
        # also the only case in which `auto` may use one.
        storage_dir=storage_dir, allow_visible=(not headless) or None)


def _with_retries(action, attempts: int, *, sleep=time.sleep, backoff=(0.75, 2.0, 4.0)) -> dict:
    """Retry only what retrying can fix: a timeout, a reset, a 5xx.

    `Blocked`, `ChallengeDetected` and `AuthRequired` are raised immediately — a
    retry loop against a refusal is how an agent turns a "no" into a hammering.
    """
    last: ScrapeError | None = None
    for attempt in range(max(1, attempts + 1)):
        try:
            return action()
        except Transient as exc:
            last = exc
            if attempt < attempts:
                sleep(backoff[min(attempt, len(backoff) - 1)])
                continue
            raise
    raise last or Transient("capture failed")


def _profile_for(root: Path) -> dict:
    """The identity once per run. Empty profile means 'no filtering', not 'no match'."""
    from ..engine import identity
    try:
        data = identity.profile(root)
    except Exception:  # noqa: BLE001 - a broken identity must not stop a capture
        return {}
    return data if data.get("fields") else {}


def _match_for(record: dict, profile: dict) -> dict | None:
    if not profile:
        return None
    from ..engine import identity
    job = {"title": record.get("title", ""), "description": record.get("text", ""),
           "location": "", "work_type": "", "url": record.get("url", "")}
    return identity.score_job(job, profile)


def _posting_markdown(record: dict, *, title: str, body: str) -> str:
    challenge = record.get("challenge") or {}
    lines = [
        "---",
        f"source: {record['policy']['source']}",
        f"url: {record['url']}",
        f"captured_at: {_iso()}",
        f"driver: {record['driver']}",
        f"title: {title.replace(chr(10), ' ')[:300]}",
        f"session: {'yes (' + record['session']['source'] + ')' if record['session']['used'] else 'no'}",
        f"robots: {record['robots'].get('reason', 'not checked')}",
    ]
    if challenge.get("detected"):
        trail = [str(part) for part in (
            challenge.get("detected"),
            f"policy={challenge.get('policy')}" if challenge.get("policy") else "",
            f"resolved_by={challenge.get('resolved_by')}" if challenge.get("resolved_by") else "",
            f"waited={challenge.get('waited_s')}s" if challenge.get("waited_s") else "",
        ) if part]
        lines.append("challenge: " + "; ".join(trail))
    match = record.get("match") or {}
    if match:
        lines.append(f"match: {match['band']} {match['score']}")
        if match.get("disqualifiers"):
            lines.append("match_against: " + "; ".join(match["disqualifiers"])[:300])
    if record.get("screenshot"):
        lines.append(f"screenshot: {record['screenshot']}")
    if record.get("final_url") and record["final_url"] != record["url"]:
        lines.append(f"resolved_url: {record['final_url']}")
    lines += ["---", "", f"# {title or record['url']}", "", body.strip(), ""]
    return "\n".join(lines)


def _write_posting(root: Path, record: dict, *, refresh: bool) -> dict:
    """Write the posting and its provenance, or report it as a duplicate."""
    title = (record.get("title") or "").strip()
    existing = _posting_index(root).get(record["url"])
    if existing is not None and not refresh:
        return {"written": False, "duplicate": True, "path": str(existing.relative_to(root))}

    body = record["text"]
    sanitized = source_engine.sanitize(body, record["policy"]["source"])
    filename = existing.name if existing is not None else _posting_name(
        record["policy"]["source"], title, record["url"])
    path = root / filename
    markdown = _posting_markdown(record, title=title, body=sanitized["clean"])
    trash_then_write_text(root, path, markdown)

    provenance = root / PROVENANCE_DIR / f"{path.stem}.json"
    provenance.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        **{key: value for key, value in record.items() if key not in {"html", "text"}},
        "posting": str(path.relative_to(root)),
        "chars": len(sanitized["clean"]),
        "sanitize": {"flagged": sanitized["flagged"], "findings": sanitized["findings"]},
        "sha256": hashlib.sha256(markdown.encode("utf-8")).hexdigest(),
    }
    trash_then_write_text(root, provenance, json.dumps(payload, indent=2, ensure_ascii=False))
    return {"written": True, "duplicate": False, "path": str(path.relative_to(root)),
            "provenance": str(provenance.relative_to(root)),
            "flagged": sanitized["flagged"], "findings": sanitized["findings"],
            "chars": len(sanitized["clean"])}


def _record_run(root: Path, record: dict) -> None:
    path = root / RUN_LOG
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def _run_log(root: Path, limit: int = 20) -> list[dict]:
    path = root / RUN_LOG
    if not path.is_file():
        return []
    rows: list[dict] = []
    try:
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines()[-limit:]:
            try:
                rows.append(json.loads(line))
            except ValueError:
                continue
    except OSError:
        return []
    return rows


# --------------------------------------------------------------------------
# one URL
# --------------------------------------------------------------------------

def capture_url(root: Path | str, url: str, *, source: str = "", driver: str = "auto",
                headless: bool = True, screenshot: bool = True, timeout_s: float = 30,
                wait_until: str = "load", selector: str = "",
                session: bool = False, robots: bool | None = None,
                delay_ms: int = DEFAULT_DELAY_MS, refresh: bool = False,
                user_agent: str = "", challenge: str = "auto",
                await_clear_s: float | None = None, min_match: int = 0) -> dict:
    """Capture one page the user named and archive it as a posting."""
    root = Path(root).resolve()
    started = time.monotonic()
    # The policy is asked here as well as inside `_fetched`, so a refusal happens
    # before any engine is even selected — and so a caller that replaces the fetch
    # (a test, a future driver) cannot walk around the gate by accident. The
    # declared name is kept: it is what a session is keyed by.
    declared = source
    guard.assert_capture_allowed(url, declared, root)
    subject = url
    complete = False
    reason = ""
    try:
        record = _with_retries(
            lambda: _fetched(root, url, source=declared, driver=driver, headless=headless,
                             timeout_s=timeout_s, wait_until=wait_until, selector=selector,
                             screenshot=screenshot, session=session, robots=robots,
                             delay_ms=delay_ms, allow_private=guard.is_private(url),
                             user_agent=user_agent, challenge=challenge,
                             await_clear_s=await_clear_s),
            1)
        record["match"] = _match_for(record, _profile_for(root)) or {}
        filtered = bool(min_match and record["match"]
                        and record["match"].get("score", 0) < min_match)
        if filtered:
            # Relevance filtering is the user's request, so it is recorded rather
            # than silently dropped: `filtered` names the score and the floor.
            written = {"written": False, "duplicate": False, "filtered": True,
                       "filtered_below": min_match, "path": None}
        else:
            written = _write_posting(root, record, refresh=refresh)
        complete = bool(record["text"].strip())
        reason = "" if complete else "the page produced no readable text"
        if filtered:
            complete = False
            reason = (f"relevance {record['match'].get('score')} is below the floor "
                      f"{min_match}; nothing was archived")
        result = {
            "ok": complete, "url": url, "subject": subject, "complete": complete,
            "reason": reason or None, "captured_at": _iso(), "driver": record["driver"],
            "title": record["title"], "source": record["policy"]["source"],
            "policy": record["policy"], "session": record["session"],
            "robots": record["robots"], "paced_ms": record["paced_ms"],
            "screenshot": record["screenshot"], "posting": written.get("path"),
            "challenge": record.get("challenge") or {},
            "match": record.get("match") or {},
            "filtered": filtered,
            **written,
        }
    except (AuthRequired, Blocked, ChallengeDetected, DriverUnavailable, RecipeError) as exc:
        result = {"ok": False, "url": url, "complete": False,
                  "reason": f"{type(exc).__name__}: {exc}", "captured_at": _iso(),
                  "challenge": getattr(exc, "record", None) or {}}
    except ScrapeError as exc:
        result = {"ok": False, "url": url, "complete": False,
                  "reason": f"{type(exc).__name__}: {exc}", "captured_at": _iso()}
    result["duration_ms"] = int((time.monotonic() - started) * 1000)
    _record_run(root, {"kind": "capture", **result})
    return result


# --------------------------------------------------------------------------
# a recipe
# --------------------------------------------------------------------------

def _page_url(start_url: str, param: str, number: int) -> str:
    parsed = urlparse(start_url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query[param] = str(number)
    return urlunparse(parsed._replace(query=urlencode(query)))


def _node_text(node, selector: str) -> str:
    if not selector:
        return ""
    found = node.cssselect(selector)
    return " ".join(found[0].text_content().split()) if found else ""


def _list_items(html: str, base_url: str, listing: dict) -> list[dict]:
    from .extract import document

    tree = document(html)
    items: list[dict] = []
    for node in tree.cssselect(listing["item"]):
        anchor = node.cssselect(listing["link"])
        if anchor:
            href = anchor[0].get("href") or ""
            label = " ".join(anchor[0].text_content().split())
        else:
            href = node.get("href") or ""
            label = " ".join(node.text_content().split())
        if not href:
            continue
        items.append({
            "url": urljoin(base_url, href),
            "title": _node_text(node, listing.get("title", "")) or label,
            "company": _node_text(node, listing.get("company", "")),
            "location": _node_text(node, listing.get("location", "")),
            "pay": _node_text(node, listing.get("pay", "")),
        })
    return items


def _next_link(html: str, base_url: str, selector: str) -> str:
    from .extract import document

    tree = document(html)
    try:
        nodes = tree.cssselect(selector)
    except Exception:  # noqa: BLE001
        return ""
    for node in nodes:
        href = node.get("href") if node.tag == "a" else None
        if not href:
            anchors = node.cssselect("a")
            href = anchors[0].get("href") if anchors else None
        if href and not href.startswith(("#", "javascript:")):
            return urljoin(base_url, href)
    return ""


def run_recipe(root: Path | str, recipe: recipes.Recipe, *, limit: int | None = None,
               pages: int | None = None, driver: str = "auto",
               headless: bool | None = None, refresh: bool = False,
               screenshot: bool = True, timeout_s: float | None = None,
               delay_ms: int | None = None, challenge: str | None = None,
               await_clear_s: float | None = None, min_match: int | None = None) -> dict:
    """Walk one recipe: list pages, then each item, then report what happened."""
    root = Path(root).resolve()
    started = time.monotonic()
    # A recipe for a board the ledger refuses is refused here, before a single
    # listing request — not on the third item, after two pages have loaded.
    guard.assert_capture_allowed(recipe.start_url, recipe.source, root)
    max_items = max(1, min(limit or recipe.max_items, 500))
    max_pages = max(1, min(pages or recipe.max_pages, 50))
    headless = recipe.headless if headless is None else headless
    timeout_s = timeout_s or recipe.timeout_s
    delay_ms = recipe.delay_ms if delay_ms is None else delay_ms
    needs_session = recipe.auth == "required"
    robots = recipe.robots
    mode = recipe.pagination.get("mode", "none")
    policy = challenge or recipe.challenge or "auto"
    floor = recipe.min_match if min_match is None else min_match
    identity_profile = _profile_for(root)
    filtered: list[dict] = []

    failures: list[dict] = []
    written: list[dict] = []
    duplicates: list[dict] = []
    drivers: set[str] = set()
    pages_fetched = 0
    truncated = False
    capped = False
    reason = ""

    def fetch_page(url: str, *, selector: str = "") -> dict:
        page = _with_retries(
            lambda: _fetched(root, url, source=recipe.source, driver=driver,
                             headless=headless, timeout_s=timeout_s,
                             wait_until=recipe.wait_until,
                             selector=selector or recipe.wait_selector,
                             screenshot=False, session=needs_session, robots=robots,
                             delay_ms=delay_ms, allow_private=guard.is_private(url),
                             challenge=policy, await_clear_s=await_clear_s),
            recipe.retries)
        drivers.add(page["driver"])
        return page

    def archive(page: dict, url: str, *, title: str = "", listing_item: dict | None = None) -> None:
        body = page["text"]
        if listing_item is not None:
            body = html_text(page["html"], selector=recipe.detail.get("content", ""),
                             remove=recipe.detail.get("remove", []))
        record = {**page, "text": body, "title": title or page["title"] or ""}
        match = _match_for(record, identity_profile)
        record["match"] = match or {}
        if floor and match and match["score"] < floor:
            filtered.append({"url": url, "title": record["title"], "score": match["score"],
                             "band": match["band"], "reasons": match["reasons"][:3]})
            return
        outcome = _write_posting(root, record, refresh=refresh)
        entry = {"url": url, "title": record["title"], "driver": page["driver"],
                 "company": (listing_item or {}).get("company", ""),
                 "match": record["match"], **outcome}
        (written if outcome["written"] else duplicates).append(entry)

    # -- a single-page recipe: the start URL is the posting -----------------
    if not recipe.is_list:
        try:
            page = fetch_page(recipe.start_url)
            pages_fetched += 1
            archive(page, recipe.start_url)
            complete = bool(page["text"].strip())
            result = _finish(started, recipe, complete=complete,
                             reason="" if complete else "the page produced no readable text",
                             pages_fetched=pages_fetched, items=1,
                             written=written, duplicates=duplicates, failures=failures,
                             drivers=sorted(drivers), filtered=filtered, min_match=floor)
        except ScrapeError as exc:
            failures.append({"stage": "page", "url": recipe.start_url,
                             "error": f"{type(exc).__name__}: {exc}"})
            result = _finish(started, recipe, complete=False,
                             reason=f"{type(exc).__name__}: {exc}",
                             pages_fetched=pages_fetched, items=0, written=[], duplicates=[],
                             failures=failures, drivers=sorted(drivers))
        _record_run(root, {"kind": "recipe", **result})
        return result

    # -- the listing ------------------------------------------------------
    items: list[dict] = []
    current = recipe.start_url
    page_index = 0
    while current and page_index < max_pages:
        try:
            page = fetch_page(current)
        except (Blocked, ChallengeDetected, AuthRequired, DriverUnavailable) as exc:
            failures.append({"stage": "list", "url": current,
                             "error": f"{type(exc).__name__}: {exc}",
                             "challenge": getattr(exc, "record", None) or {}})
            reason = reason or f"the listing page could not be read: {type(exc).__name__}"
            break
        except ScrapeError as exc:
            failures.append({"stage": "list", "url": current,
                             "error": f"{type(exc).__name__}: {exc}"})
            reason = reason or "the listing page could not be read"
            break
        pages_fetched += 1
        base = page["final_url"] or current
        found = _list_items(page["html"], base, recipe.list)
        items.extend(found)

        if mode == "none" or not found:
            break
        page_index += 1
        if page_index >= max_pages:
            # The page had items and the budget is spent: more may exist. Saying
            # so is the difference between a partial capture and claimed coverage.
            capped = True
            break
        if mode == "query":
            current = _page_url(recipe.start_url, recipe.pagination.get("param", "page"),
                                int(recipe.pagination.get("start", 1)) + page_index)
        elif mode == "next-link":
            current = _next_link(page["html"], base, recipe.pagination.get("selector", ""))
        else:
            break

    if not items:
        reason = reason or ("the list selector matched no items; check list.item and list.link"
                           if pages_fetched else "no listing page was read")
    if len(items) > max_items:
        truncated = True
        reason = reason or f"stopped at --limit {max_items} of {len(items)} listed items"
    items = items[:max_items]

    # -- each item's own page ---------------------------------------------
    attempted = 0
    seen: set[str] = set()
    for item in items:
        if item["url"] in seen:
            continue
        seen.add(item["url"])
        attempted += 1
        try:
            page = fetch_page(item["url"])
            pages_fetched += 1
            archive(page, item["url"], title=item.get("title", ""), listing_item=item)
        except ScrapeError as exc:
            failures.append({"stage": "detail", "url": item["url"],
                             "error": f"{type(exc).__name__}: {exc}"})

    complete = bool(not failures and not truncated and not capped
                    and attempted == len(items) and items and (written or duplicates))
    if not complete and not reason:
        reason = (f"{len(failures)} item(s) failed" if failures
                  else "no item was captured")

    result = _finish(started, recipe, complete=complete, reason=reason,
                     pages_fetched=pages_fetched, items=len(items), attempted=attempted,
                     written=written, duplicates=duplicates, failures=failures,
                     truncated=truncated, capped=capped, drivers=sorted(drivers),
                     filtered=filtered, min_match=floor)
    _record_run(root, {"kind": "recipe", **result})
    return result


def _finish(started: float, recipe: recipes.Recipe, **fields) -> dict:
    written = fields.get("written") or []
    return {
        "recipe": recipe.id,
        "source": recipe.source,
        "start_url": recipe.start_url,
        "auth": recipe.auth,
        "captured_at": _iso(),
        "duration_ms": int((time.monotonic() - started) * 1000),
        "truncated": fields.pop("truncated", False),
        "capped": fields.pop("capped", False),
        "items_captured": len(written),
        **fields,
    }
# --------------------------------------------------------------------------
# status
# --------------------------------------------------------------------------

def _last_run_for(root: Path, recipe_id: str) -> dict | None:
    for row in reversed(_run_log(root, limit=200)):
        if row.get("recipe") == recipe_id:
            return row
    return None


def _due(recipe: recipes.Recipe, last: dict | None) -> dict:
    if not recipe.cadence_hours:
        return {"due": False, "reason": "no cadence declared; runs only when asked"}
    if last is None:
        return {"due": True, "reason": "never captured"}
    try:
        ran = datetime.fromisoformat(str(last.get("captured_at")))
    except (TypeError, ValueError):
        return {"due": True, "reason": "the last run has no readable timestamp"}
    if ran.tzinfo is None:
        ran = ran.replace(tzinfo=timezone.utc)
    next_due = ran + timedelta(hours=recipe.cadence_hours)
    return {"due": _now() >= next_due, "next_due": next_due.isoformat(timespec="seconds"),
            "reason": ("due now" if _now() >= next_due
                       else f"next due {next_due.isoformat(timespec='seconds')}")}


def status(root: Path | str) -> dict:
    """Everything a session needs to decide what to capture next, and why not."""
    root = Path(root).resolve()
    found, errors = recipes.discover(root)
    store = SessionStore(root)
    rows = []
    for recipe in found:
        last = _last_run_for(root, recipe.id)
        rows.append({
            "id": recipe.id,
            "source": recipe.source,
            "origin": recipe.origin,
            "start_url": recipe.start_url,
            "auth": recipe.auth,
            "kind": "list" if recipe.is_list else "single",
            "cadence_hours": recipe.cadence_hours,
            "path": recipe.path,
            "last_run": ({"captured_at": last.get("captured_at"),
                          "complete": last.get("complete"),
                          "items_captured": last.get("items_captured"),
                          "reason": last.get("reason")} if last else None),
            **_due(recipe, last),
        })
    postings = sorted(root.glob(f"{POSTING_PREFIX}*.md"))
    from .challenge import describe as describe_challenge
    return {
        "root": str(root),
        "recipes": rows,
        "recipe_errors": errors,
        "due": [row["id"] for row in rows if row["due"]],
        "sessions": store.status(),
        "engines": browser.available(),
        "challenge": describe_challenge(root),
        "policy": guard.describe_policy(root),
        "captured_postings": len(postings),
        "run_log": str((root / RUN_LOG).relative_to(root)),
        "last_run": (_run_log(root, limit=1) or [None])[-1],
        "rule": ("A run is complete only when every requested page loaded and every listed "
                 "item was captured. A blocked board, an expired session, a challenge or a "
                 "limit is reported as partial, never as coverage."),
    }


def due_recipes(root: Path | str) -> list[recipes.Recipe]:
    """The recipes whose declared cadence has elapsed, newest deadline first."""
    found, _errors = recipes.discover(Path(root).resolve())
    owed = []
    for recipe in found:
        if _due(recipe, _last_run_for(Path(root).resolve(), recipe.id))["due"]:
            owed.append(recipe)
    return owed


__all__ = ["DEFAULT_DELAY_MS", "POSTING_PREFIX", "RUN_LOG", "capture_url", "due_recipes",
           "run_recipe", "slug_for", "status"]
