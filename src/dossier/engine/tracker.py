"""Application tracking and follow-up cadence.

Deterministic arithmetic over an append-only log. Two rules the code enforces
rather than requests:

* A record becomes `applied` only when the caller passes `confirmed=True`,
  because a generated document existing on disk is not evidence that anyone
  submitted it.
* A follow-up date is derived from an explicit `Applied YYYY-MM-DD` record.
  A tracker row's own date column is usually the evaluation date, and driving
  a cadence off it nags the user about applications they never sent.

Cadence: applied chains every 7 days and goes cold after two follow-ups with no
reply; responded chases after 1 day then every 3; an interview gets a thank-you
after 1 day then every 3 with no cap. A `- next #N <date>` line pins a date and
overrides the computation; a `- cleared #N <date>` line retires the cadence
without closing the application.
"""

from __future__ import annotations

import datetime as dt
import re
from collections import Counter
from pathlib import Path

from ..domain_jobs import canonical_status

DEFAULT_CADENCE = {
    "applied_first": 7, "applied_subsequent": 7, "applied_max_followups": 2,
    "responded_initial": 1, "responded_subsequent": 3, "interview_thankyou": 1,
}
ACTIONABLE = {"applied", "responded", "interview"}
TERMINAL = {"offer", "rejected", "withdrawn"}
URGENCY_ORDER = {"urgent": 0, "overdue": 1, "waiting": 2, "cold": 3, "retired": 4}

ROW_RE = re.compile(r"^\|\s*(\d+)?\s*\|(.+)\|\s*$")
BULLET_RE = re.compile(r"^-\s+(\d{4}-\d{2}-\d{2})\s+\u00b7\s+#(\d+)\s+(.+?)(?:\s+\u2014\s+(.*))?$")
OVERRIDE_RE = re.compile(
    r"^-\s+next\s+#(\d+)\s+(\d{4}-\d{2}-\d{2})(?:\s+\(set\s+(\d{4}-\d{2}-\d{2})\))?", re.I)
CLEARED_RE = re.compile(r"^-\s+cleared\s+#(\d+)\s+(\d{4}-\d{2}-\d{2})", re.I)
APPLIED_NOTE_RE = re.compile(r"\bapplied\s+~?(\d{4}-\d{2}-\d{2})", re.I)
APPLIED_NUMBERED_RE = re.compile(r"\bapplied\s+~?(\d{4}-\d{2}-\d{2})[^#\n]*#(\d+)", re.I)

COLUMN_ALIASES = {
    "date": {"date", "applied", "when"},
    "company": {"company", "employer", "organisation", "organization"},
    "role": {"role", "title", "position"},
    "fit": {"fit", "fit rating", "score"},
    "resume": {"resume file", "resume", "artefact", "artifact", "file", "files"},
    "status": {"status", "state"},
    "notes": {"notes", "note", "comment"},
}


def parse_date(value: str | None) -> dt.date | None:
    if not value or not re.match(r"^\d{4}-\d{2}-\d{2}$", value.strip()):
        return None
    try:
        return dt.date.fromisoformat(value.strip())
    except ValueError:
        return None


def _is_separator(cells: list[str]) -> bool:
    return bool(cells) and all(set(cell) <= {"-", ":", " "} for cell in cells)


def _map_header(cells: list[str]) -> dict[str, int] | None:
    mapping: dict[str, int] = {}
    for index, cell in enumerate(cells):
        key = cell.strip().casefold()
        for field, aliases in COLUMN_ALIASES.items():
            if key in aliases:
                mapping.setdefault(field, index)
    return mapping if "status" in mapping or "company" in mapping else None


def parse(root: Path | str) -> list[dict]:
    """Read the tracker into numbered records. Numbers are 1-based row ordinals.

    The `#N` references in a follow-ups log point at these row numbers, so the
    numbering has to match what a human counts in the file.
    """
    path = Path(root) / "job-history.md"
    if not path.exists():
        return []
    records: list[dict] = []
    mapping: dict[str, int] | None = None
    number = 0
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line.startswith("|") or line.count("|") < 3:
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if _is_separator(cells):
            continue
        if mapping is None:
            candidate = _map_header(cells)
            if candidate:
                mapping = candidate
                continue
        if cells[0].casefold() in {"date", "#", "number"} and "company" in " ".join(cells).casefold():
            continue
        number += 1
        if mapping:
            def cell(field: str, default: str = "") -> str:
                index = mapping.get(field)
                return cells[index] if index is not None and index < len(cells) else default
            record = {
                "number": number,
                "date": cell("date"),
                "company": cell("company"),
                "role": cell("role"),
                "fit": cell("fit"),
                "resume": cell("resume"),
                "status": canonical_status(cell("status")),
                "notes": cell("notes"),
            }
        else:
            padded = cells + [""] * (6 - len(cells))
            record = {
                "number": number,
                "date": padded[0], "company": padded[1], "role": padded[2],
                "fit": padded[3], "resume": padded[4],
                "status": canonical_status(padded[5]), "notes": padded[6] if len(padded) > 6 else "",
            }
        records.append(record)
    return records


def _applied_dates(root: Path) -> tuple[dict[int, str], dict[int, str]]:
    """(applied date per row, source) from the tracker's notes and the follow-up log."""
    dates: dict[int, str] = {}
    source: dict[int, str] = {}
    for record in parse(root):
        match = APPLIED_NOTE_RE.search(record.get("notes") or "")
        if match and parse_date(match.group(1)):
            dates[record["number"]] = match.group(1)
            source[record["number"]] = "tracker notes"
    followups = Path(root) / "follow-ups.md"
    if followups.exists():
        text = followups.read_text(encoding="utf-8", errors="replace")
        for match in APPLIED_NUMBERED_RE.finditer(text):
            if parse_date(match.group(1)):
                number = int(match.group(2))
                dates.setdefault(number, match.group(1))
                source.setdefault(number, "follow-ups log")
    return dates, source


def summary(root: Path | str) -> dict:
    records = parse(root)
    counts = Counter(record["status"] for record in records)
    dates, sources = _applied_dates(root)
    actionable = [record for record in records if record["status"] in ACTIONABLE]
    return {
        "path": str(Path(root) / "job-history.md"),
        "rows": len(records),
        "status_counts": dict(sorted(counts.items())),
        "actionable": len(actionable),
        "terminal": sum(counts[status] for status in TERMINAL if status in counts),
        "draft_only": counts.get("drafted", 0),
        "confirmed_application_dates": {str(k): v for k, v in sorted(dates.items())},
        "date_sources": {str(k): v for k, v in sorted(sources.items())},
        "actionable_without_date": [
            record["number"] for record in actionable if record["number"] not in dates
        ],
        "note": (
            "`drafted` is not `applied`. Only a confirmed submission moves a row, and only a "
            "confirmed Applied date starts the follow-up cadence."
        ),
    }


def _followups(content: str) -> dict[int, list[str]]:
    by_app: dict[int, list[str]] = {}
    for line in content.splitlines():
        stripped = line.rstrip("\r")
        if stripped.startswith("|"):
            parts = [part.strip() for part in stripped.split("|")]
            if len(parts) < 5:
                continue
            number = next((int(part) for part in parts if part.isdigit()), None)
            dates = [part for part in parts if parse_date(part)]
            if number is not None and dates:
                by_app.setdefault(number, []).append(dates[0])
            continue
        match = BULLET_RE.match(stripped)
        if match:
            by_app.setdefault(int(match.group(2)), []).append(match.group(1))
    return by_app


def _directives(content: str, pattern: re.Pattern) -> dict[int, dict]:
    found: dict[int, dict] = {}
    for line in content.splitlines():
        match = pattern.match(line.strip())
        if not match:
            continue
        if not parse_date(match.group(2)):
            continue
        set_date = match.group(3) if pattern.groups >= 3 and match.group(3) else match.group(2)
        found[int(match.group(1))] = {"date": match.group(2), "set": set_date}
    return found


def cadence(root: Path | str, today: dt.date | None = None, overdue_only: bool = False) -> dict:
    """Compute urgency and the next due date per actionable application."""
    root = Path(root)
    records = parse(root)
    followups_path = root / "follow-ups.md"
    content = followups_path.read_text(encoding="utf-8", errors="replace") if followups_path.exists() else ""
    by_app = _followups(content)
    overrides = _directives(content, OVERRIDE_RE)
    cleared = _directives(content, CLEARED_RE)
    applied, sources = _applied_dates(root)
    today = today or dt.date.today()

    entries = []
    for record in records:
        status = record["status"]
        if status not in ACTIONABLE:
            continue
        applied_value = applied.get(record["number"])
        applied_date = parse_date(applied_value)
        if applied_date is None:
            entries.append({
                "number": record["number"],
                "company": record["company"],
                "role": record["role"],
                "status": status,
                "applied_date": None,
                "urgency": "needs-date",
                "next_date": None,
                "followup_count": len(by_app.get(record["number"], [])),
                "reason": "no confirmed Applied YYYY-MM-DD record; cadence will not run",
            })
            continue

        followups = sorted(by_app.get(record["number"], []), reverse=True)
        count = len(followups)
        last = parse_date(followups[0]) if followups else None
        days_since = (today - applied_date).days
        days_since_last = (today - last).days if last else None

        urgency, next_date = _compute(status, applied_date, last, count, days_since, days_since_last)

        override = overrides.get(record["number"])
        if override and not (followups and followups[0] > override["set"]):
            pinned = parse_date(override["date"])
            next_date = pinned
            urgency = "overdue" if pinned and (pinned - today).days <= 0 else "waiting"

        clear = cleared.get(record["number"])
        if clear and not (followups and followups[0] > clear["set"]):
            urgency, next_date = "retired", None

        entries.append({
            "number": record["number"],
            "company": record["company"],
            "role": record["role"],
            "status": status,
            "applied_date": applied_value,
            "applied_date_source": sources.get(record["number"], "unknown"),
            "days_since_application": days_since,
            "followup_count": count,
            "urgency": urgency,
            "next_date": next_date.isoformat() if next_date else None,
        })

    entries.sort(key=lambda entry: (URGENCY_ORDER.get(entry["urgency"], 9), entry["number"]))
    retired = [entry for entry in entries if entry["urgency"] == "retired"]
    undated = [entry for entry in entries if entry["urgency"] == "needs-date"]
    active = [entry for entry in entries if entry["urgency"] not in {"retired", "needs-date"}]
    visible = [entry for entry in entries if entry["urgency"] != "needs-date"]
    if overdue_only:
        visible = [entry for entry in visible if entry["urgency"] in {"urgent", "overdue"}]

    return {
        "analysis_date": today.isoformat(),
        "total_tracked": len(records),
        "actionable": len(active),
        "undated": len(undated),
        "retired": len(retired),
        "counts": {
            urgency: sum(1 for entry in active if entry["urgency"] == urgency)
            for urgency in ("urgent", "overdue", "waiting", "cold")
        },
        "entries": visible,
        "needs_date": undated,
        "cadence": DEFAULT_CADENCE,
        "note": "Deterministic arithmetic. This mode drafts messages; it never sends anything.",
    }


def _compute(status: str, applied: dt.date, last: dt.date | None, count: int,
             days_since: int, days_since_last: int | None, cadence=None):
    cadence = cadence or DEFAULT_CADENCE
    if status == "applied":
        if count >= cadence["applied_max_followups"]:
            return "cold", None
        if count == 0:
            due = applied + dt.timedelta(days=cadence["applied_first"])
            return ("overdue" if days_since >= cadence["applied_first"] else "waiting"), due
        if last:
            due = last + dt.timedelta(days=cadence["applied_subsequent"])
            overdue = days_since_last is not None and days_since_last >= cadence["applied_subsequent"]
            return ("overdue" if overdue else "waiting"), due
        due = applied + dt.timedelta(days=cadence["applied_first"])
        return ("overdue" if days_since >= cadence["applied_first"] else "waiting"), due
    if status == "responded":
        if last:
            due = last + dt.timedelta(days=cadence["responded_subsequent"])
            overdue = days_since_last is not None and days_since_last >= cadence["responded_subsequent"]
            return ("overdue" if overdue else "waiting"), due
        due = applied + dt.timedelta(days=cadence["responded_initial"])
        if days_since < cadence["responded_initial"]:
            return "urgent", due
        return ("overdue" if days_since >= cadence["responded_subsequent"] else "waiting"), due
    if status == "interview":
        if last:
            due = last + dt.timedelta(days=cadence["responded_subsequent"])
            overdue = days_since_last is not None and days_since_last >= cadence["responded_subsequent"]
            return ("overdue" if overdue else "waiting"), due
        due = applied + dt.timedelta(days=cadence["interview_thankyou"])
        return ("overdue" if days_since >= cadence["interview_thankyou"] else "waiting"), due
    return "waiting", None


def _header_map(path: Path) -> dict[str, int] | None:
    """The tracker table's own column mapping, read from its header row."""
    if not path.exists():
        return None
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line.startswith("|") or line.count("|") < 3:
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if _is_separator(cells) or _map_header(cells) is None:
            continue
        return _map_header(cells)
    return None


def record_outcome(root: Path | str, number: int, outcome: str, applied_date: str | None = None,
                   confirmed: bool = False, note: str = "") -> dict:
    """Move a tracker row's status. Refuses to write `applied` without confirmation."""
    root = Path(root)
    status = canonical_status(outcome)
    if status == "applied" and not confirmed:
        return {
            "written": False,
            "refused": "drafted-is-not-applied",
            "detail": (
                "Refusing to mark a row applied: no confirmation that the user submitted it. "
                "Pass confirmed=True after the user says they sent it."
            ),
        }
    if status in ACTIONABLE and not applied_date:
        return {
            "written": False,
            "refused": "confirmed-date",
            "detail": (
                f"Status `{status}` is actionable, so it needs an explicit applied date — "
                "otherwise the follow-up cadence has nothing to count from."
            ),
        }
    if applied_date and not parse_date(applied_date):
        return {"written": False, "refused": "bad-date", "detail": "applied_date must be YYYY-MM-DD"}

    path = root / "job-history.md"
    if not path.exists():
        return {"written": False, "refused": "no-tracker", "detail": f"{path} does not exist"}
    records = {record["number"]: record for record in parse(root)}
    if number not in records:
        return {"written": False, "refused": "no-such-row", "detail": f"no row #{number}"}

    from ..safety import trash
    from ..config import AppConfig

    config = AppConfig.create(root)
    trash(config, path)

    original = path.read_text(encoding="utf-8")
    header = _header_map(path)
    lines = original.splitlines(keepends=True)
    data_index = 0
    changed = False
    date_for_log: str | None = None
    for position, raw in enumerate(lines):
        line = raw.strip()
        if not line.startswith("|") or line.count("|") < 3:
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if _is_separator(cells) or _map_header(cells):
            continue
        data_index += 1
        if data_index != number:
            continue
        new_cells = list(cells)
        status_index = header["status"] if header and "status" in header else len(new_cells) - 1
        new_cells[status_index] = status
        if applied_date:
            stamp = f"Applied {applied_date}" + (f" — {note}" if note else "")
            notes_index = header.get("notes") if header else None
            if notes_index is not None and notes_index < len(new_cells):
                new_cells[notes_index] = (new_cells[notes_index] + " " + stamp).strip()
            else:
                # No notes column to carry the date. Widening the table would
                # break its alignment, so the date goes to the follow-up log,
                # which is where the cadence reads confirmed dates from.
                date_for_log = stamp
        newline = "\r\n" if raw.endswith("\r\n") else "\n"
        lines[position] = "| " + " | ".join(new_cells) + " |" + newline
        changed = True
        break

    if not changed:
        return {"written": False, "refused": "row-not-found", "detail": f"row #{number} not located in the table"}

    path.write_text("".join(lines), encoding="utf-8")

    logged_to = None
    if date_for_log:
        followups = root / "follow-ups.md"
        if not followups.exists():
            followups.write_text("# Follow-up log\n\n", encoding="utf-8")
        text = followups.read_text(encoding="utf-8")
        if not text.endswith("\n"):
            text += "\n"
        followups.write_text(text + f"- {date_for_log} (row #{number})\n", encoding="utf-8")
        logged_to = str(followups)

    return {
        "written": True,
        "row": number,
        "status": status,
        "applied_date": applied_date,
        "applied_date_logged_to": logged_to,
        "backup": str(config.dossier_dir / "trash"),
    }


def append_followup(root: Path | str, number: int, when: str, channel: str = "", contact: str = "",
                    note: str = "") -> dict:
    """Append one follow-up entry. Append-only by design — nothing is rewritten."""
    if not parse_date(when):
        return {"written": False, "detail": "when must be YYYY-MM-DD"}
    root = Path(root)
    target = root / "follow-ups.md"
    if not target.exists():
        return {"written": False, "detail": f"{target} does not exist"}
    parts = [part for part in (when, channel, contact, note) if part]
    line = f"- {when} \u00b7 #{number} {' '.join(parts[1:])}".rstrip()
    text = target.read_text(encoding="utf-8")
    if not text.endswith("\n"):
        text += "\n"
    target.write_text(text + line + "\n", encoding="utf-8")
    return {"written": True, "line": line, "path": str(target)}
