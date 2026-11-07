from dataclasses import dataclass

# The policy table and its single predicate both live in `engine.sources`. Two
# copies of the fetchable set is the drift docs/LESSONS.md warns about: this
# module used to treat `manual_only` as prohibited while `engine.sources.allowed`
# treated only `prohibited` as blocked, so the ledger and the guard could
# disagree about the same board. Nothing is restated here — the set below is
# derived from the one table, and the guard asks the one predicate.
from .engine.sources import FETCHABLE_POLICIES, POLICIES, SourceRefused, assert_allowed

PROHIBITED = {name for name, entry in POLICIES.items()
              if entry["policy"] not in FETCHABLE_POLICIES}
ENDPOINTS = {
    "greenhouse": "https://boards-api.greenhouse.io/v1/boards/{board}/jobs",
    "lever": "https://api.lever.co/v0/postings/{site}?mode=json",
    "ashby": "https://api.ashbyhq.com/posting-api/job-board/{board}",
    "himalayas": "https://himalayas.app/jobs/api",
    "remotive": "https://remotive.com/api/remote-jobs",
    "arbeitnow": "https://www.arbeitnow.com/api/job-board-api",
    "remoteok": "https://remoteok.com/api",
    "jobicy": "https://jobicy.com/api/v2/remote-jobs",
    "weworkremotely": "https://weworkremotely.com/categories/remote-programming-jobs.rss",
}


@dataclass
class Job:
    id: str
    title: str
    company: str
    location: str = ""
    url: str = ""
    source: str = ""
    description: str = ""
    work_type: str = ""
    pay: str = ""


#: One exception type for a refused fetch. The old name is kept as an alias so
#: `except FeedPolicyError` in a caller still catches what the guard raises.
FeedPolicyError = SourceRefused


class FeedAdapter:
    policy = "official_public"
    source = ""
    endpoint = ""
    #: What the endpoint returns. Only WeworkRemotely is XML; the base case is JSON.
    format = "json"

    def __init__(self, http=None, root=None):
        self.http = http
        self.root = root

    def fetch(self, *args, **kwargs):
        # The fetch boundary asks the same predicate the ledger reports from,
        # before the client is touched, so neither half can drift.
        assert_allowed(self.source, self.root)
        if not self.http:
            raise RuntimeError("HTTP client required")
        return self.parse(self.http(*args, **kwargs))

    def parse(self, data):
        return []


def _jobs(items, source):
    records = []
    for item in items:
        if not isinstance(item, dict):
            continue
        location = item.get("location", item.get("locations", ""))
        if isinstance(location, list):
            location = ", ".join(str(x) for x in location)
        elif isinstance(location, dict):
            # Greenhouse answers `location: {name: "Hamilton"}`; `str(dict)` in a
            # corpus row is a location nobody can filter on.
            location = location.get("name") or location.get("label") or ""
        records.append(Job(
            str(item.get("id", item.get("job_id", ""))),
            str(item.get("title", item.get("name", ""))),
            str(item.get("company", item.get("company_name", ""))),
            str(location),
            str(item.get("url", item.get("absolute_url", item.get("apply_url", "")))),
            source,
            str(item.get("description", "")),
            str(item.get("work_type", item.get("employment_type", ""))),
            str(item.get("salary", item.get("compensation", ""))),
        ))
    return records


class Greenhouse(FeedAdapter):
    source, endpoint = "greenhouse", ENDPOINTS["greenhouse"]
    def parse(self, data): return _jobs(data.get("jobs", data) if isinstance(data, (dict, list)) else [], self.source)


class Lever(FeedAdapter):
    source, endpoint = "lever", ENDPOINTS["lever"]
    def parse(self, data): return _jobs(data if isinstance(data, list) else [], self.source)


class Ashby(FeedAdapter):
    source, endpoint = "ashby", ENDPOINTS["ashby"]
    def parse(self, data): return _jobs(data.get("jobs", data) if isinstance(data, (dict, list)) else [], self.source)


class Himalayas(FeedAdapter):
    source, endpoint = "himalayas", ENDPOINTS["himalayas"]
    def parse(self, data): return _jobs(data.get("jobs", data) if isinstance(data, (dict, list)) else [], self.source)


class Remotive(FeedAdapter):
    source, endpoint = "remotive", ENDPOINTS["remotive"]
    def parse(self, data): return _jobs(data.get("jobs", []) if isinstance(data, dict) else [], self.source)


class Arbeitnow(FeedAdapter):
    source, endpoint = "arbeitnow", ENDPOINTS["arbeitnow"]
    def parse(self, data): return _jobs(data.get("data", data) if isinstance(data, (dict, list)) else [], self.source)


class RemoteOK(FeedAdapter):
    """Remote OK publishes the whole board as one JSON array.

    The first element is a legal notice with no `position`, not a job; keeping it
    put a blank row in every corpus that ever ingested this feed.
    """

    source, endpoint = "remoteok", ENDPOINTS["remoteok"]

    def parse(self, data):
        items = data if isinstance(data, list) else data.get("jobs", []) if isinstance(data, dict) else []
        records = []
        for item in items:
            if not isinstance(item, dict) or not item.get("position"):
                continue
            pay = ""
            low, high = item.get("salary_min"), item.get("salary_max")
            if low or high:
                pay = f"{low or '?'}-{high or '?'} {item.get('salary_currency') or ''}".strip()
            records.append(Job(
                str(item.get("id", item.get("slug", ""))),
                str(item.get("position", "")),
                str(item.get("company", "")),
                str(item.get("location") or "Remote"),
                str(item.get("url", item.get("apply_url", ""))),
                self.source,
                str(item.get("description", "")),
                "remote",
                pay,
            ))
        return records


class Jobicy(FeedAdapter):
    source, endpoint = "jobicy", ENDPOINTS["jobicy"]

    def parse(self, data):
        items = data.get("jobs", []) if isinstance(data, dict) else []
        records = []
        for item in items:
            if not isinstance(item, dict):
                continue
            kinds = item.get("jobType") or []
            work_type = ", ".join(str(kind) for kind in kinds) if isinstance(kinds, list) else str(kinds)
            salary = ""
            low, high = item.get("annualSalaryMin"), item.get("annualSalaryMax")
            if low or high:
                salary = f"{low or '?'}-{high or '?'} {item.get('salaryCurrency') or ''}".strip()
            records.append(Job(
                str(item.get("id", "")), str(item.get("jobTitle", "")),
                str(item.get("companyName", "")), str(item.get("jobGeo") or "Remote"),
                str(item.get("url", "")), self.source,
                str(item.get("jobDescription") or item.get("jobExcerpt") or ""),
                work_type, salary))
        return records


class WeWorkRemotely(FeedAdapter):
    """RSS, parsed with `defusedxml` rather than an XML library that resolves entities.

    A feed is third-party input; an XML parser with entity expansion is a way for a
    fetched document to read local files. `defusedxml` is already a dependency for
    exactly this reason.
    """

    source, endpoint, format = "weworkremotely", ENDPOINTS["weworkremotely"], "xml"

    def parse(self, data):
        from defusedxml.ElementTree import fromstring

        text = data if isinstance(data, (str, bytes)) else ""
        if not text:
            return []
        try:
            root = fromstring(text)
        except Exception:  # noqa: BLE001 - a malformed feed is an empty feed, not a crash
            return []
        records = []
        for item in root.iter("item"):
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            company, _, role = title.partition(": ")
            region = (item.findtext("region") or "Remote").strip()
            description = item.findtext("description") or ""
            if not link:
                continue
            records.append(Job(link.rsplit("/", 1)[-1], role.strip() or title,
                               company.strip(), region, link, self.source,
                               description, "remote", ""))
        return records


class Prohibited(FeedAdapter):
    """A board with no public read-only adapter, refused at the fetch boundary."""

    policy = "prohibited"

    def __init__(self, source, http=None, root=None):
        super().__init__(http=http, root=root)
        self.source = source

    def fetch(self, *args, **kwargs):
        # Two distinct refusals, so the message names the real reason: the
        # workspace policy forbids the board, or no public adapter exists for it.
        assert_allowed(self.source, self.root)
        raise FeedPolicyError(
            f"{self.source} has no public read-only adapter in Dossier, so it cannot be "
            "fetched automatically. Use a user-supplied posting or a licensed source."
        )


ADAPTERS = {cls.source: cls for cls in (Greenhouse, Lever, Ashby, Himalayas, Remotive,
                                       Arbeitnow, RemoteOK, Jobicy, WeWorkRemotely)}

#: Adapters whose endpoint needs a board or site slug substituted into it.
BOARD_PLACEHOLDERS = ("greenhouse", "lever", "ashby")


def endpoint_for(source: str, board: str = "") -> str:
    """The URL one board is fetched from, with the slug filled in.

    A board-scoped adapter with no slug used to raise a bare `KeyError` from
    `str.format`, which is unreadable at a command line. Naming the requirement is
    the difference between "this is broken" and "this needs `--board`".
    """
    name = (source or "").strip().casefold()
    if name not in ADAPTERS:
        raise ValueError(f"unknown feed {source!r}; known: {', '.join(sorted(ADAPTERS))}")
    template = ENDPOINTS[name]
    if "{" in template:
        slug = (board or "").strip()
        if not slug:
            raise ValueError(f"{name} needs --board <slug>: {template}")
        return template.format(board=slug, site=slug)
    return template


def fetch_board(source: str, *, board: str = "", http=None, root=None,
                timeout: float = 30.0) -> dict:
    """Fetch one public board and hand back its records as corpus rows.

    This is the first capture layer: a documented read-only JSON endpoint, no
    browser and no session. The policy guard runs inside `FeedAdapter.fetch`,
    before the client is touched, so a prohibited or manual-only board is refused
    with the same predicate the ledger reports from.
    """
    name = (source or "").strip().casefold()
    # Policy first: a prohibited board must be refused with the board's own reason,
    # not with "unknown feed", and before the client is constructed.
    from .engine import sources as source_engine
    source_engine.assert_allowed(name, root)
    url = endpoint_for(name, board)
    format_ = ADAPTERS[name].format
    close = None
    if http is None:
        import httpx
        client = httpx.Client(follow_redirects=True, timeout=timeout,
                              headers={"User-Agent": "Dossier/0.1 (+user-initiated job search)",
                                       "Accept": "application/rss+xml, application/json;q=0.9, */*;q=0.8"})
        close = client.close
        if format_ == "xml":
            http = lambda target: _text_or_error(client, target)  # noqa: E731
        else:
            http = lambda target: _json_or_error(client, target)  # noqa: E731
    try:
        jobs = adapter(name, http=http, root=root).fetch(url)
    finally:
        if close is not None:
            close()
    rows = [{"id": job.id, "title": job.title, "employer": job.company,
             "location": job.location, "url": job.url, "source": job.source,
             "description": job.description, "work_type": job.work_type,
             "pay": job.pay} for job in jobs]
    return {"source": name, "url": url, "records": len(rows), "jobs": rows}


def _json_or_error(client, url: str):
    """A JSON payload, or an error that names the status instead of a parse trace."""
    response = client.get(url)
    if response.status_code >= 400:
        raise RuntimeError(f"{url} answered {response.status_code}")
    try:
        return response.json()
    except ValueError as exc:
        raise RuntimeError(f"{url} did not return JSON: {exc}") from None


def _text_or_error(client, url: str) -> str:
    response = client.get(url)
    if response.status_code >= 400:
        raise RuntimeError(f"{url} answered {response.status_code}")
    return response.text



def adapter(name, http=None, root=None):
    normalized = name.casefold()
    if normalized in PROHIBITED:
        return Prohibited(normalized, http=http, root=root)
    if normalized not in ADAPTERS:
        raise ValueError("unknown feed")
    return ADAPTERS[normalized](http, root)
