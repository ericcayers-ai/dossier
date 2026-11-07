"""Board-agnostic job corpus engine.

Every captured board lives in its own `<board>_data/` folder in one standard
layout, and the aggregate is derived from those parts — never hand-edited. The
engine owns identifier uniqueness, facet rebuilds, deduplication and the
three-tier fit carry-forward, all of which are arithmetic and therefore must
not be re-derived in prose by a model.

Two defects this code exists to prevent, both observed on real data:

* Boards reuse small ids across their own exports, so a pre-existing duplicate
  id survives a naive `setdefault`. A consumer that renders the corpus as a
  keyed list then keeps or drops the wrong rows after a filter changes the row
  count. Ids are therefore always reassigned sequentially.
* Several sources publish many distinct roles behind one listing URL. Keying a
  fit carry-forward on URL alone silently copies one posting's score onto
  unrelated rows, so a URL is only a key when it is unique in the ranking view.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from ..safety import trash_then_write_text

CAP = 20
FIT_ORDER = {"High": 0, "Medium": 1, "Low": 2, "Skip": 3, "unset": 4, "": 4}

FIT_FIELDS = (
    "fit", "fit_confidence", "fit_reason", "fit_override", "fit_override_reason",
    "draft_target", "existing_resume_coverage", "posting_status",
    "last_detail_check", "detail_evidence_file",
)

WORK_TYPE_ALIASES = {
    "fixed term": "Fixed Term/Temporary",
    "fixed-term": "Fixed Term/Temporary",
    "full time": "Permanent Full time",
    "full-time": "Permanent Full time",
    "part-time": "Part time",
}

_EMPTY = {"unknown", "not stated", "none", "null"}


# -- normalisation ---------------------------------------------------------

def pay_display(record: dict) -> str:
    amount, unit = record.get("pay_amount"), record.get("pay_unit")
    if amount is None:
        return record.get("pay_display", "Not stated")
    try:
        value = float(amount)
    except (TypeError, ValueError):
        return "Not stated"
    if unit == "annual":
        return f"${value:,.0f} per year"
    return f"${value:,.2f} per hour"


def pay_band(record: dict) -> str:
    unit, amount = record.get("pay_unit"), record.get("pay_amount")
    if amount is None:
        return "Not stated"
    try:
        value = float(amount)
    except (TypeError, ValueError):
        return "Not stated"
    if unit == "annual":
        return "$60k+ per year" if value >= 60000 else "Under $60k per year"
    if value < 25:
        return "Under $25/hr"
    if value < 27:
        return "$25-27/hr"
    if value < 29:
        return "$27-29/hr"
    if value < 30:
        return "$29-30/hr"
    return "$30/hr"


def work_type(record: dict) -> str:
    """Prefer a captured work type; derive one only from real signal.

    Labelling every sparse record "Casual" makes the facet meaningless, so an
    unresolved row reports "Not stated" rather than a guess.
    """
    existing = str(record.get("work_type") or "").strip()
    if existing and existing.casefold() not in _EMPTY:
        return WORK_TYPE_ALIASES.get(existing.casefold(), existing)
    title = (record.get("title") or "").casefold()
    hours = record.get("hours_per_week")
    unit = record.get("pay_unit")
    if any(word in title for word in ("intern", "summer student", "graduate")):
        return "Internship"
    if hours and hours >= 30 and unit == "annual":
        return "Permanent Full time"
    if unit == "annual":
        return "Fixed Term/Temporary"
    if hours and hours <= 2:
        return "One-off / Ad hoc"
    if "election" in title:
        return "Casual (Event-based)"
    if hours and hours < 30:
        return "Part time"
    if hours:
        return "Casual"
    return "Not stated"


def _facet(jobs: list[dict], key: str, label: str) -> list[dict]:
    counts = Counter((job.get(key) or "Unknown") for job in jobs)
    return [{label: name, "count": count} for name, count in counts.most_common(CAP)]


# -- urls and keys ---------------------------------------------------------

def norm_url(value: str) -> str:
    text = (value or "").strip().rstrip("/").casefold()
    for separator in ("?", "#"):
        text = text.split(separator, 1)[0]
    return text.rstrip("/")


def norm_pair(title: str, employer: str) -> str:
    return f"{(title or '').strip().casefold()}|{(employer or '').strip().casefold()}"


def norm_title(title: str) -> str:
    return (title or "").strip().casefold()


def dedupe(jobs: list[dict]) -> tuple[list[dict], dict]:
    """Drop repeats: same normalised URL, or same title+employer when no URL.

    A shared URL is the same posting, whatever employer string a particular
    capture happened to record — one board labels the employer "SEEK listing"
    where another names the real company, and both rows used to survive. Title
    plus employer is only used when there is no URL at all, since two genuinely
    distinct postings can share both ("Retail Assistant" at a large chain).
    """
    seen_urls: set[str] = set()
    seen_pairs: set[str] = set()
    kept: list[dict] = []
    dropped = Counter()
    for job in jobs:
        url = norm_url(job.get("url", ""))
        pair = norm_pair(job.get("title"), job.get("employer"))
        if url:
            if url in seen_urls:
                dropped["duplicate-url"] += 1
                continue
            seen_urls.add(url)
        elif pair in seen_pairs:
            dropped["duplicate-title-employer"] += 1
            continue
        seen_pairs.add(pair)
        kept.append(job)
    return kept, {"input": len(jobs), "kept": len(kept), "dropped": dict(dropped)}


# -- building --------------------------------------------------------------

def build_facets(jobs: list[dict], out_dir: Path, write_corpus: bool = True,
                 root: Path | str | None = None) -> dict:
    """Normalise a job list and (re)write the standard facet files.

    Returns a report rather than printing, so a caller can assert on the counts
    instead of trusting a log line.

    Every file here replaces a previous version of itself, so each one is
    written through `safety.trash_then_write_text`: an aggregate rebuilt in place
    with no trash copy is data loss on the user's canonical corpus, not a
    refresh. `root` is the workspace the trash belongs to; it defaults to the
    folder holding `out_dir`, which is how `combine` lays the aggregate out.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    trash_root = Path(root) if root is not None else out_dir.parent

    for index, job in enumerate(jobs, 1):
        job["id"] = index
        job["pay_display"] = pay_display(job)
        job["work_type"] = work_type(job)

    if write_corpus:
        trash_then_write_text(
            trash_root, out_dir / "all_jobs.json",
            json.dumps(jobs, indent=2, ensure_ascii=False))

    def dump(name: str, data) -> None:
        trash_then_write_text(
            trash_root, out_dir / name,
            json.dumps(data, indent=2, ensure_ascii=False))

    dump("industries.json", _facet(jobs, "industry", "industry"))
    dump("employers.json", _facet(jobs, "employer", "employer"))
    dump("locations.json", _facet(jobs, "location", "location"))
    dump("sub_classifications.json", _facet(jobs, "sub_classification", "sub_classification"))
    work_types = Counter(work_type(job) for job in jobs)
    dump("work_types.json", [{"work_type": k, "count": v} for k, v in work_types.most_common(CAP)])
    bands = Counter(pay_band(job) for job in jobs)
    dump("pay_bands.json", [{"pay_band": k, "count": v} for k, v in bands.most_common(CAP)])
    sources = Counter(str(job.get("source")) for job in jobs if job.get("source"))
    if sources:
        dump("sources.json", [{"source": k, "count": v} for k, v in sources.most_common()])

    ids = [job.get("id") for job in jobs]
    return {
        "folder": out_dir.name,
        "rows": len(jobs),
        "distinct_ids": len(set(ids)),
        "duplicate_ids": len(ids) - len(set(ids)),
        "sources": len(sources),
        "work_types": dict(work_types.most_common(CAP)),
        "pay_bands": dict(bands.most_common(CAP)),
        "unknown_employers": sum(1 for job in jobs if not (job.get("employer") or "").strip()),
    }


def board_folders(root: Path) -> list[Path]:
    """Every `<board>_data/` folder under a workspace that holds a corpus."""
    return sorted(
        path.parent for path in Path(root).glob("*_data/all_jobs.json")
        if path.parent.name != "all_boards_data"
    )


def combine(root: Path | str, out_name: str = "all_boards_data") -> dict:
    """Merge every board folder into one aggregate with the same layout."""
    root = Path(root)
    folders = board_folders(root)
    merged: list[dict] = []
    parts: list[dict] = []
    for folder in folders:
        try:
            records = json.loads((folder / "all_jobs.json").read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            parts.append({"board": folder.name, "error": str(exc)})
            continue
        if not isinstance(records, list):
            parts.append({"board": folder.name, "error": "all_jobs.json is not a list"})
            continue
        board = folder.name.replace("_data", "")
        for record in records:
            if isinstance(record, dict):
                record["source"] = board
                merged.append(record)
        parts.append({"board": board, "rows": len(records)})

    kept, dedupe_report = dedupe(merged)
    report = build_facets(kept, root / out_name, root=root)
    report["boards"] = parts
    report["dedupe"] = dedupe_report
    return report


# -- fit carry-forward -----------------------------------------------------

def build_index(ranking: list[dict]) -> dict:
    """Three-tier lookup that never guesses between distinct postings."""
    url_counts = Counter(norm_url(row.get("url", "")) for row in ranking)
    pair_counts = Counter(norm_pair(row.get("title"), row.get("employer")) for row in ranking)
    by_url: dict[str, dict] = {}
    by_pair: dict[str, dict] = {}
    by_group: dict[str, dict[str, list[dict]]] = {}
    for row in ranking:
        url_key = norm_url(row.get("url", ""))
        if url_counts[url_key] == 1:
            by_url[url_key] = row
        pair_key = norm_pair(row.get("title"), row.get("employer"))
        if pair_counts[pair_key] == 1:
            by_pair[pair_key] = row
        by_group.setdefault(url_key, {}).setdefault(norm_title(row.get("title")), []).append(row)
    return {
        "by_url": by_url,
        "by_pair": by_pair,
        "by_group": by_group,
        "url_counts": url_counts,
        "shared_urls": sum(1 for count in url_counts.values() if count > 1),
        "unique_urls": len(url_counts),
    }


def match_row(row: dict, index: dict) -> tuple[dict | None, str | None]:
    """(ranking_row, tier) or (None, None) when a match would be a guess."""
    url_key = norm_url(row.get("url", ""))
    if url_key in index["by_url"]:
        return index["by_url"][url_key], "unique-url"
    pair_key = norm_pair(row.get("title"), row.get("employer"))
    if pair_key in index["by_pair"]:
        return index["by_pair"][pair_key], "unique-title-employer"
    candidates = index["by_group"].get(url_key, {}).get(norm_title(row.get("title")), [])
    if len(candidates) == 1:
        return candidates[0], "shared-url-unique-title"
    return None, None


def propagate_fit(aggregate: list[dict], ranking: list[dict]) -> dict:
    """Carry scored fit fields onto aggregate rows. Never re-scores, never guesses."""
    index = build_index(ranking)
    before = Counter(str(row.get("fit") or "unset") for row in aggregate)
    tiers: Counter = Counter()
    unmatched: list[dict] = []
    for row in aggregate:
        source, tier = match_row(row, index)
        if source is None:
            unmatched.append(row)
            continue
        tiers[tier] += 1
        for field in FIT_FIELDS:
            if source.get(field) is not None:
                row[field] = source[field]
    after = Counter(str(row.get("fit") or "unset") for row in aggregate)
    return {
        "rows": len(aggregate),
        "scored_before": sum(v for k, v in before.items() if k != "unset"),
        "fits_before": dict(sorted(before.items())),
        "scored_after": sum(v for k, v in after.items() if k != "unset"),
        "fits_after": dict(sorted(after.items())),
        "match_tiers": dict(tiers),
        "unmatched": len(unmatched),
        "unmatched_titles": [row.get("title") for row in unmatched][:20],
        "shared_listing_urls": index["shared_urls"],
        "unique_listing_urls": index["unique_urls"],
    }


# -- ranking ---------------------------------------------------------------

def rank(jobs: list[dict]) -> list[dict]:
    """Order a corpus so the strongest targets come first.

    Fit first, then the user-visible signals that a model cannot invent: whether
    a posting is live, how specific its evidence is, and how recent it is. A
    weighted score never outranks a hard disqualifier — Skip rows stay last
    whatever else is true of them.
    """
    def key(job: dict):
        fit = str(job.get("fit") or "unset")
        status = str(job.get("posting_status") or "")
        dead = any(token in status for token in ("inactive", "expired", "passed", "unresolved"))
        return (
            FIT_ORDER.get(fit, 4),
            1 if dead else 0,
            0 if job.get("detail_evidence_file") else 1,
            -_recency(job),
            str(job.get("title") or ""),
        )

    return sorted(jobs, key=key)


def _recency(job: dict) -> int:
    """Sortable recency from whatever date field a board actually supplied."""
    for field in ("created_date", "last_detail_check", "start_date"):
        raw = str(job.get(field) or "")
        digits = "".join(ch for ch in raw if ch.isdigit())
        if len(digits) >= 8:
            try:
                return int(digits[:8])
            except ValueError:
                continue
    return 0


def rank_report(jobs: list[dict], limit: int = 40) -> dict:
    ordered = rank(jobs)
    counts = Counter(str(job.get("fit") or "unset") for job in ordered)
    return {
        "rows": len(ordered),
        "fits": dict(sorted(counts.items())),
        "top": [
            {
                "id": job.get("id"),
                "title": job.get("title"),
                "employer": job.get("employer"),
                "fit": job.get("fit"),
                "posting_status": job.get("posting_status"),
                "url": job.get("url"),
                "source": job.get("source"),
            }
            for job in ordered[:limit]
        ],
    }


def aggregate_hash(jobs: list[dict]) -> str:
    """Stable fingerprint of the corpus, so idempotence can be asserted."""
    import hashlib
    payload = json.dumps(
        [
            {
                "id": job.get("id"),
                "title": job.get("title"),
                "employer": job.get("employer"),
                "url": job.get("url"),
                "fit": job.get("fit"),
                "source": job.get("source"),
            }
            for job in jobs
        ],
        ensure_ascii=False, sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def load(root: Path | str) -> list[dict]:
    path = Path(root) / "all_boards_data" / "all_jobs.json"
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, list) else []


def write(root: Path | str, out_name: str = "all_boards_data") -> dict:
    """Rebuild the whole aggregate from its board folders, in place."""
    return combine(root, out_name)


__all__ = [
    "FIT_ORDER",
    "aggregate_hash",
    "board_folders",
    "build_facets",
    "build_index",
    "combine",
    "dedupe",
    "load",
    "match_row",
    "norm_pair",
    "norm_title",
    "norm_url",
    "pay_band",
    "pay_display",
    "propagate_fit",
    "rank",
    "rank_report",
    "work_type",
    "write",
]
