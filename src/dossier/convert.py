from dataclasses import dataclass
from pathlib import Path
import csv
import json
import shutil


def _pymupdf():
    """PyMuPDF under its supported module name, falling back to the `fitz` alias.

    `fitz` is deprecated and prints a warning through whatever stream was
    current when it was first imported, which raises inside a test runner whose
    capture is already closed.
    """
    try:
        import pymupdf
        return pymupdf
    except ImportError:
        import fitz
        return fitz


@dataclass
class RendererInfo:
    name: str
    available: bool
    detail: str = ""


@dataclass
class Route:
    target: str
    fidelity: str
    requires: str | None = None


def available_renderers():
    """Renderer availability, answered once — by `engine/render`.

    This module used to carry its own Word-path check (one install location only)
    and its own docx2pdf call, so the API and the CLI could disagree about
    whether a renderer existed at all. The authoritative answer now lives in
    `engine.render`; only the extra names this adapter's callers may read are
    added here.
    """
    from .engine import render as docx_render

    table = dict(docx_render.available_renderers())
    pandoc = shutil.which("pandoc")
    table["pandoc"] = RendererInfo("Pandoc", pandoc is not None, pandoc or "not found")
    return table


def routes(ext):
    """Conversion routes with their fidelity class.

    The table lives in `engine.render`; this adapter only reshapes it into the
    dataclass the API and the older tests expect, so the fidelity of a route is
    declared exactly once.
    """
    from .engine import render

    return [Route(item["target"], item["fidelity"], item["requires"])
            for item in render.routes(ext)]


def _write_docx_from_markdown(source: Path, target: Path):
    from docx import Document
    document = Document()
    for line in source.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("# "): document.add_heading(line[2:], level=1)
        elif line.startswith("## "): document.add_heading(line[3:], level=2)
        elif line.startswith("- "): document.add_paragraph(line[2:], style="List Bullet")
        elif line.strip(): document.add_paragraph(line)
    document.save(target)


def _text_from(path: Path) -> str:
    from .extract import extract_text
    text, meta = extract_text(path)
    if meta.get("error") and not text:
        raise ValueError(meta["error"])
    return text


def _csv_to_json(src: Path, target: Path):
    with src.open(newline="", encoding="utf-8", errors="replace") as handle:
        rows = list(csv.DictReader(handle))
    target.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")


def _json_to_csv(src: Path, target: Path):
    data = json.loads(src.read_text(encoding="utf-8"))
    if isinstance(data, dict) and isinstance(data.get("rows"), list):
        data = data["rows"]
    if not isinstance(data, list) or (data and not all(isinstance(row, dict) for row in data)):
        raise ValueError("JSON to CSV requires a list of objects")
    keys = list(data[0]) if data else []
    with target.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=keys)
        writer.writeheader()
        writer.writerows(data)


def convert(src, target, opts=None):
    src, target = Path(src), Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    ext, target_ext = src.suffix.casefold(), target.suffix.casefold()
    if src.resolve() == target.resolve():
        raise ValueError("source and target must differ")
    if ext == ".pdf" and target_ext == ".png":
        pymupdf = _pymupdf()
        document = pymupdf.open(str(src))
        if not document.page_count:
            raise ValueError("PDF has no pages")
        document[0].get_pixmap(matrix=pymupdf.Matrix(150 / 72, 150 / 72), alpha=False).save(str(target))
        return target
    if ext == ".docx" and target_ext == ".pdf":
        # One authoritative DOCX->PDF path: `engine/render` drives a private
        # `DispatchEx` Word instance and always quits it. The docx2pdf call that
        # used to live here attached to whatever Word instance was already
        # registered, so a stale invisible WINWORD.EXE made every conversion after
        # the first die with `AttributeError: Open.SaveAs` — the exact failure
        # `engine/render` exists to prevent. `/api/render` and `/api/export` both
        # come through here, so the API and the CLI now use the same renderer.
        from .engine import render as docx_render

        docx_render.export_pdf(src, target)
        if not target.exists() or target.stat().st_size == 0:
            raise RuntimeError("the renderer returned without a PDF output")
        return target
    if ext == ".md" and target_ext == ".docx":
        _write_docx_from_markdown(src, target); return target
    if ext in {".docx", ".pdf"} and target_ext in {".md", ".txt"}:
        target.write_text(_text_from(src), encoding="utf-8"); return target
    if ext == ".md" and target_ext == ".txt":
        shutil.copyfile(src, target); return target
    if ext == ".csv" and target_ext == ".json":
        _csv_to_json(src, target); return target
    if ext == ".json" and target_ext == ".csv":
        _json_to_csv(src, target); return target
    if target_ext == ".zip":
        import zipfile
        members = (opts or {}).get("members") or [src]
        with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            names = []
            for member in members:
                path = Path(member); archive.write(path, path.name); names.append(path.name)
            archive.writestr("manifest.json", json.dumps({"files": names}, indent=2))
        return target
    raise ValueError(f"unsupported conversion {ext} to {target_ext}")
