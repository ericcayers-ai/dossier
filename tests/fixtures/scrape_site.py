"""A tiny local site that behaves like the awkward parts of a real board.

Used by `tests/test_scrape.py` and by a manual smoke run:

    python tests/fixtures/scrape_site.py --port 8765
    dossier scrape run --recipe local-listing --root <workspace>

It serves, on one origin:

* `/` — a listing with two items, wrapped in navigation and footer noise and a
  `<script>` body that must not reach the archive.
* `/job/1`, `/job/2` — detail pages with a requirements list.
* `/login` + `POST /login` — a real cookie-setting form, so "signed in" is a
  cookie and not a flag a test can fake.
* `/auto-login` — sets the same cookie and then shows `#signed-in`, so the sign-in wait
  can be exercised without a person.
* `/private/` — redirects to `/login` without the cookie, serves the listing with it.
* `/dynamic` — a page whose content is written by JavaScript after load.
* `/robots.txt` — allows `/job/`, disallows `/blocked/`.
* `/blocked/page` — a 403.
* `/challenge` — a "Just a moment" interstitial.
* `/challenge-clears` — an interstitial that stops being one after ~1.2 s.
* `/slow` — answers after five seconds, for the timeout path.

Standard library only: a fixture that needs an install is a fixture that fails on
a clean machine.
"""

from __future__ import annotations

import argparse
import threading
import time
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

LISTING = """<!doctype html><html><head><title>Open roles</title></head><body>
<nav><a href="/">Home</a> <a href="/jobs">Jobs</a> <a href="/about">About</a>
  <a rel="next" href="/page/2">Next page</a></nav>
<header><h1>Open roles</h1></header>
<main>
  <article class="card">
    <h2><a href="/job/1">Senior Engineer</a></h2>
    <span class="company">Acme</span> <span class="location">Hamilton</span>
    <span class="salary">$120,000</span>
    <p>Build the platform.</p>
  </article>
  <article class="card">
    <h2><a href="/job/2">Data Analyst</a></h2>
    <span class="company">Beta</span> <span class="location">Remote</span>
    <p>Explain the numbers.</p>
  </article>
</main>
<footer>&copy; Fixture Ltd. Cookie preferences. Subscribe to our newsletter.</footer>
<script>window.tracker = "not posting text";</script>
</body></html>"""

LISTING_PAGE_2 = """<!doctype html><html><head><title>Open roles - page 2</title></head><body>
<main>
  <article class="card"><h2><a href="/job/3">Platform Engineer</a></h2>
    <span class="company">Gamma</span> <span class="location">Auckland</span></article>
</main>
</body></html>"""

PRIVATE_LISTING = """<!doctype html><html><head><title>Members only roles</title></head><body>
<main>
  <article class="card"><h2><a href="/job/9">Insider Role</a></h2>
    <span class="company">Secretive</span> <span class="location">Wellington</span></article>
</main></body></html>"""

JOB = """<!doctype html><html><head><title>{title} at {company}</title></head><body>
<nav><a href="/">Home</a></nav>
<main>
  <h1>{title}</h1>
  <p class="company">{company} - {location}</p>
  <p>We are hiring a {title}.</p>
  <h2>Requirements</h2>
  <ul><li>Python</li><li>SQL</li><li>Clear writing</li></ul>
</main>
<footer>Apply through the fixture. Newsletter.</footer>
</body></html>"""

LOGIN = """<!doctype html><html><head><title>Sign in</title></head><body>
<main><h1>Sign in</h1>
<form method="post" action="/login">
  <label>Email <input name="email"></label>
  <label>Password <input name="password" type="password"></label>
  <button type="submit">Sign in</button>
</form></main></body></html>"""

#: A page that signs itself in, so the `sign_in` wait can be exercised without a
#: person. It sets the same cookie the real form does, and only then shows the
#: element the wait is looking for.
AUTO_LOGIN = """<!doctype html><html><head><title>Signing in</title></head><body>
<main id="waiting"><p>Signing you in…</p></main>
<script>
setTimeout(function () {
  document.cookie = 'session=ok; path=/';
  document.getElementById('waiting').innerHTML = '<div id="signed-in">Signed in</div>';
}, 300);
</script></body></html>"""

DYNAMIC = """<!doctype html><html><head><title>Dynamic role</title></head><body>
<main><h1>Dynamic role</h1><div id="slot">Loading…</div>
<script>
setTimeout(function () {
  document.getElementById('slot').textContent =
    'Rendered by JavaScript: Rust, Playwright and a requirements list.';
}, 400);
</script></main></body></html>"""

CHALLENGE = """<!doctype html><html><head><title>Just a moment...</title></head><body>
<h1>Checking your browser before accessing the site</h1>
<p>Verify you are human.</p></body></html>"""

#: A check that passes on its own: the interstitial is real, and so is its resolution.
CHALLENGE_CLEARS = """<!doctype html><html><head><title>Just a moment...</title></head><body>
<main id="slot"><h1>Checking your browser before accessing the site</h1></main>
<script>
setTimeout(function () {
  document.title = 'Clear of the check';
  document.getElementById('slot').innerHTML =
    '<h1>Clear of the check</h1><p>Senior Engineer at Acme. Requirements: Python.</p>';
}, 1200);
</script></body></html>"""

ROBOTS = "User-agent: *\nDisallow: /blocked/\nAllow: /\n"


class Handler(BaseHTTPRequestHandler):
    server_version = "DossierFixture/1.0"

    def log_message(self, *args):  # keep the test output clean
        return

    # -- helpers ----------------------------------------------------------
    def _send(self, body: str, status: int = 200, headers: dict | None = None) -> None:
        payload = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        for name, value in (headers or {}).items():
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(payload)

    def _redirect(self, location: str, cookie: str | None = None) -> None:
        self.send_response(303)
        self.send_header("Location", location)
        if cookie:
            self.send_header("Set-Cookie", cookie)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _cookie(self) -> str:
        raw = self.headers.get("Cookie", "")
        jar = SimpleCookie()
        try:
            jar.load(raw)
        except Exception:  # noqa: BLE001
            return ""
        return jar["session"].value if "session" in jar else ""

    # -- routes -----------------------------------------------------------
    def do_GET(self):  # noqa: N802 - http.server's contract
        path = self.path.split("?")[0].rstrip("/") or "/"
        self.server.requests.append(path)  # type: ignore[attr-defined]

        if path == "/robots.txt":
            payload = ROBOTS.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
        if path == "/":
            return self._send(LISTING)
        if path == "/page/2":
            return self._send(LISTING_PAGE_2)
        if path.startswith("/job/"):
            number = path.rsplit("/", 1)[-1]
            titles = {"1": ("Senior Engineer", "Acme", "Hamilton"),
                      "2": ("Data Analyst", "Beta", "Remote"),
                      "3": ("Platform Engineer", "Gamma", "Auckland"),
                      "9": ("Insider Role", "Secretive", "Wellington")}
            title, company, location = titles.get(number, ("Role " + number, "Acme", "Remote"))
            return self._send(JOB.format(title=title, company=company, location=location))
        if path == "/login":
            return self._send(LOGIN)
        if path == "/auto-login":
            return self._send(AUTO_LOGIN)
        if path == "/private" or path == "/private/listing":
            if self._cookie() == "ok":
                return self._send(PRIVATE_LISTING)
            return self._redirect("/login")
        if path == "/private-after-login":
            if self._cookie() == "ok":
                return self._send(PRIVATE_LISTING)
            return self._redirect("/login")
        if path == "/dynamic":
            return self._send(DYNAMIC)
        if path == "/challenge":
            return self._send(CHALLENGE, status=200)
        if path == "/challenge-clears":
            return self._send(CHALLENGE_CLEARS, status=200)
        if path.startswith("/blocked"):
            return self._send("<html><body>Forbidden</body></html>", status=403)
        if path == "/slow":
            time.sleep(5)
            return self._send("<html><body><main><p>Slow but fine.</p></main></body></html>")
        if path == "/boom":
            return self._send("<html><body>Server error</body></html>", status=500)
        return self._send("<html><body><main><p>Not found.</p></main></body></html>", status=404)

    def do_POST(self):  # noqa: N802
        path = self.path.split("?")[0].rstrip("/") or "/"
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length).decode("utf-8", "replace") if length else ""
        if path == "/login":
            # A fixture login is a cookie. No credential is read, stored or echoed.
            self.server.logins.append(body[:200])  # type: ignore[attr-defined]
            return self._redirect("/private", cookie="session=ok; Path=/; HttpOnly")
        return self._send("<html><body>Not found</body></html>", status=404)


class FixtureSite:
    """A running fixture: `with FixtureSite() as site: site.base`."""

    def __init__(self, port: int = 0, host: str = "127.0.0.1"):
        self.httpd = ThreadingHTTPServer((host, port), Handler)
        self.httpd.requests = []  # type: ignore[attr-defined]
        self.httpd.logins = []  # type: ignore[attr-defined]
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)

    @property
    def base(self) -> str:
        host, port = self.httpd.server_address[:2]
        return f"http://{host}:{port}"

    @property
    def requests(self) -> list[str]:
        return self.httpd.requests  # type: ignore[attr-defined]

    @property
    def logins(self) -> list[str]:
        return self.httpd.logins  # type: ignore[attr-defined]

    def __enter__(self) -> "FixtureSite":
        self.thread.start()
        return self

    def __exit__(self, *exc) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=5)


def serve(port: int = 0) -> FixtureSite:
    return FixtureSite(port)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Dossier capture fixture site")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    site = serve(args.port).__enter__()
    print(f"fixture listening on {site.base} - Ctrl+C to stop")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        site.__exit__()
