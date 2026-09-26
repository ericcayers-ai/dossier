from dataclasses import dataclass
from pathlib import Path
import csv
import json
import shutil
import sys
import threading


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


_word_lock = threading.Lock()
_WORD = Path(r"C:/Program Files/Microsoft Office/root/Office16/WINWORD.EXE")


def available_renderers():
    word = sys.platform == "win32" and _WORD.exists()
    return {
        "word": RendererInfo("Word", word, str(_WORD)),
        "libreoffice": RendererInfo("LibreOffice", shutil.which("soffice") is not None),
        "pandoc": RendererInfo("Pandoc", shutil.which("pandoc") is not None),
        "pymupdf": RendererInfo("PyMuPDF", True),
    }


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
        if not available_renderers()["word"].available:
            raise RuntimeError("Word renderer unavailable; install Microsoft Word or use LibreOffice")
        with _word_lock:
            try:
                from docx2pdf import convert as word_convert
                word_convert(str(src), str(target), keep_active=True)
            except Exception as exc:
                raise RuntimeError(f"Word is busy with a dialog or conversion failed: {exc}") from exc
        if not target.exists() or target.stat().st_size == 0:
            raise RuntimeError("Word conversion returned without a PDF output")
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
