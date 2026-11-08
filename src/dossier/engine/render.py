"""Rendering: DOCX to PDF to page image.

Word automation is driven through a private COM instance rather than docx2pdf.
docx2pdf attaches to whatever Word instance is already registered, and a stale
invisible WINWORD.EXE left by an earlier run makes `Documents.Open` return a
non-document, so every conversion after the first dies with
`AttributeError: Open.SaveAs` — a failure whose text points nowhere near its
cause. `DispatchEx` forces a private instance, `ExportAsFixedFormat` is the
supported PDF path, and the instance is always quit.

Nothing here silently installs a renderer. If Word is absent and LibreOffice is
absent, a conversion fails loudly, because "rendered" is a claim that has to be
true.
"""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

WD_FORMAT_PDF = 17
WD_DO_NOT_SAVE = 0
SKIP_DIRS = {".dossier", ".git", "__pycache__", "node_modules", ".venv", ".pytest_cache"}
_WORD_PATHS = (
    Path(r"C:/Program Files/Microsoft Office/root/Office16/WINWORD.EXE"),
    Path(r"C:/Program Files (x86)/Microsoft Office/root/Office16/WINWORD.EXE"),
)


@dataclass
class RendererInfo:
    name: str
    available: bool
    detail: str = ""


def available_renderers() -> dict[str, RendererInfo]:
    word = next((path for path in _WORD_PATHS if path.exists()), None)
    return {
        "word": RendererInfo("Word", word is not None, str(word or "not found")),
        "libreoffice": RendererInfo("LibreOffice", shutil.which("soffice") is not None,
                                    shutil.which("soffice") or "not found"),
        "pdfium": RendererInfo("PDFium", _has_pdfium(), "python import pypdfium2"),
        "pymupdf": RendererInfo("PyMuPDF (AGPL, optional)", _has_pymupdf(),
                                "python import pymupdf"),
    }


def _has_pymupdf() -> bool:
    try:
        import pymupdf  # noqa: F401
        return True
    except ImportError:
        try:
            import fitz  # noqa: F401
            return True
        except ImportError:
            return False


def _pymupdf():
    try:
        import pymupdf
        return pymupdf
    except ImportError:
        import fitz
        return fitz


def _has_pdfium() -> bool:
    """PDFium is the default engine: BSD-3-Clause / Apache-2.0, not copyleft."""
    try:
        import pypdfium2  # noqa: F401
        return True
    except ImportError:
        return False


def text_layout(pdf: Path) -> dict | None:
    """Pages, page sizes and text blocks for one PDF, with a top-left origin.

    One shape for two engines so `verify` never has to know which is installed:
    PDFium first (permissive), PyMuPDF second (AGPL, optional extra). Block
    coordinates are top-left based like PyMuPDF's, because the margin check is
    written in that frame; PDFium reports bottom-left, so `y` is flipped here.
    """
    pdf = Path(pdf)
    if _has_pdfium():
        import pypdfium2 as pdfium

        pages: list[dict] = []
        with pdfium.PdfDocument(str(pdf)) as document:
            for index in range(len(document)):
                page = document[index]
                width, height = page.get_size()
                textpage = page.get_textpage()
                blocks = []
                for rect_index in range(textpage.count_rects()):
                    left, bottom, right, top = textpage.get_rect(rect_index)
                    text = textpage.get_text_bounded(left, bottom, right, top)
                    if not text.strip():
                        continue
                    blocks.append({"x0": left, "y0": height - top,
                                   "x1": right, "y1": height - bottom, "text": text})
                pages.append({"width": width, "height": height, "blocks": blocks})
        return {"engine": "pdfium", "pages": pages}

    if _has_pymupdf():
        pymupdf = _pymupdf()
        pages = []
        with pymupdf.open(str(pdf)) as document:
            for page in document:
                blocks = [
                    {"x0": block[0], "y0": block[1], "x1": block[2], "y1": block[3],
                     "text": block[4]}
                    for block in page.get_text("blocks") if block[4].strip()
                ]
                pages.append({"width": page.rect.width, "height": page.rect.height,
                              "blocks": blocks})
        return {"engine": "pymupdf", "pages": pages}

    return None


def _has_pywin32() -> bool:
    try:
        import win32com.client  # noqa: F401
        return True
    except ImportError:
        return False


def pdf_pages(path: Path) -> int | None:
    layout = text_layout(path)
    if layout is None:
        return None
    return len(layout["pages"])


class RendererUnavailable(RuntimeError):
    pass


def export_pdf(docx: Path, pdf: Path) -> dict:
    """Render one DOCX to PDF. Fails loudly when no renderer exists."""
    docx, pdf = Path(docx), Path(pdf)
    if not docx.exists():
        raise FileNotFoundError(str(docx))
    pdf.parent.mkdir(parents=True, exist_ok=True)

    if _has_pywin32() and available_renderers()["word"].available:
        import win32com.client  # type: ignore

        word = win32com.client.DispatchEx("Word.Application")
        word.Visible = False
        word.DisplayAlerts = 0
        document = None
        # Cleanup failures are collected and reported rather than swallowed. A
        # `Quit` that fails leaves exactly the invisible WINWORD.EXE this module
        # exists to avoid, so a silent `pass` here would hide the next failure's
        # cause — which is the failure mode the docstring describes.
        cleanup: list[str] = []
        try:
            document = word.Documents.Open(str(docx), ReadOnly=True, AddToRecentFiles=False)
            document.ExportAsFixedFormat(str(pdf), WD_FORMAT_PDF)
        finally:
            if document is not None:
                try:
                    document.Close(WD_DO_NOT_SAVE)
                except Exception as exc:  # noqa: BLE001
                    cleanup.append(f"document.Close failed: {type(exc).__name__}: {exc}")
            try:
                word.Quit()
            except Exception as exc:  # noqa: BLE001
                cleanup.append(f"word.Quit failed: {type(exc).__name__}: {exc}")
        result = {"renderer": "word-private-com", "path": str(pdf), "pages": pdf_pages(pdf)}
        if cleanup:
            result["cleanup"] = cleanup
        return result

    soffice = shutil.which("soffice")
    if soffice:
        import subprocess
        result = subprocess.run(
            [soffice, "--headless", "--convert-to", "pdf", "--outdir",
             str(pdf.parent), str(docx)],
            capture_output=True, text=True, timeout=180,
        )
        produced = pdf.parent / (docx.stem + ".pdf")
        if result.returncode != 0 or not produced.exists():
            raise RuntimeError(
                f"LibreOffice conversion failed (rc={result.returncode}): "
                f"{result.stderr.strip()[:200]}"
            )
        if produced != pdf:
            produced.replace(pdf)
        return {"renderer": "libreoffice", "path": str(pdf), "pages": pdf_pages(pdf)}

    raise RendererUnavailable(
        "No DOCX renderer available. Install Microsoft Word or LibreOffice, or hand the "
        "document to the user and report it as NOT visually verified."
    )


def pdf_to_png(pdf: Path, png: Path, page: int = 0, dpi: int = 150) -> Path:
    """Rasterise one PDF page so a human or a vision model can look at it."""
    pdf, png = Path(pdf), Path(png)
    png.parent.mkdir(parents=True, exist_ok=True)
    if _has_pdfium():
        import pypdfium2 as pdfium

        with pdfium.PdfDocument(str(pdf)) as document:
            if not len(document):
                raise ValueError("PDF has no pages")
            if page >= len(document):
                raise IndexError(f"page {page} out of range ({len(document)} pages)")
            document[page].render(scale=dpi / 72).to_pil().save(str(png))
        return png
    if not _has_pymupdf():
        raise RendererUnavailable(
            "No PDF rasteriser is importable; install pypdfium2 (permissive) or the "
            "optional PyMuPDF extra."
        )
    pymupdf = _pymupdf()
    with pymupdf.open(str(pdf)) as document:
        if not document.page_count:
            raise ValueError("PDF has no pages")
        if page >= document.page_count:
            raise IndexError(f"page {page} out of range ({document.page_count} pages)")
        scale = dpi / 72
        document[page].get_pixmap(matrix=pymupdf.Matrix(scale, scale), alpha=False).save(str(png))
    return png


def source_docx(pdf: Path, root: Path) -> Path | None:
    """The DOCX a PDF came from: the sibling first, then a copy at the root."""
    sibling = pdf.with_suffix(".docx")
    if sibling.exists():
        return sibling
    at_root = Path(root) / sibling.name
    return at_root if at_root.exists() else None


def stale_pairs(root: Path | str) -> list[tuple[Path, Path]]:
    """(docx, pdf) pairs where the render is older than its source."""
    root = Path(root)
    pairs: list[tuple[Path, Path]] = []
    for pdf in sorted(root.rglob("*.pdf")):
        if any(part in SKIP_DIRS for part in pdf.parts):
            continue
        docx = source_docx(pdf, root)
        if docx is not None and docx.stat().st_mtime_ns > pdf.stat().st_mtime_ns:
            pairs.append((docx, pdf))
    return pairs


def render_stale(root: Path | str, backup_dir: Path | None = None) -> dict:
    """Rebuild every render whose DOCX source is newer. Superseded files are kept."""
    root = Path(root)
    pairs = stale_pairs(root)
    if not pairs:
        return {"stale": 0, "rebuilt": 0, "failed": [], "checked": True}

    backup = backup_dir or root / ".dossier" / "trash" / (
        "render-backup-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S"))
    backup.mkdir(parents=True, exist_ok=True)

    rebuilt, failed = [], []
    for docx, pdf in pairs:
        keep = backup / f"{pdf.parent.name}__{pdf.name}".replace("/", "_")
        if not keep.exists():
            shutil.copy2(pdf, keep)
        before = docx.stat().st_mtime_ns
        try:
            outcome = export_pdf(docx, pdf)
        except Exception as exc:  # noqa: BLE001
            failed.append({"pdf": str(pdf.relative_to(root)),
                           "error": f"{type(exc).__name__}: {exc}"[:200]})
            continue
        fresh = pdf.exists() and pdf.stat().st_mtime_ns >= before
        entry = {
            "pdf": str(pdf.relative_to(root)),
            "source": str(docx.relative_to(root)),
            "pages": pdf_pages(pdf) if fresh else None,
            "bytes": pdf.stat().st_size if pdf.exists() else 0,
        }
        # A Word instance that would not close is the cause of the *next*
        # failure, so it travels with this render's report instead of vanishing.
        if outcome.get("cleanup"):
            entry["cleanup"] = outcome["cleanup"]
        (rebuilt if fresh else failed).append(entry)

    return {
        "stale": len(pairs),
        "rebuilt": len(rebuilt),
        "rebuilt_detail": rebuilt,
        "failed": failed,
        "backup_dir": str(backup),
        "checked": True,
        "renderer": available_renderers()["word"].detail,
    }


def routes(ext: str) -> list[dict]:
    """Conversion routes with their fidelity class, stated before the click."""
    ext = ext.casefold()
    if ext == ".docx":
        return [{"target": ".pdf", "fidelity": "faithful", "requires": "word"},
                {"target": ".md", "fidelity": "semantic", "requires": None},
                {"target": ".txt", "fidelity": "semantic", "requires": None}]
    if ext == ".pdf":
        return [{"target": ".png", "fidelity": "faithful", "requires": "pymupdf"},
                {"target": ".md", "fidelity": "extracted", "requires": None},
                {"target": ".txt", "fidelity": "extracted", "requires": None}]
    if ext == ".md":
        return [{"target": ".docx", "fidelity": "semantic", "requires": None},
                {"target": ".pdf", "fidelity": "faithful", "requires": "word"}]
    if ext in {".csv", ".json"}:
        return [{"target": ".json" if ext == ".csv" else ".csv", "fidelity": "semantic",
                 "requires": None}]
    return []


def report_path(root: Path | str, name: str) -> Path:
    directory = Path(root) / "resync"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    return path


def write_report(root: Path | str, name: str, payload: dict) -> Path:
    from ..safety import trash_then_write_text

    path = report_path(root, name)
    trash_then_write_text(root, path, json.dumps(payload, indent=2, ensure_ascii=False))
    return path
