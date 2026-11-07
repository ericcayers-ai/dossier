"""The session store: the user's own sign-in, and nothing else.

An authenticated board is reachable because *the user* signed in, in a window
they could see, with credentials Dossier never received. This module stores what
a browser hands back afterwards — cookies and localStorage entries, the same pair
Playwright calls a `storage_state` — and refuses everything else.

The gate is structural, not a promise:

* `save()` **rebuilds** the record from the `cookies` and `origins` keys only.
  Any other key in the payload — a password, a username, an API token, a full
  profile dump — is dropped before anything is written, so no code path can
  persist a credential even by accident.
* A session with no cookies and no origin entries is not saved: an empty jar is
  not a session, and a file that claims otherwise makes an unauthenticated
  capture look authenticated.
* `cookies_for()` and `assert_session_domain()` compare the *host of the request*
  against the cookies' own domains. A session for one board is never attached to
  a request for another: that is how a cookie jar leaks to a third party.
* Every file is written `0600` and lives under `.dossier/`, which is disposable,
  git-ignored and never part of a handoff packet.

An expired jar is reported as expired rather than retried silently, because the
fix is a human action (`dossier scrape login <source>`), not a backoff loop.
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

from .errors import AuthRequired, ScrapeError

SESSION_DIR = ".dossier/scrape/sessions"
META_SUFFIX = ".meta.json"
STORAGE_SUFFIX = ".storage.json"

#: Methods that may create a session. `user-login` is a visible browser the user
#: drove; `imported-cookies` is a cookie file the user exported from their own
#: browser. There is deliberately no `automated` method: nothing in this package
#: may type a credential.
METHODS = ("user-login", "imported-cookies")


def slug(source: str) -> str:
    """A filesystem-safe name for a board. Two boards that slug alike would share
    a jar, which would silently authenticate one against the other."""
    kept = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in (source or "").strip().casefold())
    cleaned = "-".join(part for part in kept.split("-") if part)
    if not cleaned:
        raise ScrapeError("a session needs a source name (for example: linkedin)")
    return cleaned


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _domain_matches(domain: str, host: str) -> bool:
    domain = (domain or "").lstrip(".").casefold()
    host = (host or "").casefold()
    if not domain or not host:
        return False
    return host == domain or host.endswith("." + domain)


def _cookie_expiry(value) -> int:
    """Playwright wants whole seconds since the epoch, or -1 for a session cookie."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return -1
    if number <= 0:
        return -1
    return int(number)


def _sanitize_cookie(cookie: dict) -> dict | None:
    if not isinstance(cookie, dict):
        return None
    name, value = cookie.get("name"), cookie.get("value")
    if not isinstance(name, str) or not name:
        return None
    if not isinstance(value, str):
        value = "" if value is None else str(value)
    return {
        "name": name,
        "value": value,
        "domain": str(cookie.get("domain", "")),
        "path": str(cookie.get("path") or "/"),
        "expires": _cookie_expiry(cookie.get("expires")),
        "httpOnly": bool(cookie.get("httpOnly", False)),
        "secure": bool(cookie.get("secure", False)),
        "sameSite": cookie.get("sameSite") if cookie.get("sameSite") in {"Strict", "Lax", "None"} else "Lax",
    }


def _sanitize_origins(origins) -> list[dict]:
    cleaned: list[dict] = []
    for entry in origins or []:
        if not isinstance(entry, dict):
            continue
        origin = entry.get("origin")
        items = entry.get("localStorage")
        if not isinstance(origin, str) or not isinstance(items, list):
            continue
        kept = [
            {"name": str(item.get("name")), "value": str(item.get("value"))}
            for item in items
            if isinstance(item, dict) and isinstance(item.get("name"), str)
            and isinstance(item.get("value"), (str, int, float, bool))
        ]
        cleaned.append({"origin": origin, "localStorage": kept})
    return cleaned


class SessionStore:
    """Reads and writes per-board browser state under `.dossier/scrape/sessions/`."""

    def __init__(self, root: Path | str):
        self.root = Path(root).resolve()

    # -- locations ---------------------------------------------------------
    @property
    def directory(self) -> Path:
        return self.root / SESSION_DIR

    def storage_path(self, source: str) -> Path:
        return self.directory / f"{slug(source)}{STORAGE_SUFFIX}"

    def meta_path(self, source: str) -> Path:
        return self.directory / f"{slug(source)}{META_SUFFIX}"

    # -- reads -------------------------------------------------------------
    def exists(self, source: str) -> bool:
        return self.storage_path(source).is_file()

    def load(self, source: str) -> dict | None:
        """The sanitized storage state, or None. Never raises on a corrupt file.

        A corrupt session is not a session: returning None makes the caller ask
        the user to sign in again instead of attaching garbage to a request.
        """
        path = self.storage_path(source)
        if not path.is_file():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        if not isinstance(data, dict):
            return None
        cookies = [c for c in (_sanitize_cookie(item) for item in data.get("cookies") or []) if c]
        origins = _sanitize_origins(data.get("origins"))
        if not cookies and not origins:
            return None
        return {"cookies": cookies, "origins": origins}

    def meta(self, source: str) -> dict | None:
        try:
            data = json.loads(self.meta_path(source).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        return data if isinstance(data, dict) else None

    def cookies_for(self, source: str, url: str) -> list[dict]:
        """The stored cookies whose domain covers this URL, and nothing else."""
        from urllib.parse import urlparse

        state = self.load(source)
        host = (urlparse(url).hostname or "").casefold()
        if not state or not host:
            return []
        return [cookie for cookie in state["cookies"] if _domain_matches(cookie["domain"], host)]

    def expired(self, source: str, now: float | None = None) -> bool:
        """True when every stored cookie has a past expiry and none is a session cookie."""
        state = self.load(source)
        if not state or not state["cookies"]:
            return False
        moment = time.time() if now is None else now
        return all(cookie["expires"] != -1 and cookie["expires"] < moment for cookie in state["cookies"])

    # -- writes ------------------------------------------------------------
    def save(self, source: str, storage_state: dict, *, source_url: str,
             method: str = "user-login", label: str = "") -> dict:
        """Persist the user's own browser state. Only cookies and localStorage survive.

        `method` must be a user-driven one (see `METHODS`); `source_url` is the
        page the user signed in on and is required so a receipt can say where the
        session came from.
        """
        if method not in METHODS:
            raise ScrapeError(
                f"refusing to create a session with method {method!r}: a session may only come "
                f"from {' or '.join(METHODS)}. Dossier never signs in on the user's behalf.")
        if not isinstance(storage_state, dict):
            raise ScrapeError("storage_state must be the object Playwright's context.storage_state() returns")
        if not (source_url or "").strip():
            raise ScrapeError("source_url is required: a session must name the page the user signed in on")
        cookies = [c for c in (_sanitize_cookie(item) for item in storage_state.get("cookies") or []) if c]
        origins = _sanitize_origins(storage_state.get("origins"))
        if not cookies and not origins:
            raise ScrapeError(
                "the browser state held no cookies and no localStorage entries, so it is not a "
                "session. Nothing was saved.")
        dropped = sorted(set(storage_state) - {"cookies", "origins"})
        record = {"cookies": cookies, "origins": origins}
        meta = {
            "source": slug(source),
            "method": method,
            "source_url": source_url,
            "label": label,
            "saved_at": _now_iso(),
            "updated_at": _now_iso(),
            "cookie_count": len(cookies),
            "origin_count": len(origins),
            "hosts": sorted({cookie["domain"].lstrip(".") for cookie in cookies}),
            "dropped_keys": dropped,
            "never_stored": ["password", "username", "api tokens", "page content"],
        }
        previous = self.meta(source) or {}
        if previous.get("saved_at"):
            meta["first_saved_at"] = previous["saved_at"]

        self.directory.mkdir(parents=True, exist_ok=True)
        self._write(self.storage_path(source), record)
        self._write(self.meta_path(source), meta)
        return meta

    def clear(self, source: str) -> bool:
        removed = False
        for path in (self.storage_path(source), self.meta_path(source)):
            try:
                path.unlink()
                removed = True
            except FileNotFoundError:
                continue
        return removed

    def _write(self, path: Path, payload: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        try:
            os.chmod(path, 0o600)
        except OSError:
            # Windows may ignore the mode; the file still never leaves this folder.
            pass

    # -- reporting ---------------------------------------------------------
    def status(self) -> list[dict]:
        """One row per stored session. Cookie *values* are never included."""
        if not self.directory.is_dir():
            return []
        rows = []
        for path in sorted(self.directory.glob(f"*{STORAGE_SUFFIX}")):
            source = path.name[: -len(STORAGE_SUFFIX)]
            meta = self.meta(source) or {}
            rows.append({
                "source": source,
                "present": True,
                "method": meta.get("method"),
                "source_url": meta.get("source_url"),
                "saved_at": meta.get("saved_at"),
                "hosts": meta.get("hosts", []),
                "cookie_count": meta.get("cookie_count"),
                "origin_count": meta.get("origin_count"),
                "expired": self.expired(source),
                "path": str(path.relative_to(self.root)),
            })
        return rows

    def assert_session_domain(self, source: str, url: str) -> dict:
        """Refuse to attach a session to a host its cookies do not belong to."""
        from urllib.parse import urlparse

        host = (urlparse(url).hostname or "").casefold()
        state = self.load(source)
        if state is None:
            raise AuthRequired(
                f"no saved session for {source}. Sign in yourself with "
                f"`dossier scrape login {source} --url <sign-in page>` — Dossier never "
                "types a credential on your behalf.")
        if not host or not any(_domain_matches(cookie["domain"], host) for cookie in state["cookies"]):
            hosts = sorted({cookie["domain"].lstrip(".") for cookie in state["cookies"]})
            raise AuthRequired(
                f"the stored {source} session has no cookies for {host or 'this host'} "
                f"(its cookies belong to: {', '.join(hosts) or 'none'}). Refusing to send a "
                "session to a host it does not belong to; sign in on that host first.")
        if self.expired(source):
            raise AuthRequired(
                f"the saved {source} session has expired. Sign in again with "
                f"`dossier scrape login {source} --url <sign-in page>`.")
        return state


def parse_netscape_cookies(text: str) -> list[dict]:
    """Read a Netscape/Mozilla `cookies.txt` export into Playwright cookie dicts.

    Seven tab-separated fields: domain, include-subdomains, path, secure, expiry,
    name, value. The one subtlety that matters: a line prefixed `#HttpOnly_` is a
    *real* cookie, and treating every `#` line as a comment loses exactly the
    session cookie a signed-in export exists to carry. Malformed lines are
    skipped rather than guessed at, because a half-read cookie value is a broken
    session that looks valid.
    """
    cookies: list[dict] = []
    for raw in (text or "").splitlines():
        line = raw.strip("\r")
        if not line.strip():
            continue
        http_only = line.startswith("#HttpOnly_")
        if line.startswith("#") and not http_only:
            continue
        fields = line.split("\t")
        if len(fields) != 7:
            continue
        domain, _include, path, secure, expiry, name, value = fields
        if http_only:
            domain = domain[len("#HttpOnly_"):]
        if not name or not domain:
            continue
        cookies.append({
            "name": name,
            "value": value,
            "domain": domain,
            "path": path or "/",
            "expires": _cookie_expiry(expiry),
            "httpOnly": http_only,
            "secure": secure.strip().upper() == "TRUE",
            "sameSite": "Lax",
        })
    return cookies


def import_netscape_cookies(store: SessionStore, source: str, text: str, *,
                            source_url: str) -> dict:
    """Store a cookie export the user made from their own browser."""
    cookies = parse_netscape_cookies(text)
    if not cookies:
        raise ScrapeError(
            "no cookies were found in that file. A Netscape cookie export starts with "
            "'# Netscape HTTP Cookie File'; an empty or JSON file is not one.")
    return store.save(source, {"cookies": cookies, "origins": []},
                      source_url=source_url, method="imported-cookies",
                      label="imported from a Netscape cookie file")
