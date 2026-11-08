"""Two browser engines behind one call, chosen for a reason the receipt records.

`obscura` is the default: a Rust/V8 headless engine on this machine, invoked as a
subprocess, no Python browser dependency, robots-aware. It is the right tool for
a public page — and it cannot hold a session, because it has no interactive
window and no profile the user can sign into.

`playwright` + Chromium is the session engine. It is the only layer that can show
the user a real sign-in page, take back the resulting cookies and localStorage,
and replay them headless. It is also the fallback for a page obscura cannot
render.

Both return the same `Fetched` record, so the runner never branches on engine and
a receipt always says which one produced the bytes. What neither driver does is
answer a challenge or disguise itself as something it is not: a detected
interstitial raises `ChallengeDetected` and the run records a blocker.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path

from .errors import (AuthRequired, Blocked, ChallengeDetected, DriverUnavailable,
                     ScrapeError, Transient)

#: Where a packaged build of obscura lives on this machine, after `which`.
OBSCURA_CANDIDATES = (
    Path.home() / ".dsh" / "tools" / "obscura" / "obscura.exe",
    Path.home() / ".pi" / "agent" / "bin" / "obscura.exe",
)

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
)


@dataclass(frozen=True)
class Fetch:
    """One page request, in the vocabulary both engines understand."""

    url: str
    selector: str = ""
    wait_until: str = "load"
    timeout_s: float = 30.0
    screenshot: Path | None = None
    session_state: dict | None = None
    session_source: str = ""
    headless: bool = True
    allow_private: bool = False
    user_agent: str = ""
    storage_dir: Path | None = None
    stealth: bool = False
    #: Seconds to keep the page open while an interstitial clears on its own (or is
    #: completed by the user in a visible window). 0 means "do not wait".
    await_clear_s: float = 0.0
    #: Ask the configured solver for a token once the wait fails.
    solve: bool = False


@dataclass
class Fetched:
    url: str
    final_url: str = ""
    status: int | None = None
    html: str = ""
    title: str = ""
    driver: str = ""
    elapsed_ms: int = 0
    screenshot: str | None = None
    session_used: bool = False
    challenge: dict = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"url": self.url, "final_url": self.final_url, "status": self.status,
                "title": self.title, "driver": self.driver, "elapsed_ms": self.elapsed_ms,
                "screenshot": self.screenshot, "session_used": self.session_used,
                "challenge": self.challenge,
                "html_bytes": len(self.html.encode("utf-8", "ignore")), "notes": self.notes}


# --------------------------------------------------------------------------
# obscura
# --------------------------------------------------------------------------

def obscura_path() -> Path | None:
    """The packaged binary, or whatever `obscura` resolves to, or None."""
    override = os.environ.get("DOSSIER_OBSCURA", "").strip()
    if override:
        candidate = Path(override).expanduser()
        if candidate.is_file():
            return candidate
    found = shutil.which("obscura")
    if found:
        return Path(found)
    for candidate in OBSCURA_CANDIDATES:
        if candidate.is_file():
            return candidate
    return None


def _obscura_command(binary: Path, args: list[str]) -> list[str]:
    """The argv for the obscura binary, refusing a shim argument that cmd would re-parse.

    A `.cmd`/`.bat` shim has to run through `cmd /c`, and cmd re-parses the flattened
    command line rather than taking argv: `subprocess.list2cmdline` only quotes an
    argument that contains a space or a tab, so a captured URL such as
    `http://host/?a=1&calc` reaches cmd unquoted and the `&` forks a second command.
    Measured on this machine (`probe-cmd-shim.py`): the `cmd /c` list form truncates the
    URL at the `&`, which is the fork, not a quoting accident.

    So the shim is still supported for ordinary URLs, and an argument carrying a cmd
    metacharacter is refused with a sentence that names the fix. The `.exe` build of
    obscura has none of these semantics; this only ever applies to a shim.
    """
    if binary.suffix.casefold() in {".cmd", ".bat"}:
        for argument in args:
            offender = next((bad for bad in '&|<>^"\r\n' if bad in argument), None)
            if offender is not None:
                raise RuntimeError(
                    f"refusing to pass {argument[:60]!r} to the {binary.suffix} shim "
                    f"{binary.name}: cmd.exe would re-parse {offender!r} as a command "
                    "separator. Point DOSSIER_OBSCURA at the obscura .exe instead."
                )
        return ["cmd", "/c", str(binary), *args]
    return [str(binary), *args]


def obscura_version(binary: Path | None = None) -> str | None:
    binary = binary or obscura_path()
    if binary is None:
        return None
    try:
        result = subprocess.run(_obscura_command(binary, ["--version"]), capture_output=True,
                                text=True, timeout=20)
    except (OSError, subprocess.SubprocessError):
        return None
    text = (result.stdout or result.stderr or "").strip().splitlines()
    return text[0] if text else None


class ObscuraDriver:
    """A subprocess around `obscura fetch`. Public pages only, by construction."""

    name = "obscura"

    def __init__(self, binary: Path | None = None):
        self.binary = binary or obscura_path()
        if self.binary is None:
            raise DriverUnavailable(
                "obscura is not installed and not on PATH. Install the release from "
                "github.com/h4ckf0r0day/obscura, or use --driver playwright.")

    def available(self) -> bool:
        return self.binary is not None

    def capture(self, fetch: Fetch) -> Fetched:
        if fetch.session_state:
            raise DriverUnavailable(
                "obscura cannot replay a saved session; use --driver playwright for an "
                "authenticated capture.")
        # `--screenshot` and `--dump` are mutually exclusive in obscura: with `-s` the
        # engine writes the PNG and emits NO document on stdout, which looked exactly
        # like an empty page and was reported as one. So the dump is written to a temp
        # file with `-o` (stdout stays clean of progress lines) and an image is left to
        # Playwright, which can do both in one pass.
        import tempfile

        notes: list[str] = []
        handle = tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8")
        handle.close()
        dump_path = Path(handle.name)
        extra = [
            "fetch", fetch.url,
            "--dump", "html",
            "-o", str(dump_path),
            "--timeout", str(int(max(1, fetch.timeout_s))),
            "--wait-until", fetch.wait_until,
        ]
        if fetch.selector:
            extra += ["--selector", fetch.selector]
        if fetch.allow_private:
            extra += ["--allow-private-network"]
        if fetch.stealth:
            extra += ["--stealth"]
        if fetch.await_clear_s:
            # obscura has no window to hand to a person, but its adaptive settle is
            # the same idea: give the page time before the snapshot is taken.
            extra += ["--wait", str(max(1, int(fetch.await_clear_s)))]
        if fetch.user_agent:
            extra += ["--user-agent", fetch.user_agent]
        if fetch.storage_dir:
            fetch.storage_dir.mkdir(parents=True, exist_ok=True)
            extra += ["--storage-dir", str(fetch.storage_dir)]
        command = _obscura_command(self.binary, extra)
        if fetch.screenshot:
            notes.append("obscura cannot dump and screenshot in one pass; "
                         "no image was taken (use --driver playwright for one)")

        started = time.monotonic()
        try:
            result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8",
                                    errors="replace", timeout=fetch.timeout_s + 45)
        except subprocess.TimeoutExpired:
            raise Transient(f"obscura timed out after {fetch.timeout_s + 45:.0f}s on {fetch.url}") from None
        except OSError as exc:
            raise DriverUnavailable(f"obscura could not be started: {exc}") from None
        finally:
            elapsed = int((time.monotonic() - started) * 1000)

        stderr = (result.stderr or "").strip()
        html = ""
        try:
            if dump_path.is_file():
                html = dump_path.read_text(encoding="utf-8", errors="replace")
        finally:
            try:
                dump_path.unlink()
            except OSError:
                pass
        if not html.strip():
            html = result.stdout or ""
        if result.returncode != 0:
            raise _classify_obscura_failure(fetch.url, result.returncode, stderr)
        if not html.strip():
            raise Transient(f"obscura returned an empty document for {fetch.url}"
                            + (f" ({stderr})" if stderr else ""))
        return Fetched(url=fetch.url, final_url=fetch.url, status=None, html=html,
                       driver=self.name, elapsed_ms=elapsed,
                       screenshot=None,
                       challenge={"stealth": fetch.stealth,
                                  "waited_s": float(max(1, int(fetch.await_clear_s))) if fetch.await_clear_s else 0.0},
                       notes=notes + [line for line in stderr.splitlines()[:3] if line])


def _classify_obscura_failure(url: str, code: int, stderr: str) -> ScrapeError:
    lowered = stderr.casefold()
    detail = stderr.splitlines()[-1][:300] if stderr else f"exit {code}"
    if "robots" in lowered:
        return Blocked(f"robots.txt refused {url} ({detail})")
    if any(marker in lowered for marker in ("403", "forbidden", "401", "429", "too many requests")):
        return Blocked(f"{url} refused the request ({detail})")
    if any(marker in lowered for marker in ("timeout", "timed out", "deadline")):
        return Transient(f"{url} timed out ({detail})")
    if any(marker in lowered for marker in ("captcha", "challenge", "verify you are human")):
        return ChallengeDetected(f"{url} served a human-verification interstitial ({detail})")
    return Transient(f"obscura failed on {url} with exit {code}: {detail}")


# --------------------------------------------------------------------------
# playwright
# --------------------------------------------------------------------------

def _playwright():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:  # pragma: no cover - exercised by the doctor's blocker path
        raise DriverUnavailable(
            "Playwright is not installed in this interpreter. Install it with "
            "`uv sync --extra browser` and then `python -m playwright install chromium`."
        ) from None
    return sync_playwright


class PlaywrightDriver:
    """Chromium through Playwright: the authenticated engine, and the render fallback."""

    name = "playwright"

    def available(self) -> bool:
        try:
            _playwright()
        except DriverUnavailable:
            return False
        return True

    def _launch(self, playwright, *, headless: bool):
        return playwright.chromium.launch(
            headless=headless,
            args=["--disable-blink-features=AutomationControlled",
                  "--disable-dev-shm-usage"],
        )

    def _context(self, browser, fetch: Fetch, *, extra_headers: dict | None = None):
        options = {
            "viewport": {"width": 1280, "height": 900},
            "user_agent": fetch.user_agent or DEFAULT_USER_AGENT,
            "locale": "en-NZ",
            "timezone_id": "Pacific/Auckland",
            "ignore_https_errors": False,
        }
        if fetch.session_state:
            options["storage_state"] = fetch.session_state
        if extra_headers:
            options["extra_http_headers"] = extra_headers
        if fetch.stealth:
            # `bypass_csp` lets the init script and a solver's token survive a page
            # whose Content-Security-Policy would otherwise drop injected code.
            options["bypass_csp"] = True
        context = browser.new_context(**options)
        if fetch.stealth:
            from .challenge import STEALTH_INIT_SCRIPT
            context.add_init_script(STEALTH_INIT_SCRIPT)
        return context

    def capture(self, fetch: Fetch) -> Fetched:
        sync_playwright = _playwright()
        from playwright.sync_api import Error as PlaywrightError
        from playwright.sync_api import TimeoutError as PlaywrightTimeout

        started = time.monotonic()
        notes: list[str] = []
        challenge_record: dict = {}
        with sync_playwright() as playwright:
            browser = self._launch(playwright, headless=fetch.headless)
            try:
                context = self._context(browser, fetch)
                page = context.new_page()
                page.set_default_timeout(fetch.timeout_s * 1000)
                try:
                    response = page.goto(fetch.url, wait_until=fetch.wait_until,
                                         timeout=fetch.timeout_s * 1000)
                except PlaywrightTimeout as exc:
                    raise Transient(f"Chromium timed out loading {fetch.url}: {exc}".splitlines()[0]) from None
                status = response.status if response is not None else None
                if status in (401, 403, 407, 429):
                    raise Blocked(f"{fetch.url} answered {status}")

                # An interstitial that clears itself is not a wall; it is a page that
                # needed time. Waiting is the first answer under every policy except
                # `block`, and it is what makes a visible window useful.
                from .challenge import clear_waiter, solve
                from .extract import challenge_marker, text as page_text
                marker = _page_challenge(page, challenge_marker, page_text)
                if marker:
                    challenge_record = {"detected": marker, "stealth": fetch.stealth,
                                        "headless": fetch.headless, "attempt": "wait"}
                    if fetch.await_clear_s:
                        cleared, waited, reason = clear_waiter(
                            page, seconds=fetch.await_clear_s,
                            selector=fetch.selector)
                        challenge_record.update({"waited_s": waited, "wait_reason": reason,
                                                 "cleared": cleared})
                        marker = None if cleared else _page_challenge(page, challenge_marker, page_text)
                    if marker and fetch.solve:
                        outcome = solve(page, url=page.url)
                        challenge_record["solver"] = outcome
                        if outcome.get("solved"):
                            cleared, waited, reason = clear_waiter(page, seconds=20.0)
                            challenge_record.update({"waited_s": waited, "wait_reason": reason,
                                                     "cleared": cleared})
                            marker = None if cleared else _page_challenge(
                                page, challenge_marker, page_text)
                    if marker:
                        challenge_record.setdefault("cleared", False)

                if fetch.selector:
                    try:
                        page.wait_for_selector(fetch.selector, timeout=fetch.timeout_s * 1000)
                    except PlaywrightTimeout:
                        notes.append(f"selector {fetch.selector!r} never appeared; "
                                     "the text below is whatever did render")
                html = page.content()
                title = page.title()
                final_url = page.url
                if fetch.screenshot:
                    fetch.screenshot.parent.mkdir(parents=True, exist_ok=True)
                    page.screenshot(path=str(fetch.screenshot), full_page=True)
                context.close()
            except PlaywrightError as exc:
                raise Transient(f"Chromium failed on {fetch.url}: {str(exc).splitlines()[0]}") from None
            finally:
                browser.close()
        elapsed = int((time.monotonic() - started) * 1000)
        return Fetched(url=fetch.url, final_url=final_url, status=status, html=html,
                       title=title, driver=self.name, elapsed_ms=elapsed,
                       screenshot=str(fetch.screenshot) if fetch.screenshot else None,
                       session_used=bool(fetch.session_state), challenge=challenge_record,
                       notes=notes)

    def sign_in(self, *, url: str, store, source: str, success_selector: str = "",
                timeout_s: float = 180.0, headless: bool = False,
                confirm=None, poll_seconds: float = 1.0) -> dict:
        """Open a visible window for the user's own sign-in, then store the result.

        Dossier types nothing and sees no credential: it opens the page, waits for
        the user to finish, and reads back the cookies the browser was given. The
        wait ends on `success_selector` appearing, on `confirm()` returning, or on
        `timeout_s` — whichever comes first. A timeout saves nothing and says so.
        """
        sync_playwright = _playwright()
        from playwright.sync_api import Error as PlaywrightError

        if confirm is None and not success_selector:
            raise ScrapeError(
                "sign_in needs either a success selector or a confirm callable; without one "
                "there is no way to know the user has finished")

        state = None
        opened_at = time.monotonic()
        with sync_playwright() as playwright:
            browser = self._launch(playwright, headless=headless)
            try:
                context = browser.new_context(viewport={"width": 1280, "height": 900},
                                              user_agent=DEFAULT_USER_AGENT, locale="en-NZ")
                page = context.new_page()
                page.goto(url, wait_until="domcontentloaded",
                          timeout=min(timeout_s, 60) * 1000)
                done = False
                if confirm is not None:
                    confirm()
                    done = True
                else:
                    while time.monotonic() - opened_at < timeout_s:
                        try:
                            if page.query_selector(success_selector) is not None:
                                done = True
                                break
                        except PlaywrightError:
                            break
                        page.wait_for_timeout(int(poll_seconds * 1000))
                if done:
                    state = context.storage_state()
                context.close()
            finally:
                browser.close()

        if not state:
            raise AuthRequired(
                f"no sign-in detected at {url} within {timeout_s:g}s. Nothing was saved. "
                "Re-run and finish the sign-in in the window that opens.")
        return store.save(source, state, source_url=url, method="user-login",
                          label="signed in by the user in a visible browser window")


# --------------------------------------------------------------------------
# selection and capability reporting
# --------------------------------------------------------------------------

DRIVERS = {"obscura": ObscuraDriver, "playwright": PlaywrightDriver}


def available() -> dict[str, dict]:
    """Both engines, without starting either."""
    report: dict[str, dict] = {}
    binary = obscura_path()
    report["obscura"] = {
        "available": binary is not None,
        "path": str(binary) if binary else None,
        "version": obscura_version(binary) if binary else None,
        "sessions": False,
        "detail": ("fast public-page engine; obeys robots.txt by default" if binary
                   else "not installed; public captures fall back to Playwright"),
    }
    playwright_ok = PlaywrightDriver().available()
    report["playwright"] = {
        "available": playwright_ok,
        "path": None,
        "version": _playwright_version() if playwright_ok else None,
        "sessions": True,
        "detail": ("Chromium with saved sessions; install the browser with "
                   "`python -m playwright install chromium` if a launch fails"
                   if playwright_ok else
                   "not installed; authenticated capture is unavailable "
                   "(`uv sync --extra browser`)"),
    }
    return report


def _playwright_version() -> str | None:
    try:
        from playwright._impl._driver import compute_driver_executable  # noqa: F401
    except Exception:  # noqa: BLE001
        pass
    try:
        from importlib.metadata import version
        return version("playwright")
    except Exception:  # noqa: BLE001
        return None


def select(name: str = "auto", *, needs_session: bool = False) -> str:
    """Pick an engine, honouring an explicit choice and refusing a silent downgrade."""
    name = (name or "auto").strip().casefold()
    report = available()
    if name != "auto":
        if name not in DRIVERS:
            raise DriverUnavailable(f"unknown driver {name!r}; known: {', '.join(DRIVERS)}")
        if not report[name]["available"]:
            raise DriverUnavailable(f"driver {name!r} is not available: {report[name]['detail']}")
        if needs_session and not report[name]["sessions"]:
            raise DriverUnavailable(
                f"driver {name!r} cannot hold a session; use --driver playwright for an "
                "authenticated capture")
        return name
    if needs_session:
        if report["playwright"]["available"]:
            return "playwright"
        raise DriverUnavailable(
            "an authenticated capture needs Playwright, which is not installed here. "
            "Install it with `uv sync --extra browser`.")
    if report["obscura"]["available"]:
        return "obscura"
    if report["playwright"]["available"]:
        return "playwright"
    raise DriverUnavailable(
        "no browser engine is available. Install obscura (public pages) or run "
        "`uv sync --extra browser` for Playwright.")


def capture(fetch: Fetch, driver: str = "auto") -> Fetched:
    """Run one fetch through the selected engine."""
    chosen = select(driver, needs_session=bool(fetch.session_state))
    engine = DRIVERS[chosen]()
    result = engine.capture(fetch)
    marker = _challenge(fetch, result)
    if marker:
        record = dict(result.challenge or {})
        record["detected"] = record.get("detected") or marker
        record.setdefault("cleared", False)
        result.challenge = record
        raise ChallengeDetected(
            f"{result.url} served a human-verification interstitial ({marker!r})"
            + (f" after waiting {record['waited_s']:g}s" if record.get("waited_s") else "")
            + ". The policy in force decides the next step; the run records this.")
    if result.challenge:
        result.challenge.setdefault("cleared", True)
    return result


def _page_challenge(page, marker_fn, text_fn) -> str | None:
    """The interstitial phrase the live page is showing, if any."""
    try:
        html = page.content()
        title = page.title()
    except Exception:  # noqa: BLE001 - a navigating page is not a failure
        return None
    try:
        body = text_fn(html)[:2000]
    except Exception:  # noqa: BLE001
        body = ""
    return marker_fn(title, body)


def _challenge(fetch: Fetch, result: Fetched) -> str | None:
    from .extract import challenge_marker, text

    try:
        body = text(result.html)[:2000]
    except Exception:  # noqa: BLE001 - a broken page still gets the title check
        body = ""
    return challenge_marker(result.title or "", body)


__all__ = ["DEFAULT_USER_AGENT", "DRIVERS", "Fetch", "Fetched", "ObscuraDriver",
           "PlaywrightDriver", "available", "capture", "obscura_path", "obscura_version",
           "select"]
