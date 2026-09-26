"""Zero-model JD skill-gap classifier and gap aggregation.

Extracts an explicit requirement token list from a job description with regex
and classifies each token against resume text:

  existing   -- named in a skills-type section
  supported  -- appears in prose elsewhere in the resume
  gap        -- the posting wants it and the resume has no trace of it

This never adds anything to a resume. It only classifies and reports, which is
what makes it safe to run before a model touches the document: the model gets
a verified list of which true things to surface, not a licence to invent.

`saw_requirement_section` is returned because "found a requirements section
and recognised zero terms" and "never found a requirements section at all"
both print as zero and mean very different things.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

_REQ_HEADER_WORDS = [
    r"required", r"requirements", r"qualifications", r"must[- ]have",
    r"preferred", r"nice[- ]to[- ]have",
    r"what\s+we(?:'|\u2019)?\s*re\s+looking\s+for",
    r"what\s+you(?:(?:'|\u2019)ll|\s+will)?\s+bring",
    r"what\s+you(?:(?:'|\u2019)ll|\s+will)?\s+be\s+doing",
    r"who\s+you\s+are", r"about\s+you",
    r"your\s+(?:background|experience|profile)",
    r"you\s+(?:may|might|could)\s+be\s+a\s+good\s+fit",
    r"you(?:(?:'|\u2019)ll|\s+will)?\s+have",
    r"it(?:'|\u2019)?s\s+important\s+to\s+us\s+that\s+you\s+have",
    r"it\s+would\s+be\s+great\s+if\s+you\s+ha(?:ve|d)",
    r"ideal\s+candidate",
    r"the\s+fit",
    r"key\s+responsibilities",
    r"day\s+to\s+day",
    r"the\s+role",
    r"skills\s+(?:and|&)\s+experience",
]

# Prose archiving (a scraped board page, a pasted advert) often carries no
# markdown headings at all, so a short line ending in ':' or '?' is treated as
# a section boundary. Without this, a requirements block stays open through the
# marketing copy underneath it and "Free", "Fun" and "Why" are reported as
# missing skills.
_SECTION_LINE_RE = re.compile(r"^(?![-*\u2022])\S[^\n]{0,58}[:?]$")
REQUIREMENT_HEADER_RE = re.compile(
    r"^#{0,6}\s*(?:" + "|".join(_REQ_HEADER_WORDS) + r")s?\b.*$",
    re.IGNORECASE | re.MULTILINE,
)

_NON_REQ_HEADER_WORDS = [
    r"you\s+will(?!\s+have)", r"benefits?", r"perks?",
    r"benefits\s+and\s+perks", r"compensation", r"salary", r"pay\s+range",
    r"what\s+we\s+offer", r"why\b",
    r"about\s+(?:us|the\s+company|the\s+team|the\s+role)",
    r"how\s+(?:and\s+where\s+)?we\s+work",
    r"join\b", r"our\s+(?:purpose|mission|story|values)",
    r"the\s+opportunity", r"equal\s+opportunity", r"eeo", r"diversity",
    r"interview\s+process", r"how\s+to\s+apply", r"to\s+apply",
]
NON_REQUIREMENT_HEADER_RE = re.compile(
    r"^#{0,6}\s*(?:" + "|".join(_NON_REQ_HEADER_WORDS) + r")\b.*$",
    re.IGNORECASE | re.MULTILINE,
)

# Headings with no ASCII word boundary, checked by prefix.
_CJK_REQ_HEADERS = ("應徵條件", "資格條件", "職務需求", "條件要求", "任職資格",
                    "必要條件", "基本要求", "職位要求", "加分項目", "加分條件")
_CJK_NON_REQ_HEADERS = ("工作內容", "工作職責", "職責範疇", "福利", "薪資", "薪酬",
                        "公司介紹", "關於我們", "應徵方式", "如何應徵")

BULLET_LINE_RE = re.compile(r"^\s*[-*\u2022]\s*(.+)\r?$")
SKILL_TOKEN_RE = re.compile(
    r"\b([A-Z][A-Za-z0-9+.#]{0,29}[A-Za-z0-9+#](?:\.[a-z]{2,4})?)(?!\w)"
)
SKILLS_SECTION_RE = re.compile(r"^#{0,6}\s*(skills|technologies|tools|technical skills)\b", re.IGNORECASE)

STOPWORDS = {
    "the", "and", "for", "with", "you", "your", "our", "this", "that",
    "these", "those", "must", "able", "ability", "strong", "excellent",
    "proven", "a", "an", "or", "in", "of", "to", "as", "is", "are",
    "bachelor", "bachelors", "master", "masters", "degree", "diploma",
    "certification", "certificate", "experience", "years", "year",
    "senior", "junior", "entry", "level", "minimum", "preferred",
    "required", "candidates", "candidate", "applicants", "applicant",
    "ideal", "successful", "knowledge", "understanding", "familiarity",
    "exposure", "background", "skills", "skill", "communication", "team",
    "teams", "work", "working", "deep", "interest", "genuine", "solid",
    "comfortable", "passion", "passionate", "track", "record", "real",
    "bonus", "plus", "hands", "proficiency", "fluency", "expertise",
    "demonstrated", "extensive", "practical", "good", "great", "clear",
    "build", "builds", "building", "deploy", "deploys", "deploying",
    "develop", "develops", "developing", "design", "designs", "designing",
    "implement", "implements", "implementing", "create", "creates",
    "creating", "use", "uses", "using", "manage", "manages", "managing",
    # Sentence openers and function words: a capitalised first word of a
    # sentence is not a skill, and reporting "If", "We" or "At" as a gap makes
    # the whole report untrustworthy.
    "if", "we", "at", "it", "its", "why", "what", "when", "where", "whether",
    "who", "how", "so", "but", "from", "into", "over", "on", "by", "no", "not",
    "us", "don", "does", "did", "has", "have", "had", "can", "could", "would",
    "should", "may", "might", "will", "do", "be", "been", "being",
    # Posting prose opens every bullet with a participle. "Acting", "Delivering"
    # and "Providing" are not skills, and reporting them as gaps buries the two
    # tokens in the list that are real.
    "acting", "adapting", "analysing", "analyzing", "answering", "applying",
    "assisting", "building", "capturing", "collaborating", "communicating",
    "completing", "contributing", "coordinating", "creating", "delivering",
    "demonstrating", "developing", "diagnosing", "documenting", "driving",
    "ensuring", "escalating", "establishing", "evaluating", "following",
    "growing", "handling", "helping", "identifying", "implementing",
    "improving", "investigating", "keeping", "leading", "learning",
    "liaising", "maintaining", "making", "managing", "mentoring",
    "monitoring", "organising", "organizing", "owning", "partnering",
    "performing", "planning", "preparing", "presenting", "prioritising",
    "prioritizing", "processing", "providing", "reporting", "resolving",
    "responding", "reviewing", "running", "scheduling", "sharing",
    "supporting", "taking", "teaching", "testing", "training",
    "troubleshooting", "understanding", "using", "working", "writing",
    # Adverbs and connectives that open a clause.
    "continuously", "accurately", "effectively", "efficiently", "proactively",
    "independently", "collaboratively", "consistently", "professionally",
    "comfortably", "relatively", "typically", "usually", "often",
}


def _line_is_req_header(line: str) -> bool:
    stripped = line.lstrip("# ").strip()
    return bool(REQUIREMENT_HEADER_RE.match(line)) or any(
        stripped.startswith(header) for header in _CJK_REQ_HEADERS
    )


def _line_is_non_req_header(line: str) -> bool:
    stripped = line.lstrip("# ").strip()
    return bool(NON_REQUIREMENT_HEADER_RE.match(line)) or any(
        stripped.startswith(header) for header in _CJK_NON_REQ_HEADERS
    )


def _line_is_section_boundary(line: str) -> bool:
    """A heading written as prose: short, and ending in ':' or '?'."""
    return bool(_SECTION_LINE_RE.match(line.strip()))


def _extract_tokens(content: str, skills: set[str]) -> None:
    for token in SKILL_TOKEN_RE.findall(content):
        if token.casefold() not in STOPWORDS:
            skills.add(token)


def scan_posting(text: str) -> tuple[list[str], bool]:
    """Return (tokens, saw_requirement_section)."""
    skills: set[str] = set()
    in_block = False
    saw_section = False
    for line in text.split("\n"):
        if _line_is_non_req_header(line):
            in_block = False
            continue
        if _line_is_req_header(line):
            in_block = True
            saw_section = True
            if ":" in line:
                _extract_tokens(line.split(":", 1)[1], skills)
            continue
        # An unrecognised heading written as prose ends an open block rather
        # than letting the requirement list bleed into the marketing copy below.
        if _line_is_section_boundary(line):
            in_block = False
            continue
        if in_block and re.match(r"^#{1,6}\s", line):
            in_block = False
            continue
        if not in_block:
            continue
        bullet = BULLET_LINE_RE.match(line)
        _extract_tokens(bullet.group(1) if bullet else line, skills)
    return sorted(skills), saw_section


def _skills_section(resume_text: str) -> str:
    captured = ""
    capturing = False
    for line in resume_text.split("\n"):
        if SKILLS_SECTION_RE.match(line):
            capturing = True
            continue
        if capturing and re.match(r"^#{1,6}\s", line):
            capturing = False
            continue
        if capturing:
            captured += line.casefold() + "\n"
    return captured


def classify(tokens: list[str], resume_text: str) -> dict:
    resume_lower = resume_text.casefold()
    skills_section = _skills_section(resume_text)
    existing, supported, gap = [], [], []
    for token in tokens:
        key = token.strip().casefold()
        if key in skills_section:
            existing.append(token)
        elif key in resume_lower:
            supported.append(token)
        else:
            gap.append(token)
    return {"existing": existing, "supported": supported, "gap": gap}


def analyze(posting_text: str, resume_text: str) -> dict:
    tokens, saw_section = scan_posting(posting_text)
    result = classify(tokens, resume_text)
    result["saw_requirement_section"] = saw_section
    result["skills_found"] = len(tokens)
    result["warning"] = (
        None if saw_section
        else "No requirements-style header was found. This extraction may be empty "
             "because nothing was checked, not because there was nothing to find."
    )
    result["counts"] = {key: len(value) for key, value in result.items() if isinstance(value, list)}
    return result


def write(posting_path: Path, resume_path: Path, out_path: Path) -> dict:
    result = analyze(
        Path(posting_path).read_text(encoding="utf-8", errors="replace"),
        Path(resume_path).read_text(encoding="utf-8", errors="replace"),
    )
    result["posting"] = str(posting_path)
    result["resume"] = str(resume_path)
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    return result


def aggregate(root: Path | str) -> dict:
    """Count recurring gaps across every keyword report in a workspace.

    This is the honest answer to "what should I learn next": gaps that real
    postings actually asked for, counted, not a generic list.
    """
    root = Path(root)
    gap_counts: Counter = Counter()
    existing_counts: Counter = Counter()
    reports: list[dict] = []

    for path in sorted(root.glob("*.skillgap.json")) + sorted(root.glob("keyword-gap-*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            reports.append({"file": path.name, "error": str(exc)})
            continue
        gap = data.get("gap") or []
        existing = data.get("existing") or []
        gaps = [str(item) for item in gap if isinstance(item, str)]
        for token in gaps:
            gap_counts[token] += 1
        for token in existing:
            existing_counts[str(token)] += 1
        reports.append({
            "file": path.name,
            "skills_found": data.get("skills_found", len(gap) + len(existing)),
            "existing": len(existing),
            "gap": len(gaps),
        })

    return {
        "reports": len(reports),
        "files": reports,
        "recurring_gaps": [
            {"skill": skill, "postings": count}
            for skill, count in gap_counts.most_common()
        ],
        "already_surfaced": [
            {"skill": skill, "postings": count}
            for skill, count in existing_counts.most_common(20)
        ],
        "note": (
            "A recurring gap is a learning target or an honest omission in the resume — "
            "never a licence to word-stuff a skill the person does not have."
        ),
    }
