from pathlib import Path
import json
import re
from datetime import date, datetime, timedelta


def load_jobs(root: Path) -> list[dict]:
    path = root / "all_boards_data" / "all_jobs.json"
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, list) else []


def canonical_status(value: str) -> str:
    value = str(value).casefold().strip()
    aliases = {
        "draft": "drafted", "drafted": "drafted", "to apply": "queued",
        "queued": "queued", "applied": "applied", "responded": "responded",
        "interview": "interview", "offer": "offer", "rejected": "rejected",
        "withdrawn": "withdrawn", "closed": "withdrawn",
    }
    return aliases.get(value, value)


def parse_history(path: Path) -> list[dict]:
    if not path.exists():
        return []
    records = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.startswith("|") or line.count("|") < 3:
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if not cells or all(set(cell) <= {"-", ":", " "} for cell in cells):
            continue
        if cells[0].casefold() in {"date", "number", "#"}:
            continue
        if len(cells) >= 6:
            records.append({
                "date": cells[0], "company": cells[1], "role": cells[2],
                "fit": cells[3], "resume": cells[4],
                "status": canonical_status(cells[5]),
            })
        elif len(cells) >= 4:
            records.append({"date": cells[0], "company": cells[1], "role": cells[2], "status": canonical_status(cells[-1])})
    return records


def due_items(root: Path) -> list[dict]:
    records = parse_history(root / "job-history.md")
    followups = root / "follow-ups.md"
    if followups.exists():
        text = followups.read_text(encoding="utf-8", errors="replace")
    else:
        text = ""
    applied_dates = {}
    for match in re.finditer(r"Applied\s+(\d{4}-\d{2}-\d{2}).*?#(\d+)", text, re.I):
        applied_dates[int(match.group(2))] = date.fromisoformat(match.group(1))
    result = []
    today = date.today()
    for index, record in enumerate(records, start=1):
        if record.get("status") not in {"applied", "responded", "interview"}:
            continue
        when = applied_dates.get(index)
        if not when:
            continue
        due = when + timedelta(days=7 if record["status"] == "applied" else 1)
        result.append({**record, "number": index, "next_date": due.isoformat(), "urgency": "overdue" if due < today else "waiting"})
    return result
