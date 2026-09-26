"""Negotiation ROI — talking points anchored in verbatim-verified achievements.

The safety gate is the entire point of this module. A quantified claim from a
story bank reaches a negotiation draft only if the same number, with a matching
unit, also appears verbatim in the resume text, matched boundary-aware so
"8 hours" cannot false-positive inside "18 hours" and "60%" cannot match inside
"160%". An unverified figure is dropped silently — not flagged, not included
with a caveat — because a number spoken aloud in a real negotiation that does
not hold up damages credibility and the offer itself.

Wage and task frequency are never guessed. Either the story states them or the
caller supplies them; otherwise the claim is reported uncalculable with the
missing input named.
"""

from __future__ import annotations

import re
from pathlib import Path

FREQUENCY_MAP = {
    "daily": 260, "weekly": 52, "biweekly": 26, "bi-weekly": 26,
    "monthly": 12, "quarterly": 4, "annually": 1, "yearly": 1,
}

_FREQ_PATTERNS = [
    (re.compile(r"\bbi-?weekly\b|\bevery\s+(?:other|two)\s+weeks?\b", re.I), "biweekly"),
    (re.compile(r"\bdaily\b|\bevery\s+day\b|\beach\s+day\b", re.I), "daily"),
    (re.compile(r"\bweekly\b|\bevery\s+week\b|\beach\s+week\b|\bonce\s+a\s+week\b", re.I), "weekly"),
    (re.compile(r"\bmonthly\b|\bevery\s+month\b|\beach\s+month\b|\bonce\s+a\s+month\b", re.I), "monthly"),
    (re.compile(r"\bquarterly\b|\bevery\s+quarter\b", re.I), "quarterly"),
    (re.compile(r"\bannually\b|\byearly\b|\bevery\s+year\b|\bonce\s+a\s+year\b", re.I), "annually"),
]

WAGE_TEXT_RE = re.compile(r"\$\s?(\d+(?:\.\d+)?)\s*(?:/|per\s+)\s*(?:hr|hour)\b", re.I)
TIME_REDUCTION_RE = re.compile(
    r"(\d+(?:\.\d+)?)\s*(hours?|hrs?|h)\b[^.\n\d]{0,40}?(?:down to|to|\u2192|->|\u279e)\s*"
    r"(\d+(?:\.\d+)?)\s*(hours?|hrs?|h)?\b",
    re.I,
)
PERCENT_REDUCTION_RE = re.compile(
    r"(?:cut|reduced?|decreased?|dropped|shaved)[^.\n]{0,60}?by\s+(\d+(?:\.\d+)?)\s*%", re.I
)

HOUR_UNIT_FAMILY = ["hour", "hours", "hr", "hrs", "h"]

TRANSFERABILITY = (
    "this is arithmetic only -- it does not judge whether this achievement's "
    "context (company size, industry, scale) transfers to the target role. That "
    "judgment is yours to make before using this number in a real conversation."
)


def sentence_around(text: str, start: int, end: int) -> str:
    starts = [text.rfind(". ", 0, start) + 2, text.rfind("\n", 0, start) + 1]
    begin = max(starts)
    ends = [pos for pos in (text.find(". ", end), text.find("\n", end)) if pos != -1]
    finish = min(ends) if ends else len(text)
    return text[begin:finish].strip()


def format_number(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else str(value)


def parse_stories(text: str) -> list[dict]:
    """Split a story bank into stories by '### [Theme] Title' headers."""
    stories = []
    parts = re.split(r"^###\s+(.+)$", text, flags=re.MULTILINE)
    for index in range(1, len(parts), 2):
        title_line = parts[index].strip()
        body = parts[index + 1] if index + 1 < len(parts) else ""
        match = re.match(r"\[(.+?)\]\s*(.*)", title_line)
        theme, title = (match.group(1), match.group(2)) if match else (None, title_line)
        stories.append({"theme": theme, "title": title, "text": body})
    return stories


def extract_quantified_claims(story_text: str, story_title: str) -> list[dict]:
    claims = []
    for match in TIME_REDUCTION_RE.finditer(story_text):
        before_value, before_unit, after_value, after_unit = match.groups()
        claims.append({
            "story": story_title, "type": "time-reduction",
            "raw": match.group(0).strip(),
            "sentence": sentence_around(story_text, match.start(), match.end()),
            "before": {"value": float(before_value), "unit": before_unit},
            "after": {"value": float(after_value), "unit": after_unit or before_unit},
        })
    for match in PERCENT_REDUCTION_RE.finditer(story_text):
        claims.append({
            "story": story_title, "type": "percent-reduction",
            "raw": match.group(0).strip(),
            "sentence": sentence_around(story_text, match.start(), match.end()),
            "percent": float(match.group(1)),
        })
    return claims


def _number_variants(value: float, unit_family: list[str]) -> list[str]:
    number = format_number(value)
    variants = []
    for unit in unit_family:
        variants.append(f"{number} {unit}")
        variants.append(f"{number}{unit}")
    return variants


def _any_variant_in_text(variants: list[str], text: str) -> bool:
    haystack = text.casefold()
    for variant in variants:
        pattern = r"(?<![\d.])" + re.escape(variant.casefold()) + r"(?![\d.])"
        if re.search(pattern, haystack):
            return True
    return False


def _percentage_in_text(percent: float, text: str) -> bool:
    number = format_number(percent)
    return bool(re.search(rf"(?<![\d.]){re.escape(number)}\s?%(?!\d)", text.casefold()))


def verify_claim(claim: dict, resume_text: str) -> bool:
    """The gate. False means the claim never reaches output, not that it is flagged."""
    if claim["type"] == "time-reduction":
        before = _number_variants(claim["before"]["value"], HOUR_UNIT_FAMILY)
        after = _number_variants(claim["after"]["value"], HOUR_UNIT_FAMILY)
        return _any_variant_in_text(before, resume_text) and _any_variant_in_text(after, resume_text)
    if claim["type"] == "percent-reduction":
        return _percentage_in_text(claim["percent"], resume_text)
    return False


def resolve_frequency(story_text: str, frequency: str | None, occurrences: float | None):
    for pattern, key in _FREQ_PATTERNS:
        if pattern.search(story_text):
            return FREQUENCY_MAP[key], f'story text ("{key}")'
    if occurrences is not None:
        return occurrences, "--occurrences"
    if frequency and frequency in FREQUENCY_MAP:
        return FREQUENCY_MAP[frequency], f"--frequency {frequency}"
    return None, None


def resolve_wage(story_text: str, wage: float | None):
    match = WAGE_TEXT_RE.search(story_text)
    if match:
        value = float(match.group(1))
        return value, f'story text ("${format_number(value)}/hr")'
    if wage is not None:
        return wage, "--wage"
    return None, None


def compute_calculation(claim: dict, story_text: str, wage=None, frequency=None, occurrences=None):
    if claim["type"] != "time-reduction":
        return None, "percent-only claim: no time baseline to convert into hours saved"
    hours_saved = claim["before"]["value"] - claim["after"]["value"]
    if not hours_saved > 0:
        return None, (
            f"not a time reduction ({claim['before']['value']}h is not greater "
            f"than {claim['after']['value']}h)"
        )
    hourly, wage_source = resolve_wage(story_text, wage)
    if hourly is None:
        return None, (
            "missing hourly-wage basis -- supply --wage <number> or state it in the "
            'story ("$X/hr")'
        )
    per_year, frequency_source = resolve_frequency(story_text, frequency, occurrences)
    if per_year is None:
        return None, (
            "missing task frequency -- supply --frequency "
            "<daily|weekly|biweekly|monthly|quarterly|annually> / --occurrences <N>, "
            "or state it in the story"
        )
    annual_value = hours_saved * hourly * per_year
    return {
        "hours_saved_per_occurrence": hours_saved,
        "hourly_wage": hourly,
        "wage_source": wage_source,
        "occurrences_per_year": per_year,
        "frequency_source": frequency_source,
        "annual_value": annual_value,
        "formula": (
            f"{format_number(hours_saved)}h x ${format_number(hourly)}/hr x "
            f"{format_number(per_year)}/year = ${annual_value:,.0f}/year"
        ),
    }, None


def build_draft_paragraph(claim: dict, calculation: dict) -> str:
    return (
        f"Achievement: {claim['sentence']}\n"
        f"Estimated value: {calculation['formula']}\n"
        f"Note: {TRANSFERABILITY}"
    )


def analyze(story_bank_text: str, resume_text: str, wage=None, frequency=None, occurrences=None) -> dict:
    stories = parse_stories(story_bank_text)
    calculable, uncalculable, warnings = [], [], []
    claims_found = excluded_unverified = 0

    for story in stories:
        label = f"[{story['theme']}] {story['title']}" if story["theme"] else story["title"]
        claims = extract_quantified_claims(story["text"], label)
        claims_found += len(claims)
        for claim in claims:
            if not verify_claim(claim, resume_text):
                excluded_unverified += 1
                continue
            calculation, reason = compute_calculation(
                claim, story["text"], wage, frequency, occurrences)
            if calculation:
                calculable.append({
                    "story": claim["story"],
                    "claim_type": claim["type"],
                    "achievement": claim["sentence"],
                    "calculation": calculation,
                    "draft_paragraph": build_draft_paragraph(claim, calculation),
                })
            else:
                uncalculable.append({
                    "story": claim["story"],
                    "claim_type": claim["type"],
                    "achievement": claim["sentence"],
                    "reason": reason,
                })

    if excluded_unverified:
        warnings.append(
            f"{excluded_unverified} quantified claim(s) were excluded: no matching figure "
            "found verbatim in the resume (safety gate)."
        )
    if not stories:
        warnings.append("No stories found in the story bank.")

    return {
        "stories_scanned": len(stories),
        "claims_found": claims_found,
        "verified": len(calculable) + len(uncalculable),
        "excluded_unverified": excluded_unverified,
        "calculable": calculable,
        "uncalculable": uncalculable,
        "warnings": warnings,
        "gate": "negotiation-verbatim",
    }


def analyze_paths(root: Path | str, wage=None, frequency=None, occurrences=None) -> dict:
    """Run the gate over the workspace's own story bank and resume extract."""
    root = Path(root)
    story_bank = root / "interview-prep" / "story-bank.md"
    resume = root / "resume.md"
    missing = [str(path) for path in (story_bank, resume) if not path.exists()]
    if missing:
        return {
            "error": "missing required input",
            "missing": missing,
            "gate": "negotiation-verbatim",
        }
    return analyze(
        story_bank.read_text(encoding="utf-8", errors="replace"),
        resume.read_text(encoding="utf-8", errors="replace"),
        wage, frequency, occurrences,
    )


def write_drafts(root: Path | str, result: dict) -> Path:
    """Persist only the verified, calculable talking points."""
    root = Path(root)
    target = root / "negotiation-drafts.md"
    lines = [
        "# Negotiation talking points",
        "",
        "Generated from verified achievements only. Every figure below appears verbatim "
        "in the resume; anything that did not match was dropped by the safety gate.",
        "",
        f"- Stories scanned: {result.get('stories_scanned', 0)}",
        f"- Quantified claims found: {result.get('claims_found', 0)}",
        f"- Excluded (no verbatim resume match): {result.get('excluded_unverified', 0)}",
        "",
        "## Draft talking points",
        "",
    ]
    if result.get("calculable"):
        for entry in result["calculable"]:
            lines.append(f"### {entry['story']}")
            lines.append("")
            lines.append("```text")
            lines.append(entry["draft_paragraph"])
            lines.append("```")
            lines.append("")
    else:
        lines.append("None yet. A claim needs a time baseline, a stated wage and a stated "
                     "frequency before it can be converted into a number you can say out loud.")
        lines.append("")
    if result.get("uncalculable"):
        lines.append("## Verified but not calculable")
        lines.append("")
        for entry in result["uncalculable"]:
            lines.append(f"- **{entry['story']}** ({entry['claim_type']}): {entry['reason']}")
        lines.append("")
    if result.get("warnings"):
        lines.append("## Warnings")
        lines.append("")
        for warning in result["warnings"]:
            lines.append(f"- {warning}")
        lines.append("")
    target.write_text("\n".join(lines), encoding="utf-8")
    return target
