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
from ..copy import plural

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
    layout = render.text_layout(pdf)
    if layout is None:
        return {"pdf": str(pdf), "ok": False, "issues": [{
            "type": "no-extractor",
            "detail": "No PDF text extractor is importable; install pypdfium2 (permissive) "
                      "or the optional PyMuPDF extra",
        }]}
    issues: list[dict] = []
    pages_text: list[str] = []

    for index, page in enumerate(layout["pages"]):
        pages_text.append("\n".join(block["text"] for block in page["blocks"]))
        # A page with no text block at all is a page an ATS reads as nothing.
        # The branch that was here tested `blocks and not any(True for _ in
        # blocks)`, which cannot be true, so the issue type was unreachable.
        if not page["blocks"]:
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
            "detail": f"only {plural(len(years),'recognisable year')}; an ATS may not read the dates",
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
           margins: dict | None = None, image: Path | None = None, dpi: int = 150) -> dict:
    """Inspect the rendered page and produce the page image the gate requires.

    Geometry alone is not inspection. `rendered-inspection` says a document is
    not 'visually verified' until a rendered page image was produced and looked
    at, so this rasterises page 1 to `<pdf stem>-page-1.png` (or the path the
    caller named) and fails with `no-page-image` when it cannot. `ok` can
    therefore never be true on a text diff or a geometry sweep alone.
    """
    pdf = Path(pdf)
    layout = render.text_layout(pdf)
    if layout is None:
        return {"pdf": str(pdf), "ok": False, "page_image": None, "issues": [{
            "type": "no-rasteriser",
            "detail": "No PDF reader is importable; install pypdfium2 (permissive) or the "
                      "optional PyMuPDF extra",
        }]}
    issues: list[dict] = []
    margins = margins or {}
    left = float(margins.get("left") or 36.0)
    right = float(margins.get("right") or 36.0)
    top = float(margins.get("top") or 36.0)
    bottom = float(margins.get("bottom") or 36.0)

    page_count = len(layout["pages"])
    if expected_pages is not None and page_count != expected_pages:
        issues.append({"type": "page-count", "expected": expected_pages, "actual": page_count})
    for index, page in enumerate(layout["pages"]):
        width, height = page["width"], page["height"]
        x_min, x_max = left - margin_tol, width - right + margin_tol
        y_min, y_max = top - margin_tol, height - bottom + margin_tol
        blocks = page["blocks"]
        if not blocks:
            issues.append({"type": "blank-page", "page": index + 1})
            continue
        for block in blocks:
            x0, y0, x1, y1, text = (block["x0"], block["y0"], block["x1"], block["y1"],
                                    block["text"])
            if x0 < x_min or x1 > x_max or y0 < y_min or y1 > y_max:
                issues.append({
                    "type": "overflow",
                    "page": index + 1,
                    "bbox": [round(x0, 1), round(y0, 1), round(x1, 1), round(y1, 1)],
                    "page_size": [round(width, 1), round(height, 1)],
                    "text": text.strip()[:50],
                })

    page_image = Path(image) if image is not None else pdf.parent / f"{pdf.stem}-page-1.png"
    try:
        render.pdf_to_png(pdf, page_image, dpi=dpi)
    except Exception as exc:  # noqa: BLE001
        issues.append({
            "type": "no-page-image",
            "detail": f"no page image could be produced: {type(exc).__name__}: {exc}"[:200],
        })
        page_image = None

    return {
        "pdf": str(pdf),
        "pages": page_count,
        "expected_pages": expected_pages,
        "overflow_count": sum(1 for issue in issues if issue["type"] == "overflow"),
        "page_image": str(page_image) if page_image else None,
        "image_bytes": page_image.stat().st_size if page_image and page_image.exists() else 0,
        "issues": issues,
        "ok": not issues,
        "rule": ("A text diff is not a visual check. Nothing is 'visually verified' until a "
                 "rendered page image was produced and looked at, so this check fails when it "
                 "cannot produce one."),
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
    page_image: str | None = None

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
                       "detail": f"{plural(len(layer['issues']),'issue')} in the extracted text",
                       "result": layer})
        margins = None
        geometry_source = margins_from or candidate or base
        if geometry_source and Path(geometry_source).suffix.casefold() == ".docx":
            from .tailor import layout_spec
            margins = layout_spec(Path(geometry_source))["margins_pt"]
        rendered = visual(pdf, expected_pages=expected_pages, margins=margins)
        page_image = rendered.get("page_image")
        checks.append({"id": "rendered-page", "ok": rendered["ok"],
                       "detail": f"{plural(rendered['pages'],'page')}, "
                                 f"{plural(rendered['overflow_count'],'overflow block')}, "
                                 f"page image {'produced' if page_image else 'MISSING'}"
                                 + ("" if margins else " (default margins: pass the source .docx)"),
                       "result": rendered})
    else:
        # No PDF means no page image, so the rendered-inspection gate cannot pass.
        # Reporting `not_visually_verified: true` while `passed` stayed true would
        # be a claim of visual verification made from a text diff alone, which the
        # gate forbids in as many words.
        checks.append({
            "id": "rendered-inspection",
            "ok": False,
            "detail": ("no PDF supplied and no page image produced: a text diff alone does not "
                       "verify a rendered document. Render it first, or hand it to the user and "
                       "report it as NOT visually verified."),
        })
        skipped.append("text-layer (no PDF rendered)")

    return {
        "checks": checks,
        "skipped": skipped,
        "passed": bool(checks) and _all_ok(checks),
        "not_visually_verified": not pdf,
        "page_image": page_image,
    }


def _all_ok(checks: list[dict]) -> bool:
    """Every check passed. Spelled out rather than using `all`, which this module
    shadows with its own entry point."""
    for check in checks:
        if not check["ok"]:
            return False
    return True


# -- template fill ---------------------------------------------------------

def template_fill(template: Path, candidate: Path, spec: dict | None = None) -> dict:
    """Check a document built from a user template, and say what is missing.

    A template fill has a different failure mode from a tailored resume: the
    layout is the user's from the start, so there is nothing to diff — the thing
    that goes wrong is a placeholder nobody supplied. So the checks are:

    * **no leftovers** — no `{{…}}` survives into the document;
    * **values present** — every supplied field appears in the built text;
    * **template preserved** — every paragraph of the template that had no token
      (and no approved swap) is still there, so a fill did not quietly delete a
      line the user wrote.

    A text diff against the template is *not* run: a filled field is a legitimate
    difference, and flagging it would make the gate unusable.
    """
    from . import tailor as tailor_module
    from docx import Document
    from collections import Counter

    template = Path(template)
    candidate = Path(candidate)
    checks: list[dict] = []
    fields = {str(k).strip(): str(v) for k, v in ((spec or {}).get("fields") or {}).items()}
    swaps = {str(k).strip(): str(v) for k, v in ((spec or {}).get("replace") or {}).items()}

    template_doc = Document(str(template))
    candidate_doc = Document(str(candidate))
    template_text = " \n ".join(paragraph.text for _loc, paragraph in
                                tailor_module.iter_paragraphs(template_doc))
    candidate_text = " \n ".join(paragraph.text for _loc, paragraph in
                                 tailor_module.iter_paragraphs(candidate_doc))

    leftovers = sorted({match.group(0) for _loc, paragraph in
                        tailor_module.iter_paragraphs(candidate_doc)
                        for match in tailor_module.FIELD_TOKEN.finditer(paragraph.text)})
    checks.append({
        "id": "no-leftover-placeholders",
        "ok": not leftovers,
        "detail": ("no placeholder survived" if not leftovers
                   else f"{plural(len(leftovers),'placeholder')} unfilled: {', '.join(leftovers[:8])}"),
        "result": {"leftovers": leftovers},
    })

    missing = sorted(key for key, value in fields.items()
                     if value.strip() and value.strip() not in candidate_text)
    checks.append({
        "id": "values-present",
        "ok": not missing,
        "detail": (f"all {plural(len(fields),'supplied value')} appear in the document" if not missing
                   else f"{plural(len(missing),'supplied value')} are absent: {', '.join(missing[:8])}"),
        "result": {"missing": missing},
    })

    template_blocks = [paragraph.text.strip() for _loc, paragraph in
                       tailor_module.iter_paragraphs(template_doc)
                       if paragraph.text.strip() and not tailor_module.FIELD_TOKEN.search(paragraph.text)]
    candidate_blocks = Counter(paragraph.text.strip() for _loc, paragraph in
                               tailor_module.iter_paragraphs(candidate_doc)
                               if paragraph.text.strip())
    lost = [block for block in template_blocks if block not in swaps and candidate_blocks[block] < 1]
    checks.append({
        "id": "template-preserved",
        "ok": not lost,
        "detail": ("every untouched template paragraph survived" if not lost
                   else f"{plural(len(lost),'template paragraph')} missing: {lost[0][:80]}"),
        "result": {"lost": lost[:20], "checked": len(template_blocks)},
    })

    return {
        "template": str(template),
        "candidate": str(candidate),
        "checks": checks,
        "passed": _all_ok(checks),
        "declared": sorted({match.group(1).strip() for _loc, paragraph in
                            tailor_module.iter_paragraphs(template_doc)
                            for match in tailor_module.FIELD_TOKEN.finditer(paragraph.text)}),
        "template_chars": len(template_text),
        "candidate_chars": len(candidate_text),
    }
