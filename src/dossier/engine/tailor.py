"""Document generation — layout cloning, structural reordering, cover letters.

The engine owns document mechanics; a model supplies prose. That split is what
makes generated documents safe: the base `.docx` is copied byte-for-byte and
only the runs a caller names are touched, so fonts, tables, spacing, pagination
and every unapproved bullet survive automatically.

Method A (in-place editing) is the only supported default. A rebuild from a
generic template flattens tables to plain text and strips formatting, so it is
not offered as a fallback: when no base document exists, `BaseDocumentMissing`
is raised and the caller asks the user for one.
"""

from __future__ import annotations

import copy
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path

EMU_PER_POINT = 12700
DEFAULT_FONT = "Calibri"


class BaseDocumentMissing(RuntimeError):
    """Raised instead of falling back to a generic template."""


def _require(path: Path) -> Path:
    path = Path(path)
    if not path.exists():
        raise BaseDocumentMissing(
            f"No base document at {path}. Layout cloning needs a real user-supplied .docx; "
            "there is no template fallback. Ask the user for the file."
        )
    if path.suffix.casefold() != ".docx":
        raise BaseDocumentMissing(f"{path} is not a .docx; layout cloning needs the real document.")
    return path


def _document(path: Path):
    from docx import Document
    return Document(str(_require(path)))


# -- reading ---------------------------------------------------------------

def iter_paragraphs(document):
    """Every paragraph with a stable location label, body and tables included."""
    for index, paragraph in enumerate(document.paragraphs):
        yield f"body:{index}", paragraph
    for table_index, table in enumerate(document.tables):
        for row_index, row in enumerate(table.rows):
            for cell_index, cell in enumerate(row.cells):
                for paragraph_index, paragraph in enumerate(cell.paragraphs):
                    yield f"table:{table_index}/{row_index}/{cell_index}:{paragraph_index}", paragraph
    for section_index, section in enumerate(document.sections):
        for scope in ("header", "footer"):
            container = getattr(section, scope)
            for paragraph_index, paragraph in enumerate(container.paragraphs):
                yield f"{scope}:{section_index}:{paragraph_index}", paragraph


def read_blocks(path: Path) -> list[dict]:
    """Dump the document's text with locations, so a diff can name what moved."""
    document = _document(path)
    blocks = []
    for location, paragraph in iter_paragraphs(document):
        text = paragraph.text
        if text.strip():
            blocks.append({"location": location, "text": text})
    return blocks


def read_text(path: Path) -> str:
    return "\n".join(block["text"] for block in read_blocks(path))


def _read_xml(payload: bytes):
    """Parse an XML part from a user-supplied .docx.

    The document is local and user-supplied, so this is not an untrusted-input
    path — but a .docx is a zip that can carry anything, so entity expansion is
    refused outright rather than relied on to be safe. `defusedxml` is used when
    installed; otherwise a document declaring a DOCTYPE is rejected, which is
    what a billion-laughs or XXE payload requires.
    """
    try:
        from defusedxml.ElementTree import fromstring
        return fromstring(payload)
    except ImportError:
        pass
    if b"<!DOCTYPE" in payload[:4096] or b"<!ENTITY" in payload[:4096]:
        raise ValueError("refusing to parse an XML part that declares a DOCTYPE or ENTITY")
    import xml.etree.ElementTree as ElementTree
    return ElementTree.fromstring(payload)


def _theme_fonts(path: Path) -> dict[str, str]:
    """The document's declared fonts, in resolution order.

    Runs often carry no explicit `w:rFonts` and inherit from the document
    defaults or the theme. Reporting a hard-coded fallback as the primary font
    would make a generated cover letter quietly render in the wrong typeface,
    so the real declaration is read before any default is used.
    """
    import zipfile
    found: dict[str, str] = {}
    namespace = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    drawing = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
    try:
        with zipfile.ZipFile(path) as archive:
            names = set(archive.namelist())
            if "word/styles.xml" in names:
                root = _read_xml(archive.read("word/styles.xml"))
                node = root.find(f".//{namespace}docDefaults/{namespace}rPrDefault/"
                                 f"{namespace}rPr/{namespace}rFonts")
                if node is not None:
                    value = node.get(f"{namespace}ascii")
                    if value:
                        found["doc_default"] = value
            if "word/theme/theme1.xml" in names:
                root = _read_xml(archive.read("word/theme/theme1.xml"))
                for scheme, label in (("majorFont", "theme_major"), ("minorFont", "theme_minor")):
                    node = root.find(f".//{drawing}{scheme}")
                    if node is None:
                        continue
                    latin = node.find(f"{drawing}latin")
                    if latin is not None and latin.get("typeface"):
                        found[label] = latin.get("typeface")
    except (OSError, ValueError, ImportError):
        return found
    return found


def layout_spec(path: Path) -> dict:
    """The design facts a generated document must preserve.

    Read from the base rather than assumed, because the whole point of Method A
    is that the output is visually indistinguishable from the user's own file.
    """
    path = _require(path)
    document = _document(path)
    section = document.sections[0]

    def points(value) -> float | None:
        return round(value / EMU_PER_POINT, 2) if value is not None else None

    fonts: dict[str, int] = {}
    sizes: dict[float, int] = {}
    colors: dict[str, int] = {}
    for _, paragraph in iter_paragraphs(document):
        for run in paragraph.runs:
            name = run.font.name or _rfonts_name(run)
            if name:
                fonts[name] = fonts.get(name, 0) + 1
            if run.font.size is not None:
                key = round(run.font.size.pt, 1)
                sizes[key] = sizes.get(key, 0) + 1
            rgb = run.font.color.rgb if run.font.color and run.font.color.type is not None else None
            if rgb is not None:
                value = str(rgb).upper()
                if value not in {"000000", "FFFFFF"}:
                    colors[value] = colors.get(value, 0) + 1

    declared = _theme_fonts(path)
    if fonts:
        primary_font = max(fonts, key=fonts.get)
        font_source = "explicit run"
    elif declared.get("doc_default"):
        primary_font = declared["doc_default"]
        font_source = "document default"
    elif declared.get("theme_minor") or declared.get("theme_major"):
        primary_font = declared.get("theme_minor") or declared["theme_major"]
        font_source = "theme"
    else:
        primary_font = DEFAULT_FONT
        font_source = "fallback"

    return {
        "path": str(path),
        "page_width_pt": points(section.page_width),
        "page_height_pt": points(section.page_height),
        "margins_pt": {
            "left": points(section.left_margin),
            "right": points(section.right_margin),
            "top": points(section.top_margin),
            "bottom": points(section.bottom_margin),
        },
        "paragraphs": len(document.paragraphs),
        "tables": len(document.tables),
        "table_cells": sum(len(table.rows) * len(table.columns) for table in document.tables),
        "fonts": dict(sorted(fonts.items(), key=lambda item: -item[1])),
        "declared_fonts": declared,
        "primary_font": primary_font,
        "primary_font_source": font_source,
        "font_sizes": {str(k): v for k, v in sorted(sizes.items(), key=lambda item: -item[1])},
        "accent_colors": dict(sorted(colors.items(), key=lambda item: -item[1])),
        "primary_accent": max(colors, key=colors.get) if colors else None,
    }


def _rfonts_name(run) -> str | None:
    element = run._element.find(
        "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}rPr")
    if element is None:
        return None
    fonts = element.find(
        "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}rFonts")
    if fonts is None:
        return None
    return fonts.get("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}ascii")


# -- writing ---------------------------------------------------------------

def _set_paragraph_text(paragraph, text: str) -> bool:
    """Replace a paragraph's text, keeping its first run's formatting."""
    runs = paragraph.runs
    if not runs:
        if paragraph.text.strip():
            return False
        paragraph.add_run(text)
        return True
    runs[0].text = text
    for run in runs[1:]:
        run.text = ""
    return True


@dataclass
class CloneResult:
    output: str
    applied: list[dict] = field(default_factory=list)
    missed: list[str] = field(default_factory=list)


def apply_replacements(base: Path, output: Path, replacements: dict[str, str],
                       allow_substring: bool = False) -> CloneResult:
    """Copy the base and swap named paragraphs. Every other byte is preserved.

    A replacement that matches nothing is reported as missed rather than
    silently skipped — a tailoring pass that quietly did nothing is worse than
    one that fails.
    """
    base = _require(base)
    output = Path(output)
    if output.resolve() == base.resolve():
        raise ValueError("refusing to overwrite the base document in place")
    output.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(base, output)

    document = _document(output)
    remaining = dict(replacements)
    applied: list[dict] = []

    for location, paragraph in iter_paragraphs(document):
        full = paragraph.text
        if not full.strip():
            continue
        for old, new in list(remaining.items()):
            matched = old in full if allow_substring else full.strip() == old.strip()
            if not matched:
                continue
            before = full
            _set_paragraph_text(paragraph, new)
            applied.append({"location": location, "before": before, "after": new})
            remaining.pop(old, None)
            break

    document.save(str(output))
    return CloneResult(str(output), applied, sorted(remaining))


def reorder_cell_blocks(base: Path, output: Path, table_index: int, row: int, column: int,
                        blocks: dict[str, list[int]], order: list[str],
                        separator_index: int) -> dict:
    """Move whole blocks within a table cell, preserving per-paragraph formatting.

    The separator gotcha, verified live: if each block keeps its own trailing
    blank paragraph, whichever block lands last loses it and leaves an uneven
    gap that no text diff can see. One blank paragraph is therefore cloned as a
    uniform separator between blocks, and none after the final one.
    """
    base = _require(base)
    output = Path(output)
    if output.resolve() == base.resolve():
        raise ValueError("refusing to overwrite the base document in place")
    output.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(base, output)

    document = _document(output)
    cell = document.tables[table_index].cell(row, column)
    cell_element = cell._tc
    paragraphs = [paragraph._p for paragraph in cell.paragraphs]

    missing = [key for key in order if key not in blocks]
    if missing or separator_index >= len(paragraphs):
        raise ValueError(f"unknown block(s) {missing} or separator index out of range")

    blank_template = paragraphs[separator_index]
    groups = {key: [paragraphs[index] for index in indices] for key, indices in blocks.items()}
    affected = sorted({index for indices in blocks.values() for index in indices})

    ordered: list = []
    for position, key in enumerate(order):
        ordered.extend(groups[key])
        if position < len(order) - 1:
            ordered.append(copy.deepcopy(blank_template))

    for index in reversed(affected):
        cell_element.remove(paragraphs[index])
    for element in ordered:
        cell_element.append(element)

    document.save(str(output))
    return {
        "output": str(output),
        "table": table_index,
        "cell": [row, column],
        "order": order,
        "moved_paragraphs": len(ordered),
        "separator_source": separator_index,
    }


def cover_letter(base: Path, output: Path, *, name: str, contact: str, date_line: str,
                 recipient: str, greeting: str, body: list[str], signoff: str) -> dict:
    """Build a one-page letter that reads as the resume's sibling.

    Shared with the resume so the pair looks like one person's paperwork: the
    base's font, its accent colour, and its page geometry. Distinct from it so
    the letter is not a resume-shaped blob: a letterhead block and flowing body
    paragraphs, with no table, no section headers and no bullet list.
    """
    base = _require(base)
    spec = layout_spec(base)
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)

    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.shared import Pt

    source = _document(base)
    document = Document()

    source_section = source.sections[0]
    target_section = document.sections[0]
    for attribute in ("page_width", "page_height", "left_margin", "right_margin",
                      "top_margin", "bottom_margin"):
        value = getattr(source_section, attribute)
        if value is not None:
            setattr(target_section, attribute, value)

    font_name = spec["primary_font"] or DEFAULT_FONT
    accent = spec["primary_accent"]
    base_size = None
    if spec["font_sizes"]:
        try:
            base_size = float(max(spec["font_sizes"], key=lambda key: spec["font_sizes"][key]))
        except (TypeError, ValueError):
            base_size = None

    def style_run(run, size: float | None = None, bold: bool = False, color: str | None = None):
        run.font.name = font_name
        if size is not None:
            run.font.size = Pt(size)
        run.bold = bold
        if color:
            from docx.shared import RGBColor
            run.font.color.rgb = RGBColor.from_string(color)
        rpr = run._element.get_or_add_rPr()
        rfonts = rpr.get_or_add_rFonts()
        for attribute in ("ascii", "hAnsi", "cs"):
            rfonts.set(
                "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}" + attribute,
                font_name,
            )

    heading = document.add_paragraph()
    heading.alignment = WD_ALIGN_PARAGRAPH.CENTER
    style_run(heading.add_run(name), size=20, bold=True, color=accent)

    if contact:
        line = document.add_paragraph()
        line.alignment = WD_ALIGN_PARAGRAPH.CENTER
        style_run(line.add_run(contact), size=(base_size or 11) - 1)
        _bottom_rule(line)

    if date_line:
        document.add_paragraph()
        style_run(document.add_paragraph().add_run(date_line), size=base_size)

    if recipient:
        for part in recipient.splitlines():
            style_run(document.add_paragraph().add_run(part), size=base_size)

    if greeting:
        document.add_paragraph()
        style_run(document.add_paragraph().add_run(greeting), size=base_size)

    for paragraph_text in body:
        document.add_paragraph()
        style_run(document.add_paragraph().add_run(paragraph_text), size=base_size)

    document.add_paragraph()
    style_run(document.add_paragraph().add_run(signoff), size=base_size)

    document.save(str(output))
    return {
        "output": str(output),
        "font": font_name,
        "accent": accent,
        "base_size_pt": base_size,
        "paragraphs": len(body) + 6,
        "geometry": spec["margins_pt"],
    }


def _bottom_rule(paragraph) -> None:
    from docx.oxml.ns import qn
    from docx.oxml import OxmlElement
    properties = paragraph._p.get_or_add_pPr()
    borders = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), "6")
    bottom.set(qn("w:space"), "1")
    bottom.set(qn("w:color"), "auto")
    borders.append(bottom)
    properties.append(borders)


def objective_replacement(current_objective: str, new_objective: str) -> dict[str, str]:
    """The one replacement a default tailoring pass is allowed to make."""
    if not new_objective.strip():
        raise ValueError("refusing to write an empty objective")
    if "\n" in new_objective:
        raise ValueError("an objective is one paragraph; split the text instead")
    return {current_objective: new_objective}


def find_base_documents(root: Path | str) -> list[Path]:
    """Candidate base documents in a folder, excluding generated artefacts."""
    root = Path(root)
    tailored = re.compile(r"resume[_-][a-z0-9]", re.IGNORECASE)
    found = []
    for path in sorted(root.glob("*.docx")):
        stem = path.stem
        if stem.casefold().endswith("_coverletter") or tailored.search(stem):
            continue
        if "resume" in stem.casefold() or "cv" in stem.casefold():
            found.append(path)
    return found


def import_base(source: Path, root: Path | str, name: str = "base-resume.docx",
                overwrite: bool = False) -> dict:
    """Copy a user-supplied base document into the workspace.

    A workspace folder is where the search lives, not necessarily where the
    user's own resume file sits. Copying rather than referencing keeps the
    app's root confinement intact and leaves the user's original untouched.
    """
    source = _require(source)
    root = Path(root)
    if not root.is_dir():
        raise NotADirectoryError(str(root))
    target = root / (name if name.lower().endswith(".docx") else name + ".docx")
    if target.exists() and not overwrite:
        return {
            "imported": False,
            "detail": f"{target} already exists; pass overwrite=True to replace it.",
            "target": str(target),
        }
    spec = layout_spec(source)
    if not spec["paragraphs"]:
        raise BaseDocumentMissing(f"{source} has no readable paragraphs; it is not a usable base.")
    shutil.copy2(source, target)
    return {
        "imported": True,
        "source": str(source),
        "target": str(target),
        "primary_font": spec["primary_font"],
        "paragraphs": spec["paragraphs"],
        "tables": spec["tables"],
        "original_untouched": True,
    }
