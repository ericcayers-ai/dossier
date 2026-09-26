import csv
import json

import pytest
from docx import Document

from dossier.convert import convert, routes


def test_routes_and_semantic_documents(tmp_path):
    assert any(route.target == ".pdf" and route.fidelity == "faithful" for route in routes(".docx"))
    markdown = tmp_path / "notes.md"
    markdown.write_text("# Heading\n\nA paragraph.\n- One\n")
    docx = tmp_path / "notes.docx"
    text = tmp_path / "notes.txt"
    convert(markdown, docx)
    convert(docx, text)
    assert docx.exists() and "Heading" in text.read_text()


def test_csv_json_round_trip(tmp_path):
    source = tmp_path / "rows.csv"
    source.write_text('name,note\nAda,"hello, world"\n')
    json_path = tmp_path / "rows.json"
    csv_path = tmp_path / "rows-again.csv"
    convert(source, json_path)
    convert(json_path, csv_path)
    with csv_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert rows == [{"name": "Ada", "note": "hello, world"}]


def test_pdf_to_png(tmp_path):
    pymupdf = pytest.importorskip("pymupdf")
    pdf = tmp_path / "one.pdf"
    document = pymupdf.open()
    page = document.new_page()
    page.insert_text((72, 72), "Dossier render")
    document.save(pdf)
    png = tmp_path / "one.png"
    convert(pdf, png)
    assert png.exists() and png.stat().st_size > 1000
