"""The cross-session work loop.

A model injected into this workspace has no memory of the last one. The loop
gives it one: it reads the resolved workspace and the filesystem, decides the
single next unit of work, and records what each session handed back. That is
what turns a pile of scripts into an operating system — the state lives here,
not in a conversation.

Selection is deterministic and ordered by consequence. A data-integrity defect
outranks a stale render; a missing base document outranks everything, because
nothing downstream can be trusted while the source of truth is absent.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from . import manifest
from .workspace import Workspace, resolve, write_state
from ..copy import plural

STATE_NAME = "agent-loop.json"
MAX_HISTORY = 200


def _state_path(workspace: Workspace) -> Path:
    return Path(workspace.root) / ".dossier" / STATE_NAME


def _load(path: Path) -> dict:
    if not path.exists():
        return {"schema_version": manifest.SCHEMA_VERSION, "history": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"schema_version": manifest.SCHEMA_VERSION, "history": [],
                "recovered_from": "unreadable state file"}
    if not isinstance(data, dict):
        return {"schema_version": manifest.SCHEMA_VERSION, "history": []}
    data.setdefault("history", [])
    return data


def _save(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    state["updated"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    state["history"] = state["history"][-MAX_HISTORY:]
    # The state file lives at `<root>/.dossier/agent-loop.json`, so the workspace
    # the trash belongs to is two levels up. Every save after the first replaces a
    # real file, and each one is recoverable.
    from ..safety import trash_then_write_text

    trash_then_write_text(path.parent.parent, path,
                          json.dumps(state, indent=2, ensure_ascii=False))


def _postings_without_analysis(workspace: Workspace) -> list[str]:
    """Postings that have no keyword report yet.

    A report is either a `keywords-*` markdown analysis or the mechanical
    `<posting-stem>.skillgap.json` the gap classifier writes. Accepting only the
    first would leave the loop reporting the same unit forever after a session
    had already done it.
    """
    analysed = " ".join(
        report.rel.casefold() for report in workspace.keyword_reports
    )
    root = Path(workspace.root)
    for posting in workspace.postings:
        own = Path(posting.rel).name.casefold()
        # Sibling artifacts of the posting, never the posting itself — globbing
        # `<stem>.*` would otherwise match the posting and mark it analysed.
        siblings = [
            path.name.casefold() for path in root.glob(f"{posting.name}.*")
            if path.name.casefold() != own
        ]
        analysed += " " + " ".join(siblings)
    missing = []
    for posting in workspace.postings:
        token = posting.name.casefold().replace("job-posting-", "").replace("posting-", "")
        if token and token not in analysed:
            missing.append(posting.rel)
    return missing


def _stale_render_count(root: Path) -> int:
    from ..engine import render
    try:
        return len(render.stale_pairs(root))
    except OSError:
        return 0


def _candidate(mode_id: str, reason: str, **extra) -> dict:
    item = manifest.mode(mode_id)
    return {
        "mode": item.id,
        "label": item.label,
        "stage": item.stage,
        "kind": item.kind,
        "reason": reason,
        "summary": item.summary,
        "blocks": list(item.gates),
        "engine": item.engine,
        **extra,
    }


def next_unit(root: Path | str, workspace: Workspace | None = None) -> dict:
    """The single next unit of work, with the reason it was chosen."""
    space = workspace or resolve(root)
    corpus_state = space.corpus or {}
    tracker_state = space.tracker or {}
    coverage_state = space.coverage or {}

    # 1. Source of truth absent — nothing downstream is trustworthy.
    if not space.identity_doc:
        return _candidate("setup", "No identity doc: every claim needs an evidence base first.",
                          needs_user=True, blocking=True)
    if not space.base_documents:
        return _candidate(
            "build",
            "No base .docx in this folder. Document generation is blocked until the user "
            "supplies the resume file this workspace clones.",
            needs_user=True, blocking=True)

    # 2. Data integrity — a keyed list rendering the wrong rows outranks cosmetics.
    if corpus_state.get("present") and corpus_state.get("duplicate_ids"):
        return _candidate(
            "corpus",
            f"{plural(corpus_state['duplicate_ids'],'duplicate id')} in the corpus: keyed lists will "
            "render wrong rows after a filter changes the row count.",
            targets=[corpus_state.get("path")], blocking=False)

    # 3. Scoring incomplete — ranking is the input to tailoring.
    if corpus_state.get("present") and corpus_state.get("unscored"):
        return _candidate(
            "rank",
            f"{plural(corpus_state['unscored'],'corpus row')} carry no fit score; ranking is incomplete.",
            targets=[corpus_state.get("path")])

    # 4. Source freshness unproven.
    if coverage_state.get("stale"):
        return _candidate(
            "sources",
            "Coverage snapshot is missing or older than 7 days: source freshness is unproven. "
            "A fresh `dossier feeds fetch <source>` or `dossier scrape run --due` records it; "
            "a partial capture must not be reported as exhaustive.",
            targets=[coverage_state.get("path")] if coverage_state.get("present") else [])

    # 5. Renders older than their source — a stale PDF is a wrong artifact.
    stale = _stale_render_count(Path(space.root))
    if stale:
        return _candidate(
            "render",
            f"{plural(stale,'PDF render')} older than the DOCX source.",
            targets=[space.root])

    # 6. Postings captured but never analysed.
    unanalysed = _postings_without_analysis(space)
    if unanalysed:
        return _candidate(
            "keywords",
            f"{plural(len(unanalysed),'archived posting')} have no keyword report yet.",
            targets=unanalysed[:12])

    # 7. Actionable applications with no confirmed date stall the cadence.
    undated = tracker_state.get("actionable_without_date") or []
    if undated:
        return _candidate(
            "followup",
            f"{plural(len(undated),'application row')} actionable but with no confirmed "
            "'Applied YYYY-MM-DD' record: the cadence cannot run. Rows {', '.join(undated[:6])}",
            needs_user=True, targets=[tracker_state.get("path")])

    # 8. Postings analysed but no tailored document generated.
    if space.postings and not space.artefacts:
        return _candidate(
            "build",
            f"{plural(len(space.postings),'analysed posting')} but no tailored document exists yet.",
            targets=[posting.rel for posting in space.postings[:6]])

    # 9. Nothing outstanding — reconcile and report.
    return _candidate(
        "audit",
        "No outstanding defect found. Reconcile the workspace and report state.",
        targets=[space.root])


def status(root: Path | str) -> dict:
    space = resolve(root)
    state = _load(_state_path(space))
    history = state.get("history", [])
    return {
        "root": space.root,
        "updated": state.get("updated"),
        "sessions": len(history),
        "last": history[-1] if history else None,
        "blockers": space.blockers,
        "counts": space.counts,
        "next": next_unit(root, space),
        "recent": [
            {"at": entry.get("at"), "mode": entry.get("mode"), "status": entry.get("status"),
             "artifacts": entry.get("artifacts", [])}
            for entry in history[-8:]
        ],
    }


REQUIRED_HAND_BACK = ("mode", "status", "artifacts", "evidence", "gaps")


def commit(root: Path | str, handback: dict, workspace: Workspace | None = None) -> dict:
    """Absorb a session's result and advance the loop.

    Validates the handback shape rather than trusting it: a model reporting
    "done" with no evidence and no artifacts is exactly the failure this exists
    to catch.
    """
    space = workspace or resolve(root)
    problems = [field for field in REQUIRED_HAND_BACK if field not in handback]
    if problems:
        return {
            "accepted": False,
            "problems": [f"handback is missing {plural(len(problems),'required field')}: {', '.join(problems)}"],
            "expected": list(REQUIRED_HAND_BACK),
        }

    status_value = str(handback.get("status", "")).strip()
    allowed = {"completed", "blocked", "needs-user-input", "partial"}
    if status_value not in allowed:
        return {
            "accepted": False,
            "problems": [f"status {status_value!r} is not one of {sorted(allowed)}"],
        }

    # The mode names what was done, and `next_unit` reads the history back. A
    # free-text mode value was stored verbatim, so a typo became a history row
    # nothing could ever route from.
    from . import manifest as manifest_module
    mode_value = str(handback.get("mode", "")).strip()
    if mode_value and mode_value not in manifest_module.MODE_INDEX:
        return {
            "accepted": False,
            "problems": [f"mode {mode_value!r} is not a declared mode; known: "
                         f"{', '.join(sorted(manifest_module.MODE_INDEX))}"],
        }

    evidence = [str(item) for item in handback.get("evidence") or []]
    artifacts = [item for item in handback.get("artifacts") or [] if isinstance(item, dict)]
    gaps = [str(item) for item in handback.get("gaps") or []]

    problems = []
    if status_value == "completed" and not evidence:
        problems.append(
            "status 'completed' with no evidence: a verbatim output line is required, because "
            "reading is not running."
        )
    if status_value == "completed" and not artifacts:
        problems.append(
            "status 'completed' with no artifacts: name the file this session produced or "
            "changed, or report 'partial'."
        )
    for artifact in artifacts:
        path = artifact.get("path")
        if not path:
            problems.append("an artifact entry has no path")
            continue
        resolved = Path(path)
        if not resolved.is_absolute():
            resolved = Path(space.root) / path
        if not resolved.exists():
            problems.append(f"artifact not found on disk: {path}")

    if problems:
        return {"accepted": False, "problems": problems}

    state = _load(_state_path(space))
    state.setdefault("history", []).append({
        "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "mode": handback.get("mode"),
        "status": status_value,
        "artifacts": [artifact.get("path") for artifact in artifacts],
        "evidence": evidence[:20],
        "gaps": gaps[:20],
        "next": [str(item) for item in handback.get("next") or []],
    })
    _save(_state_path(space), state)
    write_state(space, Path(space.root) / ".dossier")

    return {
        "accepted": True,
        "recorded": state["history"][-1],
        "next": next_unit(root, space if status_value != "completed" else None),
        "sessions": len(state["history"]),
    }


def reset(root: Path | str) -> dict:
    """Clear loop history. Destructive, so it says exactly what it cleared."""
    space = resolve(root)
    path = _state_path(space)
    state = _load(path)
    count = len(state.get("history", []))
    _save(path, {"schema_version": manifest.SCHEMA_VERSION, "history": []})
    return {"cleared": count, "path": str(path)}
