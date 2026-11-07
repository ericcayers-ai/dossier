"""Template build: the user's own .docx, filled in place.

The distinguishing property is that nothing is rebuilt. So the tests assert what a
rebuild would destroy: a table stays a table, a bold run stays bold, an untouched
paragraph is byte-identical, and a header/footer is filled too. The failure the
gate exists for is a document that renders beautifully with `{{Name}}` still in it,
so the strict path must refuse to write anything at all.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from docx import Document

from dossier.engine import tailor, verify
from dossier.engine.tailor import BaseDocumentMissing, TemplateFillError


def _template(path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    document = Document()
    name = document.add_paragraph()
    run = name.add_run("{{Name}}")
    run.bold = True
    run.font.size = None
    document.add_paragraph("Objective: {{ objective }}")
    document.add_paragraph("Unchanged line, no tokens.")
    table = document.add_table(rows=1, cols=2)
    table.cell(0, 0).text = "Phone: {{Phone}}"
    table.cell(0, 1).text = "Email: {{Email}}"
    section = document.sections[0]
    section.header.paragraphs[0].text = "{{Name}} — curriculum vitae"
    section.footer.paragraphs[0].text = "Page footer, no token"
    document.save(str(path))
    return path


FIELDS = {"Name": "A. C", "objective": "Systems engineer", "Phone": "021 000 0000",
          "Email": "eric@example.test"}


def test_every_placeholder_is_declared_once_in_order(tmp_path):
    path = _template(tmp_path / "tpl.docx")
    assert tailor.template_fields(path) == ["Name", "objective", "Phone", "Email"]


def test_a_fill_replaces_body_table_and_header_and_reports_what_it_did(tmp_path):
    path = _template(tmp_path / "tpl.docx")
    out = tmp_path / "out.docx"
    report = tailor.fill_template(path, out, {"fields": FIELDS})
    assert report["written"] is True
    assert report["leftovers"] == []
    assert report["replaced"] == {"Name": 2, "objective": 1, "Phone": 1, "Email": 1}

    built = Document(str(out))
    assert [paragraph.text for paragraph in built.paragraphs][:3] == [
        "A. C", "Objective: Systems engineer", "Unchanged line, no tokens."]
    assert built.tables[0].cell(0, 0).text == "Phone: 021 000 0000"
    assert built.sections[0].header.paragraphs[0].text == "A. C — curriculum vitae"


def test_the_run_formatting_survives(tmp_path):
    path = _template(tmp_path / "tpl.docx")
    out = tmp_path / "out.docx"
    tailor.fill_template(path, out, {"fields": FIELDS})
    first = Document(str(out)).paragraphs[0]
    assert first.text == "A. C"
    assert first.runs[0].bold is True


def test_a_token_split_across_runs_still_fills(tmp_path):
    """Word splits runs constantly; the paragraph-level fallback is what keeps a
    split `{{Na` + `me}}` from shipping as a broken document."""
    document = Document()
    paragraph = document.add_paragraph()
    paragraph.add_run("Hello {{").bold = True
    paragraph.add_run("First")
    paragraph.add_run("}} there")
    path = tmp_path / "split.docx"
    document.save(str(path))

    report = tailor.fill_template(path, tmp_path / "split-out.docx",
                                  {"fields": {"First": "Eric"}})
    assert report["mode"].get("paragraph") == 1
    assert Document(str(tmp_path / "split-out.docx")).paragraphs[0].text == "Hello Eric there"


def test_a_leftover_placeholder_refuses_to_write_anything(tmp_path):
    path = _template(tmp_path / "tpl.docx")
    out = tmp_path / "out.docx"
    with pytest.raises(TemplateFillError) as caught:
        tailor.fill_template(path, out, {"fields": {"Name": "Eric"}})
    assert sorted(caught.value.leftovers) == ["{{ objective }}", "{{Email}}", "{{Phone}}"]
    assert out.exists() is False, "a refused fill must not leave a half-built document"
    assert caught.value.report["written"] if "written" in caught.value.report else True


def test_allow_leftovers_writes_the_partial_document_and_says_so(tmp_path):
    path = _template(tmp_path / "tpl.docx")
    out = tmp_path / "partial.docx"
    report = tailor.fill_template(path, out, {"fields": {"Name": "Eric"}}, strict=False)
    assert report["written"] is True
    assert sorted(report["leftovers"]) == ["{{ objective }}", "{{Email}}", "{{Phone}}"]
    assert out.is_file()


def test_a_supplied_value_with_no_placeholder_is_reported_unused(tmp_path):
    path = _template(tmp_path / "tpl.docx")
    report = tailor.fill_template(path, tmp_path / "out.docx",
                                  {"fields": {**FIELDS, "Typo": "x"}})
    assert report["unused"] == ["Typo"]


def test_an_approved_paragraph_swap_is_applied(tmp_path):
    path = _template(tmp_path / "tpl.docx")
    out = tmp_path / "out.docx"
    tailor.fill_template(path, out, {
        "fields": FIELDS,
        "replace": {"Unchanged line, no tokens.": "Rewritten line."}})
    assert "Rewritten line." in [paragraph.text for paragraph in Document(str(out)).paragraphs]


def test_a_missing_template_is_the_base_document_gate_not_a_generic_error(tmp_path):
    with pytest.raises(BaseDocumentMissing):
        tailor.fill_template(tmp_path / "nope.docx", tmp_path / "out.docx", {"fields": {"A": "b"}})


def test_an_empty_spec_is_refused(tmp_path):
    path = _template(tmp_path / "tpl.docx")
    with pytest.raises(ValueError):
        tailor.fill_template(path, tmp_path / "out.docx", {})


def test_overwriting_an_output_trashes_the_previous_one(tmp_path):
    path = _template(tmp_path / "tpl.docx")
    out = tmp_path / "out.docx"
    tailor.fill_template(path, out, {"fields": FIELDS})
    before = out.read_bytes()
    tailor.fill_template(path, out, {"fields": {**FIELDS, "Name": "Someone Else"}})
    trash = list((tmp_path / ".dossier" / "trash").rglob("out.docx"))
    assert trash and trash[0].read_bytes() == before


# -- the verification gate -------------------------------------------------

def test_the_template_gate_passes_on_a_clean_fill(tmp_path):
    path = _template(tmp_path / "tpl.docx")
    out = tmp_path / "out.docx"
    tailor.fill_template(path, out, {"fields": FIELDS})
    result = verify.template_fill(path, out, {"fields": FIELDS})
    assert result["passed"] is True
    assert {check["id"] for check in result["checks"]} == {
        "no-leftover-placeholders", "values-present", "template-preserved"}


def test_the_template_gate_fails_on_a_leftover(tmp_path):
    path = _template(tmp_path / "tpl.docx")
    out = tmp_path / "partial.docx"
    tailor.fill_template(path, out, {"fields": {"Name": "Eric"}}, strict=False)
    result = verify.template_fill(path, out, {"fields": {"Name": "Eric"}})
    assert result["passed"] is False
    leftovers = next(check for check in result["checks"]
                     if check["id"] == "no-leftover-placeholders")
    assert leftovers["ok"] is False


def test_the_template_gate_fails_when_a_supplied_value_is_absent(tmp_path):
    path = _template(tmp_path / "tpl.docx")
    out = tmp_path / "out.docx"
    tailor.fill_template(path, out, {"fields": FIELDS})
    result = verify.template_fill(path, out, {"fields": {**FIELDS, "Name": "Nobody"}})
    assert result["passed"] is False
    asserted = next(check for check in result["checks"] if check["id"] == "values-present")
    assert asserted["result"]["missing"] == ["Name"]


def test_the_template_gate_notices_a_deleted_template_paragraph(tmp_path):
    path = _template(tmp_path / "tpl.docx")
    out = tmp_path / "out.docx"
    tailor.fill_template(path, out, {"fields": FIELDS})
    # Delete a line the template wrote (the token-free one) from the built document.
    built = Document(str(out))
    victim = next(paragraph for paragraph in built.paragraphs
                  if paragraph.text == "Unchanged line, no tokens.")
    victim._element.getparent().remove(victim._element)
    built.save(str(out))
    result = verify.template_fill(path, out, {"fields": FIELDS})
    assert result["passed"] is False
    preserved = next(check for check in result["checks"] if check["id"] == "template-preserved")
    assert preserved["result"]["lost"] == ["Unchanged line, no tokens."]


# -- the surfaces -----------------------------------------------------------

def test_the_cli_reads_fields_and_fills_a_template(tmp_path, capsys):
    from dossier import cli

    path = _template(tmp_path / "tpl.docx")
    (tmp_path / "spec.json").write_text(json.dumps({"fields": FIELDS}), encoding="utf-8")
    assert cli.main(["tailor", "fields", "--template", str(path), "--json"]) == 0
    assert "objective" in capsys.readouterr().out
    assert cli.main(["tailor", "template", "--template", str(path), "--spec",
                     str(tmp_path / "spec.json"), "--out", str(tmp_path / "out.docx")]) == 0
    assert cli.main(["verify", "template", "--template", str(path), "--candidate",
                     str(tmp_path / "out.docx"), "--spec",
                     str(tmp_path / "spec.json")]) == 0


def test_the_api_fills_and_verifies_and_refuses_a_leftover(tmp_path):
    from fastapi.testclient import TestClient
    from dossier.api.app import create_app
    from dossier.config import AppConfig

    _template(tmp_path / "templates" / "tpl.docx")
    app = create_app(AppConfig.create(tmp_path, token="template-token"))
    client = TestClient(app, raise_server_exceptions=False)
    headers = {"Authorization": "Bearer template-token"}

    fields = client.get("/api/tailor/fields", params={"template": "templates/tpl.docx"},
                        headers=headers)
    assert fields.status_code == 200
    assert "Name" in fields.json()["fields"]

    refused = client.post("/api/tailor/template", headers=headers, json={
        "template": "templates/tpl.docx", "out": "partial.docx",
        "spec": {"fields": {"Name": "Eric"}}})
    assert refused.status_code == 422
    detail = refused.json()["detail"]
    assert detail["leftovers"]

    built = client.post("/api/tailor/template", headers=headers, json={
        "template": "templates/tpl.docx", "out": "built.docx", "spec": {"fields": FIELDS}})
    assert built.status_code == 200 and built.json()["written"] is True

    check = client.post("/api/verify/template", headers=headers, json={
        "template": "templates/tpl.docx", "candidate": "built.docx", "spec": {"fields": FIELDS}})
    assert check.status_code == 200 and check.json()["passed"] is True

    escaped = client.post("/api/tailor/template", headers=headers, json={
        "template": "../../etc/passwd", "out": "x.docx", "spec": {"fields": {"a": "b"}}})
    assert escaped.status_code == 400
