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
from dataclasses import dataclass, field
from pathlib import Path

from ..safety import trash_if_present, trash_then_copy

EMU_PER_POINT = 12700
DEFAULT_FONT = "Calibri"


class BaseDocumentMissing(RuntimeError):
    """Raised instead of falling back to a generic template."""


def _trash_root(root: Path | str | None, base: Path) -> Path:
    """The workspace an overwrite in this module belongs to.

    A caller that knows its workspace passes it. Otherwise the base document's
    folder is used, because `find_base_documents` looks for the base at the
    workspace root, so that folder is the workspace the output belongs to.
    """
    if root is not None:
        return Path(root).expanduser()
    return Path(base).expanduser().resolve().parent


#: Every field a cover-letter spec declares.
COVER_LETTER_FIELDS = ("name", "contact", "date_line", "recipient", "greeting", "body", "signoff")


def cover_letter_spec(payload) -> tuple[dict, list[str]]:
    """Split a user-supplied cover-letter spec into declared fields and the rest.

    A spec is a JSON file a person writes, so it can carry anything — `role` and
    `employer` are the two most natural things to put in one, and passing them
    straight through as `**kwargs` turned the documented command into a
    traceback. Undeclared keys are returned so the caller can name them (never
    silently dropped), and a missing declared field is reported as the error it
    is rather than surfacing as a `TypeError` for a missing argument.
    """
    if not isinstance(payload, dict):
        raise ValueError("a cover-letter spec must be a JSON object")
    missing = [field for field in COVER_LETTER_FIELDS if field not in payload]
    if missing:
        raise ValueError(
            "the cover-letter spec is missing required field(s): " + ", ".join(missing))
    declared = {field: payload[field] for field in COVER_LETTER_FIELDS}
    ignored = sorted(str(key) for key in payload if key not in COVER_LETTER_FIELDS)
    return declared, ignored


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
                       allow_substring: bool = False,
                       root: Path | str | None = None) -> CloneResult:
    """Copy the base and swap named paragraphs. Every other byte is preserved.

    A replacement that matches nothing is reported as missed rather than
    silently skipped — a tailoring pass that quietly did nothing is worse than
    one that fails. An output that already exists is copied over only after it
    has been filed in `.dossier/trash/` (gate: `never-only-copy`).
    """
    base = _require(base)
    output = Path(output)
    if output.resolve() == base.resolve():
        raise ValueError("refusing to overwrite the base document in place")
    output.parent.mkdir(parents=True, exist_ok=True)
    trash_then_copy(_trash_root(root, base), base, output)

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
                        separator_index: int, root: Path | str | None = None) -> dict:
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
    trash_then_copy(_trash_root(root, base), base, output)

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
                 recipient: str, greeting: str, body: list[str], signoff: str,
                 root: Path | str | None = None) -> dict:
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

    # A re-run replaces the previous letter, so the old bytes are filed first,
    # in the workspace the caller named (or the base document's folder).
    trash_if_present(_trash_root(root, base), output)
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


_TAILORED = re.compile(r"resume[_-][a-z0-9]", re.IGNORECASE)


def is_base_document(path: Path | str) -> bool:
    """True for a resume the user wrote, false for one this pipeline produced.

    One definition, used by both the workspace resolver and the importer, so
    "which file do we clone?" cannot be answered two different ways.
    """
    path = Path(path)
    if path.suffix.casefold() != ".docx":
        return False
    stem = path.stem
    if stem.casefold().endswith("_coverletter"):
        return False
    if _TAILORED.search(stem):
        return False
    return "resume" in stem.casefold() or "cv" in stem.casefold()


def is_generated_document(path: Path | str) -> bool:
    """True for a document this pipeline produced: a tailored resume or its letter."""
    path = Path(path)
    if path.suffix.casefold() != ".docx":
        return False
    return path.stem.casefold().endswith("_coverletter") or bool(_TAILORED.search(path.stem))


def find_base_documents(root: Path | str) -> list[Path]:
    """Candidate base documents in a folder, excluding generated artefacts."""
    root = Path(root)
    return [path for path in sorted(root.glob("*.docx")) if is_base_document(path)]


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
    # `overwrite=True` is consent to replace, not consent to lose: the file being
    # replaced is kept in the trash. The refusal path above writes nothing at all,
    # which is why it does not trash anything.
    trash_then_copy(root, source, target)
    return {
        "imported": True,
        "source": str(source),
        "target": str(target),
        "primary_font": spec["primary_font"],
        "paragraphs": spec["paragraphs"],
        "tables": spec["tables"],
        "original_untouched": True,
    }


# -- templates -------------------------------------------------------------
#
# A user's own document is not only a "base" to clone: it can be a form to fill.
# The difference matters. `apply_replacements` swaps named paragraphs in a copy of
# the user's resume; `fill_template` fills `{{placeholders}}` in a copy of the
# user's *template*, leaving every other byte alone. Both preserve the layout,
# because both start from the user's file — neither invents one.

import re as _re
from ..copy import plural

#: `{{Name}}`, `{{ Name }}`, `{{objective}}`. Deliberately narrow: a token is a
#: short label, not a sentence, so a document that merely contains braces is not
#: mistaken for a template.
FIELD_TOKEN = _re.compile(r"\{\{\s*([A-Za-z0-9_.\- ]{1,80}?)\s*\}\}")


class TemplateFillError(ValueError):
    """A template that would be written with unfilled placeholders."""

    def __init__(self, message: str, leftovers: list[str], report: dict):
        super().__init__(message)
        self.leftovers = leftovers
        self.report = report


def template_fields(template: Path) -> list[str]:
    """Every placeholder in a document, in first-appearance order, deduplicated."""
    seen: list[str] = []
    for _location, paragraph in iter_paragraphs(_document(template)):
        for match in FIELD_TOKEN.finditer(paragraph.text):
            key = match.group(1).strip()
            if key not in seen:
                seen.append(key)
    return seen


def _token(key: str):
    return _re.compile(r"\{\{\s*" + _re.escape(key) + r"\s*\}\}")


def _substitute_paragraph(paragraph, fields: dict[str, str]) -> tuple[int, str]:
    """Fill one paragraph, preferring a run-level swap so its formatting survives.

    A token inside a single run is replaced *in that run*, so a bold name stays
    bold. A token split across runs (Word does this constantly) cannot be replaced
    run-wise, so the paragraph's text is rebuilt with the first run's formatting —
    visible, and better than leaving `{{Name}}` in a document someone will send to
    an employer.

    Returns `(tokens_replaced, mode)` with mode `run`, `paragraph` or `none`.
    """
    text = paragraph.text
    if "{{" not in text:
        return 0, "none"
    total = sum(len(_token(key).findall(text)) for key in fields if _token(key).search(text))
    if total:
        run_hits = 0
        for key in fields:
            token = _token(key)
            for run in paragraph.runs:
                current = run.text or ""
                if token.search(current):
                    run_hits += len(token.findall(current))
                    run.text = token.sub(lambda _m, value=fields[key]: value, current)
        if run_hits == total:
            return total, "run"
    if not FIELD_TOKEN.search(text):
        return 0, "none"
    rebuilt = FIELD_TOKEN.sub(
        lambda match: fields.get(match.group(1).strip(), match.group(0)), text)
    _set_paragraph_text(paragraph, rebuilt)
    return total, "paragraph"


def fill_template(template: Path | str, output: Path | str, spec: dict,
                  root: Path | str | None = None, *,
                  strict: bool = True) -> dict:
    """Fill a user-supplied `.docx` template from a spec, preserving its layout.

    `spec` is `{"fields": {name: value}}` and optionally `{"replace": {old: new}}`
    for a paragraph the template writer wants swapped whole rather than tokenised.
    The output is the user's template with values written in; nothing is rebuilt,
    restyled or regenerated.

    With `strict` (the default) a template that would still contain `{{…}}` is
    **not written at all**: a half-filled resume that renders beautifully is still
    a half-filled resume, and the leftover list is far more useful than the file.
    """
    template = _require(Path(template))
    output = Path(output)
    if output.resolve() == template.resolve():
        raise ValueError("refusing to overwrite the template in place")
    if not isinstance(spec, dict):
        raise ValueError("spec must be a JSON object with a 'fields' map")
    fields = {str(key).strip(): str(value) for key, value in (spec.get("fields") or {}).items()}
    swaps = {str(key): str(value) for key, value in (spec.get("replace") or {}).items()}
    if not fields and not swaps:
        raise ValueError("the spec has no 'fields' and no 'replace' entries; nothing to fill")

    document = _document(template)
    declared = template_fields(template)
    unused = sorted(set(fields) - set(declared))
    replaced: dict[str, int] = {}
    modes: dict[str, int] = {}
    touched = 0
    for _location, paragraph in iter_paragraphs(document):
        before = paragraph.text
        if not before:
            continue
        count, mode = _substitute_paragraph(paragraph, fields)
        if count:
            touched += 1
            for key in fields:
                hits = len(_token(key).findall(before))
                if hits:
                    replaced[key] = replaced.get(key, 0) + hits
            modes[mode] = modes.get(mode, 0) + 1
        swap = swaps.get(before.strip())
        if swap is not None:
            _set_paragraph_text(paragraph, swap)
            touched += 1

    leftovers = sorted({match.group(0) for _location, paragraph in iter_paragraphs(document)
                        for match in FIELD_TOKEN.finditer(paragraph.text)})
    report = {
        "template": str(template),
        "output": str(output),
        "fields": len(fields),
        "declared": sorted(declared),
        "replaced": replaced,
        "mode": modes,
        "unused": unused,
        "leftovers": leftovers,
        "paragraphs_touched": touched,
        "strict": strict,
    }
    if leftovers and strict:
        raise TemplateFillError(
            f"{template.name} still contains {plural(len(leftovers),'unfilled placeholder')}: "
            f"{', '.join(leftovers[:8])}. Supply them in the spec, or pass "
            "--allow-leftovers to write the partial document.", leftovers, report)

    output.parent.mkdir(parents=True, exist_ok=True)
    trash_then_copy(_trash_root(root, template), template, output)
    document.save(str(output))
    report["written"] = True
    report["bytes"] = output.stat().st_size
    return report
