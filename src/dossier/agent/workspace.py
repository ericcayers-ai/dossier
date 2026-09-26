"""Resolve a folder into the state the agent contract operates on.

Read-only discovery: nothing here writes to a source file. The result answers,
for any model that injects itself, the questions it would otherwise have to
guess at — which resume is the base, where the identity doc lives, how many
postings and applications exist, which sources are captured and how stale the
coverage is.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path

from ..engine import tailor
from ..engine.tracker import canonical_status, parse as parse_tracker

IDENTITY_SUFFIX = "-IDENTITY.md"
SKIP_DIRS = {".dossier", ".git", "__pycache__", "node_modules", ".venv", ".pytest_cache"}


@dataclass
class ArtifactHit:
    name: str
    role: str
    path: str
    rel: str
    size: int
    mtime: float
    detail: str = ""


@dataclass
class Workspace:
    root: str
    name: str
    resolved_on: str
    identity_doc: ArtifactHit | None = None
    resume_extract: ArtifactHit | None = None
    base_documents: list[ArtifactHit] = field(default_factory=list)
    base_candidates_outside_root: list[ArtifactHit] = field(default_factory=list)
    postings: list[ArtifactHit] = field(default_factory=list)
    keyword_reports: list[ArtifactHit] = field(default_factory=list)
    artefacts: list[ArtifactHit] = field(default_factory=list)
    renders: list[ArtifactHit] = field(default_factory=list)
    proofs: list[ArtifactHit] = field(default_factory=list)
    counts: dict = field(default_factory=dict)
    tracker: dict = field(default_factory=dict)
    corpus: dict = field(default_factory=dict)
    coverage: dict = field(default_factory=dict)
    bundles: dict = field(default_factory=dict)
    blockers: list[str] = field(default_factory=list)
    ready: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def _hit(path: Path, root: Path, role: str, detail: str = "") -> ArtifactHit:
    stat = path.stat()
    return ArtifactHit(
        name=path.stem,
        role=role,
        path=str(path),
        rel=path.relative_to(root).as_posix(),
        size=stat.st_size,
        mtime=stat.st_mtime,
        detail=detail,
    )


def _walk(root: Path) -> list[Path]:
    found: list[Path] = []
    for path in root.rglob("*"):
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.is_file():
            found.append(path)
    return found


def _is_base_document(path: Path) -> bool:
    """A resume the user wrote, not one this pipeline produced.

    Delegates to the engine so the resolver and the importer cannot disagree
    about which file is the source of truth.
    """
    return tailor.is_base_document(path)


def _newest(paths: list[Path]) -> Path | None:
    return max(paths, key=lambda p: p.stat().st_mtime) if paths else None


def _external_base_candidates(root: Path) -> list[Path]:
    """Base-document candidates just outside the workspace.

    A workspace folder is where the search lives, not necessarily where the
    user's own resume file sits — on this machine the resume is one folder over.
    Scanning the parent and its immediate children is a bounded, read-only guess
    that lets the engine name a real file instead of just reporting "missing".
    """
    parent = root.parent
    if not parent.is_dir():
        return []
    seen: dict[Path, None] = {}
    for folder in [parent, *sorted(child for child in parent.iterdir() if child.is_dir())]:
        if folder == root or any(part in SKIP_DIRS for part in folder.parts):
            continue
        try:
            for path in sorted(folder.glob("*.docx")):
                if _is_base_document(path):
                    seen[path] = None
        except OSError:
            continue
    return list(seen)


def _load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _corpus_state(root: Path) -> dict:
    boards = sorted(
        path.parent.name for path in root.glob("*_data/all_jobs.json")
        if path.parent.name != "all_boards_data"
    )
    path = root / "all_boards_data" / "all_jobs.json"
    if not path.exists():
        return {
            "present": False,
            "board_folders": boards,
            "board_folders_count": len(boards),
            "detail": (
                f"{len(boards)} board folder(s) present but no aggregate. "
                "Run `dossier corpus build` to merge them."
                if boards else "No captured board data and no aggregate."
            ),
        }
    data = _load_json(path)
    if not isinstance(data, list):
        return {"present": True, "error": "corpus is not a JSON list", "path": str(path)}
    ids = [str(row.get("id", "")) for row in data if isinstance(row, dict)]
    fits: dict[str, int] = {}
    sources: dict[str, int] = {}
    unscored_ids = 0
    for row in data:
        if not isinstance(row, dict):
            continue
        fit = str(row.get("fit") or "unset")
        fits[fit] = fits.get(fit, 0) + 1
        source = str(row.get("source") or "unknown")
        sources[source] = sources.get(source, 0) + 1
        if fit == "unset":
            unscored_ids += 1
    duplicate_ids = len(ids) - len(set(ids))
    return {
        "present": True,
        "path": str(path),
        "board_folders": boards,
        "board_folders_count": len(boards),
        "rows": len(data),
        "distinct_ids": len(set(ids)),
        "duplicate_ids": duplicate_ids,
        "unscored": unscored_ids,
        "fits": dict(sorted(fits.items())),
        "sources": dict(sorted(sources.items())),
        "sources_count": len(sources),
    }


def _tracker_state(root: Path) -> dict:
    history_path = root / "job-history.md"
    records = parse_tracker(root)
    counts: dict[str, int] = {}
    for record in records:
        status = canonical_status(record.get("status", "unknown"))
        counts[status] = counts.get(status, 0) + 1
    followups = root / "follow-ups.md"
    applied_dates: dict[int, str] = {}
    if followups.exists():
        text = followups.read_text(encoding="utf-8", errors="replace")
        for match in re.finditer(r"Applied\s+(\d{4}-\d{2}-\d{2}).*?#(\d+)", text, re.IGNORECASE):
            try:
                date.fromisoformat(match.group(1))
            except ValueError:
                continue
            applied_dates[int(match.group(2))] = match.group(1)
    return {
        "present": history_path.exists(),
        "path": str(history_path),
        "rows": len(records),
        "status_counts": dict(sorted(counts.items())),
        "confirmed_application_dates": {
            str(number): when for number, when in sorted(applied_dates.items())
        },
        "actionable_without_date": [
            index
            for index, record in enumerate(records, start=1)
            if canonical_status(record.get("status", "")) in {"applied", "responded", "interview"}
            and index not in applied_dates
        ],
    }


def _coverage_state(root: Path) -> dict:
    candidates = sorted(root.glob("nz-job-search-coverage-*.json"))
    if not candidates:
        return {"present": False}
    path = candidates[-1]
    data = _load_json(path)
    if not isinstance(data, dict):
        return {"present": True, "path": str(path), "error": "unreadable"}
    captured_on = data.get("captured_on")
    age_days = None
    if captured_on:
        try:
            age_days = (date.today() - date.fromisoformat(str(captured_on))).days
        except ValueError:
            age_days = None
    statuses = data.get("source_statuses") or {}
    return {
        "present": True,
        "path": str(path),
        "file": path.name,
        "captured_on": captured_on,
        "age_days": age_days,
        "stale": age_days is None or age_days > 7,
        "merged_rows": data.get("merged_rows"),
        "ranking_rows": data.get("ranking_rows"),
        "sources": len(statuses) or len(data.get("sources", []) or []),
        "limits": data.get("current_limits", {}),
    }


def resolve(root: Path | str) -> Workspace:
    """Discover everything the contract needs about a folder. Never writes."""
    root = Path(root).resolve()
    if not root.is_dir():
        raise NotADirectoryError(f"not a folder: {root}")

    files = _walk(root)
    by_suffix: dict[str, list[Path]] = {}
    for path in files:
        by_suffix.setdefault(path.suffix.casefold(), []).append(path)

    identity_candidates = [p for p in files if p.name.upper().endswith(IDENTITY_SUFFIX.upper())]
    identity_path = _newest(identity_candidates)

    resume_extract = root / "resume.md"
    base_candidates = sorted(p for p in by_suffix.get(".docx", []) if _is_base_document(p))

    postings = sorted(by_suffix.get(".md", []), key=lambda p: p.name)
    postings = [p for p in postings if p.name.casefold().startswith(("job-posting-", "posting-"))]
    keywords = [p for p in by_suffix.get(".md", []) if p.name.casefold().startswith(("keywords-", "keyword-"))]
    artefacts = [p for p in by_suffix.get(".docx", []) if tailor.is_generated_document(p)]
    renders = by_suffix.get(".pdf", [])
    proofs = [p for p in by_suffix.get(".png", []) if re.search(r"-page-\d+", p.name, re.IGNORECASE)]

    workspace = Workspace(
        root=str(root),
        name=root.name,
        resolved_on=date.today().isoformat(),
        identity_doc=_hit(identity_path, root, "identity") if identity_path else None,
        resume_extract=_hit(resume_extract, root, "identity") if resume_extract.exists() else None,
        base_documents=[_hit(p, root, "source") for p in base_candidates],
        base_candidates_outside_root=[
            _hit(p, p.parent, "source", detail="outside the workspace root")
            for p in _external_base_candidates(root)
        ],
        postings=[_hit(p, root, "source") for p in postings],
        keyword_reports=[_hit(p, root, "analysis") for p in keywords],
        artefacts=[_hit(p, root, "artifact") for p in artefacts],
        renders=[_hit(p, root, "render") for p in renders],
        proofs=[_hit(p, root, "proof") for p in proofs],
        counts={
            "files": len(files),
            "postings": len(postings),
            "keyword_reports": len(keywords),
            "artefacts": len(artefacts),
            "renders": len(renders),
            "proofs": len(proofs),
            "base_documents": len(base_candidates),
        },
        tracker=_tracker_state(root),
        corpus=_corpus_state(root),
        coverage=_coverage_state(root),
    )

    # Bundle rules: per-folder if present, otherwise the shipped template.
    rules_path = root / ".dossier" / "bundles.json"
    if not rules_path.exists():
        rules_path = Path(__file__).parents[2] / "templates" / "bundles.json"
    workspace.bundles = _load_json(rules_path) or {}

    # Blockers are stated plainly so an injected model does not have to infer them.
    if not workspace.identity_doc:
        workspace.blockers.append(
            f"No *{IDENTITY_SUFFIX} found. Build one from real project/coursework evidence "
            "before writing any resume copy."
        )
    if not workspace.base_documents:
        outside = workspace.base_candidates_outside_root
        hint = (
            " Candidate(s) found outside this folder: "
            + ", ".join(f"`{doc.path}`" for doc in outside[:3])
            + ". Ask the user which one is their base, then import it with "
            "`dossier tailor import` before generating anything."
        ) if outside else ""
        workspace.blockers.append(
            "No base .docx in this folder. Document generation is blocked: layout cloning "
            "needs a real user document; there is no template fallback." + hint
        )
    if not workspace.tracker.get("present"):
        workspace.blockers.append("No job-history.md tracker. Application state is unknown.")
    if workspace.tracker.get("actionable_without_date"):
        workspace.blockers.append(
            "Application rows without a confirmed 'Applied YYYY-MM-DD': "
            f"{workspace.tracker['actionable_without_date']}. Follow-up cadence will not run for these."
        )
    if workspace.corpus.get("duplicate_ids"):
        workspace.blockers.append(
            f"Corpus has {workspace.corpus['duplicate_ids']} duplicate ids; keyed lists will render wrong rows."
        )
    if workspace.corpus.get("present") and workspace.corpus.get("unscored"):
        workspace.blockers.append(
            f"{workspace.corpus['unscored']} corpus rows carry no fit score; ranking is incomplete."
        )
    if not workspace.corpus.get("present") and workspace.corpus.get("board_folders_count"):
        workspace.blockers.append(
            f"{workspace.corpus['board_folders_count']} captured board folder(s) have no merged "
            "aggregate; run `dossier corpus build` before ranking or tailoring from them."
        )
    if workspace.coverage.get("stale"):
        workspace.blockers.append(
            "Coverage snapshot is missing or older than 7 days; source freshness is unproven."
        )

    ready = []
    if workspace.resume_extract:
        ready.append("analysis (diagnose, keywords, rewrite) can run from resume.md")
    if workspace.base_documents:
        ready.append("document generation can run (base .docx present)")
    if workspace.postings:
        ready.append(f"{len(workspace.postings)} archived posting(s) available as tailoring targets")
    if workspace.corpus.get("present"):
        ready.append(f"corpus loaded: {workspace.corpus.get('rows')} rows from "
                     f"{workspace.corpus.get('sources_count')} boards")
    if workspace.tracker.get("present"):
        ready.append(f"tracker loaded: {workspace.tracker.get('rows')} rows")
    workspace.ready = ready
    return workspace


def write_state(workspace: Workspace, dossier_dir: Path) -> Path:
    """Persist the resolved state beside the index so a later session reuses it."""
    dossier_dir.mkdir(parents=True, exist_ok=True)
    target = dossier_dir / "workspace.json"
    target.write_text(json.dumps(workspace.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
    return target
