from dataclasses import dataclass
from pathlib import Path
from datetime import datetime, timedelta, timezone
import hashlib, json, os, re, shutil, tempfile, threading, time

from .config import AppConfig

class PathEscape(ValueError): pass
class Conflict(RuntimeError): pass
@dataclass(frozen=True)
class FileStamp:
    mtime_ns:int; sha256:str; size:int

def stamp(path:Path)->FileStamp:
    b=path.read_bytes(); s=path.stat()
    return FileStamp(s.st_mtime_ns, hashlib.sha256(b).hexdigest(), len(b))
def resolve_in_root(root:Path, rel:str)->Path:
    if rel == '':
        return root.resolve()
    if rel is None or Path(rel).is_absolute() or Path(rel).drive:
        raise PathEscape("absolute paths are not accepted")
    root=root.resolve(); p=(root / rel).resolve()
    try: p.relative_to(root)
    except ValueError: raise PathEscape("path escapes root") from None
    return p
def matches(path, expect)->bool:
    """Does the file on disk satisfy this write precondition?

    `expect is None` means *no precondition*: a caller that supplied no stamp is
    allowed to write whatever is currently there. An explicit stamp is a
    precondition in both directions — the file must still exist and must still
    carry exactly that content, so a stamp for a file that has since been
    deleted is a conflict.

    Conflating "no stamp" with "must not already exist" is what made a file
    saveable only once: the API sends no stamp when the client omits one, and
    every write after the first hit `Conflict` on a file that was there.
    """
    if expect is None: return True
    if not path.exists(): return False
    current = stamp(path)
    if current.sha256 != getattr(expect,'sha256',None): return False
    if current.size != getattr(expect,'size',None): return False
    # The content is the precondition; the mtime is only a cheap hint. A stamp that
    # travelled through the browser lost precision: `mtime_ns` is ~1.79e18, above
    # 2**53, so JSON.parse rounds it to the nearest double and the value comes back
    # 100ns off. Comparing it exactly made every save from the UI a false
    # `Conflict("file changed on disk")`.
    mtime = getattr(expect,'mtime_ns',None)
    if mtime is None: return True
    return abs(current.mtime_ns - int(mtime)) <= 1_000
def _trash_relative(config:"AppConfig", path:Path)->Path:
    """Where a backup of `path` belongs inside `.dossier/trash/`, as a RELATIVE path.

    A file inside the workspace keeps its relative layout, so restoring it is a
    copy back to the same place. Anything else — a `--out` the user aimed at
    another folder — is filed under `_external/` with its drive and folders
    preserved, because the gate is about not losing the bytes, not about where
    the user happened to put the file.

    The return value must stay relative: `trash()` joins it onto the trash
    prefix, and on Windows joining an absolute path onto a prefix discards the
    prefix, which made the backup destination the source file itself.
    """
    root = config.root.resolve()
    try:
        rel = path.relative_to(root)
    except ValueError:
        anchor = (path.drive or path.anchor or "").replace(":", "")
        # Split on both separators: on POSIX the anchor is "/", and leaving it in
        # `head` made the joined destination absolute, i.e. the source file itself —
        # which is exactly what the invariant below refuses. Found by CI on Linux.
        head = [part for part in re.split(r"[\/]+", anchor) if part]
        return Path("_external", *head, *path.parts[1:])
    # Re-resolve as a check that the relative form lands back inside the root,
    # then hand back the relative form.
    resolve_in_root(root, str(rel))
    return rel
def trash(config, path:Path)->Path:
    """Copy `path` into `.dossier/trash/<utc>/` before it is overwritten.

    Returns the backup path, or `path` itself when there was nothing to keep.
    """
    path=Path(path).resolve()
    if not path.exists(): return path
    out=config.dossier_dir/'trash'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')/_trash_relative(config,path)
    # Invariant, checked rather than assumed: a backup destination equal to the
    # source is not a backup. `shutil.copy2` does not raise for this (it reaches
    # `CopyFile2` and fails with a locked-file error), so it is asserted here.
    if out.resolve() == path:
        raise RuntimeError(f"trash destination would be the file itself: {path}")
    out.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(path,out); return out
_WRITE_LOCKS: dict = {}
_WRITE_LOCKS_GUARD = threading.Lock()

def _write_lock(path:Path):
    """One mutex per destination path, process-wide.

    On Windows any open reader of a file blocks `os.replace` over it, because
    the default share mode omits FILE_SHARE_DELETE. Two writers inside this one
    process — an API retry and a second tab, the agent and the UI — would
    therefore fail each other's renames with WinError 32 no matter how long they
    retried. Serialising the observe→write→rename sequence per path removes that
    class of failure outright; the retry below still covers another process.
    """
    key = str(path)
    with _WRITE_LOCKS_GUARD:
        return _WRITE_LOCKS.setdefault(key, threading.Lock())

def atomic_write(path:Path,data:bytes,expect:FileStamp|None=None)->FileStamp:
    path=path.resolve(); path.parent.mkdir(parents=True,exist_ok=True)
    with _write_lock(path):
        return _atomic_write_locked(path, data, expect)

def _atomic_write_locked(path:Path,data:bytes,expect:FileStamp|None)->FileStamp:
    if not matches(path,expect): raise Conflict("file changed on disk")
    # Second check, just before the rename, closes the window between the
    # caller's stamp and this write. With no precondition, "unchanged" means the
    # file still holds what it held when this call started — or still does not
    # exist, so a concurrent create is not silently clobbered.
    observed = stamp(path) if path.exists() else None
    # A unique temp name per call: a fixed `path + '.tmp'` let two writers of the
    # same target (an API retry, a second tab, the agent and the UI) share one
    # scratch file, so one could rename it out from under the other or delete the
    # other's bytes in the cleanup below. The file is created in the same
    # directory so `os.replace` stays atomic — same volume, no copy.
    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix='.'+path.name+'.', suffix='.tmp')
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd,'wb') as f: f.write(data); f.flush(); os.fsync(f.fileno())
        current = stamp(path) if path.exists() else None
        if current != observed: raise Conflict("file changed on disk")
        _replace_with_retry(tmp, path, observed)
        return stamp(path)
    finally:
        # Cleanup must never mask the error that got us here, and must never fail
        # the write: on Windows another handle can still hold the temp file for a
        # moment (a scanner, a reader), which is a reason to wait, not to raise.
        for _ in range(50):
            try:
                tmp.unlink()
                break
            except FileNotFoundError:
                break
            except PermissionError:
                time.sleep(0.01)
def _replace_with_retry(tmp:Path, path:Path, observed:FileStamp|None)->None:
    """`os.replace`, retried while Windows still holds the destination open.

    WinError 32 (sharing violation) and 5 (access denied) are transient here: a
    virus scanner, an open reader or the previous writer's handle keeps
    `IDENTITY.md` busy for a few milliseconds. Giving up on the first attempt is
    what turned a locked file into a 500 in the UI. A changed destination is not
    transient — that is a `Conflict`, re-raised immediately.
    """
    delay = 0.01
    for attempt in range(6):
        try:
            os.replace(tmp, path); return
        except (PermissionError, OSError) as exc:
            win = getattr(exc, 'winerror', None) or (exc.args[0] if isinstance(exc, OSError) and exc.args else None)
            transient = isinstance(exc, PermissionError) or win in (5, 32, 33)
            if not transient or attempt == 5:
                raise
            try:
                current = stamp(path) if path.exists() else None
            except PermissionError:
                # The destination is unreadable this instant, which says nothing
                # about whether it changed; wait it out instead of guessing.
                time.sleep(delay); delay = min(delay * 2, 0.2); continue
            if current != observed: raise Conflict("file changed on disk") from None
            time.sleep(delay); delay = min(delay * 2, 0.2)
def trash_if_present(target, path:Path)->Path|None:
    """Back up `path` when it exists, so the caller's next write is recoverable.

    For writers that cannot go through `trash_then_write` — a library that saves
    a document object rather than bytes — this is the backup half on its own.
    """
    path = Path(path)
    if not path.exists(): return None
    config = target if isinstance(target, AppConfig) else AppConfig.create(Path(target))
    config.ensure()
    return trash(config, path)
def trash_then_write(target, path:Path, data:bytes, expect:FileStamp|None=None)->FileStamp:
    """The one sanctioned overwrite path: back the old bytes up, then replace.

    `target` is an `AppConfig` or a workspace root. Every overwrite in the
    engine routes through here so `.dossier/trash/` holds the previous version
    of anything this program replaces (gate: `never-only-copy`).
    """
    config = target if isinstance(target, AppConfig) else AppConfig.create(Path(target))
    path = Path(path)
    trash_if_present(config, path)
    return atomic_write(path, data, expect)
def trash_then_write_text(target, path:Path, text:str,
                          expect:FileStamp|None=None)->FileStamp:
    return trash_then_write(target, path, text.encode("utf-8"), expect)
def trash_then_copy(target, source:Path, destination:Path)->Path:
    """Copy `source` over `destination`, keeping the replaced file in the trash."""
    destination = Path(destination)
    trash_if_present(target, destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    return destination
TRASH_STAMP = '%Y%m%dT%H%M%S%fZ'

def _trash_stamp_to_iso(name:str)->str|None:
    try:
        return datetime.strptime(name,TRASH_STAMP).replace(tzinfo=timezone.utc).isoformat()
    except (ValueError,TypeError):
        return None
def list_trash(config)->dict:
    """What is in `.dossier/trash/`, newest first, split by restorability.

    `entries` are the backups this module wrote: each sits under a timestamp
    folder and its remainder is the original workspace-relative path, which is
    what a restore needs. `external` are backups of files that lived outside the
    workspace (they have no workspace-relative path). `unmanaged` is anything
    else in the folder — `render_stale` keeps superseded PDFs in
    `trash/render-backup-<ts>/` under a flattened name, so there is no honest way
    to map one back to a path and it is reported rather than guessed at.
    """
    trash_dir = config.dossier_dir / 'trash'
    entries:list[dict] = []
    external:list[dict] = []
    unmanaged:list[dict] = []
    if not trash_dir.is_dir():
        return {"entries": entries, "external": external, "unmanaged": unmanaged}
    for path in sorted(trash_dir.rglob('*')):
        if not path.is_file():
            continue
        try:
            relative = path.relative_to(trash_dir)
            trash_rel = path.relative_to(config.root).as_posix()
        except ValueError:
            continue
        parts = relative.parts
        stat = path.stat()
        row = {
            "trash_rel": trash_rel,
            "name": path.name,
            "size": stat.st_size,
            "mtime_ns": stat.st_mtime_ns,
            "stamp": parts[0] if parts else "",
            "trashed_at": _trash_stamp_to_iso(parts[0]) if parts else None,
        }
        if len(parts) < 2 or row["trashed_at"] is None:
            unmanaged.append({**row, "rel": None})
            continue
        original = Path(*parts[1:])
        if original.parts and original.parts[0] == "_external":
            external.append({**row, "rel": None})
            continue
        entries.append({**row, "rel": original.as_posix()})
    entries.sort(key=lambda item: (item["stamp"], item["trash_rel"]), reverse=True)
    external.sort(key=lambda item: (item["stamp"], item["trash_rel"]), reverse=True)
    unmanaged.sort(key=lambda item: item["trash_rel"], reverse=True)
    return {"entries": entries, "external": external, "unmanaged": unmanaged}
def restore_from_trash(config, rel:str, trash_rel:str|None=None)->dict:
    """Put one trashed file back at its original workspace-relative path.

    Whatever currently occupies the destination is trashed first, so a restore is
    never a way to lose the file that replaced the original (gate:
    `never-only-copy`). A `trash_rel` outside `.dossier/trash/`, or one that is
    not under a timestamp folder, is refused rather than guessed at.
    """
    rel = (rel or "").strip()
    if not rel:
        raise ValueError("rel is required: it is the workspace-relative path to restore")
    destination = resolve_in_root(config.root, rel)
    trash_dir = config.dossier_dir / 'trash'
    if trash_rel:
        source = resolve_in_root(config.root, trash_rel)
        try:
            inside = trash_dir.resolve() in source.resolve().parents
        except OSError:
            inside = False
        if not inside or not source.is_file():
            raise ValueError("trash_rel must name a file inside .dossier/trash/")
        stamp = source.resolve().relative_to(trash_dir.resolve()).parts[0]
        if _trash_stamp_to_iso(stamp) is None:
            raise ValueError(
                f"{trash_rel} is not a restorable trash entry: it is not under a "
                "timestamped trash folder")
    else:
        candidates = [entry for entry in list_trash(config)["entries"] if entry["rel"] == Path(rel).as_posix()]
        if not candidates:
            raise FileNotFoundError(f"no trash copy of {rel}")
        source = resolve_in_root(config.root, candidates[0]["trash_rel"])
    trash_if_present(config, destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    return {"restored": True, "rel": Path(rel).as_posix(), "path": str(destination),
            "from": str(source)}


# -- retention: an age cap on the trash ------------------------------------
#
# A retention limit is not permission to skip the copy. `trash()` still runs
# before every overwrite and still keeps every superseded byte; pruning only
# ever deletes a backup that ALREADY existed and is already older than the
# window. The two properties cannot conflict because pruning never runs inside
# `trash()`, never inspects the write in flight, and never touches the newest
# entry -- the one a current write just created.

#: How long a superseded copy stays restorable, in days. 30 covers a full
#: month-long application cycle -- long enough that "I overwrote that last
#: week" is still recoverable -- while bounding the folder. `0` disables
#: pruning entirely, keeping every backup forever.
TRASH_RETENTION_DAYS_DEFAULT = 30
ENV_RETENTION_DAYS = "DOSSIER_TRASH_RETENTION_DAYS"
WORKSPACE_TRASH_FILE = "trash.json"
RETENTION_RECORD = "trash-retention.json"
#: A quarantined entry is renamed to this prefix before it is deleted. The
#: prefix is deliberately NOT a timestamp, so `restore_from_trash` refuses it
#: and `list_trash` reports it as unmanaged: an entry that was half-deleted can
#: never be mistaken for a restorable one.
PRUNE_QUARANTINE_PREFIX = ".pruning-"
#: How many per-entry rows the persisted prune report keeps. Enough to explain
#: a run, bounded so the record cannot become the bloat it exists to prevent.
RETENTION_RECORD_ROWS = 50


def _retention_int(value) -> int|None:
    """A whole non-negative number of days, or None when the value is junk."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value >= 0 else None
    if isinstance(value, str):
        text = value.strip()
        if text.isdigit():
            return int(text)
    return None


def _read_trash_override(config) -> dict:
    """The workspace's `.dossier/trash.json`, or {} — never raises."""
    try:
        data = json.loads(
            (config.dossier_dir / WORKSPACE_TRASH_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def retention_settings(config, override:int|None=None)->dict:
    """The effective retention window and where the number came from.

    Precedence, mirroring `dossier.model`: an explicit argument wins, then the
    workspace's `.dossier/trash.json`, then the process environment, then the
    default. Invalid values are skipped with a warning rather than coerced, so
    a typo in a config file cannot silently disable or shorten the cap.
    """
    warnings:list[str] = []
    days = TRASH_RETENTION_DAYS_DEFAULT
    source = "default"

    raw = os.environ.get(ENV_RETENTION_DAYS, "").strip()
    if raw:
        parsed = _retention_int(raw)
        if parsed is None:
            warnings.append(f"ignored invalid {ENV_RETENTION_DAYS}={raw!r}: "
                            "expected a whole number of days")
        else:
            days, source = parsed, "environment"

    value = _read_trash_override(config).get("retention_days")
    if value is not None:
        parsed = _retention_int(value)
        if parsed is None:
            warnings.append("ignored invalid 'retention_days' in "
                            f".dossier/{WORKSPACE_TRASH_FILE}: expected a whole "
                            "number of days")
        else:
            days, source = parsed, "workspace"

    if override is not None:
        parsed = _retention_int(override)
        if parsed is None:
            warnings.append(f"ignored invalid retention_days override {override!r}")
        else:
            days, source = parsed, "argument"

    return {"retention_days": days, "source": source, "enabled": days > 0,
            "warnings": warnings,
            "config_file": f".dossier/{WORKSPACE_TRASH_FILE}",
            "environment_variable": ENV_RETENTION_DAYS}


def _entry_stats(entry:Path)->tuple[int,int]:
    """(file count, byte total) for one trash entry, without following a link.

    `os.walk(followlinks=False)` is used rather than `rglob` so a symlinked
    directory inside the trash is never descended into; a link counts as
    nothing, because the bytes behind it are not ours to measure or delete.
    """
    files = 0
    total = 0
    for dirpath, dirnames, filenames in os.walk(entry, followlinks=False):
        dirnames[:] = [name for name in dirnames
                       if not os.path.islink(os.path.join(dirpath, name))]
        for name in filenames:
            full = os.path.join(dirpath, name)
            try:
                if os.path.islink(full):
                    continue
                total += os.path.getsize(full)
                files += 1
            except OSError:
                continue
    return files, total


def _purge_entry(trash_root:Path, entry:Path)->dict:
    """Delete one aged-out entry after making it unrestorable first.

    The entry is renamed to a quarantine name, then deleted. `restore_from_trash`
    only accepts a file under a TIMESTAMPED folder, so the instant the rename
    lands the entry is unreachable by a restore -- there is no window in which a
    half-deleted tree still looks like a valid backup, and a delete that fails
    partway leaves quarantine debris (which `list_trash` reports as unmanaged)
    rather than a truncated restorable entry.
    """
    files, size = _entry_stats(entry)
    quarantine = trash_root / (PRUNE_QUARANTINE_PREFIX + entry.name)
    try:
        if quarantine.exists():
            # Leftover from an interrupted earlier run. It already carries a
            # non-timestamp name, so nothing can restore from it.
            shutil.rmtree(quarantine, ignore_errors=True)
        os.replace(entry, quarantine)
    except OSError as exc:
        return {"files": files, "bytes": size, "purged": False, "quarantined": False,
                "reason": f"could not be quarantined: {exc}"}
    try:
        shutil.rmtree(quarantine)
    except OSError as exc:
        return {"files": files, "bytes": size, "purged": False, "quarantined": True,
                "reason": "quarantined and no longer restorable, but not yet "
                          f"deleted: {exc}"}
    return {"files": files, "bytes": size, "purged": True, "quarantined": True,
            "reason": "removed"}


def prune_trash(config, *, now=None, retention_days:int|None=None, protect=None,
                apply:bool=True)->dict:
    """Delete trash entries older than the retention window. Reports every decision.

    Safety rules, each enforced here rather than assumed by a caller:

    * The **newest** entry is never pruned. A write in flight creates the newest
      entry, so the backup that write just made can never be its own victim. This
      guard deliberately does not consult the clock, so it holds even if the
      system clock is wrong. Its cost is bounded and stated: at most ONE entry
      can outlive the window, and only while the trash holds nothing newer.
    * `protect` names a trash path that must survive (the entry a caller's write
      just created); it is kept even if an injected clock would expire it.
    * Only a top-level, **timestamp-named directory** is a candidate. A file, a
      symlink, an `_external`-only stray or anything else is reported as skipped,
      never guessed at.
    * An entry whose directory resolves outside the trash root is skipped, and a
      symlink is never followed: `_purge_entry` moves the link itself.
    * An entry **written to inside the window** is treated as possibly partial and
      kept -- a copy still landing has a fresh mtime even under an old stamp.
    * Age is measured from the timestamp folder name, which is the authoritative
      "trashed at" instant. The boundary is inclusive: an entry exactly
      `retention_days` old survives, and `age > retention_days` is what expires.

    Returns the report; `apply=False` is a dry run that deletes nothing.
    """
    settings = retention_settings(config, retention_days)
    moment = now or datetime.now(timezone.utc)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)

    report = {
        "retention_days": settings["retention_days"],
        "retention_source": settings["source"],
        "retention_config_file": settings["config_file"],
        "retention_environment_variable": settings["environment_variable"],
        "enabled": settings["enabled"],
        "dry_run": not apply,
        "now": moment.isoformat(),
        "cutoff": None,
        "removed": [], "kept": [], "skipped": [],
        "quarantined": [],
        "removed_count": 0, "kept_count": 0, "skipped_count": 0, "purged_count": 0,
        "entries_remaining": 0,
        "freed_bytes": 0,
        "warnings": list(settings["warnings"]),
        "reason": "",
    }
    if not settings["enabled"]:
        report["reason"] = ("retention is 0 days: pruning is disabled and every "
                            "backup is kept")
        return report

    trash_dir = config.dossier_dir / 'trash'
    if not trash_dir.is_dir():
        report["reason"] = "there is no trash folder yet, so there is nothing to prune"
        return report
    try:
        trash_root = trash_dir.resolve()
    except OSError as exc:
        report["reason"] = f"the trash folder could not be resolved: {exc}"
        return report

    cutoff = moment - timedelta(days=settings["retention_days"])
    report["cutoff"] = cutoff.isoformat()

    protected:set[Path] = set()
    if protect:
        items = [protect] if isinstance(protect, (str, Path)) else list(protect)
        for item in items:
            try:
                protected.add(Path(item).resolve())
            except OSError:
                continue

    try:
        children = sorted(trash_dir.iterdir(), key=lambda item: item.name)
    except OSError as exc:
        report["reason"] = f"the trash folder could not be listed: {exc}"
        return report

    candidates:list[Path] = []
    for child in children:
        if child.name.startswith(PRUNE_QUARANTINE_PREFIX):
            report["quarantined"].append(child.name)
            continue
        candidates.append(child)

    stamped = [item for item in candidates
               if _trash_stamp_to_iso(item.name) is not None]
    newest = stamped[-1].name if stamped else None

    for entry in candidates:
        row = {"entry": entry.name}
        if entry.is_symlink():
            report["skipped"].append({**row, "reason":
                "it is a symlink; a link is never followed out of the trash, so "
                "pruning leaves it alone"})
            continue
        if not entry.is_dir():
            report["skipped"].append({**row, "reason":
                "not a timestamped trash entry (it is a file, not a backup folder)"})
            continue
        stamp = _trash_stamp_to_iso(entry.name)
        if stamp is None:
            report["skipped"].append({**row, "reason":
                "not a timestamped trash entry; restore refuses these, so pruning "
                "does not guess at them"})
            continue
        try:
            resolved = entry.resolve()
        except OSError:
            report["skipped"].append({**row, "reason": "the entry could not be resolved"})
            continue
        if trash_root not in resolved.parents:
            report["skipped"].append({**row, "reason":
                "it resolves outside the trash folder"})
            continue
        if entry.name == newest:
            report["kept"].append({**row, "reason":
                "the newest entry: a write in flight must never lose its own backup"})
            continue
        if resolved in protected:
            report["kept"].append({**row, "reason":
                "protected: this is the entry the caller's write just created"})
            continue

        trashed_at = datetime.strptime(entry.name, TRASH_STAMP).replace(tzinfo=timezone.utc)
        age_days = (moment - trashed_at).total_seconds() / 86400.0
        row = {**row, "trashed_at": stamp, "age_days": round(age_days, 3)}
        if age_days <= settings["retention_days"]:
            report["kept"].append({**row, "reason":
                f"within the {settings['retention_days']}-day retention window"})
            continue
        try:
            activity = datetime.fromtimestamp(entry.stat().st_mtime, tz=timezone.utc)
        except OSError:
            report["skipped"].append({**row, "reason": "the entry could not be stat'ed"})
            continue
        if moment - activity <= timedelta(days=settings["retention_days"]):
            report["kept"].append({**row, "reason":
                "written to inside the retention window, so it may be a partial "
                "entry; not yet prunable"})
            continue

        if not apply:
            files, size = _entry_stats(entry)
            report["removed"].append({**row, "files": files, "bytes": size,
                                      "reason": "older than the retention window "
                                                "(dry run: nothing was deleted)"})
            continue
        outcome = _purge_entry(trash_root, entry)
        report["removed"].append({**row, **outcome})
        if not outcome["purged"]:
            report["warnings"].append(
                f"{entry.name} was not fully deleted: {outcome['reason']}")

    report["removed_count"] = len(report["removed"])
    report["kept_count"] = len(report["kept"])
    report["skipped_count"] = len(report["skipped"])
    report["freed_bytes"] = sum(row.get("bytes", 0) for row in report["removed"])
    report["purged_count"] = sum(1 for row in report["removed"] if row.get("purged"))
    report["entries_remaining"] = len(stamped) - report["purged_count"]

    if apply and report["purged_count"]:
        _record_prune(config, report)
    return report


def _record_prune(config, report:dict)->None:
    """Persist the last prune so a server-start prune is still visible later.

    Written through `trash_then_write`, so even this bookkeeping obeys
    `never-only-copy`. It cannot feed the pruner: the record's own backup is the
    newest entry, the newest entry is never pruned, and a run that deleted
    nothing writes nothing -- so repeated no-op prunes cost zero entries.
    """
    def keep(rows):
        return rows[:RETENTION_RECORD_ROWS]
    record = {
        "pruned_at": report["now"],
        "retention_days": report["retention_days"],
        "retention_source": report["retention_source"],
        "cutoff": report["cutoff"],
        "removed_count": report["removed_count"],
        "kept_count": report["kept_count"],
        "skipped_count": report["skipped_count"],
        "freed_bytes": report["freed_bytes"],
        "removed": keep(report["removed"]),
        "kept": keep(report["kept"]),
        "skipped": keep(report["skipped"]),
    }
    try:
        trash_then_write(config, config.dossier_dir / RETENTION_RECORD,
                         json.dumps(record, indent=2, ensure_ascii=False).encode("utf-8"))
    except (OSError, Conflict, RuntimeError):
        # Observability is best-effort. A prune that already deleted exactly the
        # right entries must not report failure because its own log could not land.
        pass


def last_prune_report(config)->dict|None:
    """The last recorded prune report, or None when pruning has never run."""
    try:
        data = json.loads(
            (config.dossier_dir / RETENTION_RECORD).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None

