"""The licence gate: a runtime dependency must never be copyleft.

`LICENSE` says MIT and `pyproject.toml` declares an SPDX expression. Neither is an
audit of what a default install pulls in — on 2026-11-09 `pymupdf` (AGPL-3.0-or-
commercial) sat in `dependencies` while both said MIT. This test reads the declared
runtime set, resolves each name against the installed metadata, and fails on a
copyleft or non-commercial licence. PyMuPDF may appear only in an extra.
"""
from __future__ import annotations

import re
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
COPYLEFT = re.compile(
    r"(?i)\b(AGPL|GPL|LGPL|SSPL|CC-BY-NC|CC BY-NC|non[- ]?commercial|"
    r"Business Source|Commons Clause|Artifex)\b")
PERMISSIVE = re.compile(
    r"(?i)\b(MIT|BSD|Apache|PSF|ISC|MPL|Python Software|Public Domain|Unlicense|Zlib)\b")


def _declared() -> list[str]:
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    names = []
    for entry in data["project"].get("dependencies", []):
        name = re.split(r"[<>=!~\[; ]", entry.strip(), maxsplit=1)[0]
        names.append(name)
    return names


def _normalise(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _installed_licence(name: str) -> tuple[str, str] | None:
    """(dist-name, licence-text) for one installed package, or None if it is absent.

    `importlib.metadata` rather than a hard-coded `site-packages` path, so the gate
    works on Linux CI as well as on the Windows machine it was written on.
    """
    from importlib import metadata as importlib_metadata

    wanted = _normalise(name)
    try:
        dist = importlib_metadata.distribution(wanted)
    except importlib_metadata.PackageNotFoundError:
        return None
    meta = dist.metadata
    licence = meta.get("License-Expression") or meta.get("License") or ""
    classifiers = [value.split("::")[-1].strip()
                   for value in meta.get_all("Classifier") or []
                   if value.startswith("License")]
    if len(licence) > 200:  # some packages paste the whole licence text here
        licence = licence.splitlines()[0] if licence.splitlines() else licence
    return meta.get("Name") or name, " / ".join(part for part in [licence, *classifiers] if part)



def test_every_runtime_dependency_is_permissive():
    declared = _declared()
    assert declared, "pyproject.toml declares no runtime dependencies"
    problems: list[str] = []
    judged = 0
    unjudged: list[str] = []
    for name in declared:
        found = _installed_licence(name)
        if found is None:
            unjudged.append(name)
            continue
        dist, licence = found
        if not licence.strip():
            unjudged.append(f"{dist} (no licence metadata)")
            continue
        if COPYLEFT.search(licence):
            problems.append(f"{dist}: {licence}")
            continue
        if PERMISSIVE.search(licence):
            judged += 1
    assert not problems, problems
    # A gate that silently judges nothing is worse than no gate.
    assert judged >= 8, f"only {judged} runtime dependencies could be judged; unjudged: {unjudged}"


def test_pymupdf_is_an_extra_and_never_a_runtime_dependency():
    """PyMuPDF is AGPL-3.0-or-commercial; it may only be opt-in."""
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    runtime = " ".join(data["project"].get("dependencies", [])).lower()
    assert "pymupdf" not in runtime
    assert "pymupdf" in " ".join(data["project"].get("optional-dependencies", {})).lower()


def test_no_source_module_imports_pymupdf_directly():
    """The engine goes through `render.text_layout`, which prefers PDFium."""
    offenders = []
    for path in sorted((ROOT / "src").rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        if re.search(r"^\s*(import|from)\s+(pymupdf|fitz)\b", text, re.M):
            offenders.append(str(path.relative_to(ROOT)))
    # render.py is the single sanctioned fallback and imports lazily inside functions.
    allowed = {"src/dossier/engine/render.py"}
    normalised = {path.replace(chr(92), "/") for path in offenders}
    assert normalised <= allowed, offenders
