from dataclasses import dataclass, asdict
from pathlib import Path
import json
import re


@dataclass
class Rules:
    strip_prefixes: list[str]
    strip_suffixes: list[str]
    strip_patterns: list[str]


def load_rules(root: Path) -> Rules:
    path = root / ".dossier" / "bundles.json"
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
    else:
        template = Path(__file__).parents[2] / "templates" / "bundles.json"
        data = json.loads(template.read_text(encoding="utf-8"))
    return Rules(**data)


def stem_key(rel: str, rules: Rules) -> str:
    name = Path(rel).stem
    lowered = name.casefold()
    for prefix in sorted(rules.strip_prefixes, key=len, reverse=True):
        if lowered.startswith(prefix.casefold()):
            name = name[len(prefix):]
            break
    lowered = name.casefold()
    for suffix in sorted(rules.strip_suffixes, key=len, reverse=True):
        if lowered.endswith(suffix.casefold()):
            name = name[:-len(suffix)]
            break
    for pattern in rules.strip_patterns:
        name = re.sub(pattern, "", name, flags=re.IGNORECASE)
    return re.sub(r"[-_\s]+", "-", name).casefold().strip("-")


def classify_role(rel: str, rules: Rules) -> str:
    name = Path(rel).name.casefold()
    parent = str(Path(rel).parent).casefold()
    if name.startswith("job-posting-"):
        return "source"
    if any(name.startswith(prefix.casefold()) for prefix in (
        "keywords-", "keyword-gap-", "diagnosis-", "jd-gap-input-",
        "workflow-", "skill-gap-",
    )):
        return "analysis"
    if "rendered-" in parent or re.search(r"-page-\d+\.", name):
        return "proof"
    if Path(rel).suffix.casefold() == ".pdf":
        return "render"
    if Path(rel).suffix.casefold() in {".docx", ".zip"}:
        return "artifact"
    if Path(rel).suffix.casefold() in {".png", ".jpg", ".jpeg", ".webp"}:
        return "proof"
    return "other"


@dataclass
class Member:
    rel: str
    role: str
    size: int
    mtime_ns: int
    stale: bool = False


@dataclass
class Bundle:
    stem_key: str
    members: list[dict]
    stale: list[str]


def resolve_bundle(conn, rel: str) -> Bundle:
    row = conn.execute("SELECT stem_key FROM files WHERE rel = ?", (rel,)).fetchone()
    key = row["stem_key"] if row else ""
    rows = conn.execute(
        "SELECT rel, ext, size, mtime_ns, role FROM files WHERE stem_key = ? ORDER BY rel",
        (key,),
    ).fetchall()
    latest_docx = max((r["mtime_ns"] for r in rows if r["ext"] == ".docx"), default=0)
    members = []
    for row in rows:
        stale = row["ext"] == ".pdf" and latest_docx and row["mtime_ns"] < latest_docx
        members.append(asdict(Member(row["rel"], row["role"], row["size"], row["mtime_ns"], bool(stale))))
    return Bundle(key, members, [member["rel"] for member in members if member["stale"]])
