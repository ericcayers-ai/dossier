"""The hiring panel: seven seats, seven scores, and quotes that must be real."""
from __future__ import annotations

import pytest

from dossier.engine import panel

RESUME = """# A. Candidate
eric@example.com | 021 000 0000

## Experience

- Responsible for helping the team with various tasks — improving things
- Built a Python scraper that reduced manual data entry by 40%
- Worked on a dashboard used by 12 staff

## Education

2021 — University of Waikato, BSc Computer Science

## Skills

Python, SQL, Git
"""

POSTING = """We need a support engineer with Python, SQL and Linux experience.
You will write automation and runbooks. Docker exposure is a plus.
"""


def test_all_seven_seats_report_a_score():
    result = panel.run(RESUME, posting=POSTING)
    assert len(result["seats"]) == 7
    assert {seat["id"] for seat in result["seats"]} == {
        "ats", "recruiter", "manager", "lead", "keywords", "screen", "honesty"}
    assert all(0 <= seat["score"] <= 100 for seat in result["seats"])
    assert 0 <= result["score"] <= 100


def test_every_quote_is_the_documents_own_line():
    """The whole promise is "quotes the exact line"; it is checked, not trusted."""
    result = panel.run(RESUME, posting=POSTING)
    posting_lines = POSTING.split(chr(10))
    lines = RESUME.replace("\r\n", "\n").split("\n")
    quoted = 0
    for seat in result["seats"]:
        for finding in seat["findings"]:
            if finding["quote"]:
                quoted += 1
                assert finding["line"] is not None
                pool = posting_lines if finding.get("source") == "posting" else lines
                assert finding["quote"] in pool[finding["line"] - 1]
    for item in result["plan"]:
        if item["quote"]:
            pool = posting_lines if item.get("source") == "posting" else lines
            assert item["quote"] in pool[(item["line"] or 1) - 1]
    assert quoted >= 2, "the fixture has real objections to quote"


def test_a_fabricated_quote_is_refused():
    guard = panel._Guard(["a line", "another line"])
    with pytest.raises(ValueError):
        guard.finding("ats", 1, "words that are not there", "why", "fix")
    with pytest.raises(ValueError):
        guard.finding("ats", 9, "a line", "why", "fix")


def test_the_panel_names_the_weakest_three_in_order():
    result = panel.run(RESUME, posting=POSTING)
    assert 1 <= len(result["plan"]) <= 3
    assert [item["order"] for item in result["plan"]] == list(range(1, len(result["plan"]) + 1))
    seats = {seat["id"]: seat["score"] for seat in result["seats"]}
    assert seats["manager"] < seats["recruiter"], "the posting's unanswered must-haves cost most"


def test_without_a_posting_the_two_posting_seats_say_so():
    result = panel.run(RESUME)
    assert result["has_posting"] is False
    manager = next(seat for seat in result["seats"] if seat["id"] == "manager")
    assert manager["findings"][0]["why"].startswith("No posting was supplied")


def test_a_clean_resume_passes_and_has_no_plan():
    clean = """# Sam Rivers
sam@example.com | 021 111 1111

## Experience

- Built a Python parser that cut invoice handling from 40 minutes to 6 across 12 sites
- Migrated 31 SQL reports to a scheduled job, removing 9 hours of weekly copying

## Education

2019 University of Waikato, BSc Computer Science

## Skills

Python, SQL, Linux
"""
    posting = "Python and SQL for report automation in Linux."
    result = panel.run(clean, posting=posting)
    assert result["score"] >= 80, result["score"]
    assert result["verdict"] == "pass"
    ats = next(seat for seat in result["seats"] if seat["id"] == "ats")
    assert ats["score"] >= 80


def test_the_rendered_report_quotes_and_never_invents():
    text = panel.render(panel.run(RESUME, posting=POSTING))
    assert "# Hiring panel:" in text
    assert "## The chair's plan" in text
    assert "line 5" in text or "line 4" in text or "posting line" in text
