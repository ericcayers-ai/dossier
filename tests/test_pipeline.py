"""The six-step job pipeline, end to end over one workspace.

Open item D: the pieces existed but nothing ran ingest -> filter -> tailor ->
letter -> track over a single workspace and then asked the tracker "what did I
apply to, with which variant, and what is next". This is that run, through the
real CLI, with the two submission gates refused before they are satisfied.

Every person, employer and document here is fictional.
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

from docx import Document

from dossier import cli
from dossier.engine import tracker

BOARD_PAYLOAD = {"jobs": [
    {"id": 1, "title": "Software Engineer", "company": "Acme",
     "location": {"name": "Hamilton"}, "absolute_url": "https://boards.example/acme/1",
     "description": "<p>Build data pipelines with Python and SQL.</p>"},
    {"id": 2, "title": "Commission-only Sales Agent", "company": "Beta",
     "location": {"name": "Remote"}, "absolute_url": "https://boards.example/beta/2",
     "description": "<p>Uncapped earning potential.</p>"},
    {"id": 3, "title": "Senior Legal Counsel", "company": "Gamma",
     "location": {"name": "Auckland"}, "absolute_url": "https://boards.example/gamma/3",
     "description": "<p>Advise the business on commercial contracts.</p>"},
]}

ANSWERS = {
    "target_roles": "software engineer",
    "seniority": "graduate",
    "employment": "full-time, internship",
    "location": "Hamilton",
    "right_to_work": "NZ citizen",
    "deal_breakers": "commission-only",
    "must_have": "Python",
}

FIELDS = {"Name": "Alex Example",
          "objective": "Graduate software engineer — Python and SQL data pipelines",
          "Phone": "021 000 0000", "Email": "alex@example.test"}


def _run(capsys, argv, expect=0):
    code = cli.main(argv)
    out = capsys.readouterr().out
    assert code == expect, f"{argv} exited {code}, expected {expect}\n{out}"
    return json.loads(out) if "--json" in argv else out


def _base_template(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    document = Document()
    name = document.add_paragraph()
    name.add_run("{{Name}}").bold = True
    document.add_paragraph("Objective: {{ objective }}")
    document.add_paragraph("Skills: Python, SQL, Docker")
    table = document.add_table(rows=1, cols=2)
    table.cell(0, 0).text = "Phone: {{Phone}}"
    table.cell(0, 1).text = "Email: {{Email}}"
    document.save(str(path))
    return path


def test_the_six_step_pipeline_runs_over_one_workspace(tmp_path, capsys):
    import httpx

    root = str(tmp_path)
    today = dt.date.today()
    (tmp_path / "resume.md").write_text("## Skills\nPython, SQL, Docker\n", encoding="utf-8")

    # 1. Ingest: a board capture lands as corpus rows, and records its coverage.
    payload = json.dumps(BOARD_PAYLOAD).encode("utf-8")

    def handler(request):
        return httpx.Response(200, content=payload,
                              headers={"content-type": "application/json"})

    original = httpx.Client

    class Patched(original):
        def __init__(self, *args, **kwargs):
            kwargs["transport"] = httpx.MockTransport(handler)
            super().__init__(*args, **kwargs)

    httpx.Client = Patched
    try:
        _run(capsys, ["feeds", "fetch", "greenhouse", "--board", "acme",
                      "--root", root, "--limit", "50", "--json"])
    finally:
        httpx.Client = original

    built = _run(capsys, ["corpus", "build", "--root", root, "--json"])
    assert built["rows"] == 3 and built["distinct_ids"] == 3
    snapshot = json.loads(
        (tmp_path / f"nz-job-search-coverage-{today.isoformat()}.json").read_text(encoding="utf-8"))
    assert snapshot["source_statuses"] == {"greenhouse": "captured"}
    assert snapshot["current_source_counts"] == {"greenhouse": 3}

    # 2. Filter: answered intent scores the corpus; rejects stay listed with a reason.
    answers_path = tmp_path / "answers.json"
    answers_path.write_text(json.dumps(ANSWERS), encoding="utf-8")
    saved = _run(capsys, ["identity", "answer", "--from-json", str(answers_path),
                          "--root", root, "--json"])
    assert saved["complete"] is True and saved["missing_required"] == []

    match = _run(capsys, ["identity", "match", "--root", root, "--json"])
    assert match["present"] is True and match["scored"] == 3
    assert match["matched"][0]["title"] == "Software Engineer"
    assert match["matched"][0]["employer"] == "Acme"
    rejected = {row["title"]: row for row in match["disqualified"]}
    assert "Commission-only Sales Agent" in rejected
    assert "deal-breaker" in rejected["Commission-only Sales Agent"]["disqualifiers"][0]
    band = match["matched"][0]["band"]

    # The grounded profile becomes the workspace's identity document.
    written_identity = _run(capsys, ["identity", "write", "--root", root, "--json"])
    assert written_identity["path"].endswith("-IDENTITY.md")
    assert written_identity["fields"] > 0
    assert (tmp_path / written_identity["path"]).exists()

    # Fit is a judgement recorded over the measured bands, never a re-score;
    # propagate carries it onto the corpus and refuses unmatched rows.
    fit_by_band = {"strong": "High", "possible": "Medium", "unlikely": "Low"}
    ranking = [{"url": row["url"], "title": row["title"], "employer": row["employer"],
                "fit": fit_by_band[row["band"]], "fit_reason": "; ".join(row["reasons"])}
               for row in match["matched"]]
    ranking += [{"url": row["url"], "title": row["title"], "employer": row["employer"],
                 "fit": "Skip", "fit_reason": "; ".join(row["disqualifiers"])}
                for row in match["disqualified"]]
    ranking_path = tmp_path / "ranking.json"
    ranking_path.write_text(json.dumps(ranking), encoding="utf-8")
    propagated = _run(capsys, ["corpus", "propagate", "--ranking", str(ranking_path),
                               "--root", root, "--json"])
    assert propagated["unmatched"] == 0 and propagated["scored_after"] == 3

    # 3. Tailor: the user's own template, filled from a spec grounded in the posting.
    base = _base_template(tmp_path / "templates" / "base-resume.docx")
    listed = _run(capsys, ["tailor", "fields", "--template", str(base), "--json"])
    assert listed["fields"] == ["Name", "objective", "Phone", "Email"]
    spec_path = tmp_path / "fields.json"
    spec_path.write_text(json.dumps({"fields": FIELDS}), encoding="utf-8")
    variant = tmp_path / "variants" / "resume_acme-software-engineer.docx"
    filled = _run(capsys, ["tailor", "template", "--template", str(base),
                           "--spec", str(spec_path), "--out", str(variant),
                           "--root", root, "--json"])
    assert filled["written"] is True and filled["leftovers"] == []
    checked = _run(capsys, ["verify", "template", "--template", str(base),
                            "--candidate", str(variant), "--spec", str(spec_path), "--json"])
    assert checked["passed"] is True
    tailored_text = "\n".join(p.text for p in Document(str(variant)).paragraphs)
    assert FIELDS["objective"] in tailored_text
    assert "Skills: Python, SQL, Docker" in tailored_text

    # 4. Letter: the resume's sibling, built from the tailored variant.
    letter_spec = {
        "name": FIELDS["Name"],
        "contact": f"{FIELDS['Email']} | {FIELDS['Phone']}",
        "date_line": today.strftime("%d %B %Y").lstrip("0"),
        "recipient": "Hiring Team, Acme",
        "greeting": "Dear Hiring Team,",
        "body": [
            "I am applying for the Software Engineer role advertised on your Greenhouse board.",
            "My background is in Python and SQL data pipelines, and I am looking for a "
            "graduate role where I can build them in production.",
        ],
        "signoff": "Kind regards,\nAlex Example",
    }
    letter_spec_path = tmp_path / "letter.json"
    letter_spec_path.write_text(json.dumps(letter_spec), encoding="utf-8")
    letter = tmp_path / "letters" / "acme-cover-letter.docx"
    built_letter = _run(capsys, ["tailor", "cover-letter", "--base", str(variant),
                                 "--spec", str(letter_spec_path), "--out", str(letter),
                                 "--root", root, "--json"])
    assert Path(built_letter["output"]).exists()
    letter_text = "\n".join(p.text for p in Document(str(letter)).paragraphs)
    assert letter_spec["body"][0] in letter_text
    assert FIELDS["Name"] in letter_text

    # 5. Track: the agent writes the row (job-history.md is user/agent-authored),
    # then the submission gates refuse until the user confirms.
    variant_rel = "variants/resume_acme-software-engineer.docx"
    (tmp_path / "job-history.md").write_text(
        "# Job history\n\n"
        "| Date | Company | Role | Fit | Resume file | Status | Notes |\n"
        "| --- | --- | --- | --- | --- | --- | --- |\n"
        f"| {today.isoformat()} | Acme | Software Engineer | {band} | {variant_rel} "
        "| drafted | tailored from the greenhouse capture |\n",
        encoding="utf-8")

    refused = _run(capsys, ["track", "outcome", "1", "applied", "--root", root, "--json"], expect=1)
    assert refused["refused"] == "drafted-is-not-applied"
    refused = _run(capsys, ["track", "outcome", "1", "applied", "--applied", today.isoformat(),
                            "--root", root, "--json"], expect=1)
    assert refused["refused"] == "drafted-is-not-applied"
    applied = _run(capsys, ["track", "outcome", "1", "applied", "--applied", today.isoformat(),
                            "--confirmed", "--root", root, "--json"])
    assert applied["written"] is True

    # 6. The tracker alone answers: what, with which variant, and what is next.
    summary = _run(capsys, ["track", "summary", "--root", root, "--json"])
    assert summary["rows"] == 1 and summary["status_counts"] == {"applied": 1}
    assert summary["confirmed_application_dates"] == {"1": today.isoformat()}

    # The agent contract reads the same confirmed date the engine does.
    from dossier.agent import workspace
    space = workspace.resolve(tmp_path)
    assert space.tracker["confirmed_application_dates"] == {"1": today.isoformat()}
    assert space.tracker["actionable_without_date"] == []

    records = tracker.parse(tmp_path)
    assert records[0]["company"] == "Acme"
    assert records[0]["role"] == "Software Engineer"
    assert records[0]["resume"] == variant_rel
    assert (tmp_path / variant_rel).exists()

    cadence = _run(capsys, ["track", "cadence", "--root", root, "--json"])
    entry = cadence["entries"][0]
    assert entry["number"] == 1 and entry["company"] == "Acme"
    assert entry["applied_date"] == today.isoformat()
    assert entry["next_date"] is not None and entry["next_date"] >= today.isoformat()

    # follow-ups.md is agent-authored like job-history.md; the command appends only.
    (tmp_path / "follow-ups.md").write_text("# Follow-ups\n", encoding="utf-8")
    followed = _run(capsys, ["track", "followup", "1", "--date", today.isoformat(),
                             "--channel", "email", "--root", root, "--json"])
    assert followed["written"] is True
    cadence = _run(capsys, ["track", "cadence", "--root", root, "--json"])
    assert cadence["entries"][0]["followup_count"] == 1

    history = (tmp_path / "job-history.md").read_text(encoding="utf-8")
    assert "applied" in history and variant_rel in history

    # With all six steps done the workspace reports no blockers: identity doc,
    # base document, scored corpus, fresh coverage and a dated tracker row.
    space = workspace.resolve(tmp_path)
    assert space.blockers == []
    assert space.counts["base_documents"] == 1
    assert space.counts["artefacts"] >= 1
