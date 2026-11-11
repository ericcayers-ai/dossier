"""Identity and relevance: mining with provenance, answers over documents, scoring.

The rules under test are the ones that make the shortlist trustworthy:

* a document value is a *proposal* with a file and line, never an assertion;
* an explicit answer beats a document value;
* a field with neither never appears, and `IDENTITY.md` refuses to invent one;
* a deal-breaker caps the band and is named — a weighted score never hides it;
* a capture can refuse an irrelevant page **and record that it did**.
"""

from __future__ import annotations

import json

import pytest

from dossier.engine import identity


def _workspace(root):
    (root / "DEVELOPER-IDENTITY.md").write_text(
        "# Sam Example — Developer Identity Reference\n\n"
        "Second-year Computer Science student at the University of Waikato, Hamilton, New Zealand.\n"
        "Primary email: sam@example.test; phone 021 555 0100.\n"
        "Timezone: Pacific/Auckland\n"
        "Looking for a summer internship; speak English and Japanese.\n",
        encoding="utf-8")
    (root / "resume.md").write_text(
        "# Sam\n\n## Experience\nBuilt things.\n\nSkills\n"
        "Technical: Python, SQL, Playwright, Git\n"
        "Communication: Clear writing\n",
        encoding="utf-8")
    (root / "job-history.md").write_text(
        "| Date | Company | Role | Fit | Resume file | Status |\n"
        "|---|---|---|---|---|---|\n"
        "| Sep 2026 | Acme | Software Engineer Intern | High | a.docx | drafted |\n"
        "| Aug 2026 | Beta | Data Analyst | Medium | b.docx | drafted |\n",
        encoding="utf-8")
    return root


# -- mining ----------------------------------------------------------------

def test_mining_reads_the_documents_and_cites_each_value(tmp_path):
    _workspace(tmp_path)
    proposals = {item["field"]: item for item in identity.mine_documents(tmp_path)}
    assert proposals["name"]["value"] == "Sam"
    assert proposals["email"]["value"] == "sam@example.test"
    assert proposals["timezone"]["value"] == "Pacific/Auckland"
    assert proposals["seniority"]["value"] == "student/intern"
    assert "Python" in proposals["skills"]["value"]
    assert "Software Engineer Intern" in proposals["applied_roles"]["value"]
    for item in proposals.values():
        assert item["source"].endswith(".md")
        assert item["line"] and item["line"] > 0, item["field"]
        assert item["evidence"]


def test_an_empty_workspace_proposes_nothing_and_invents_nothing(tmp_path):
    assert identity.mine_documents(tmp_path) == []
    data = identity.profile(tmp_path)
    assert data["fields"] == {}
    assert data["complete"] is False


def test_an_answer_beats_a_mined_value(tmp_path):
    _workspace(tmp_path)
    identity.save_answers(tmp_path, {"location": "Auckland"})
    data = identity.profile(tmp_path)
    assert data["fields"]["location"]["value"] == "Auckland"
    assert data["fields"]["location"]["source"] == "answer"
    # A mined field that was not answered keeps its provenance.
    assert data["fields"]["timezone"]["source"] == "document"
    assert data["fields"]["timezone"]["evidence"]["path"].endswith(".md")


def test_clearing_an_answer_removes_it(tmp_path):
    _workspace(tmp_path)
    identity.save_answers(tmp_path, {"location": "Auckland"})
    identity.save_answers(tmp_path, {"location": ""})
    assert "location" not in identity.load_answers(tmp_path)


def test_an_unknown_question_is_refused(tmp_path):
    with pytest.raises(ValueError) as caught:
        identity.save_answers(tmp_path, {"favourite_colour": "blue"})
    assert "favourite_colour" in str(caught.value)


def test_completeness_names_exactly_the_required_gaps(tmp_path):
    _workspace(tmp_path)
    data = identity.profile(tmp_path)
    assert set(data["missing_required"]) == {"target_roles", "employment", "right_to_work",
                                             "location"} - {"location", "target_roles"}
    identity.save_answers(tmp_path, {"target_roles": "Software Engineer Intern",
                                     "employment": "internship", "location": "Hamilton",
                                     "right_to_work": "citizen"})
    data = identity.profile(tmp_path)
    assert data["missing_required"] == []
    assert data["complete"] is True


def test_the_questionnaire_reports_what_is_already_known(tmp_path):
    _workspace(tmp_path)
    identity.save_answers(tmp_path, {"employment": "internship"})
    rows = {row["id"]: row for row in identity.questions_with_state(tmp_path)}
    assert rows["employment"]["answered"] is True
    assert rows["employment"]["source"] == "answer"
    assert rows["seniority"]["answered"] is True
    assert rows["seniority"]["source"] == "document"
    assert rows["seniority"]["evidence"]["path"]


# -- writing ---------------------------------------------------------------

def test_write_updates_a_managed_block_and_preserves_user_prose(tmp_path):
    _workspace(tmp_path)
    identity.save_answers(tmp_path, {"employment": "internship"})
    first = identity.write_identity(tmp_path)
    assert first["path"] == "DEVELOPER-IDENTITY.md"
    text = (tmp_path / "DEVELOPER-IDENTITY.md").read_text(encoding="utf-8")
    assert identity.IDENTITY_MARKER_START in text
    assert "Sam Example — Developer Identity Reference" in text, "user prose was destroyed"
    assert "**Employment:** internship" in text

    identity.save_answers(tmp_path, {"employment": "part-time"})
    identity.write_identity(tmp_path)
    text = (tmp_path / "DEVELOPER-IDENTITY.md").read_text(encoding="utf-8")
    assert text.count(identity.IDENTITY_MARKER_START) == 1
    assert "part-time" in text and "**Employment:** internship" not in text


def test_write_refuses_an_empty_identity(tmp_path):
    with pytest.raises(ValueError):
        identity.write_identity(tmp_path)


def test_write_names_a_new_document_so_the_workspace_can_find_it(tmp_path):
    """A first write must land on *-IDENTITY.md: a plain IDENTITY.md default was
    invisible to document mining and to the agent's identity blocker."""
    identity.save_answers(tmp_path, {"target_roles": "software engineer",
                                     "seniority": "graduate", "employment": "full-time",
                                     "location": "Hamilton", "right_to_work": "NZ citizen"})
    written = identity.write_identity(tmp_path)
    assert written["path"].endswith("-IDENTITY.md")
    from dossier.agent import workspace
    space = workspace.resolve(tmp_path)
    assert space.identity_doc is not None
    assert not any("IDENTITY.md found" in blocker for blocker in space.blockers)


# -- scoring ---------------------------------------------------------------

PROFILE = {
    "fields": {
        "target_roles": {"value": ["Software Engineer Intern", "Backend Developer"], "source": "answer"},
        "seniority": {"value": "student/intern", "source": "answer"},
        "employment": {"value": ["internship"], "source": "answer"},
        "location": {"value": "Hamilton", "source": "answer"},
        "remote": {"value": "yes", "source": "answer"},
        "must_have": {"value": ["Python"], "source": "answer"},
        "deal_breakers": {"value": ["commission only", "door-to-door"], "source": "answer"},
        "salary_floor": {"value": 60000, "source": "answer"},
        "skills": {"value": ["Python", "SQL"], "source": "document"},
    }
}

GOOD = {"title": "Software Engineer Intern", "employer": "Acme", "location": "Hamilton",
        "work_type": "internship", "description": "Python and SQL. Build things.",
        "pay": "$65,000", "date": "2026-11-01T00:00:00+00:00"}
BAD = {"title": "Senior Principal Engineer", "employer": "BigCo", "location": "Auckland",
       "work_type": "full-time", "description": "10+ years required. Commission only.",
       "pay": "$40,000", "date": "2025-01-01T00:00:00+00:00"}


def test_a_matching_job_scores_strong_with_reasons():
    result = identity.score_job(GOOD, PROFILE)
    assert result["band"] == "strong"
    assert result["score"] >= 65
    assert result["disqualifiers"] == []
    assert any("title matches your target" in reason for reason in result["reasons"])
    assert any("must-have" in reason for reason in result["reasons"])


def test_a_deal_breaker_caps_the_band_and_is_named():
    result = identity.score_job(BAD, PROFILE)
    assert result["band"] == "unlikely"
    assert result["disqualifiers"], "a deal-breaker must be recorded"
    assert "commission only" in result["disqualifiers"][0]
    assert result["score"] <= 25


def test_a_senior_role_cannot_outrank_a_student_target():
    job = dict(GOOD, title="Senior Software Engineer", description="Python. 8+ years.")
    result = identity.score_job(job, PROFILE)
    assert result["band"] == "unlikely"
    assert any("senior" in item for item in result["disqualifiers"])


def test_pay_below_the_floor_disqualifies():
    job = dict(GOOD, pay="$45,000")
    result = identity.score_job(job, PROFILE)
    assert result["band"] == "unlikely"
    assert any("floor" in item for item in result["disqualifiers"])


def test_onsite_only_disqualifies_a_remote_role():
    profile = json.loads(json.dumps(PROFILE))
    profile["fields"]["remote"]["value"] = "onsite only"
    job = dict(GOOD, location="Remote", work_type="internship")
    result = identity.score_job(job, profile)
    assert any("remote" in item for item in result["disqualifiers"])


def test_role_families_match_without_an_exact_title():
    profile = json.loads(json.dumps(PROFILE))
    profile["fields"]["target_roles"]["value"] = ["software engineer"]
    result = identity.score_job(dict(GOOD, title="Backend Developer"), profile)
    assert any("role family" in reason for reason in result["reasons"])


# -- ranking the corpus ----------------------------------------------------

def _corpus(root, rows):
    (root / "all_boards_data").mkdir(parents=True, exist_ok=True)
    (root / "all_boards_data" / "all_jobs.json").write_text(json.dumps(rows), encoding="utf-8")


def test_ranking_returns_a_shortlist_and_keeps_the_disqualified_visible(tmp_path):
    identity.save_answers(tmp_path, {key: PROFILE["fields"][key]["value"]
                                     for key in ("target_roles", "seniority", "employment",
                                                 "location", "remote", "must_have",
                                                 "deal_breakers", "salary_floor")})
    _corpus(tmp_path, [dict(GOOD, id="1", url="https://a/1", source="remoteok"),
                       dict(BAD, id="2", url="https://a/2", source="remoteok")])
    report = identity.rank_corpus(tmp_path, limit=10)
    assert report["present"] is True
    assert report["rows"] == 2
    assert report["matched"][0]["title"] == "Software Engineer Intern"
    assert report["band_counts"]["strong"] == 1
    assert report["disqualified"] and report["disqualified"][0]["title"] == BAD["title"]
    assert report["disqualified"][0]["disqualifiers"]


def test_ranking_says_why_it_cannot_run(tmp_path):
    empty = identity.rank_corpus(tmp_path)
    assert empty["present"] is False and "identity" in empty["reason"]
    identity.save_answers(tmp_path, {"target_roles": "Engineer", "seniority": "junior",
                                     "employment": "full-time", "location": "Hamilton",
                                     "right_to_work": "citizen"})
    no_corpus = identity.rank_corpus(tmp_path)
    assert no_corpus["present"] is False and "corpus" in no_corpus["reason"]


def test_match_band_filter_excludes_lower_bands(tmp_path):
    identity.save_answers(tmp_path, {key: PROFILE["fields"][key]["value"]
                                     for key in ("target_roles", "seniority", "employment",
                                                 "location", "remote", "must_have",
                                                 "deal_breakers", "salary_floor")})
    _corpus(tmp_path, [dict(GOOD, id="1", url="https://a/1"),
                       dict(GOOD, id="2", url="https://a/2", title="Barista",
                            description="Coffee.", location="Hamilton")])
    strong_only = identity.rank_corpus(tmp_path, limit=10, min_band="strong")
    assert all(row["band"] == "strong" for row in strong_only["matched"])


# -- the surfaces ----------------------------------------------------------

def test_the_cli_answers_mines_and_matches(tmp_path, capsys):
    from dossier import cli

    _workspace(tmp_path)
    assert cli.main(["identity", "questions", "--root", str(tmp_path), "--json"]) == 0
    out = capsys.readouterr().out
    assert "target_roles" in out
    assert cli.main(["identity", "answer", "--root", str(tmp_path),
                     "--from-json", _answers_file(tmp_path)]) == 0
    assert cli.main(["identity", "mine", "--root", str(tmp_path), "--json"]) == 0
    assert "python" in capsys.readouterr().out.casefold()
    assert cli.main(["identity", "write", "--root", str(tmp_path)]) == 0
    assert "DEVELOPER-IDENTITY.md" in capsys.readouterr().out
    _corpus(tmp_path, [dict(GOOD, id="1", url="https://a/1")])
    assert cli.main(["identity", "match", "--root", str(tmp_path)]) == 0
    assert "Software Engineer Intern" in capsys.readouterr().out


def _answers_file(root):
    path = root / "answers.json"
    path.write_text(json.dumps({"target_roles": "Software Engineer Intern",
                                "seniority": "student/intern", "employment": "internship",
                                "location": "Hamilton", "right_to_work": "citizen",
                                "must_have": "Python", "salary_floor": 60000}), encoding="utf-8")
    return str(path)


def test_the_api_exposes_the_identity_and_the_match(tmp_path):
    from fastapi.testclient import TestClient
    from dossier.api.app import create_app
    from dossier.config import AppConfig

    _workspace(tmp_path)
    _corpus(tmp_path, [dict(GOOD, id="1", url="https://a/1"), dict(BAD, id="2", url="https://a/2")])
    app = create_app(AppConfig.create(tmp_path, token="identity-token"))
    client = TestClient(app, raise_server_exceptions=False)
    headers = {"Authorization": "Bearer identity-token"}

    state = client.get("/api/identity", headers=headers).json()
    assert state["questions"] == len(identity.QUESTIONS)
    assert len(state["question_list"]) == len(identity.QUESTIONS)
    assert state["proposals"]
    assert state["complete"] is False

    saved = client.post("/api/identity/answers", headers=headers, json={"answers": {
        "target_roles": "Software Engineer Intern", "seniority": "student/intern",
        "employment": "internship", "location": "Hamilton", "right_to_work": "citizen",
        "deal_breakers": "commission only", "salary_floor": 60000}})
    assert saved.status_code == 200 and saved.json()["complete"] is True

    written = client.post("/api/identity/write", headers=headers, json={})
    assert written.status_code == 200 and written.json()["fields"] > 0

    match = client.get("/api/match", headers=headers, params={"limit": 10}).json()
    assert match["present"] is True and match["rows"] == 2
    assert match["matched"][0]["title"] == "Software Engineer Intern"
    assert match["disqualified"]

    bad = client.post("/api/identity/answers", headers=headers, json={"answers": {"nope": 1}})
    assert bad.status_code == 400
