"""Environment capability report.

Answers "what can this machine actually do" before a run starts, so a missing
renderer or an unimportable dependency surfaces as a named blocker instead of a
half-finished batch and a hopeful summary.
"""

from __future__ import annotations

import importlib
import platform
import sqlite3
import sys
from pathlib import Path

from . import render

REQUIRED = ("fastapi", "uvicorn", "watchfiles", "docx", "pymupdf")
OPTIONAL = ("win32com", "pypdf", "openpyxl", "pandas", "PIL")

CAPABILITIES = {
    "docx_read": "python-docx",
    "docx_write": "python-docx",
    "docx_to_pdf": "Microsoft Word or LibreOffice",
    "pdf_text_layer": "pymupdf",
    "pdf_to_image": "pymupdf",
    "fts_search": "sqlite3 with FTS5",
    "capture_public": "obscura, or Playwright+Chromium",
    "capture_authenticated": "Playwright+Chromium with a user-created session",
}


def _importable(name: str) -> dict:
    try:
        module = importlib.import_module(name)
    except Exception as exc:  # noqa: BLE001
        return {"module": name, "ok": False, "detail": f"{type(exc).__name__}: {exc}"}
    return {"module": name, "ok": True, "detail": getattr(module, "__version__", "importable")}


def _fts5() -> bool:
    try:
        connection = sqlite3.connect(":memory:")
        connection.execute("CREATE VIRTUAL TABLE probe USING fts5(x)")
        connection.close()
        return True
    except sqlite3.Error:
        return False


def capture_report() -> dict:
    """The browser engines, without importing Playwright unless it is installed.

    Doctor must answer "can this machine capture a page" in the same breath as
    "can it render a document", because a brief that promises an authenticated
    capture on a machine with no browser is a promise the engine cannot keep.
    """
    try:
        from ..scrape import browser
        engines = browser.available()
    except Exception as exc:  # noqa: BLE001 - doctor reports, it never fails the run
        return {"engines": {}, "detail": f"capture layer unavailable: {type(exc).__name__}: {exc}"}
    return {"engines": engines}


def report(root: Path | str | None = None) -> dict:
    required = [_importable(name) for name in REQUIRED]
    optional = [_importable(name) for name in OPTIONAL]
    renderers = {name: {"available": info.available, "detail": info.detail}
                 for name, info in render.available_renderers().items()}
    capture = capture_report()
    engines = capture.get("engines", {})
    # The outbound model path is the one integration that needs credentials, and
    # `model.availability()` is documented as safe to call here. Without this,
    # the only way to learn it was unavailable was to make a call and take a 503.
    try:
        from .. import model as model_module
        model_state = model_module.availability(root)
    except Exception as exc:  # noqa: BLE001 - doctor reports, it never fails
        model_state = {"available": False,
                       "reason": f"the model layer could not be read: {type(exc).__name__}: {exc}"}

    capabilities = {
        "docx_read": all(entry["ok"] for entry in required if entry["module"] == "docx"),
        "docx_write": all(entry["ok"] for entry in required if entry["module"] == "docx"),
        "docx_to_pdf": renderers["word"]["available"] or renderers["libreoffice"]["available"],
        "pdf_text_layer": renderers["pymupdf"]["available"],
        "pdf_to_image": renderers["pymupdf"]["available"],
        "fts_search": _fts5(),
        "private_word_instance": _importable("win32com")["ok"],
        "capture_public": bool(engines.get("obscura", {}).get("available")
                                or engines.get("playwright", {}).get("available")),
        "capture_authenticated": bool(engines.get("playwright", {}).get("available")),
    }

    blockers = []
    if not capabilities["docx_read"]:
        blockers.append("python-docx is not importable: document generation and diffing cannot run.")
    if not capabilities["docx_to_pdf"]:
        blockers.append(
            "No DOCX renderer (Word or LibreOffice): documents cannot be rendered, so they "
            "cannot be claimed as visually verified."
        )
    if not capabilities["pdf_text_layer"]:
        blockers.append(
            "PyMuPDF is not importable: the ATS text-layer check cannot run, and a PDF that "
            "extracts as garbage would pass unnoticed."
        )
    if not capabilities["fts_search"]:
        blockers.append("SQLite FTS5 is unavailable: full-text search over the workspace is disabled.")
    if not capabilities["capture_authenticated"]:
        # Not a blocker: a public capture still works, and a workspace that never
        # signs in needs nothing. It is named because one whole mode depends on it.
        capture_detail = engines.get("playwright", {}).get("detail", "Playwright is absent")
        capture_warning = ("Authenticated capture is unavailable: " + capture_detail)
    else:
        capture_warning = None

    corpus = None
    if root:
        targets = Path(root)
        if targets.is_dir():
            from . import corpus as corpus_engine
            jobs = corpus_engine.load(targets)
            corpus = {
                "path": str(targets / "all_boards_data" / "all_jobs.json"),
                "rows": len(jobs),
                "hash": corpus_engine.aggregate_hash(jobs) if jobs else None,
            }

    return {
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "python": sys.version.split()[0],
            "executable": sys.executable,
        },
        "required": required,
        "optional": optional,
        "renderers": renderers,
        "capture": {"engines": engines, "detail": capture.get("detail"),
                    "warning": capture_warning},
        "model": model_state,
        "capabilities": capabilities,
        "blockers": blockers,
        "corpus": corpus,
        "verdict": "ready" if not blockers else "degraded",
        "capability_map": CAPABILITIES,
    }
