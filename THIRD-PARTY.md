# Third-party notices

This repository's own code is MIT (`LICENSE`). This file exists because a licence
claim about the *repository* is not a licence audit of what it *installs*, and the
two disagreed on 2026-11-09: `pymupdf` was a runtime dependency while `LICENSE`
said MIT.

## Runtime dependencies — all permissive

`pip install dossier` (see `dependencies` in `pyproject.toml`) pulls only these
families:

| package | licence |
|---|---|
| `fastapi`, `uvicorn[standard]`, `watchfiles` | MIT / BSD-3-Clause |
| `python-docx` | MIT |
| `pypdfium2` (PDF text, geometry, rasterising) | BSD-3-Clause / Apache-2.0 |
| `pypdf` | BSD-3-Clause |
| `pillow` | MIT-CMU |
| `docx2pdf` | MIT |
| `jinja2` | BSD-3-Clause |
| `defusedxml` | PSF-2.0 |
| `httpx` | BSD-3-Clause |

The browser UI (`ui/package-lock.json`) is MIT, MPL-2.0 (a few toolchain
packages) and BSD/Apache. `npm audit --omit=dev` reports 0 vulnerabilities at
the last check.

## Optional extra: PyMuPDF is AGPL-3.0-or-commercial

`src/dossier/engine/render.py` prefers PDFium and falls back to PyMuPDF only when
it is installed. PyMuPDF (`pymupdf` / `fitz`) is dual-licensed **AGPL-3.0** or a
commercial licence from Artifex, and it is deliberately **not** in `dependencies`:

```text
pip install "dossier[pymupdf]"
```

What that means, stated plainly: AGPL-3.0 is a strong copyleft. Importing
PyMuPDF into an application and then *conveying* the combined work (a bundled
installer, a container image, a binary, a hosted service someone else uses)
obliges you to release that combined work under the AGPL, or to buy the
commercial licence. Publishing this source repository under MIT, where the user
installs dependencies themselves, does not by itself convey a combined work —
but a bundle does. If you are packaging Dossier for other people, either stay on
`pypdfium2` (the default) or obtain the Artifex licence.

## Development and test dependencies

`pytest`, `httpx` (MIT) and — for the fixtures that synthesise sample PDFs —
`pymupdf` (AGPL, test-only). Nothing in `src/` imports PyMuPDF directly any more;
`tests/` uses it to *create* PDFs, which is not distribution of a combined work.

## What is not here

No vendored third-party source, no bundled model weights, and no asset fonts or
icon sets from a third party. `find . -name "LICENSE*"` outside `.venv/` and
`ui/node_modules/` returns exactly this repository's own `LICENSE`.
