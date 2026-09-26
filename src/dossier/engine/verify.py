"""Verification gates for generated documents.

Three independent checks, because they fail independently:

* **source diff** — did anything move that was not approved? Compared as a
  line multiset, so a multi-line table cell's internal newline handling cannot
  masquerade as a change.
* **text layer** — what an ATS parser will actually read out of the PDF. This
  is a different failure surface from the render: an icon-only contact line
  looks perfect on the page and extracts as nothing.
* **rendered page** — page count, text past the margins, blank pages. A text
  diff cannot see a clipped bullet or an uneven gap, so this is not optional.

`all()` exits non-zero on any failure, which is what lets a batch generator
assert on it instead of trusting a summary.
"""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

from . import render

CONTACT_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
CONTACT_PHONE = re.compile(r"(?:\+?\d[\d\s().-]{6,}\d)")
CID_MARKER = re.compile(r"\(cid:\d+\)")
YEAR = re.compile(r"\b(?:19|20)\d{2}\b")


def _pymupdf():
    return render._pymupdf()


def source_diff(base: Path, candidate: Path, approved: dict[str, str] | None = None) -> dict:
    """Compare a generated document against its base, as a line multiset."""
    from .tailor import read_blocks

    base_blocks = read_blocks(Path(base))
    candidate_blocks = read_blocks(Path(candidate))
    base_counter = Counter(block["text"].strip() for block in base_blocks)
    candidate_counter = Counter(block["text"].strip() for block in candidate_blocks)

    removed = list((base_counter - candidate_counter).elements())
    added = list((candidate_counter - base_counter).elements())

    approved = approved or {}
    approved_old = {key.strip() for key in approved}
    approved_new = {value.strip() for value in approved.values()}
    unexpected = [line for line in removed if line not in approved_old]
    unexplained = [line for line in added if line not in approved_new]

    return {
        "base": str(base),
        "candidate": str(candidate),
        "base_blocks": len(base_blocks),
        "candidate_blocks": len(candidate_blocks),
        "removed": removed,
        "added": added,
        "approved_removed": sorted(approved_old & set(removed)),
        "approved_added": sorted(approved_new & set(added)),
        "unexpected_removed": unexpected,
        "unexpected_added": unexplained,
        "unchanged": len(base_counter & candidate_counter),
        "ok": not unexpected and not unexplained,
        "rule": (
            "Only the objective, section order, skills order and explicitly approved bullet "
            "rewrites may differ. Every unapproved bullet, date, employer, title, education "
            "entry and contact field stays byte-identical."
        ),
    }


def text_layer(pdf: Path, expect: list[str] | None = None, keywords: list[str] | None = None,
               min_dates: int = 0) -> dict:
    """What an ATS parser reads out of the PDF's embedded text layer.

    `min_dates` is left at 0 by default because a cover letter legitimately
    carries a single date; asking for two is a resume-shaped expectation. A
    verifier that fails a clean document teaches people to ignore it.
    """
    pdf = Path(pdf)
    if not render._has_pymupdf():
        return {"pdf": str(pdf), "ok": False,
                "issues": [{"type": "no-extractor", "detail": "PyMuPDF is not importable"}]}
    pymupdf = _pymupdf()
    issues: list[dict] = []
    pages_text: list[str] = []

    with pymupdf.open(str(pdf)) as document:
        for index, page in enumerate(document):
            pages_text.append(page.get_text("text"))
            blocks = [block for block in page.get_text("blocks") if block[4].strip()]
            if blocks and not any(True for _ in blocks):
                issues.append({"type": "empty-page", "page": index + 1})
    text = "\n".join(pages_text)

    if not text.strip():
        issues.append({"type": "no-text", "detail": "PDF contains no extractable text at all"})

    cid = CID_MARKER.findall(text)
    if cid:
        issues.append({"type": "cid-markers", "count": len(cid), "sample": cid[0]})

    replacement = text.count("\ufffd")
    if replacement:
        issues.append({"type": "replacement-characters", "count": replacement})

    years = YEAR.findall(text)
    if len(years) < min_dates:
        issues.append({
            "type": "few-dates",
            "detail": f"only {len(years)} recognisable year(s); an ATS may not read the dates",
        })

    for field in expect or []:
        if field and field.strip() and field.strip() not in text:
            issues.append({"type": "missing-field", "value": field.strip()[:60]})

    covered, missing = [], []
    for keyword in keywords or []:
        if re.search(re.escape(keyword), text, re.IGNORECASE):
            covered.append(keyword)
        else:
            missing.append(keyword)

    return {
        "pdf": str(pdf),
        "pages": len(pages_text),
        "characters": len(text),
        "issues": issues,
        "keyword_coverage": {"covered": covered, "missing": missing},
        "sample": text.strip()[:400],
        "ok": not issues,
        "rule": (
            "Email and phone must survive as literal characters, not only inside a hyperlink "
            "target. Reading order must match visual order."
        ),
    }


def visual(pdf: Path, expected_pages: int | None = None, margin_tol: float = 4.0,
           margins: dict | None = None) -> dict:
    """Inspect the rendered page: page count, overflow, blank pages."""
    pdf = Path(pdf)
    if not render._has_pymupdf():
        return {"pdf": str(pdf), "ok": False, "issues": [
            {"type": "no-rasteriser", "detail": "PyMuPDF is not importable"}]}
    pymupdf = _pymupdf()
    issues: list[dict] = []
    margins = margins or {}
    left = float(margins.get("left") or 36.0)
    right = float(margins.get("right") or 36.0)
    top = float(margins.get("top") or 36.0)
    bottom = float(margins.get("bottom") or 36.0)

    with pymupdf.open(str(pdf)) as document:
        page_count = document.page_count
        if expected_pages is not None and page_count != expected_pages:
            issues.append({"type": "page-count", "expected": expected_pages, "actual": page_count})
        for index, page in enumerate(document):
            width, height = page.rect.width, page.rect.height
            x_min, x_max = left - margin_tol, width - right + margin_tol
            y_min, y_max = top - margin_tol, height - bottom + margin_tol
            blocks = [block for block in page.get_text("blocks") if block[4].strip()]
            if not blocks:
                issues.append({"type": "blank-page", "page": index + 1})
                continue
            for block in blocks:
                x0, y0, x1, y1, text = block[0], block[1], block[2], block[3], block[4]
                if x0 < x_min or x1 > x_max or y0 < y_min or y1 > y_max:
                    issues.append({
                        "type": "overflow",
                        "page": index + 1,
                        "bbox": [round(x0, 1), round(y0, 1), round(x1, 1), round(y1, 1)],
                        "page_size": [round(width, 1), round(height, 1)],
                        "text": text.strip()[:50],
                    })

    return {
        "pdf": str(pdf),
        "pages": page_count,
        "expected_pages": expected_pages,
        "overflow_count": sum(1 for issue in issues if issue["type"] == "overflow"),
        "issues": issues,
        "ok": not issues,
        "rule": "A text diff is not a visual check. Nothing is 'visually verified' until a page was inspected.",
    }


def contact_fields(base_docx: Path) -> list[str]:
    """Email and phone from the base, so the render can be checked against them."""
    from .tailor import read_text
    text = read_text(Path(base_docx))
    fields = CONTACT_EMAIL.findall(text)
    phones = [value.strip() for value in CONTACT_PHONE.findall(text)]
    fields.extend(phones[:2])
    return fields


def all(base: Path | None, candidate: Path | None, pdf: Path | None,
        expected_pages: int | None = None, approved: dict[str, str] | None = None,
        keywords: list[str] | None = None, min_dates: int = 0,
        margins_from: Path | None = None) -> dict:
    """Run every applicable gate and say plainly which ones could not run.

    Margins are read from the document's own section geometry rather than
    guessed. A generated letter inherits a resume's 23pt top margin, and
    checking it against a 36pt default would flag a clean page.
    """
    checks: list[dict] = []
    skipped: list[str] = []

    if base and candidate:
        diff = source_diff(base, candidate, approved)
        checks.append({"id": "source-diff", "ok": diff["ok"],
                       "detail": f"{len(diff['removed'])} removed, {len(diff['added'])} added, "
                                 f"{len(diff['unexpected_removed'])} unexpected",
                       "result": diff})
    else:
        skipped.append("source-diff (needs a base and a candidate document)")

    if pdf:
        expect = contact_fields(base) if base else []
        layer = text_layer(pdf, expect=expect, keywords=keywords, min_dates=min_dates)
        checks.append({"id": "text-layer", "ok": layer["ok"],
                       "detail": f"{len(layer['issues'])} issue(s) in the extracted text",
                       "result": layer})
        margins = None
        geometry_source = margins_from or candidate or base
        if geometry_source and Path(geometry_source).suffix.casefold() == ".docx":
            from .tailor import layout_spec
            margins = layout_spec(Path(geometry_source))["margins_pt"]
        rendered = visual(pdf, expected_pages=expected_pages, margins=margins)
        checks.append({"id": "rendered-page", "ok": rendered["ok"],
                       "detail": f"{rendered['pages']} page(s), "
                                 f"{rendered['overflow_count']} overflow block(s)"
                                 + ("" if margins else " (default margins: pass the source .docx)"),
                       "result": rendered})
    else:
        skipped.append("text-layer and rendered-page (no PDF rendered)")

    return {
        "checks": checks,
        "skipped": skipped,
        "passed": bool(checks) and _all_ok(checks),
        "not_visually_verified": not pdf,
    }


def _all_ok(checks: list[dict]) -> bool:
    """Every check passed. Spelled out rather than using `all`, which this module
    shadows with its own entry point."""
    for check in checks:
        if not check["ok"]:
            return False
    return True
