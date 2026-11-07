"""Emit the agent contract as vendor prompt packs.

Every harness reads the same contract, rendered in the shape that harness
expects. The files are generated from `manifest` and `brief`, so a change to
the contract reaches Claude Code, Codex, Cursor, Gemini and Hermes at once and
no two surfaces can disagree.

Writes are managed blocks: everything outside the Dossier markers is preserved,
which is what lets these generators run over files this project did not create.
"""

from __future__ import annotations

from pathlib import Path

from . import manifest

START = "<!-- dossier:contract:start -->"
END = "<!-- dossier:contract:end -->"


def _root_of(root: Path | str) -> Path:
    return Path(root).resolve()


def _core(root: Path) -> str:
    """The vendor-neutral body every pack shares.

    Deliberately derived from the contract alone plus the workspace path. A
    committed prompt file must not embed live state: a file count written into
    a managed block is wrong the moment the next file is saved, and the block
    can then never verify as current. Live facts are fetched by running a
    command, not frozen into the file.
    """
    lines: list[str] = []
    lines.append("## Dossier — injected agent contract")
    lines.append("")
    lines.append(
        "This repository is a Dossier workspace: the mechanical job-search work is "
        "deterministic code in `src/dossier/`, and the judgement work belongs to whichever "
        "language model is injected here."
    )
    lines.append("")
    lines.append("### Ask the engine, do not re-derive it")
    lines.append("")
    lines.append("```text")
    lines.append("dossier agent status                              # workspace state + open blockers")
    lines.append("dossier agent next                                # the next unit of work")
    lines.append("dossier agent route \"<what the user asked>\"        # which mode is this")
    lines.append("dossier agent brief --mode <mode> --markdown      # the task packet to execute")
    lines.append("dossier agent prompt                              # this contract for a live model")
    lines.append("dossier agent commit --handback <file>            # absorb your result")
    lines.append("dossier audit                                     # what is stale or missing")
    lines.append("dossier doctor                                    # what this machine can actually do")
    lines.append("dossier agent adapters                            # regenerate these packs")
    lines.append("dossier agent manifest                            # the whole contract as JSON")
    lines.append("```")
    lines.append("")
    lines.append("Every command takes `--root <folder>`; pass `--json` for machine-readable output. "
                 "The gate commands (`verify`, `corpus build`, `track outcome`, `sanitize`) exit "
                 "non-zero on failure, so assert on the exit code rather than reading prose.")
    lines.append("")
    lines.append("### Modes the engine completes without you")
    lines.append("")
    for item in manifest.engine_modes():
        lines.append(f"- `{item.id}` — {item.summary}")
    lines.append("")
    lines.append("### Modes that need your judgement")
    lines.append("")
    for item in manifest.agent_modes():
        lines.append(f"- `{item.id}` ({item.kind}) — {item.summary}")
    lines.append("")
    lines.append("### Gates — enforced in code, never softened")
    lines.append("")
    for gate in manifest.GATES:
        lines.append(f"- **`{gate.id}`** — {gate.rule}")
        lines.append(f"  - enforced by: `{gate.enforced_by}`")
        lines.append(f"  - never: {gate.never}")
    lines.append("")
    lines.append("### Pipeline")
    lines.append("")
    lines.append(" → ".join(f"{stage.id}" for stage in manifest.STAGES))
    lines.append("")
    lines.append(
        "Run `dossier agent brief --mode <mode> --markdown` for the mode you were asked to "
        "perform and follow the packet. It carries the objective, the resolved inputs with real "
        "paths, the exact commands, the decisions you own, the gates, the output paths, the "
        "verification commands and the JSON handback shape."
    )
    lines.append("")
    lines.append("### Where the workspace lives")
    lines.append("")
    lines.append(
        f"This folder is the `{root.name}` workspace root. Nothing here writes to a source file "
        "without a keystroke; every overwrite routes through `.dossier/trash/` first."
    )
    return "\n".join(lines)


def _with_header(text: str, header: str) -> str:
    """Put the pack's prescribed header at the top of the file, once.

    The header is part of the generated contract, not one-time decoration. It was
    only written when a pack *created* a file, so a pack file that already existed
    kept no H1 at all — and AGENTS.md and GEMINI.md, which prescribe different
    titles, came out byte-identical.
    """
    if not header or text.startswith(header):
        return text
    return header + text.lstrip("\n")


def upsert_block(path: Path, body: str, header: str = "", root: Path | str | None = None) -> str:
    """Write `body` between managed markers, preserving everything outside them.

    Returns "created", "appended" or "replaced" so a caller can report honestly
    what changed rather than assuming. `root` is the workspace the replaced
    version belongs to; `write_all` passes it, and it defaults to the file's own
    folder for a direct call.
    """
    from ..safety import trash_then_write_text

    path.parent.mkdir(parents=True, exist_ok=True)
    trash_root = Path(root) if root is not None else path.parent
    managed = f"{START}\n{body}\n{END}\n"
    if not path.exists():
        path.write_text(header + managed, encoding="utf-8")
        return "created"

    existing = path.read_text(encoding="utf-8", errors="replace")
    if START in existing and END in existing:
        head, _, rest = existing.partition(START)
        _, _, tail = rest.partition(END)
        updated, state = head + managed.rstrip("\n") + tail, "replaced"
    else:
        separator = "" if existing.endswith("\n\n") else ("\n" if existing.endswith("\n") else "\n\n")
        updated, state = existing + separator + managed, "appended"

    updated = _with_header(updated, header)
    if updated != existing:
        trash_then_write_text(trash_root, path, updated)
    return state


def _cursor_frontmatter() -> str:
    return (
        "---\n"
        "description: Dossier job-search engine contract\n"
        "globs: **\n"
        "alwaysApply: true\n"
        "---\n\n"
    )


def _pipeline_doc() -> str:
    """The pipeline rendered from the contract, so it cannot drift from it."""
    lines = ["## Pipeline", "",
             "The canonical order. Each mode names its own next step, so a session never has "
             "to guess what follows what.", "",
             "| # | Stage | Intent | Modes |", "|---|---|---|---|"]
    for index, stage in enumerate(manifest.STAGES, 1):
        owned = ", ".join(f"`{item.id}`" for item in manifest.MODES if item.stage == stage.id)
        lines.append(f"| {index} | {stage.label} | {stage.intent} | {owned or '—'} |")
    lines += ["", "## Modes", "",
              "`<placeholder>` marks a value to supply from the workspace or the user.",
              "",
              "| Mode | Kind | Stage | What it does | Command |", "|---|---|---|---|---|"]
    for item in manifest.MODES:
        command = f"`{item.command}`" if item.command else "— (judgement only)"
        lines.append(f"| `{item.id}` | {item.kind} | `{item.stage}` | {item.summary} | {command} |")
    lines += ["", "## Artifacts", "",
              "The files this contract is built from. The folder is the source of truth; "
              "`.dossier/` is derived and disposable.", "",
              "| Artifact | Path | Role | Producer | Consumers | Required |", "|---|---|---|---|---|---|"]
    for artifact in manifest.ARTIFACTS:
        consumers = ", ".join(f"`{name}`" for name in artifact.consumers[:6]) or "—"
        lines.append(
            f"| {artifact.name} | `{artifact.glob}` | {artifact.role} | {artifact.producer} | "
            f"{consumers} | {'yes' if artifact.required else 'no'} |")
    return "\n".join(lines)


def _contract_doc() -> str:
    """Modes and gates as a reference table."""
    lines = ["## Modes", "", "| Mode | Kind | Reads | Writes | Gates | Next | Command |",
             "|---|---|---|---|---|---|---|"]
    for item in manifest.MODES:
        reads = ", ".join(f"`{name}`" for name in item.reads)
        writes = ", ".join(f"`{name}`" for name in item.writes if isinstance(name, str)) or "—"
        gates = ", ".join(f"`{name}`" for name in item.gates) or "—"
        nexts = ", ".join(f"`{name}`" for name in item.next) or "—"
        command = f"`{item.command}`" if item.command else "—"
        lines.append(f"| `{item.id}` | {item.kind} | {reads} | {writes} | {gates} | {nexts} | {command} |")
    lines += ["", "## Gates", "", "| Gate | Rule | Enforced by | Never |", "|---|---|---|---|"]
    for gate in manifest.GATES:
        lines.append(f"| `{gate.id}` | {gate.rule} | `{gate.enforced_by}` | {gate.never} |")
    return "\n".join(lines)


def packs(root: Path | str) -> dict[str, dict]:
    """Every vendor pack as {relative path: {"body": ..., "header": ...}}."""
    path = _root_of(root)
    full = _core(path)

    packs_map: dict[str, dict] = {
        "AGENTS.md": {
            "body": full,
            "header": (
                "# Agent instructions\n\n"
                "This file is read by Codex, Cursor, OpenCode and other harnesses.\n\n"
            ),
        },
        "CLAUDE.md": {
            "body": full,
            "header": "# Claude Code instructions\n\n",
        },
        "GEMINI.md": {
            "body": full,
            "header": "# Gemini instructions\n\n",
        },
        ".cursor/rules/dossier.mdc": {
            "body": full,
            "header": _cursor_frontmatter(),
        },
        ".claude/skills/dossier/SKILL.md": {
            "body": full,
            "header": (
                "---\n"
                "name: dossier\n"
                "description: \"Use inside a Dossier job-search workspace: brief, modes, gates.\"\n"
                "---\n\n"
            ),
        },
        "docs/PIPELINE.md": {
            "body": _pipeline_doc(),
            "header": (
                "# Pipeline\n\n"
                "Generated from the contract in `src/dossier/agent/manifest.py`. "
                "Do not edit by hand; run `dossier agent adapters`.\n\n"
            ),
        },
        "docs/CONTRACT.md": {
            "body": _contract_doc(),
            "header": (
                "# Contract\n\n"
                "Modes and gates, generated from `src/dossier/agent/manifest.py`. "
                "Do not edit by hand; run `dossier agent adapters`.\n\n"
            ),
        },
    }

    # The vendor list is derived from this mapping rather than hand-kept: the
    # literal list here named four packs while `packs()` emitted eight, so it
    # silently omitted the Claude skill pack, the Cursor rule and both docs.
    vendor_list = "\n".join(
        f"- `{name}` — managed block, regenerated from the manifest"
        for name in sorted(packs_map)
    )
    packs_map["docs/agent/INJECT.md"] = {
        "body": (
            "# Injecting any model into Dossier\n\n"
            "Dossier is a job-search engine with a language-model socket. The engine owns "
            "everything mechanical and deterministic; a model plugs in for the judgement "
            "work. Any model works — the socket is a markdown packet and a JSON handback, "
            "not an SDK.\n\n"
            "## The socket\n\n"
            "1. `dossier agent next --root <folder>` tells you the next unit of work, or\n"
            "   `dossier agent route --root <folder> \"<what the user asked>\"` picks a mode.\n"
            "2. `dossier agent brief --root <folder> --mode <id>` renders the task packet.\n"
            "   Paste it as the model's system or first user message. It is self-contained.\n"
            "3. The model runs the deterministic commands, does the reasoning, writes the "
            "listed artifacts, runs the verification commands, and returns the JSON handback.\n"
            "4. `dossier agent commit --root <folder> --handback <file>` absorbs the result "
            "and advances the loop.\n\n"
            "## Why this shape\n\n"
            "- The full resume-tailoring reference is too long to use as a task packet. "
            "A brief with real paths and real commands is easier to execute.\n"
            "- The engine holds the state, so the model does not need memory across sessions.\n"
            "- Gates live in code, so a model that drifts is caught by a failing command "
            "rather than by good intentions.\n\n"
            "## Vendor packs\n\n"
        ) + vendor_list + "\n\n" + full,
        "header": "",
    }
    return packs_map


def write_all(root: Path | str) -> dict[str, str]:
    """Generate every pack. Returns {relative path: created|appended|replaced}."""
    path = _root_of(root)
    results: dict[str, str] = {}
    for rel, content in packs(path).items():
        results[rel] = upsert_block(path / rel, content["body"], content.get("header", ""),
                                    root=path)
    return results


def verify_block(root: Path | str, rel: str) -> bool:
    """True when the file carries a current managed block *and* its header.

    The header is checked too: it is part of what the generator prescribes (the
    Claude skill and the Cursor rule are identified by it, and every other pack
    opens with a distinct H1), so `--check` must be able to detect a wrong or
    missing one instead of passing on the body alone.
    """
    path = _root_of(root) / rel
    if not path.exists():
        return False
    text = path.read_text(encoding="utf-8", errors="replace")
    if START not in text or END not in text:
        return False
    pack = packs(root)[rel]
    if pack["body"] not in text:
        return False
    header = pack.get("header", "")
    return not header or text.startswith(header)
