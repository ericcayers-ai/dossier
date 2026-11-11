"""Build a fictional demo workspace and run the six-step pipeline over it.

Open item D asked for a live instance of the product; this script creates one
that can be rebuilt at any time, so the instance never depends on a scratch
folder surviving. The board is served in-process (httpx MockTransport); every
other step is the real CLI writing real files. Nothing here is a real person,
employer or application, and nothing is submitted anywhere.

Run with the repo's interpreter:

    .venv/Scripts/python.exe scripts/build_demo_workspace.py [target-dir]

Default target: C:/dossier-demo/workspace. The committed companion is
tests/test_pipeline.py, which asserts the same run over a temporary workspace.
"""
import contextlib
import datetime as dt
import io
import json
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

import httpx
from docx import Document
from dossier import cli

ROOT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("C:/dossier-demo/workspace")
ROOT.mkdir(parents=True, exist_ok=True)
root = str(ROOT)
today = dt.date.today()

BOARD = {"jobs": [
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


def run(argv, expect=0):
    print(f"\n$ dossier {' '.join(argv)}")
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        code = cli.main(argv)
    out = buffer.getvalue()
    print(out, end="")
    assert code == expect, f"exit {code}, expected {expect}"
    return out


payload = json.dumps(BOARD).encode("utf-8")
original = httpx.Client


class Patched(original):
    def __init__(self, *a, **k):
        k["transport"] = httpx.MockTransport(
            lambda request: httpx.Response(200, content=payload,
                                           headers={"content-type": "application/json"}))
        super().__init__(*a, **k)


(ROOT / "resume.md").write_text("## Skills\nPython, SQL, Docker\n", encoding="utf-8")
(ROOT / "README.md").write_text(
    "# Demo workspace\n\nFictional data for verifying the Dossier pipeline and UI.\n"
    "No real person, employer or application. Nothing here was submitted anywhere.\n",
    encoding="utf-8")

print("== 1. ingest ==")
httpx.Client = Patched
try:
    run(["feeds", "fetch", "greenhouse", "--board", "acme", "--root", root, "--limit", "50", "--json"])
finally:
    httpx.Client = original
run(["corpus", "build", "--root", root, "--json"])

print("\n== 2. filter ==")
answers = {"target_roles": "software engineer", "seniority": "graduate",
           "employment": "full-time, internship", "location": "Hamilton",
           "right_to_work": "NZ citizen", "deal_breakers": "commission-only",
           "must_have": "Python"}
answers_path = ROOT / "answers.json"
answers_path.write_text(json.dumps(answers, indent=2), encoding="utf-8")
run(["identity", "answer", "--from-json", str(answers_path), "--root", root, "--json"])
match = json.loads(run(["identity", "match", "--root", root, "--json"]))
band = match["matched"][0]["band"]
run(["identity", "write", "--root", root, "--json"])

# Fit is the agent's judgement over the measured bands (a demo choice, labelled
# as such); propagate carries it onto the corpus without re-scoring.
fit_by_band = {"strong": "High", "possible": "Medium", "unlikely": "Low"}
ranking = [{"url": row["url"], "title": row["title"], "employer": row["employer"],
            "fit": fit_by_band[row["band"]], "fit_reason": "; ".join(row["reasons"])}
           for row in match["matched"]]
ranking += [{"url": row["url"], "title": row["title"], "employer": row["employer"],
             "fit": "Skip", "fit_reason": "; ".join(row["disqualifiers"])}
            for row in match["disqualified"]]
ranking_path = ROOT / "ranking.json"
ranking_path.write_text(json.dumps(ranking, indent=2), encoding="utf-8")
run(["corpus", "propagate", "--ranking", str(ranking_path), "--root", root, "--json"])

print("\n== 3. tailor ==")
base = ROOT / "templates" / "base-resume.docx"
base.parent.mkdir(parents=True, exist_ok=True)
document = Document()
document.add_paragraph().add_run("{{Name}}").bold = True
document.add_paragraph("Objective: {{ objective }}")
document.add_paragraph("Skills: Python, SQL, Docker")
table = document.add_table(rows=1, cols=2)
table.cell(0, 0).text = "Phone: {{Phone}}"
table.cell(0, 1).text = "Email: {{Email}}"
document.save(str(base))
run(["tailor", "fields", "--template", str(base)])
fields = {"Name": "Alex Example",
          "objective": "Graduate software engineer — Python and SQL data pipelines",
          "Phone": "021 000 0000", "Email": "alex@example.test"}
spec_path = ROOT / "fields.json"
spec_path.write_text(json.dumps({"fields": fields}, indent=2), encoding="utf-8")
variant = ROOT / "variants" / "resume_acme-software-engineer.docx"
run(["tailor", "template", "--template", str(base), "--spec", str(spec_path),
     "--out", str(variant), "--root", root])
run(["verify", "template", "--template", str(base), "--candidate", str(variant),
     "--spec", str(spec_path)])

print("\n== 4. letter ==")
letter_spec = {"name": fields["Name"], "contact": f"{fields['Email']} | {fields['Phone']}",
               "date_line": today.strftime("%d %B %Y").lstrip("0"),
               "recipient": "Hiring Team, Acme", "greeting": "Dear Hiring Team,",
               "body": ["I am applying for the Software Engineer role advertised on your Greenhouse board.",
                        "My background is in Python and SQL data pipelines, and I am looking for a "
                        "graduate role where I can build them in production."],
               "signoff": "Kind regards,\nAlex Example"}
letter_spec_path = ROOT / "letter.json"
letter_spec_path.write_text(json.dumps(letter_spec, indent=2), encoding="utf-8")
letter = ROOT / "letters" / "acme-cover-letter.docx"
run(["tailor", "cover-letter", "--base", str(variant), "--spec", str(letter_spec_path),
     "--out", str(letter), "--root", root, "--json"])

print("\n== 5. track ==")
(ROOT / "job-history.md").write_text(
    "# Job history\n\n"
    "| Date | Company | Role | Fit | Resume file | Status | Notes |\n"
    "| --- | --- | --- | --- | --- | --- | --- |\n"
    f"| {today.isoformat()} | Acme | Software Engineer | {band} | variants/resume_acme-software-engineer.docx "
    "| drafted | tailored from the greenhouse capture |\n", encoding="utf-8")
run(["track", "outcome", "1", "applied", "--root", root, "--json"], expect=1)
run(["track", "outcome", "1", "applied", "--applied", today.isoformat(),
     "--confirmed", "--root", root, "--json"])
(ROOT / "follow-ups.md").write_text("# Follow-ups\n", encoding="utf-8")
run(["track", "followup", "1", "--date", today.isoformat(), "--channel", "email",
     "--root", root, "--json"])

print("\n== 6. the tracker answers ==")
run(["track", "summary", "--root", root, "--json"])
run(["track", "cadence", "--root", root])

print("\n== 7. agent status ==")
status = json.loads(run(["agent", "status", "--root", root, "--json"]))
assert status["blockers"] == [], f"demo workspace has blockers: {status['blockers']}"
print("\ndemo workspace ready:", root)
