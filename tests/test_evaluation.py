"""The measurement that decides whether the ranking is any good.

These tests exist so the eval instrument cannot silently become a flattering one. The
four things that would make it lie are each asserted against: a metric with no labels
behind it, an ungraded row counted as relevant, a grade inferred from the score it is
meant to check, and a regression that passes because the labelled set shrank.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from dossier.engine import evaluation


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _posting(root: Path, stem: str, title: str, employer: str, location: str,
             url: str, body: str = "") -> Path:
    return _write(root / f"job-posting-{stem}.md",
                  f"# {title}\n\n- Employer: {employer}\n- Location: {location}\n"
                  f"Source: {url}\n\n{body or 'Python and SQL.'}\n")


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    root = tmp_path / "ws"
    _write(root / "DEVELOPER-IDENTITY.md",
           "# Identity\n\nLocation: Hamilton\nSeniority: student/intern\n")
    _write(root / "resume.md", "## Skills\nPython, SQL, Playwright\n")
    _write(root / "job-history.md",
           "| Date | Company | Role | Fit | Resume file | Status |\n"
           "|---|---|---|---|---|---|\n"
           "| Sep 2026 | Harbourline | Summer Internship Automate Pre-Upgrade Check | High | a.docx | drafted |\n"
           "| Sep 2026 | Farmers | Retail Assistants Christmas | Medium | b.docx | drafted |\n"
           "| Sep 2026 | Nowhere Ltd | Senior Staff Engineer | High | c.docx | drafted |\n")
    _posting(root, "Harbourline", "2026/2027 Harbourline Summer Internship", "Harbourline", "Hamilton",
             "https://example.test/harbourline-1", "Python SQL intern automation")
    _posting(root, "Farmers", "Retail Assistants Christmas 2026", "Farmers", "Hamilton",
             "https://example.test/farmers-1", "Serving customers at Christmas")
    _posting(root, "Aderant", "Software Engineer Intern", "Aderant", "Auckland",
             "https://example.test/aderant-1", "Python SQL intern software engineering")
    _posting(root, "Warehouse", "Cashier Team Member", "The Warehouse", "Cambridge",
             "https://example.test/warehouse-1", "Checkout and nightfill shifts")
    return root


# -- the arithmetic --------------------------------------------------------

def test_spearman_is_negative_one_for_the_exact_reverse():
    assert evaluation.spearman([1, 2, 3, 4], [4, 3, 2, 1]) == -1.0


def test_spearman_is_one_for_the_same_order():
    assert evaluation.spearman([10, 20, 30], [1, 2, 3]) == 1.0


def test_spearman_handles_tied_scores_without_pretending_they_are_distinct():
    """A ranker that emits the same score four times must not look like a ranker
    that ordered them, and ties must be averaged rather than broken by index."""
    assert evaluation.spearman([5, 5, 5, 5], [1, 2, 3, 4]) is None
    tied = evaluation.spearman([1, 2, 2, 3], [1, 2, 3, 4])
    assert tied is not None and 0 < tied < 1


def test_ndcg_is_one_when_the_ideal_order_is_returned():
    grades = [3, 2, 1, 0]
    assert evaluation.ndcg_at_k(grades, grades, 4) == 1.0


def test_ndcg_is_below_one_when_the_order_is_reversed():
    ideal = [3, 2, 1, 0]
    assert evaluation.ndcg_at_k(list(reversed(ideal)), ideal, 4) < 1.0


def test_precision_and_recall_of_an_empty_cut_are_none_not_zero():
    """`None` says "nothing was asked". 0.0 would claim a measurement was taken."""
    assert evaluation.precision_at_k([], 10) is None
    assert evaluation.recall_at_k([], [], 25) is None


# -- the labels file -------------------------------------------------------

@pytest.mark.parametrize("raw, expected", [
    ("High", "strong"), ("medium", "possible"), ("LOW", "unlikely"),
    ("strong", "strong"), ("", ""), ("null", ""), ("?", ""),
])
def test_grade_normalisation(raw, expected):
    assert evaluation.normalise_grade(raw) == expected


def test_labels_file_accepts_the_short_shape(tmp_path):
    path = _write(tmp_path / "labels.json", json.dumps({"url:x": "strong", "url:y": "possible"}))
    loaded = evaluation.load_labels(path)
    assert set(loaded["rows"]) == {"url:x", "url:y"}


def test_labels_file_keeps_the_grade_source(tmp_path):
    path = _write(tmp_path / "labels.json", json.dumps({"rows": [
        {"key": "url:x", "grade": "strong", "source_of_grade": "tracker"},
        {"key": "url:y", "grade": None},
    ]}))
    loaded = evaluation.load_labels(path)
    assert loaded["rows"]["url:x"]["source"] == "tracker"
    assert "url:y" not in loaded["rows"], "a null grade must not become a grade"


# -- the rows --------------------------------------------------------------

def test_posting_rows_read_the_header_block(workspace):
    rows = {row["title"]: row for row in evaluation.posting_rows(workspace)}
    harbourline = rows["2026/2027 Harbourline Summer Internship"]
    assert harbourline["employer"] == "Harbourline"
    assert harbourline["location"] == "Hamilton"
    assert harbourline["url"] == "https://example.test/harbourline-1"


def test_tracker_rows_skip_the_header_separator(workspace):
    rows = evaluation.tracker_rows(workspace)
    assert len(rows) == 3
    assert {row["fit"] for row in rows} == {"High", "Medium"}


def test_tracker_grade_is_carried_only_on_an_unambiguous_match(workspace):
    rows = evaluation.posting_rows(workspace)
    grades, unmatched = evaluation.labels_from_tracker(workspace, rows)
    carried = {entry["title"] for entry in grades.values()}
    assert "2026/2027 Harbourline Summer Internship" in carried
    assert "Retail Assistants Christmas 2026" in carried
    assert "Software Engineer Intern" not in carried
    assert [row["employer"] for row in unmatched] == ["Nowhere Ltd"]


# -- the evaluation --------------------------------------------------------

def test_eval_reports_no_evaluation_rather_than_zero_when_nothing_matched(workspace, tmp_path):
    grades = _write(tmp_path / "empty.json", json.dumps({"url:not-in-corpus": "strong"}))
    report = evaluation.evaluate_workspace(workspace, grades)
    assert report["present"] is False
    assert report["n_graded"] == 0
    assert "no grade matched" in report["reason"]


def test_eval_counts_an_ungraded_row_in_the_top_slots_as_a_miss(workspace, tmp_path):
    """The slots number is the one a user experiences: a row nobody graded sitting in
    the top ten is not a hit, and it must not inflate the judged-only number."""
    rows = evaluation.posting_rows(workspace)
    grades = {"rows": [{"key": evaluation.row_key(rows[0]), "grade": "strong"}]}
    path = _write(tmp_path / "one.json", json.dumps(grades))
    report = evaluation.evaluate_workspace(workspace, path, k=2)
    top = report["product"]
    assert top["precision_slots"] is not None
    assert top["precision_slots"] <= 0.5, "only one of the two slots can be a graded hit"
    assert top["judged_in_top_k"] <= 2


def test_eval_separates_tracker_grades_from_fresh_ones(workspace, tmp_path):
    rows = evaluation.posting_rows(workspace)
    grades = {"rows": [
        {"key": evaluation.row_key(rows[0]), "grade": "strong", "source_of_grade": "tracker"},
        {"key": evaluation.row_key(rows[1]), "grade": "possible", "source_of_grade": "human"},
    ]}
    path = _write(tmp_path / "mixed.json", json.dumps(grades))
    report = evaluation.evaluate_workspace(workspace, path)
    assert report["sources"]["tracker"] == 1
    assert report["sources"]["human"] == 1
    assert report["n_graded"] == 2


def test_worksheet_leaves_unmatched_rows_ungraded(workspace):
    sheet = evaluation.worksheet(workspace)
    by_title = {row["title"]: row for row in sheet["rows"]}
    assert by_title["2026/2027 Harbourline Summer Internship"]["grade"] == "strong"
    assert by_title["2026/2027 Harbourline Summer Internship"]["source_of_grade"] == "tracker"
    assert by_title["Software Engineer Intern"]["grade"] is None
    assert sheet["corpus_hash"]


# -- the regression gate ---------------------------------------------------

def _baseline(ndcg=0.9, spearman=0.5, n_graded=18) -> dict:
    return {"ndcg": ndcg, "spearman": spearman, "n_graded": n_graded}


def _report(ndcg=0.9, spearman=0.5, n_graded=18) -> dict:
    return {"present": True, "n_graded": n_graded,
            "product": {"ndcg": ndcg, "precision": 1.0, "spearman": spearman}}


def test_gate_passes_on_an_unchanged_metric():
    verdict = evaluation.compare_to_baseline(_report(), _baseline())
    assert verdict["ok"] is True


def test_gate_fails_when_ndcg_drops_past_the_slack():
    verdict = evaluation.compare_to_baseline(_report(ndcg=0.80), _baseline())
    assert verdict["ok"] is False
    assert "nDCG" in verdict["failures"][0]


def test_gate_fails_when_spearman_drops_past_the_slack():
    verdict = evaluation.compare_to_baseline(_report(spearman=0.10), _baseline())
    assert verdict["ok"] is False
    assert "Spearman" in verdict["failures"][0]


def test_gate_ignores_drift_inside_the_slack():
    verdict = evaluation.compare_to_baseline(_report(ndcg=0.89, spearman=0.47), _baseline())
    assert verdict["ok"] is True


def test_gate_refuses_a_set_that_shrank_to_less_than_half():
    verdict = evaluation.compare_to_baseline(_report(n_graded=4), _baseline(n_graded=18))
    assert verdict["ok"] is False
    assert "shrank" in verdict["failures"][0]


def test_gate_fails_when_there_is_no_evaluation_at_all():
    verdict = evaluation.compare_to_baseline({"present": False, "reason": "no grade matched"},
                                             _baseline())
    assert verdict["ok"] is False


def test_recorded_baseline_carries_the_numbers_it_will_be_compared_against():
    recorded = evaluation.record_baseline(_report())
    assert recorded["ndcg"] == 0.9 and recorded["spearman"] == 0.5
    assert recorded["n_graded"] == 18
