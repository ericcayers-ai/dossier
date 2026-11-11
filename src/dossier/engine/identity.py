"""Identity: what the user is looking for, grounded in their own evidence.

A job search is only as good as the target it is aimed at. This module builds that
target from two sources, in this order of authority:

1. **The user's answers** — a fixed questionnaire (`QUESTIONS`) the app can ask,
   answer by answer, and resume later. Answers are stored per workspace in
   `.dossier/identity/answers.json`, so they survive a session and can be corrected.
2. **The user's documents** — `*-IDENTITY.md`, `resume.md`, `job-history.md` and any
   `*.md` in the workspace are *mined* for the same fields. A mined value is a
   proposal with a provenance line (`path:line` and the exact text), never an
   assertion.

Precedence is deliberate: an explicit answer beats a document, because a document is
usually older than the correction the user just typed. Both are reported with their
source, so nothing in the profile is unattributable.

The gate this module enforces is `identity-grounded`: a field reaches `IDENTITY.md`
only when it has an answer or a document span behind it. There is no default name,
no guessed salary, no invented target role.

Relevance (`score_job`) is deterministic arithmetic over that profile — title family,
skills overlap, location/remote, employment type, seniority, salary floor, language,
recency — with one rule from the corpus ranker carried over: **a weighted score never
hides a disqualifier.** A deal-breaker caps the band and is named in the reasons.

Nothing here calls a model. A model can propose answers through the questionnaire
surface, but the arithmetic and the provenance are code.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from ..copy import plural

PROFILE_DIR = ".dossier/identity"
ANSWERS_FILE = "answers.json"
PROFILE_FILE = "profile.json"
IDENTITY_MARKER_START = "<!-- dossier:identity:start -->"
IDENTITY_MARKER_END = "<!-- dossier:identity:end -->"

#: Bands the ranker and the capture filter both use, so one number means one thing.
BANDS = (("strong", 65), ("possible", 40), ("unlikely", 0))


# --------------------------------------------------------------------------
# the questionnaire
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Question:
    id: str
    group: str
    prompt: str
    kind: str            # text | list | choice | number | bool
    help: str = ""
    choices: tuple[str, ...] = ()
    required: bool = False


#: The questionnaire. Every `required` question is something the ranker cannot infer
#: safely: a target role, a location, an employment type, a right-to-work answer and a
#: pay floor. The rest refine the score and can be answered later.
QUESTIONS: tuple[Question, ...] = (
    Question("target_roles", "Target", "Which roles are you actually applying for?",
             "list", "Comma-separated. The ranker matches titles and role families against these.",
             required=True),
    Question("seniority", "Target", "What level are you targeting?",
             "choice", choices=("student/intern", "graduate", "junior", "mid", "senior", "lead"),
             required=True),
    Question("employment", "Target", "Which employment types?",
             "list", "e.g. internship, part-time, full-time, contract, casual",
             required=True),
    Question("location", "Where", "Where can you work? City or region.",
             "text", "Used for a location match and for a commute distance.", required=True),
    Question("remote", "Where", "Is remote acceptable?",
             "choice", choices=("yes", "hybrid only", "onsite only", "no preference")),
    Question("right_to_work", "Where", "Right to work in that country?",
             "text", "e.g. citizen, permanent resident, student visa with 20 h/week",
             required=True),
    Question("availability", "When", "When can you start?",
             "text", "e.g. November 2026, summer 2026/27, immediately"),
    Question("salary_floor", "Pay", "Minimum acceptable annual pay, in your currency?",
             "number", "A number, or blank if you would rather not set one."),
    Question("currency", "Pay", "Currency for that number.",
             "choice", choices=("NZD", "AUD", "USD", "GBP", "EUR", "other")),
    Question("must_have", "Skills", "Skills or technologies the role must involve.",
             "list", "Comma-separated. A missing must-have lowers relevance; it is not a deal-breaker."),
    Question("nice_to_have", "Skills", "Skills you would like to use.",
             "list", "Comma-separated."),
    Question("deal_breakers", "Filters", "Words that should disqualify a listing.",
             "list", "Comma-separated, e.g. commission-only, door-to-door, unpaid. "
                     "A match caps the band and says why."),
    Question("languages", "Skills", "Languages you work in.",
             "list", "Comma-separated, e.g. English, Japanese."),
    Question("disclosure", "Preferences", "Mention a health condition or accommodation need in applications?",
             "choice", help="Stored as your rule; it is never written into a document automatically.",
             choices=("never", "only when asked", "per application", "always")),
    Question("pitch", "Target", "One sentence: what you offer.",
             "text", "Used as the objective draft, never as a claim without your edit."),
)

QUESTION_INDEX = {question.id: question for question in QUESTIONS}
REQUIRED = tuple(question.id for question in QUESTIONS if question.required)


# --------------------------------------------------------------------------
# storage
# --------------------------------------------------------------------------

def _dir(root: Path | str) -> Path:
    return Path(root) / PROFILE_DIR


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_answers(root: Path | str) -> dict:
    try:
        data = json.loads((_dir(root) / ANSWERS_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    answers = data.get("answers") if isinstance(data, dict) else None
    return answers if isinstance(answers, dict) else {}


def save_answers(root: Path | str, answers: dict, *, source: str = "user") -> dict:
    """Merge answers into the workspace file. A blank value clears the answer.

    Clearing is a supported operation on purpose: a wrong answer that cannot be
    removed is worse than no answer, and the profile reports the gap honestly.
    """
    current = load_answers(root)
    changed: list[str] = []
    for key, value in (answers or {}).items():
        key = str(key).strip()
        if key not in QUESTION_INDEX:
            raise ValueError(f"unknown question {key!r}; known: {', '.join(QUESTION_INDEX)}")
        if value in (None, "", []):
            if key in current:
                current.pop(key)
                changed.append(key)
            continue
        current[key] = {"value": value, "answered_at": _now(), "source": source}
        changed.append(key)
    path = _dir(root)
    path.mkdir(parents=True, exist_ok=True)
    (path / ANSWERS_FILE).write_text(
        json.dumps({"version": 1, "updated_at": _now(), "answers": current},
                   indent=2, ensure_ascii=False), encoding="utf-8")
    return {"saved": changed, "answers": len(current)}


def _answer_list(answers: dict, key: str) -> list[str]:
    entry = answers.get(key) or {}
    value = entry.get("value")
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return [item.strip() for item in re.split(r"[,;\n]", value) if item.strip()]
    return []


def _answer_text(answers: dict, key: str) -> str:
    entry = answers.get(key) or {}
    value = entry.get("value")
    return "" if value is None else str(value).strip()


# --------------------------------------------------------------------------
# document mining
# --------------------------------------------------------------------------

_EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.]{2,}\b")
_PHONE = re.compile(r"(?:\+?64[\s-]?)?0\d{1,2}[\s-]?\d{3,4}[\s-]?\d{3,4}\b")
_NAME = re.compile(r"^#\s+([A-Z][\w'’-]{1,30})(?:\s+[A-Z][\w'’-]{1,30})?\s+[—–-]")
_TIMEZONE = re.compile(r"Timezone:\s*([A-Za-z]+/[A-Za-z_]+)", re.IGNORECASE)
_LOCATION = re.compile(
    r"\b(Hamilton|Auckland|Wellington|Christchurch|Tauranga|Dunedin|Waikato|New Zealand)\b")
_SENIORITY = (
    ("student/intern", re.compile(r"\b(second|third|first)[- ]year\b|\bstudent\b|\bintern(ship)?\b", re.I)),
    ("junior", re.compile(r"\bjunior\b|\bgraduate\b", re.I)),
    ("senior", re.compile(r"\b(senior|principal|staff)\b", re.I)),
)
_AVAILABILITY = re.compile(r"\b(summer (?:internship|2026[/-]27)|available (?:from|immediately)|"
                           r"starting (?:in )?[A-Z][a-z]+ 20\d\d)\b", re.I)
_RIGHT_TO_WORK = re.compile(r"\b(citizen|permanent resident|work visa|student visa|right to work)\b", re.I)


def _candidate_docs(root: Path | str) -> list[Path]:
    root = Path(root)
    docs: list[Path] = []
    for pattern in ("*-IDENTITY.md", "resume.md", "job-history.md", "follow-ups.md"):
        docs.extend(sorted(root.glob(pattern)))
    # A workspace may keep its own identity notes under another name; only the top
    # level is read, so a folder of 800 tailored resumes is not crawled for a name.
    for path in sorted(root.glob("*.md")):
        if path not in docs and "identity" in path.name.casefold():
            docs.append(path)
    return list(dict.fromkeys(docs))


def _line_of(path: Path, needle: str) -> tuple[int, str] | None:
    try:
        for index, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            if needle and needle in line:
                return index, line.strip()[:300]
    except OSError:
        return None
    return None


def _propose(field_name: str, value, path: Path, evidence_line: str, needle: str = "",
             confidence: str = "medium") -> dict | None:
    """One proposal, located in the file it came from.

    The line is found by searching for the evidence the caller already has: the
    needle it matched, else the first value, else the first token of a list. A
    proposal whose line cannot be located is still reported, with `line: None`,
    rather than being dropped — the citation is downgraded, not fabricated.
    """
    if value in (None, "", []):
        return None
    candidates = [needle, str(value)]
    if isinstance(value, list) and value:
        candidates.append(str(value[0]))
    located = None
    for candidate in candidates:
        if not candidate:
            continue
        located = _line_of(path, candidate)
        if located:
            break
    return {"field": field_name, "value": value, "source": str(path),
            "line": located[0] if located else None,
            "evidence": (located[1] if located else evidence_line)[:300],
            "confidence": confidence}


def mine_documents(root: Path | str) -> list[dict]:
    """Proposals from the workspace's own documents, each with its provenance.

    Deliberately conservative: a value is proposed only when a pattern makes it
    unambiguous (an email address, a `Timezone:` line, a Skills heading). A guess
    without a span behind it is not a proposal.
    """
    proposals: list[dict] = []
    for path in _candidate_docs(root):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        lines = text.splitlines()

        if path.name.casefold().endswith("-identity.md"):
            for line in lines[:20]:
                match = _NAME.match(line)
                if match:
                    proposals.append(_propose("name", match.group(1), path, line,
                                              match.group(0), confidence="high"))
                    break

        email = _EMAIL.search(text)
        if email:
            proposals.append(_propose("email", email.group(0).casefold(), path, "",
                                      email.group(0), "high"))
        phone = _PHONE.search(text)
        if phone:
            proposals.append(_propose("phone", phone.group(0), path, "", phone.group(0), "high"))

        for line in lines[:80]:
            tz = _TIMEZONE.search(line)
            if tz:
                proposals.append(_propose("timezone", tz.group(1), path, line, "Timezone", "high"))
                break

        location_hits = [match.group(0) for match in _LOCATION.finditer("\n".join(lines[:40]))]
        if location_hits:
            proposals.append(_propose("location", location_hits[0], path, "",
                                      location_hits[0], "medium"))

        for label, pattern in _SENIORITY:
            match = pattern.search(text)
            if match:
                proposals.append(_propose("seniority", label, path, "", match.group(0),
                                          "high" if label == "student/intern" else "medium"))
                break

        availability = _AVAILABILITY.search(text)
        if availability:
            proposals.append(_propose("availability", availability.group(0), path, "",
                                      availability.group(0), "medium"))

        right = _RIGHT_TO_WORK.search(text)
        if right:
            proposals.append(_propose("right_to_work", right.group(0), path, "",
                                      right.group(0), "low"))

        if path.name.casefold() == "resume.md":
            skills = _skills_from_resume(text)
            if skills:
                proposals.append(_propose("skills", skills, path, "", "## Skills", "high"))

        if path.name.casefold() == "job-history.md":
            roles = _roles_from_history(text)
            if roles:
                proposals.append(_propose("applied_roles", roles, path, "", roles[0], "high"))

        languages = _languages_from_text(text)
        if languages and not any(item["field"] == "languages" for item in proposals):
            proposals.append(_propose("languages", languages, path, "", languages[0], "low"))

    # One proposal per field on the whole list: keep the highest confidence, earliest.
    rank = {"high": 0, "medium": 1, "low": 2}
    best: dict[str, dict] = {}
    for item in proposals:
        current = best.get(item["field"])
        if current is None or rank[item["confidence"]] < rank[current["confidence"]]:
            best[item["field"]] = item
    return sorted(best.values(), key=lambda item: item["field"])


def _skills_from_resume(text: str) -> list[str]:
    """Skills from a `Skills` section, with or without markdown hashes.

    Real resumes in this workspace use a bare `Skills` line, not `## Skills`, and the
    section is often `Label: a, b, c`. Requiring a hash heading mined nothing from a
    document that plainly listed skills.
    """
    lines = text.splitlines()
    start = None
    for index, line in enumerate(lines):
        if re.fullmatch(r"(?:#{1,6}\s*)?(?:technical\s+|core\s+)?skills?\s*:?\s*", line.strip(), re.I):
            start = index + 1
            break
    if start is None:
        return []
    items: list[str] = []
    for line in lines[start:start + 14]:
        stripped = line.strip()
        if not stripped:
            continue
        if re.match(r"^(?:#{1,6}\s|Education|Experience|Referees|References)", stripped, re.I):
            break
        stripped = re.sub(r"^[-*•]\s*", "", stripped)
        if ":" in stripped:
            label, _, value = stripped.partition(":")
            stripped = value
            if label.strip() and not re.search(r"[,;|]", value):
                # `Label: single value` — keep the value, it is the searchable part.
                pass
        for part in re.split(r"[,;|]", stripped):
            part = part.strip(" .")
            if 1 < len(part) <= 60 and part not in items:
                items.append(part)
    return items[:40]


def _roles_from_history(text: str) -> list[str]:
    """Roles applied for, from the tracker's pipe table, most recent first."""
    roles: list[str] = []
    header: list[str] | None = None
    for line in text.splitlines():
        if not line.strip().startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if header is None:
            lowered = [cell.casefold() for cell in cells]
            if "role" in lowered or "title" in lowered:
                header = lowered
            continue
        if set("".join(cells)) <= set("-: "):
            continue
        if header:
            for key in ("role", "title"):
                if key in header:
                    value = cells[header.index(key)] if header.index(key) < len(cells) else ""
                    if value and value not in roles:
                        roles.append(value)
                    break
        if len(roles) >= 15:
            break
    return roles


def _languages_from_text(text: str) -> list[str]:
    found = []
    for name in ("English", "Japanese", "Māori", "Maori", "Mandarin", "French", "German", "Spanish"):
        if re.search(rf"\b{name}\b", text):
            found.append(name)
    return found[:5]


# --------------------------------------------------------------------------
# the merged profile
# --------------------------------------------------------------------------

def profile(root: Path | str) -> dict:
    """Answers over documents, every field attributable, gaps named."""
    root = Path(root)
    answers = load_answers(root)
    mined = {item["field"]: item for item in mine_documents(root)}

    fields: dict[str, dict] = {}
    for question in QUESTIONS:
        value = answers.get(question.id, {}).get("value")
        if value not in (None, "", []):
            fields[question.id] = {
                "value": value, "source": "answer",
                "answered_at": answers[question.id].get("answered_at"),
                "evidence": None, "confidence": "answered",
            }
    for name, item in mined.items():
        if name in fields:
            continue
        fields[name] = {"value": item["value"], "source": "document",
                        "evidence": {"path": _relative(root, item["source"]),
                                     "line": item["line"], "text": item["evidence"]},
                        "confidence": item["confidence"]}
    # `applied_roles` is a document-only signal: it widens the target list.
    if "applied_roles" in fields and "target_roles" not in fields:
        fields["target_roles"] = {"value": fields["applied_roles"]["value"][:10],
                                 "source": "document",
                                 "evidence": fields["applied_roles"].get("evidence"),
                                 "confidence": "medium"}

    missing = [question_id for question_id in REQUIRED if question_id not in fields]
    answered = sum(1 for question_id in QUESTION_INDEX if question_id in fields)
    return {
        "root": str(root),
        "fields": fields,
        "missing_required": missing,
        "questions": len(QUESTION_INDEX),
        "answered": answered,
        "complete": not missing,
        "sources": _source_counts(fields),
        "rule": ("An answer beats a document. Every document value carries the file and "
                 "line it came from; a field with neither is absent, not guessed."),
    }


def _relative(root: Path, path: str) -> str:
    try:
        return Path(path).resolve().relative_to(Path(root).resolve()).as_posix()
    except (ValueError, OSError):
        return path


def _source_counts(fields: dict) -> dict:
    counts = {"answer": 0, "document": 0}
    for entry in fields.values():
        counts[entry["source"]] = counts.get(entry["source"], 0) + 1
    return counts


def questions_with_state(root: Path | str) -> list[dict]:
    """The questionnaire plus what is already known, for a UI to render."""
    root = Path(root)
    data = profile(root)
    rows = []
    for question in QUESTIONS:
        known = data["fields"].get(question.id)
        rows.append({
            **asdict(question),
            "choices": list(question.choices),
            "answered": bool(known),
            "value": known["value"] if known else None,
            "source": known["source"] if known else None,
            "evidence": known["evidence"] if known else None,
        })
    return rows


# --------------------------------------------------------------------------
# IDENTITY.md
# --------------------------------------------------------------------------

def write_identity(root: Path | str, *, name: str | None = None) -> dict:
    """Write the grounded profile into the workspace's identity document.

    The block is managed: everything outside the markers is the user's own prose and
    is preserved. A field with no answer and no document span is not written, and the
    report names it — `identity-grounded` is the reason a field cannot appear here by
    having a plausible default.
    """
    from ..safety import trash_then_write_text

    root = Path(root)
    data = profile(root)
    if not data["fields"]:
        raise ValueError("the identity is empty: answer at least one question or keep an "
                         "identity document in the workspace before writing")
    target = Path(name) if name else None
    if target is None:
        existing = sorted(root.glob("*-IDENTITY.md"))
        # The name must match the *-IDENTITY.md discovery rule, or mining and the
        # agent's identity blocker never see the document this command just wrote.
        target = existing[0] if existing else root / f"{root.name}-IDENTITY.md"
    elif not target.is_absolute():
        target = root / target

    lines = [IDENTITY_MARKER_START, "## Target (written by Dossier)", ""]
    ordered = [question.id for question in QUESTIONS] + ["name", "email", "phone",
                                                         "applied_roles", "skills"]
    for key in ordered:
        entry = data["fields"].get(key)
        if not entry:
            continue
        label = key.replace("_", " ").capitalize()
        if isinstance(entry["value"], list):
            lines.append(f"- **{label}:** {', '.join(str(item) for item in entry['value'])}")
        else:
            lines.append(f"- **{label}:** {entry['value']}")
        if isinstance(entry["evidence"], dict):
            lines.append(f"  <sub>from {entry['evidence']['path']}"
                         f"{':' + str(entry['evidence']['line']) if entry['evidence'].get('line') else ''}</sub>")
    if data["missing_required"]:
        lines += ["", "Not answered yet: " + ", ".join(data["missing_required"])]
    lines += ["", f"Generated {date.today().isoformat()} from "
                  f"{plural(data['sources'].get('answer', 0),'answer')} and "
                  f"{plural(data['sources'].get('document', 0),'document value')}.",
              IDENTITY_MARKER_END]

    if target.exists():
        text = target.read_text(encoding="utf-8", errors="replace")
        block = "\n".join(lines)
        if IDENTITY_MARKER_START in text and IDENTITY_MARKER_END in text:
            head = text.split(IDENTITY_MARKER_START)[0].rstrip()
            tail = text.split(IDENTITY_MARKER_END)[-1].lstrip()
            merged = f"{head}\n\n{block}\n\n{tail}".strip() + "\n"
        else:
            merged = text.rstrip() + "\n\n" + block + "\n"
    else:
        merged = f"# {data['fields'].get('name', {}).get('value', 'Identity')}\n\n" + \
                 "\n".join(lines) + "\n"
    trash_then_write_text(root, target, merged)
    return {"path": _relative(root, str(target)), "fields": len(data["fields"]),
            "missing_required": data["missing_required"],
            "bytes": target.stat().st_size}


# --------------------------------------------------------------------------
# relevance
# --------------------------------------------------------------------------

#: Role families, so "Backend Engineer" matches a target of "software engineer"
#: without a model and without pretending every title is a separate universe.
ROLE_FAMILIES: dict[str, tuple[str, ...]] = {
    "software": ("software", "developer", "engineer", "programmer", "full stack", "backend",
                 "frontend", "platform", "systems", "devops", "sre", "qa", "test"),
    "data": ("data", "analyst", "analytics", "scientist", "ml", "machine learning", "ai",
             "bi ", "intelligence"),
    "it": ("it ", "support", "helpdesk", "help desk", "service desk", "administrator",
           "infrastructure", "network"),
    "design": ("design", "ux", "ui ", "artist", "creative", "illustrator"),
    "product": ("product", "owner", "manager", "scrum", "project"),
    "science": ("research", "scientist", "laboratory", "lab ", "biology", "chemistry"),
    "trade": ("electrician", "builder", "mechanic", "welder", "carpenter", "plumber"),
    "retail": ("retail", "sales assistant", "customer service", "cashier", "store"),
}

SENIORITY_YEARS = {"student/intern": 0, "graduate": 0, "junior": 1, "mid": 3,
                   "senior": 6, "lead": 8}
SENIORITY_TITLE_HINTS = {
    "lead": ("lead", "principal", "staff", "head of", "director", "manager"),
    "senior": ("senior", "sr ", "sr.", "principal"),
    "mid": ("mid", "intermediate"),
    "junior": ("junior", "jr ", "graduate", "entry"),
    "student/intern": ("intern", "internship", "student", "summer", "placement"),
}


def _tokens(value) -> set[str]:
    if isinstance(value, list):
        text = " ".join(str(item) for item in value)
    else:
        text = str(value or "")
    return {token for token in re.findall(r"[a-z0-9+#.]+", text.casefold()) if len(token) > 1}


def _family_of(text: str) -> set[str]:
    lowered = f" {text.casefold()} "
    return {name for name, words in ROLE_FAMILIES.items()
            if any(word in lowered for word in words)}


def _value(entry: dict | None):
    return (entry or {}).get("value")


#: Weight and ceiling per signal. `available` is the sum of the ceilings for the
#: signals the profile actually supplies, so a sparse profile is scored out of what it
#: *could* award rather than out of a full profile's maximum. Without this, the first
#: real attempt scored 554 rows and produced a top score of 40: a user who has answered
#: only roles and location had every listing marked irrelevant.
WEIGHTS = {
    "title": 40, "family": 28, "must": 30, "nice": 16, "skills": 15,
    "place": 12, "employment": 10, "seniority": 12, "pay": 8, "language": 5, "recency": 8,
}


def score_job(job: dict, data: dict) -> dict:
    """Relevance of one listing to the profile, as a percentage of what is knowable.

    The arithmetic is visible: `earned` and `available` are both returned, and every
    addition has a sentence in `reasons`. A disqualifier caps the band at `unlikely`
    and is listed first, because a weighted score must never hide one.
    """
    fields = data.get("fields") or {}
    reasons: list[str] = []
    disqualifiers: list[str] = []
    earned = 0
    available = 0

    title = str(job.get("title") or job.get("position") or "")
    description = str(job.get("description") or "")
    location = str(job.get("location") or "")
    work_type = str(job.get("work_type") or "")
    pay = str(job.get("pay") or job.get("salary") or "")
    haystack = f"{title} {description} {work_type}".casefold()

    def add(signal: str, points: int, reason: str = "") -> None:
        nonlocal earned
        earned += points
        if reason:
            reasons.append(reason)

    # -- deal-breakers first: they cap everything else ---------------------
    breakers = fields.get("deal_breakers", {}).get("value") or []
    if isinstance(breakers, str):
        breakers = [part.strip() for part in re.split(r"[,;\n]", breakers) if part.strip()]
    for word in breakers:
        if str(word).casefold() in haystack:
            disqualifiers.append(f"contains a deal-breaker: {word}")

    # -- target roles ------------------------------------------------------
    targets = fields.get("target_roles", {}).get("value") or []
    if isinstance(targets, str):
        targets = [part.strip() for part in re.split(r"[,;\n]", targets) if part.strip()]
    applied = fields.get("applied_roles", {}).get("value") or []
    if isinstance(applied, str):
        applied = [part.strip() for part in re.split(r"[,;\n]", applied) if part.strip()]
    if targets or applied:
        available += WEIGHTS["title"] + WEIGHTS["family"]
        # A target the user *answered* is intent; a target mined from the tracker is
        # history — they applied to a retail role and a compliance role in the same
        # month. History counts, at 60%: the first real attempt mined those titles and
        # then scored "Customer Care Representative" as a possible fit for a CS student.
        answered = (fields.get("target_roles") or {}).get("source") == "answer"
        scale = 1.0 if answered else 0.6
        target_tokens = set()
        for target in targets:
            target_tokens |= _tokens(target)
        overlap = target_tokens & _tokens(title)
        if overlap:
            add("title", int(WEIGHTS["title"] * scale),
                f"title matches your target on: {', '.join(sorted(overlap)[:5])}")
        else:
            families = _family_of(title) & _family_of(" ".join(str(item) for item in targets))
            history = _family_of(title) & _family_of(" ".join(str(item) for item in applied))
            if families:
                add("family", int(WEIGHTS["family"] * scale),
                    f"title is in a target role family: {', '.join(sorted(families))}")
            elif history:
                add("family", int(WEIGHTS["family"] * 0.7 * scale),
                    "title is in the family of a role you already applied for: "
                    + ", ".join(sorted(history)))
            else:
                reasons.append("title is outside every role family you named or applied for")

    # -- must-have / nice-to-have / resume skills -------------------------
    for key, weight, phrase in (("must_have", WEIGHTS["must"], "must-have"),
                                ("nice_to_have", WEIGHTS["nice"], "nice-to-have")):
        items = fields.get(key, {}).get("value") or []
        if isinstance(items, str):
            items = [part.strip() for part in re.split(r"[,;\n]", items) if part.strip()]
        if not items:
            continue
        available += weight
        hits = [item for item in items if str(item).casefold() in haystack]
        missed = [item for item in items if str(item).casefold() not in haystack]
        if hits:
            points = weight if key == "must_have" else min(weight, int(weight * 0.6) * len(hits))
            add(key, points,
                f"{len(hits)} {plural(phrase,'skill')} present: {', '.join(str(hit) for hit in hits[:4])}")
        if missed and key == "must_have":
            reasons.append(f"missing must-haves: {', '.join(str(item) for item in missed[:4])}")
    skills = fields.get("skills", {}).get("value") or []
    if isinstance(skills, str):
        skills = [part.strip() for part in re.split(r"[,;\n]", skills) if part.strip()]
    if skills:
        available += WEIGHTS["skills"]
        hits = [skill for skill in skills
                if len(str(skill)) > 2 and str(skill).casefold() in haystack]
        if hits:
            add("skills", min(WEIGHTS["skills"], 5 * len(hits)),
                f"{plural(len(hits),'skill')} from your resume appear: "
                + ", ".join(str(hit) for hit in hits[:4]))

    # -- location and remote ----------------------------------------------
    wanted = str(_value(fields.get("location")) or "").casefold()
    remote_pref = str(_value(fields.get("remote")) or "").casefold()
    is_remote = any(word in haystack or word in location.casefold()
                    for word in ("remote", "anywhere", "work from home", "distributed"))
    if wanted or remote_pref:
        available += WEIGHTS["place"]
    if wanted and wanted in location.casefold():
        add("place", WEIGHTS["place"], f"location matches {location}")
    elif is_remote and remote_pref in ("yes", "no preference", ""):
        add("place", int(WEIGHTS["place"] * 0.75), "remote role, and remote is acceptable to you")
    elif is_remote and remote_pref == "hybrid only":
        reasons.append("remote role, but you asked for hybrid")
    elif wanted:
        reasons.append(f"location {location or 'unknown'} is not {wanted}")
    if remote_pref == "onsite only" and is_remote:
        disqualifiers.append("you asked for onsite only and this is remote")

    # -- employment type ---------------------------------------------------
    employment = fields.get("employment", {}).get("value") or []
    if isinstance(employment, str):
        employment = [part.strip() for part in re.split(r"[,;\n]", employment) if part.strip()]
    if employment:
        available += WEIGHTS["employment"]
        for kind in employment:
            if (str(kind).casefold() in work_type.casefold()
                    or str(kind).casefold() in haystack[:800]):
                add("employment", WEIGHTS["employment"], f"employment type matches: {kind}")
                break

    # -- seniority ---------------------------------------------------------
    seniority = str(_value(fields.get("seniority")) or "").casefold()
    if seniority:
        available += WEIGHTS["seniority"]
        years = re.search(r"(\d+)\+?\s*years?", haystack)
        hinted = [label for label, hints in SENIORITY_TITLE_HINTS.items()
                  if any(hint in f" {title.casefold()} " for hint in hints)]
        if seniority in ("student/intern", "graduate") and (
                "senior" in hinted or "lead" in hinted or (years and int(years.group(1)) >= 5)):
            disqualifiers.append(f"role reads senior and you are targeting {seniority}")
        elif seniority in hinted:
            add("seniority", WEIGHTS["seniority"], f"seniority matches: {seniority}")
        elif seniority == "student/intern" and "intern" in haystack:
            add("seniority", WEIGHTS["seniority"], "internship wording present")

    # -- pay floor ---------------------------------------------------------
    floor = _value(fields.get("salary_floor"))
    try:
        floor_value = float(str(floor).replace(",", "")) if floor not in (None, "") else None
    except ValueError:
        floor_value = None
    if floor_value:
        available += WEIGHTS["pay"]
        numbers = [int(match.replace(",", "")) for match in re.findall(r"\d[\d,]{3,}", pay)]
        if numbers:
            top = max(numbers)
            if top < floor_value:
                disqualifiers.append(f"advertised pay {top} is under your floor {int(floor_value)}")
            else:
                add("pay", WEIGHTS["pay"], f"advertised pay reaches your floor ({top})")

    # -- language ----------------------------------------------------------
    languages = fields.get("languages", {}).get("value") or []
    if isinstance(languages, str):
        languages = [part.strip() for part in re.split(r"[,;\n]", languages) if part.strip()]
    if languages:
        available += WEIGHTS["language"]
        for language in languages:
            if str(language).casefold() in haystack:
                add("language", WEIGHTS["language"], f"mentions {language}")
                break

    # -- recency -----------------------------------------------------------
    posted = job.get("date") or job.get("posted_at") or job.get("created_at")
    if isinstance(posted, str) and len(posted) >= 10:
        try:
            moment = datetime.fromisoformat(posted.replace("Z", "+00:00"))
            age = (datetime.now(timezone.utc)
                   - moment.replace(tzinfo=moment.tzinfo or timezone.utc)).days
            available += WEIGHTS["recency"]
            if age <= 14:
                add("recency", WEIGHTS["recency"], f"posted {plural(age,'day')} ago")
            elif age > 60:
                earned -= WEIGHTS["recency"] // 2
                reasons.append(f"posted {age} days ago")
        except ValueError:
            pass

    # A profile with nothing scorable is not "0% relevant"; it is unscoreable.
    score = 0 if not available else max(0, min(100, round(100 * earned / available)))
    band = next(name for name, threshold in BANDS if score >= threshold)
    if disqualifiers:
        band = "unlikely"
        score = min(score, 25)
    return {"score": score, "band": band, "reasons": reasons,
            "disqualifiers": disqualifiers, "earned": earned, "available": available,
            "families": sorted(_family_of(title))}


def rank_corpus(root: Path | str, limit: int = 40, *, min_band: str = "") -> dict:
    """Score the captured corpus against the profile and return the shortlist.

    Disqualified rows stay in the report under `disqualified`, with their reason:
    dropping them silently is how a search becomes a filter the user cannot audit.
    """
    from .corpus import load

    root = Path(root)
    data = profile(root)
    if not data["fields"]:
        return {"present": False, "rows": 0,
                "reason": "no identity yet: answer the questionnaire or keep an identity document",
                "profile": {"missing_required": data["missing_required"]}}
    jobs = load(root)
    if not jobs:
        return {"present": False, "rows": 0,
                "reason": "no corpus: run `dossier corpus build` after a capture",
                "profile": {"missing_required": data["missing_required"]}}

    ranks = {"strong": 0, "possible": 1, "unlikely": 2}
    scored = []
    for job in jobs:
        result = score_job(job, data)
        if min_band and ranks.get(result["band"], 3) > ranks.get(min_band, 2):
            continue
        scored.append({**job, **result})
    scored.sort(key=lambda row: (-row["score"], str(row.get("title", ""))))

    matched = [row for row in scored if not row["disqualifiers"]]
    disqualified = [row for row in scored if row["disqualifiers"]]
    band_counts: dict[str, int] = {"strong": 0, "possible": 0, "unlikely": 0}
    for row in scored:
        band_counts[row["band"]] = band_counts.get(row["band"], 0) + 1
    return {
        "present": True,
        "rows": len(jobs),
        "scored": len(scored),
        "band_counts": band_counts,
        "matched": matched[:limit],
        "disqualified": disqualified[:20],
        "profile": {"answered": data["answered"], "complete": data["complete"],
                    "missing_required": data["missing_required"]},
        "hash": _corpus_hash(jobs),
        "rule": ("Relevance is arithmetic over your own profile. A deal-breaker caps the "
                 "band and is named; a weighted score never hides one."),
    }


def _corpus_hash(jobs: list[dict]) -> str:
    import hashlib
    payload = json.dumps([str(job.get("id") or job.get("url")) for job in jobs],
                         sort_keys=True).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:12]


def match_posting(path: Path | str, root: Path | str) -> dict:
    """Score one archived posting (a `job-posting-*.md`) against the profile."""
    path = Path(path)
    text = path.read_text(encoding="utf-8", errors="replace")
    title = ""
    match = re.search(r"^title:\s*(.+)$", text, re.M)
    if match:
        title = match.group(1).strip()
    job = {"title": title, "description": text, "location": "", "url": ""}
    result = score_job(job, profile(root))
    return {"posting": str(path), "title": title, **result}


__all__ = ["ANSWERS_FILE", "BANDS", "IDENTITY_MARKER_END", "IDENTITY_MARKER_START",
           "PROFILE_DIR", "QUESTION_INDEX", "QUESTIONS", "Question", "REQUIRED",
           "load_answers", "match_posting", "mine_documents", "profile",
           "questions_with_state", "rank_corpus", "save_answers", "score_job",
           "write_identity"]
