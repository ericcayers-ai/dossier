import pytest

from dossier.safety import Conflict, PathEscape, atomic_write, matches, resolve_in_root, stamp, trash


def test_escape(tmp_path):
    with pytest.raises(PathEscape):
        resolve_in_root(tmp_path, '../x')
    with pytest.raises(PathEscape):
        resolve_in_root(tmp_path, 'C:/x')


def test_atomic_conflict(tmp_path):
    path = tmp_path / 'a.txt'
    path.write_bytes(b'a')
    before = stamp(path)
    path.write_bytes(b'b')
    with pytest.raises(Conflict):
        atomic_write(path, b'c', before)
    assert not (tmp_path / 'a.txt.tmp').exists()


def test_trash(config):
    path = config.root / 'a.txt'
    path.write_text('old')
    kept = trash(config, path)
    assert kept.read_text() == 'old'


def test_no_tracked_file_carries_personal_contact_details():
    """The repo must never hold the owner's contact details or a workspace's employer names.

    `docs/PROJECT.md` calls the folder the source of truth and the repo the code; a receipt
    generated from a real workspace is one `git add -A` away from publishing somebody's job
    search. The invariant is asserted over the tracked file list, not over one path, so a new
    receipt cannot slip past it.

    The GitHub account handle is deliberately *not* in this list: since 2026-11-09 the repository
    is published under that account, so `github.com/<account>/dossier` links in CONTRIBUTING.md
    and the issue templates are the published identity, not a leak. The owner's personal name, a
    real mailbox, a phone number and a LinkedIn profile remain forbidden, which is what this
    test is for.
    """
    import subprocess
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    if not (root / ".git").exists():
        pytest.skip("not a git checkout")
    try:
        listed = subprocess.run(["git", "ls-files", "-z"], cwd=root, capture_output=True,
                                check=True, timeout=60).stdout
    except (OSError, subprocess.SubprocessError):
        pytest.skip("git is unavailable")

    # Assembled from parts so this file does not itself contain the strings it forbids.
    needles = [part.encode() for part in (
        "@gmail" + ".com", "linkedin.com" + "/in/", "+" + "64 ", "+" + "64-",
        "eric " + "ayers")]
    offenders = []
    for raw in listed.split(b"\0"):
        if not raw:
            continue
        path = root / raw.decode("utf-8", "replace")
        if not path.is_file() or path.stat().st_size > 2_000_000:
            continue
        blob = path.read_bytes().lower()
        for needle in needles:
            if needle in blob:
                offenders.append(f"{path.relative_to(root)}: {needle.decode()}")
    assert not offenders, offenders


def test_a_locked_destination_is_retried_instead_of_failing_the_write(tmp_path, monkeypatch):
    """WinError 32 for a few milliseconds is a scanner, not a reason to 500."""
    import os as _os
    from dossier import safety

    path = tmp_path / "IDENTITY.md"
    real = _os.replace
    calls = {"n": 0}

    def flaky(src, dst):
        calls["n"] += 1
        if calls["n"] <= 2:
            raise PermissionError(13, "The process cannot access the file", str(dst), 32)
        return real(src, dst)

    monkeypatch.setattr(safety.os, "replace", flaky)
    stamp_out = atomic_write(path, b"first draft")
    assert path.read_bytes() == b"first draft"
    assert stamp_out == stamp(path)
    assert calls["n"] == 3


def test_a_destination_that_never_unlocks_still_raises_and_leaves_no_temp_file(tmp_path, monkeypatch):
    import os as _os
    from dossier import safety

    path = tmp_path / "IDENTITY.md"
    path.write_bytes(b"old")

    def always_locked(src, dst):
        raise PermissionError(13, "still locked", str(dst), 32)

    monkeypatch.setattr(safety.os, "replace", always_locked)
    with pytest.raises(PermissionError):
        atomic_write(path, b"new")
    assert path.read_bytes() == b"old"
    assert [p.name for p in tmp_path.iterdir()] == ["IDENTITY.md"], "the temp file must not survive"


def test_two_writers_on_one_path_never_share_a_temp_file(tmp_path):
    """A fixed `path + '.tmp'` let concurrent writers clobber each other.

    Losing the compare-and-swap is a legitimate `Conflict` — that is the write
    contract. What must never happen is an `OSError` from a shared temp file, a
    torn destination, or a leftover `.tmp` in the workspace.
    """
    import threading

    path = tmp_path / "IDENTITY.md"
    payloads = {i: f"write {i}\n".encode() * 200 for i in range(8)}
    failures, conflicts = [], []

    def writer(i):
        for _ in range(10):
            try:
                atomic_write(path, payloads[i])
            except Conflict:
                conflicts.append(i)
            except Exception as exc:  # noqa: BLE001 - anything else is a defect
                failures.append(f"writer {i}: {type(exc).__name__}: {exc}")

    threads = [threading.Thread(target=writer, args=(i,)) for i in payloads]
    for t in threads: t.start()
    for t in threads: t.join()

    assert not failures, failures[:3]
    assert path.read_bytes() in set(payloads.values()), "a write must never leave a torn file"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["IDENTITY.md"], "no temp file may be left behind"
    assert len(conflicts) < 80, "the lock must not starve every writer"


def test_a_stamp_rounded_by_javascript_still_matches(tmp_path):
    """`mtime_ns` is ~1.79e18, past 2**53, so a browser rounds it by ~100ns.
    Comparing it exactly turned every UI save into a false conflict."""
    from dataclasses import replace

    path = tmp_path / "note.md"
    path.write_text("hello", encoding="utf-8")
    good = stamp(path)
    assert matches(path, good)
    rounded = replace(good, mtime_ns=good.mtime_ns + 128)   # what JSON.parse does
    assert matches(path, rounded), "a rounded mtime must not block the write"
    assert not matches(path, replace(good, sha256="0" * 64)), "different content is still a conflict"
    assert not matches(path, replace(good, size=good.size + 1)), "different length is still a conflict"
    assert not matches(path, replace(good, mtime_ns=good.mtime_ns + 10_000_000)), "a real edit is a conflict"
