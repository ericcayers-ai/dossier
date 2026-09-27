from dataclasses import dataclass

# Derived from the single policy table rather than restated as five names: two copies of this
# set is the drift docs/LESSONS.md warns about. The guard refuses everything the policy does
# not permit automated access to, so it is prohibited PLUS manual_only — not just the two
# `prohibited` boards. A per-workspace `.dossier/sources.json` can change the policy layer,
# but fetching still needs a real public adapter, which these boards do not have, so opening
# a policy never turns into silent scraping.
from .engine.sources import POLICIES

FETCHABLE_POLICIES = ("official_public", "partner_only")
PROHIBITED = {name for name, entry in POLICIES.items()
              if entry["policy"] not in FETCHABLE_POLICIES}
ENDPOINTS = {
    "greenhouse": "https://boards-api.greenhouse.io/v1/boards/{board}/jobs",
    "lever": "https://api.lever.co/v0/postings/{site}?mode=json",
    "ashby": "https://api.ashbyhq.com/posting-api/job-board/{board}",
    "himalayas": "https://himalayas.app/jobs/api",
    "remotive": "https://remotive.com/api/remote-jobs",
    "arbeitnow": "https://www.arbeitnow.com/api/job-board-api",
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


class FeedPolicyError(PermissionError):
    pass


class FeedAdapter:
    policy = "official_public"
    source = ""
    endpoint = ""

    def __init__(self, http=None):
        self.http = http

    def fetch(self, *args, **kwargs):
        if self.policy == "prohibited":
            raise FeedPolicyError(f"{self.source} is prohibited")
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


class Prohibited(FeedAdapter):
    policy = "prohibited"
    def __init__(self, source): self.source = source


ADAPTERS = {cls.source: cls for cls in (Greenhouse, Lever, Ashby, Himalayas, Remotive, Arbeitnow)}


def adapter(name, http=None):
    normalized = name.casefold()
    if normalized in PROHIBITED:
        return Prohibited(normalized)
    if normalized not in ADAPTERS:
        raise ValueError("unknown feed")
    return ADAPTERS[normalized](http)
