"""Challenge handling, made explicit instead of forbidden.

The earlier rule was "a challenge is a blocker": detect it, stop, report. That is the
right default for an unattended crawl, and the wrong one for an owner who is sitting in
front of the machine, authorised on the site, and asking for the page. So the policy is
now a decision the workspace records, with the answer used written into every run:

| policy | what happens |
|---|---|
| `block` | detect, stop, report (the old behaviour) |
| `await` | keep the page open and poll: many interstitials clear on their own once the check passes |
| `stealth` | retry once with a stealth context (no `navigator.webdriver`, real UA/locale/timezone, `bypass_csp`) |
| `stealth-await` | stealth, then wait |
| `solve` | call the configured solver service and inject the returned token |
| `auto` (default) | plain → stealth+await → visible window for the user → solver, if configured → report |

What stays true under every policy: the run **records** what it detected, which policy it
applied, and whether the challenge cleared. Nothing here hides a refusal behind an empty
result, and nothing types a credential. `auto` still ends with an honest blocker when the
page never becomes readable.

Stealth is a browser configuration, not a promise: it removes the signals a page can read
(`navigator.webdriver`, missing plugin/language shims, headless UA) and it reuses the saved
session if there is one. It cannot make a real sign-in unnecessary, and it does not claim
to.

The solver is a paid third-party service. It is never used by `auto` unless a key is
present in the environment, it is never used at all without `"solve"` in the policy, and
the key is read from the environment only — never written to a repo or a workspace file.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from urllib.parse import urlparse

POLICIES = ("block", "await", "stealth", "stealth-await", "solve", "auto")
DEFAULT_POLICY = "auto"
CONFIG_FILE = ".dossier/scrape.json"

#: Environment variables the solver reads. A key in a workspace file would be a
#: credential in a folder that gets copied, zipped and handed to another session.
ENV_SOLVER_KEY = "DOSSIER_SOLVER_KEY"
ENV_SOLVER_URL = "DOSSIER_SOLVER_URL"
DEFAULT_SOLVER_URL = "https://2captcha.com"

#: How long a page is polled for the interstitial to clear, per phase.
AWAIT_SECONDS_HEADLESS = 12.0
AWAIT_SECONDS_HEADED = 90.0

#: Stealth is a context, not a disguise: these are the properties a page reads to tell
#: an automated browser from a person's. Kept to signals this project can justify.
STEALTH_INIT_SCRIPT = """
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
Object.defineProperty(navigator, 'languages', {get: () => ['en-NZ', 'en']});
Object.defineProperty(navigator, 'platform', {get: () => 'Win32'});
Object.defineProperty(navigator, 'hardwareConcurrency', {get: () => 8});
Object.defineProperty(navigator, 'deviceMemory', {get: () => 8});
Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
window.chrome = window.chrome || {runtime: {}, app: {isInstalled: false}};
const originalQuery = window.navigator.permissions && window.navigator.permissions.query;
if (originalQuery) {
  window.navigator.permissions.query = (parameters) => (
    parameters && parameters.name === 'notifications'
      ? Promise.resolve({state: Notification.permission})
      : originalQuery(parameters)
  );
}
"""


class ChallengePolicyError(ValueError):
    """An unknown policy name, or a solver request with no solver configured."""


def _workspace_config(root: Path | str | None) -> dict:
    if root is None:
        return {}
    try:
        data = json.loads((Path(root) / CONFIG_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def configured_policy(root: Path | str | None = None, source: str = "") -> str:
    """The workspace's declared policy for a board, else the global one, else `auto`."""
    table = _workspace_config(root)
    per_source = table.get("sources") if isinstance(table.get("sources"), dict) else {}
    entry = per_source.get((source or "").casefold()) if source else None
    candidate = (entry or {}).get("challenge") if isinstance(entry, dict) else None
    if candidate is None:
        candidate = table.get("challenge")
    return candidate if candidate in POLICIES else DEFAULT_POLICY


def effective_policy(root: Path | str | None = None, source: str = "", *,
                     override: str | None = None, recipe_policy: str | None = None) -> str:
    """Argument, then recipe, then workspace file, then default."""
    for candidate in (override, recipe_policy):
        if candidate in (None, "", "auto"):
            if candidate == "auto":
                return "auto"
            continue
        if candidate not in POLICIES:
            raise ChallengePolicyError(
                f"unknown challenge policy {candidate!r}; known: {', '.join(POLICIES)}")
        return candidate
    return configured_policy(root, source)


def allow_visible(root: Path | str | None = None) -> bool:
    """Whether `auto` may open a visible window and wait for a person.

    Off by default because it blocks a headless run for `AWAIT_SECONDS_HEADED` on a
    challenge that will never clear by itself. Turn it on with `{"visible": true}`
    in `.dossier/scrape.json`, or per run with `--headed`.
    """
    value = _workspace_config(root).get("visible")
    return value if isinstance(value, bool) else False


def solver_config() -> dict:
    """The solver's URL and whether a key exists. The key value is never returned."""
    key = os.environ.get(ENV_SOLVER_KEY, "").strip()
    url = os.environ.get(ENV_SOLVER_URL, "").strip() or DEFAULT_SOLVER_URL
    return {"configured": bool(key), "url": url.rstrip("/"),
            "key_env": ENV_SOLVER_KEY, "provider": urlparse(url).hostname or url}


def describe(root: Path | str | None = None) -> dict:
    """What a receipt can show about the policy in force."""
    table = _workspace_config(root)
    return {
        "default": DEFAULT_POLICY,
        "configured": configured_policy(root),
        "policies": list(POLICIES),
        "config_file": CONFIG_FILE,
        "solver": {key: value for key, value in solver_config().items() if key != "key"},
        "await_seconds": {"headless": AWAIT_SECONDS_HEADLESS, "headed": AWAIT_SECONDS_HEADED},
        "rule": ("A challenge is answered by the policy this workspace configured, and the "
                 "run records the detection, the policy applied and whether it cleared. "
                 "`auto` never hides a page that stayed unreadable."),
    }


# --------------------------------------------------------------------------
# the browser half: clearing a challenge that clears itself, and stealth
# --------------------------------------------------------------------------

def clear_waiter(page, *, seconds: float, poll: float = 0.75, selector: str = ""):
    """Poll a Playwright page until the interstitial is gone or `seconds` runs out.

    Returns `(cleared, waited_seconds, reason)`. This is patience, not evasion: a
    Cloudflare-style check that passes on its own is a page that simply needed time,
    and an owner sitting in front of a visible window can also complete a real one.

    Deliberately knows nothing about how a challenge is solved. It watches the page
    it was given and reports what happened.
    """
    from .extract import challenge_marker, text

    started = time.monotonic()
    waited = 0.0
    while True:
        try:
            if selector:
                if page.query_selector(selector) is not None:
                    return True, round(time.monotonic() - started, 1), f"selector {selector!r} appeared"
                    # noqa: unreachable - kept for symmetry with the marker path
            html = page.content()
            title = page.title()
            try:
                body = text(html)[:2000]
            except Exception:  # noqa: BLE001
                body = ""
            marker = challenge_marker(title, body)
            if marker is None:
                return True, round(time.monotonic() - started, 1), "the interstitial cleared"
        except Exception:  # noqa: BLE001 - a navigating page is not a failure
            pass
        if time.monotonic() - started >= seconds:
            return False, round(time.monotonic() - started, 1), "the interstitial never cleared"
        try:
            page.wait_for_timeout(int(poll * 1000))
        except Exception:  # noqa: BLE001
            time.sleep(poll)


def inject_token(page, token: str, kind: str = "turnstile") -> bool:
    """Put a solver token where the page expects it, and submit the nearest form.

    A token is only useful if the page reads it: Turnstile uses a hidden
    `cf-turnstile-response` input, reCAPTCHA uses `g-recaptcha-response`. If neither
    exists the injection reports False rather than pretending it worked.
    """
    script = """
    (args) => {
      const [token, kind] = args;
      const names = kind === 'recaptcha'
        ? ['g-recaptcha-response']
        : ['cf-turnstile-response', 'g-recaptcha-response'];
      let placed = false;
      for (const name of names) {
        let field = document.querySelector(`[name="${name}"]`);
        if (!field) {
          field = document.createElement('textarea');
          field.name = name;
          field.style.display = 'none';
          (document.querySelector('form') || document.body).appendChild(field);
        }
        field.value = token;
        field.dispatchEvent(new Event('input', {bubbles: true}));
        placed = true;
      }
      const form = document.querySelector('form');
      if (form) { form.submit(); }
      return placed;
    }
    """
    try:
        return bool(page.evaluate(script, [token, kind]))
    except Exception:  # noqa: BLE001 - a page that reloaded mid-injection is not a crash
        return False


def sitekey_of(page) -> str:
    """The challenge's site key, from the widget element or its iframe URL."""
    script = """
    () => {
      const node = document.querySelector('[data-sitekey]');
      if (node && node.getAttribute('data-sitekey')) return node.getAttribute('data-sitekey');
      for (const frame of Array.from(document.querySelectorAll('iframe'))) {
        const src = frame.src || '';
        const match = src.match(/[?&](?:k|sitekey)=([^&]+)/);
        if (match) return decodeURIComponent(match[1]);
      }
      return '';
    }
    """
    try:
        return str(page.evaluate(script) or "")
    except Exception:  # noqa: BLE001
        return ""


def solve(page, *, url: str, seconds: float = 120.0, poll: float = 5.0, http=None) -> dict:
    """Ask the configured solver for a token and inject it.

    Returns a record, never raises: a solver outage must surface as "not solved" in the
    run, not as a traceback that loses the page. Only reached when the policy is
    `solve`, or when `auto` found a configured solver after the other phases failed.
    """
    config = solver_config()
    if not config["configured"]:
        return {"solved": False,
                "reason": f"no solver key: set {ENV_SOLVER_KEY} in the environment to use `solve`"}
    sitekey = sitekey_of(page)
    if not sitekey:
        return {"solved": False, "reason": "the page exposes no site key; there is nothing to solve"}
    kind = "recaptcha" if "recaptcha" in sitekey.lower() else "turnstile"

    if http is None:
        import httpx
        http = httpx

    key = os.environ.get(ENV_SOLVER_KEY, "").strip()
    try:
        created = http.post(f"{config['url']}/createTask", json={
            "clientKey": key,
            "task": {"type": "TurnstileTaskProxyless" if kind == "turnstile" else "RecaptchaV2TaskProxyless",
                     "websiteURL": url, "websiteKey": sitekey},
        }, timeout=30).json()
    except Exception as exc:  # noqa: BLE001
        return {"solved": False, "reason": f"the solver could not be reached: {type(exc).__name__}"}
    task_id = str((created or {}).get("taskId") or "")
    if not task_id:
        return {"solved": False, "reason": f"the solver refused the task: {str(created)[:200]}"}

    deadline = time.monotonic() + seconds
    token = ""
    while time.monotonic() < deadline:
        time.sleep(poll)
        try:
            polled = http.post(f"{config['url']}/getTaskResult",
                               json={"clientKey": key, "taskId": task_id}, timeout=30).json()
        except Exception:  # noqa: BLE001
            continue
        status = str((polled or {}).get("status", ""))
        if status == "ready":
            token = str(((polled or {}).get("solution") or {}).get("token")
                        or ((polled or {}).get("solution") or {}).get("gRecaptchaResponse") or "")
            break
        if status not in {"processing", "ready", ""}:
            return {"solved": False, "reason": f"the solver reported {status}: {str(polled)[:160]}"}
    if not token:
        return {"solved": False, "reason": f"no token within {seconds:g}s"}
    placed = inject_token(page, token, kind)
    return {"solved": placed, "kind": kind, "reason": "token injected" if placed else
            "the token was returned but the page had no field for it"}


__all__ = ["AWAIT_SECONDS_HEADED", "AWAIT_SECONDS_HEADLESS", "CONFIG_FILE",
           "ChallengePolicyError", "DEFAULT_POLICY", "ENV_SOLVER_KEY", "ENV_SOLVER_URL",
           "POLICIES", "STEALTH_INIT_SCRIPT", "allow_visible", "clear_waiter",
           "configured_policy", "describe", "effective_policy", "inject_token",
           "sitekey_of", "solve", "solver_config"]
