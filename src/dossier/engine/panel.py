"""The hiring panel: seven reviewers, each scoring and quoting the line that cost you.

The reel this implements says the real problem is that a rejection never tells you
*why*, so the fix is to make the AI play seven reviewers — recruiter, hiring manager,
sceptical team lead, an applicant tracking system and three more — have each one score
the resume and **quote the exact line** that made them say no, and then have a chair
rewrite the weakest parts.

Every seat here is mechanical: the same input produces the same score and the same
quote, and every quote is enforced to be a verbatim line of the document (see
`_finding`, which raises rather than paraphrase). The chair does not rewrite prose —
it names the line, says what is wrong with it and what the rewrite must contain, which
is the same contract the rest of the engine uses for its agent modes.

Nothing in here reaches a network, and nothing invents a fact about the candidate.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable

#: Characters that survive a human read and are mangled by a parser.
RISKY_GLYPHS = {
    "\u2014": "em dash", "\u2013": "en dash", "\u2018": "curly quote",
    "\u2019": "curly quote", "\u201c": "curly quote", "\u201d": "curly quote",
    "\u2022": "bullet glyph", "\u00a0": "non-breaking space", "\u2192": "arrow",
    "\u2026": "ellipsis",
}
BAD_BULLET = re.compile(r"^\s*[-*\u2022\u25aa]\s+", re.UNICODE)
DATE = re.compile(r"(?<!\d)((?:19|20)\d{2})(?:[-/.](\d{1,2}))?(?!\d)")
DIGIT = re.compile(r"\d")
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
PHONE = re.compile(r"(?:\+?\d[\d\s().-]{7,}\d)")
VAGUE = re.compile(
    r"\b(responsible for|helped|assisted|worked on|involved in|participated in|"
    r"familiar with|exposure to|various|several|some)\b", re.IGNORECASE)
SUPERLATIVE = re.compile(
    r"\b(passionate|hard[- ]working|team player|self[- ]starter|go[- ]getter|"
    r"excellent communication skills|detail[- ]oriented|results[- ]driven|"
    r"dynamic|proven track record)\b", re.IGNORECASE)
SECTION = {
    "experience": re.compile(r"^\s*#{0,6}\s*(work |professional |employment)?(experience|history)\b", re.I),
    "education": re.compile(r"^\s*#{0,6}\s*education\b", re.I),
    "skills": re.compile(r"^\s*#{0,6}\s*(skills|technical skills|competencies)\b", re.I),
}
STOP = set("""a an the and or of for to in on at with by as is are be been being this that
these those i my me we our you your they their it its from into per via if then than so
about across after all also any apply applicant applicants application applications role
roles job jobs work working team teams year years month months day days will would can
could should must have has had do does did not no more most less least other others""".split())


@dataclass(frozen=True)
class Reviewer:
    id: str
    name: str
    asks: str


REVIEWERS: tuple[Reviewer, ...] = (
    Reviewer("ats", "Applicant tracking system",
             "Can I parse this without losing a single line?"),
    Reviewer("recruiter", "Recruiter, 30-second scan",
             "Do I see the target role and one number in the top third?"),
    Reviewer("manager", "Hiring manager",
             "Does the evidence answer this posting's must-haves?"),
    Reviewer("lead", "Sceptical team lead",
             "Would I bet on these claims in an interview?"),
    Reviewer("keywords", "Lexical match",
             "Are the posting's own words present?"),
    Reviewer("screen", "Screen against the calendar",
             "Do the dates agree with each other?"),
    Reviewer("honesty", "Reference check",
             "Could a referee back this line up?"),
)


@dataclass
class Finding:
    reviewer: str
    verdict: str            # pass | warn | fail
    line: int | None
    quote: str
    why: str
    fix: str
    weight: int = 1
    source: str = "resume"   # which document the line number points into

    def as_dict(self) -> dict:
        return {"reviewer": self.reviewer, "verdict": self.verdict, "line": self.line,
                "quote": self.quote, "why": self.why, "fix": self.fix,
                "weight": self.weight, "source": self.source}


@dataclass
class Seat:
    reviewer: Reviewer
    score: int
    findings: list[Finding] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {"id": self.reviewer.id, "name": self.reviewer.name, "asks": self.reviewer.asks,
                "score": self.score, "findings": [f.as_dict() for f in self.findings]}


def _lines(text: str) -> list[str]:
    return text.replace("\r\n", "\n").split("\n")


def _content(lines: list[str]) -> list[tuple[int, str]]:
    """(1-based line number, stripped text) for every line that says something."""
    out = []
    for index, line in enumerate(lines, start=1):
        stripped = line.strip().lstrip("#").strip()
        if stripped:
            out.append((index, stripped))
    return out


def _clamp(value: int) -> int:
    return max(0, min(100, value))


def _verdict(issues: int) -> str:
    return "pass" if issues == 0 else ("warn" if issues == 1 else "fail")


class _Guard:
    """A quote must be the document's own words, or this raises.

    The promise the whole feature rests on is "quotes the exact line", so it is a
    checked invariant rather than a good intention.
    """

    def __init__(self, lines: list[str]):
        self.lines = lines

    def finding(self, reviewer: str, line: int | None, quote: str, why: str, fix: str,
                verdict: str = "fail", weight: int = 1) -> Finding:
        if line is not None:
            if line < 1 or line > len(self.lines):
                raise ValueError(f"line {line} is outside a {len(self.lines)}-line document")
            source = self.lines[line - 1]
            if quote and quote not in source:
                raise ValueError(f"quote {quote!r} is not in line {line}: {source!r}")
        return Finding(reviewer, verdict, line, quote, why, fix, weight)


def _ats(lines: list[str], guard: _Guard) -> Seat:
    findings: list[Finding] = []
    content = _content(lines)
    glyphs = [(n, t) for n, t in content if any(g in t for g in RISKY_GLYPHS)]
    if glyphs:
        line, text = glyphs[0]
        names = sorted({RISKY_GLYPHS[g] for g in RISKY_GLYPHS if g in text})
        findings.append(guard.finding(
            "ats", line, text[:160],
            f"{len(glyphs)} line(s) carry characters a parser may mangle ({', '.join(names)}).",
            "Replace the dash, quote and bullet glyphs with ASCII: '-', '\"' and '-'.", weight=2))
    tables = [(n, t) for n, t in content if t.count("|") >= 2]
    if tables:
        line, text = tables[0]
        findings.append(guard.finding(
            "ats", line, text[:160],
            f"{len(tables)} line(s) look like a table; column layouts are the classic "
            "thing an ATS flattens into nonsense.",
            "Rewrite the rows as one bullet per line, no pipes.", weight=2))
    long_lines = [(n, t) for n, t in content if len(t) > 220]
    if long_lines:
        line, text = long_lines[0]
        findings.append(guard.finding(
            "ats", line, text[:160], f"{len(long_lines)} line(s) run past 220 characters.",
            "Split them: one claim per bullet, under 200 characters.", verdict="warn"))
    joined = "\n".join(t for _, t in content)
    missing = [name for name, pattern in SECTION.items()
               if not any(pattern.match(t) for _, t in content)]
    if missing:
        findings.append(guard.finding(
            "ats", None, "", f"No {', '.join(missing)} heading a parser can recognise.",
            "Add plain 'Experience', 'Education' and 'Skills' headings.", weight=2))
    if not EMAIL.search(joined) or not PHONE.search(joined):
        findings.append(guard.finding(
            "ats", None, "", "No email and phone pair in the text layer.",
            "Put both in the first three lines, as text rather than inside a graphic.", weight=2))
    score = _clamp(100 - sum(12 * f.weight for f in findings))
    return Seat(REVIEWERS[0], score, findings)


def _recruiter(lines: list[str], guard: _Guard) -> Seat:
    content = _content(lines)
    if not content:
        return Seat(REVIEWERS[1], 0, [guard.finding(
            "recruiter", None, "", "The document has no readable text.", "Write the resume first.")])
    top_end = max(1, len(content) // 3)
    top = content[:top_end]
    with_number = [item for item in top if DIGIT.search(item[1])]
    role_line = next((item for item in top if re.search(r"\b(engineer|analyst|developer|designer|"
                                                       r"manager|assistant|specialist|technician|"
                                                       r"consultant|administrator|coordinator)\b",
                                                       item[1], re.I)), None)
    findings: list[Finding] = []
    if not with_number:
        line, text = top[-1]
        findings.append(guard.finding(
            "recruiter", line, text[:160],
            "Nothing in the top third is quantified, so the first decision has no evidence to "
            "rest on.", "Lead with one number: a scale, a saving, a count or a duration.", weight=3))
    if role_line is None:
        line, text = top[0]
        findings.append(guard.finding(
            "recruiter", line, text[:160],
            "The top third never names the role being applied for.",
            "Name the target role in the first two lines, matching the posting's title.",
            verdict="warn", weight=2))
    score = _clamp(100 - sum(15 * f.weight for f in findings))
    return Seat(REVIEWERS[1], score, findings)


def _tokens(text: str) -> list[str]:
    words = re.findall(r"[A-Za-z][A-Za-z+#.\-]{2,}", text)
    out, seen = [], set()
    for word in words:
        key = word.lower().strip(".-")
        if key and key not in STOP and key not in seen:
            seen.add(key)
            out.append(key)
    return out


def _manager(lines: list[str], posting: str, guard: _Guard) -> Seat:
    content = _content(lines)
    if not posting.strip():
        return Seat(REVIEWERS[2], 50, [guard.finding(
            "manager", None, "", "No posting was supplied, so the must-haves are unknown.",
            "Pass the posting: this seat reads the requirement list, not the resume alone.",
            verdict="warn")])
    required = _tokens(posting)
    body = " ".join(t for _, t in content).lower()
    missing = [term for term in required if term not in body]
    findings: list[Finding] = []
    if missing:
        posting_lines = _lines(posting)
        line = next((n for n, t in enumerate(posting_lines, start=1)
                     if any(term in t.lower() for term in missing)), 1)
        quote = posting_lines[line - 1].strip()[:160]
        findings.append(guard.finding(
            "manager", None, "", f"{len(missing)} of the posting's terms never appear: "
            f"{', '.join(missing[:8])}.",
            "Either evidence each term in a bullet, or leave it out on purpose: an unbacked "
            "keyword is the first thing an interview exposes."))
        findings.append(Finding("manager", "warn", line, quote,
                                "The posting asks for terms the resume never answers.",
                                "Answer this line in the resume, or drop the requirement honestly.",
                                1, source="posting"))
    score = _clamp(100 - round(70 * len(missing) / max(1, len(required))))
    return Seat(REVIEWERS[2], score, findings)


def _lead(lines: list[str], guard: _Guard) -> Seat:
    content = _content(lines)
    vague = [(n, t) for n, t in content if BAD_BULLET.match(t) and VAGUE.search(t)
             and not DIGIT.search(t)]
    findings: list[Finding] = []
    for line, text in vague[:3]:
        findings.append(guard.finding(
            "lead", line, text[:160],
            "A claim with no number and no object: I cannot ask a follow-up question about it.",
            "Name the system, the action and the outcome, with one number."))
    unquantified = [(n, t) for n, t in content if BAD_BULLET.match(t) and not DIGIT.search(t)]
    if len(unquantified) > len(content) // 3:
        line, text = unquantified[0]
        findings.append(guard.finding(
            "lead", line, text[:160],
            f"{len(unquantified)} of {len(content)} content lines carry no number at all.",
            "Roughly half the bullets should have a quantity in them.", verdict="warn"))
    score = _clamp(100 - sum(18 * f.weight for f in findings))
    return Seat(REVIEWERS[3], score, findings)


def _keywords(lines: list[str], posting: str, guard: _Guard) -> Seat:
    content = _content(lines)
    if not posting.strip():
        return Seat(REVIEWERS[4], 50, [guard.finding(
            "keywords", None, "", "No posting to match against.", "Pass the posting.",
            verdict="warn")])
    required = _tokens(posting)
    body = " ".join(t for _, t in content).lower()
    present = [term for term in required if term in body]
    missing = [term for term in required if term not in body]
    findings: list[Finding] = []
    if missing:
        # No quote here: a missing term is an absence, and inventing a line for it
        # would break the one promise this feature makes.
        findings.append(Finding(
            "keywords", "warn", None, "",
            f"{len(missing)} of {len(required)} posting terms are absent: "
            f"{', '.join(missing[:10])}.",
            "Add the ones you can evidence; ignore the ones you cannot.", 1))
    ratio = len(present) / max(1, len(required))
    return Seat(REVIEWERS[4], _clamp(round(50 + 50 * ratio)), findings)


def _screen(lines: list[str], guard: _Guard) -> Seat:
    content = _content(lines)
    dated: list[tuple[int, str, int]] = []
    for number, text in content:
        match = DATE.search(text)
        if match:
            dated.append((number, text, int(match.group(1))))
    findings: list[Finding] = []
    if len(dated) >= 2:
        starts = [item[2] for item in dated]
        if starts != sorted(starts, reverse=True):
            first_out_of_order = next(
                (dated[i] for i in range(1, len(dated)) if dated[i][2] > dated[i - 1][2]), dated[1])
            line, text, _ = first_out_of_order
            findings.append(guard.finding(
                "screen", line, text[:160],
                "Dates are not in reverse-chronological order, so a reader cannot scan a timeline.",
                "Sort every section newest first."))
    if len(dated) >= 4:
        years = [item[2] for item in dated]
        if max(years) - min(years) > 40:
            findings.append(Finding(
                "screen", "warn", None, "",
                f"Dates span {max(years) - min(years)} years: check that an education year and a "
                "start date are not being confused for a job range.",
                "Keep 'since' and 'current' explicit where a role is ongoing.", 1))
    score = _clamp(100 - sum(20 * f.weight for f in findings))
    return Seat(REVIEWERS[5], score, findings)


def _honesty(lines: list[str], guard: _Guard) -> Seat:
    content = _content(lines)
    findings: list[Finding] = []
    claims = [(n, t) for n, t in content if SUPERLATIVE.search(t)]
    for line, text in claims[:3]:
        findings.append(guard.finding(
            "honesty", line, text[:160],
            "A self-description with nothing behind it: any referee would have to disagree.",
            "Replace the adjective with the thing that made you say it."))
    score = _clamp(100 - sum(15 * f.weight for f in findings))
    return Seat(REVIEWERS[6], score, findings)


def run(text: str, *, posting: str = "", target_role: str = "") -> dict:
    """All seven seats, the weighted score and the chair's rewrite plan."""
    lines = _lines(text)
    if target_role:
        posting = f"{posting}\nTarget role: {target_role}".strip()
    guard = _Guard(lines)
    seats = [
        _ats(lines, guard),
        _recruiter(lines, guard),
        _manager(lines, posting, guard),
        _lead(lines, guard),
        _keywords(lines, posting, guard),
        _screen(lines, guard),
        _honesty(lines, guard),
    ]
    weights = {"ats": 1.2, "recruiter": 1.3, "manager": 1.5, "lead": 1.3,
               "keywords": 1.0, "screen": 0.8, "honesty": 0.9}
    total_weight = sum(weights[seat.reviewer.id] for seat in seats)
    score = round(sum(seat.score * weights[seat.reviewer.id] for seat in seats) / total_weight)

    # The chair: the three failures that cost the most, each with its line and the
    # instruction the rewrite has to satisfy. No prose is generated here.
    ranked = []
    for seat in seats:
        for finding in seat.findings:
            ranked.append((finding.weight * (3 if finding.verdict == "fail" else 1), seat, finding))
    ranked.sort(key=lambda item: item[0], reverse=True)
    plan = []
    seen_hosts: set[tuple[str, int | None]] = set()
    for _, seat, finding in ranked:
        key = (seat.reviewer.id, finding.line)
        if key in seen_hosts:
            continue
        seen_hosts.add(key)
        plan.append({
            "order": len(plan) + 1,
            "seat": seat.reviewer.name,
            "line": finding.line,
            "source": finding.source,
            "quote": finding.quote,
            "why": finding.why,
            "rewrite": finding.fix,
        })
        if len(plan) == 3:
            break

    verdict = "pass" if score >= 80 else ("borderline" if score >= 60 else "fail")
    return {
        "score": score,
        "verdict": verdict,
        "lines": len(lines),
        "words": len(text.split()),
        "target_role": target_role,
        "has_posting": bool(posting.strip()),
        "seats": [seat.as_dict() for seat in seats],
        "plan": plan,
        "silent_seats": [seat.reviewer.id for seat in seats if not seat.findings],
    }


def _where(item: dict) -> str:
    if not item.get("line"):
        return "document level"
    return f"{'posting ' if item.get('source') == 'posting' else ''}line {item['line']}"


def render(result: dict) -> str:
    """The same result as a table a person reads in a terminal or a document."""
    out = [f"# Hiring panel: {result['score']}/100 ({result['verdict']})", ""]
    if not result["has_posting"]:
        out.append("No posting supplied: two seats scored the resume alone.")
        out.append("")
    out.append("| Seat | Score | What it asked |")
    out.append("|---|---|---|")
    for seat in result["seats"]:
        out.append(f"| {seat['name']} | {seat['score']} | {seat['asks']} |")
    out.append("")
    for seat in result["seats"]:
        if not seat["findings"]:
            out.append(f"**{seat['name']}** — nothing to raise.")
            continue
        out.append(f"**{seat['name']}** — {seat['score']}/100")
        for finding in seat["findings"]:
            where = _where(finding)
            out.append(f"- {where}: {finding['why']}")
            if finding["quote"]:
                out.append(f"  > {finding['quote']}")
            out.append(f"  fix: {finding['fix']}")
        out.append("")
    out.append("## The chair's plan")
    if not result["plan"]:
        out.append("Nothing to rewrite: every seat passed.")
    for item in result["plan"]:
        where = _where(item)
        out.append(f"{item['order']}. {where} ({item['seat']}): {item['rewrite']}")
        if item["quote"]:
            out.append(f"   > {item['quote']}")
    return "\n".join(out)
