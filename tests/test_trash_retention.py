"""The age cap on `.dossier/trash/`.

The trash is a *safety* property (`never-only-copy`) and a retention limit must
not weaken it, so these tests pin both halves at once:

* the cap actually expires an entry, at a real boundary rather than a cutoff set
  to "now";
* the copy that `never-only-copy` requires still happens after a prune;
* nothing outside the trash is reachable, a link is never followed, and an entry
  that was half-deleted can never be restored or listed as restorable.

Age is injected through `prune_trash(now=...)` so the boundary case is exact:
with a 30-day window, an entry exactly 30 days old survives and one a single
second older does not.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from dossier import cli
from dossier.api.app import create_app
from dossier.safety import (PRUNE_QUARANTINE_PREFIX, RETENTION_RECORD,
                            TRASH_RETENTION_DAYS_DEFAULT, TRASH_STAMP, last_prune_report,
                            list_trash, prune_trash, restore_from_trash,
                            retention_settings, trash_then_write_text)

NOW = datetime(2026, 10, 11, 12, 0, 0, tzinfo=timezone.utc)
WINDOW = 30


@pytest.fixture(autouse=True)
def _clean_retention_env(monkeypatch):
    """The suite must not inherit a cap from the machine it runs on."""
    monkeypatch.delenv("DOSSIER_TRASH_RETENTION_DAYS", raising=False)


def _name(when: datetime) -> str:
    return when.strftime(TRASH_STAMP)


def _age_tree(root: Path, when: datetime) -> None:
    """Give `root` and everything under it the same mtime, so age is unambiguous."""
    stamp = when.timestamp()
    for path in sorted(root.rglob("*"), reverse=True):
        os.utime(path, (stamp, stamp))
    os.utime(root, (stamp, stamp))


def _entry(config, when: datetime, rel: str = "notes.md", content: bytes = b"old") -> Path:
    """A trash entry exactly as `trash()` lays one out, stamped `when`."""
    entry = config.dossier_dir / "trash" / _name(when)
    path = entry / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    _age_tree(entry, when)
    return entry


def _reasons(report: dict, group: str) -> dict:
    return {row["entry"]: row["reason"] for row in report[group]}


# -- the boundary, drawn from a real clock rather than "cutoff = now" --------

def test_the_age_boundary_is_inclusive_and_one_second_older_expires(config):
    """30 days survives exactly; 30 days and one second does not."""
    config.ensure()
    exact = _entry(config, NOW - timedelta(days=WINDOW))
    too_old = _entry(config, NOW - timedelta(days=WINDOW, seconds=1), rel="old.md")
    inside = _entry(config, NOW - timedelta(days=WINDOW - 1), rel="inside.md")
    newest = _entry(config, NOW - timedelta(hours=1), rel="newest.md")

    report = prune_trash(config, now=NOW, retention_days=WINDOW)

    assert [row["entry"] for row in report["removed"]] == [_name(NOW - timedelta(days=WINDOW, seconds=1))]
    assert report["removed_count"] == 1
    assert report["purged_count"] == 1
    assert report["cutoff"] == (NOW - timedelta(days=WINDOW)).isoformat()
    assert report["retention_days"] == WINDOW

    # The boundary entry is the load-bearing one: its measured age is exactly the
    # window, and it is still here afterwards.
    ages = {row["entry"]: row["age_days"] for row in report["kept"]
            if "age_days" in row}
    assert ages[_name(NOW - timedelta(days=WINDOW))] == 30.0
    assert "30-day retention window" in _reasons(report, "kept")[_name(NOW - timedelta(days=WINDOW))]

    assert exact.is_dir() and (exact / "notes.md").read_bytes() == b"old"
    assert inside.is_dir() and newest.is_dir()
    assert not too_old.exists(), "an entry past the window must actually be gone"


def test_the_default_window_is_the_number_the_module_declares(config):
    config.ensure()
    assert TRASH_RETENTION_DAYS_DEFAULT == 30
    settings = retention_settings(config)
    assert settings["retention_days"] == 30
    assert settings["source"] == "default"
    assert settings["enabled"] is True
    assert settings["warnings"] == []


# -- nothing the cap must not touch ------------------------------------------

def test_the_newest_entry_is_never_pruned_even_when_ancient(config):
    """A write in flight owns the newest entry, so it can never be its own victim."""
    config.ensure()
    ancient = _entry(config, NOW - timedelta(days=400))

    report = prune_trash(config, now=NOW, retention_days=WINDOW)

    assert report["removed_count"] == 0
    assert report["kept_count"] == 1
    assert "newest entry" in report["kept"][0]["reason"]
    assert ancient.is_dir()


def test_a_lone_aged_entry_survives_because_it_is_the_newest(config):
    """The deliberate, bounded cost of a clock-independent in-flight guard.

    The newest entry is kept whatever the clock says, because that is where a
    concurrent write lands and because that guarantee must not depend on the
    system clock being sane. So at most ONE entry can outlive the window, and
    only while the trash holds nothing newer.
    """
    config.ensure()
    lone = _entry(config, NOW - timedelta(days=400))

    report = prune_trash(config, now=NOW, retention_days=WINDOW)

    assert report["removed_count"] == 0
    assert "newest entry" in report["kept"][0]["reason"]
    assert lone.is_dir()


def test_an_entry_written_to_inside_the_window_is_treated_as_partial(config):
    """An old stamp with a fresh mtime is a copy still landing: not prunable yet."""
    config.ensure()
    stale = _entry(config, NOW - timedelta(days=90))
    # Something is still writing into it: the folder's mtime is now.
    os.utime(stale, None)
    fresh = _entry(config, NOW - timedelta(hours=1), rel="newer.md")

    report = prune_trash(config, now=NOW, retention_days=WINDOW)

    assert report["removed_count"] == 0
    assert "partial" in _reasons(report, "kept")[_name(NOW - timedelta(days=90))]
    assert stale.is_dir() and fresh.is_dir()


def test_the_entry_a_caller_protects_survives_an_otherwise_expiring_clock(config):
    config.ensure()
    in_flight = _entry(config, NOW - timedelta(days=90))
    _entry(config, NOW - timedelta(hours=1), rel="newer.md")

    report = prune_trash(config, now=NOW, retention_days=WINDOW, protect=in_flight)

    assert report["removed_count"] == 0
    assert "protected" in _reasons(report, "kept")[_name(NOW - timedelta(days=90))]
    assert in_flight.is_dir()


def test_a_symlinked_entry_is_skipped_and_the_bytes_behind_it_survive(config):
    """A link is never followed out of the trash."""
    config.ensure()
    outside = config.root.parent / "not-ours"
    outside.mkdir(exist_ok=True)
    (outside / "keep.txt").write_bytes(b"keep me")
    trash_root = config.dossier_dir / "trash"
    trash_root.mkdir(parents=True, exist_ok=True)
    link = trash_root / _name(NOW - timedelta(days=400))
    os.symlink(outside, link, target_is_directory=True)

    report = prune_trash(config, now=NOW, retention_days=WINDOW)

    assert report["removed_count"] == 0
    assert "symlink" in report["skipped"][0]["reason"]
    assert (outside / "keep.txt").read_bytes() == b"keep me"
    assert link.is_symlink()


def test_a_non_timestamped_entry_is_reported_rather_than_guessed_at(config):
    config.ensure()
    stray = config.dossier_dir / "trash" / "render-backup-20260101" / "Tailored__resume.pdf"
    stray.parent.mkdir(parents=True, exist_ok=True)
    stray.write_bytes(b"%PDF-1.4\n")
    _age_tree(stray.parent, NOW - timedelta(days=400))

    report = prune_trash(config, now=NOW, retention_days=WINDOW)

    assert report["removed_count"] == 0
    assert report["skipped_count"] == 1
    assert "not a timestamped trash entry" in report["skipped"][0]["reason"]
    assert stray.is_file()


def test_pruning_cannot_reach_a_file_that_merely_sits_beside_the_trash(config):
    config.ensure()
    (config.root / "resume.md").write_bytes(b"the user's resume")
    (config.dossier_dir / "tree.json").write_bytes(b"{}")
    _entry(config, NOW - timedelta(days=400))

    prune_trash(config, now=NOW, retention_days=WINDOW)

    assert (config.root / "resume.md").read_bytes() == b"the user's resume"
    assert (config.dossier_dir / "tree.json").read_bytes() == b"{}"


# -- a half-deleted entry is never restorable --------------------------------

def test_an_entry_that_could_not_be_deleted_is_quarantined_out_of_restore(config, monkeypatch):
    """The rename lands before the delete, so a wedged delete is never a valid backup."""
    config.ensure()
    doomed = _entry(config, NOW - timedelta(days=90), content=b"superseded bytes")
    _entry(config, NOW - timedelta(hours=1), rel="newer.md")
    rel = ".dossier/trash/" + _name(NOW - timedelta(days=90)) + "/notes.md"

    def refuse(*args, **kwargs):
        raise OSError("the file is in use")

    monkeypatch.setattr("dossier.safety.shutil.rmtree", refuse)
    report = prune_trash(config, now=NOW, retention_days=WINDOW)
    monkeypatch.undo()

    assert report["removed_count"] == 1
    assert report["purged_count"] == 0
    assert report["warnings"], "a delete that failed must be reported, not swallowed"
    assert not doomed.exists()

    quarantine = config.dossier_dir / "trash" / (PRUNE_QUARANTINE_PREFIX + _name(NOW - timedelta(days=90)))
    assert quarantine.is_dir()
    assert (quarantine / "notes.md").read_bytes() == b"superseded bytes"

    # Unrestorable by path...
    with pytest.raises(ValueError):
        restore_from_trash(config, "notes.md", rel)
    # ...including by the path the bytes actually sit at now: the file is there,
    # and it is still refused, because its folder is not a timestamped entry.
    quarantine_rel = f".dossier/trash/{quarantine.name}/notes.md"
    assert (config.root / quarantine_rel).is_file()
    with pytest.raises(ValueError):
        restore_from_trash(config, "notes.md", quarantine_rel)
    # ...and not offered as a restorable entry either.
    listing = list_trash(config)
    assert [row["rel"] for row in listing["entries"]] == ["newer.md"]
    assert [row["name"] for row in listing["unmanaged"]] == ["notes.md"]


# -- observability ------------------------------------------------------------

def test_the_report_counts_what_went_and_says_why(config):
    config.ensure()
    _entry(config, NOW - timedelta(days=90), content=b"x" * 10)
    _entry(config, NOW - timedelta(days=80), rel="b.md", content=b"y" * 5)
    _entry(config, NOW - timedelta(hours=1), rel="c.md")

    report = prune_trash(config, now=NOW, retention_days=WINDOW)

    assert (report["removed_count"], report["purged_count"], report["kept_count"]) == (2, 2, 1)
    assert report["skipped_count"] == 0
    assert report["freed_bytes"] == 15
    assert report["entries_remaining"] == 1
    assert {row["files"] for row in report["removed"]} == {1}
    assert all(row["age_days"] > WINDOW for row in report["removed"])
    assert all(row["reason"] for row in report["removed"] + report["kept"])


def test_a_prune_that_deleted_something_is_recorded_and_a_no_op_is_not(config):
    config.ensure()
    _entry(config, NOW - timedelta(days=90))
    _entry(config, NOW - timedelta(hours=1), rel="newer.md")
    assert last_prune_report(config) is None

    report = prune_trash(config, now=NOW, retention_days=WINDOW)
    stored = last_prune_report(config)

    assert stored is not None
    assert stored["removed_count"] == report["removed_count"] == 1
    assert stored["retention_days"] == WINDOW
    assert stored["pruned_at"] == NOW.isoformat()
    assert (config.dossier_dir / RETENTION_RECORD).is_file()

    # A second pass has nothing to do, so it writes no new trash entry.
    before = len(list((config.dossier_dir / "trash").iterdir()))
    again = prune_trash(config, now=NOW, retention_days=WINDOW)
    assert again["purged_count"] == 0
    assert len(list((config.dossier_dir / "trash").iterdir())) == before


def test_a_dry_run_reports_the_same_entries_without_deleting_them(config):
    config.ensure()
    doomed = _entry(config, NOW - timedelta(days=90))
    _entry(config, NOW - timedelta(hours=1), rel="newer.md")

    report = prune_trash(config, now=NOW, retention_days=WINDOW, apply=False)

    assert report["dry_run"] is True
    assert report["removed_count"] == 1
    assert report["purged_count"] == 0
    assert "dry run" in report["removed"][0]["reason"]
    assert doomed.is_dir() and (doomed / "notes.md").is_file()
    assert last_prune_report(config) is None


# -- the window is configurable ----------------------------------------------

def test_the_window_comes_from_the_workspace_file_then_the_environment(config, monkeypatch):
    config.ensure()
    monkeypatch.setenv("DOSSIER_TRASH_RETENTION_DAYS", "7")
    assert retention_settings(config)["retention_days"] == 7
    assert retention_settings(config)["source"] == "environment"

    (config.dossier_dir / "trash.json").write_text(
        json.dumps({"retention_days": 3}), encoding="utf-8")
    settings = retention_settings(config)
    assert (settings["retention_days"], settings["source"]) == (3, "workspace")

    # An explicit argument outranks both.
    settings = retention_settings(config, override=90)
    assert (settings["retention_days"], settings["source"]) == (90, "argument")


def test_an_unusable_window_is_ignored_with_a_warning_rather_than_coerced(config, monkeypatch):
    config.ensure()
    monkeypatch.setenv("DOSSIER_TRASH_RETENTION_DAYS", "soon")
    (config.dossier_dir / "trash.json").write_text(
        json.dumps({"retention_days": "later"}), encoding="utf-8")

    settings = retention_settings(config)

    assert settings["retention_days"] == TRASH_RETENTION_DAYS_DEFAULT
    assert settings["source"] == "default"
    assert len(settings["warnings"]) == 2
    assert all("whole number of days" in warning for warning in settings["warnings"])


def test_zero_days_disables_pruning_and_keeps_every_backup(config):
    config.ensure()
    _entry(config, NOW - timedelta(days=400))

    report = prune_trash(config, now=NOW, retention_days=0)

    assert report["enabled"] is False
    assert report["removed_count"] == 0
    assert "disabled" in report["reason"]
    assert (config.dossier_dir / "trash" / _name(NOW - timedelta(days=400))).is_dir()


# -- `never-only-copy` and the cap do not conflict ---------------------------

def test_an_overwrite_after_a_prune_still_keeps_its_superseded_bytes(config):
    """The cap removed a backup; the next write still copies before it replaces."""
    config.ensure()
    target = config.root / "notes.md"
    trash_then_write_text(config, target, "one")     # create
    trash_then_write_text(config, target, "two")     # keeps "one"
    real = sorted((config.dossier_dir / "trash").iterdir())[-1]
    aged = config.dossier_dir / "trash" / _name(NOW - timedelta(days=90))
    os.replace(real, aged)
    _age_tree(aged, NOW - timedelta(days=90))
    _entry(config, NOW - timedelta(hours=1), rel="somethingelse.md")

    report = prune_trash(config, now=NOW, retention_days=WINDOW)
    assert report["purged_count"] == 1
    remaining = sorted((config.dossier_dir / "trash").rglob("notes.md"))
    assert remaining == [], "the cap did not actually remove the aged-out backup"

    trash_then_write_text(config, target, "three")

    kept = sorted(path.read_text(encoding="utf-8")
                  for path in (config.dossier_dir / "trash").rglob("notes.md"))
    assert kept == ["two"], "the write after the prune kept no superseded bytes"
    assert target.read_text(encoding="utf-8") == "three"


# -- the surfaces the user actually reaches ----------------------------------

def test_the_cli_lists_the_trash_and_its_window(tmp_path, capsys):
    root = tmp_path / "ws"
    root.mkdir()
    config = _config_for(root)
    _entry(config, NOW - timedelta(days=90))

    code = cli.main(["trash", "list", "--root", str(root), "--json"])
    payload = json.loads(capsys.readouterr().out)

    assert code == 0
    assert payload["retention"]["retention_days"] == 30
    assert [row["rel"] for row in payload["entries"]] == ["notes.md"]


def test_the_cli_prunes_dry_and_then_for_real(tmp_path, capsys):
    """No clock injection here: the CLI's own clock must expire a genuinely old entry."""
    root = tmp_path / "ws"
    root.mkdir()
    config = _config_for(root)
    real_now = datetime.now(timezone.utc)
    doomed = _entry(config, real_now - timedelta(days=90))
    _entry(config, real_now - timedelta(hours=1), rel="newer.md")

    code = cli.main(["trash", "prune", "--root", str(root), "--dry-run", "--json"])
    dry = json.loads(capsys.readouterr().out)
    assert code == 0 and dry["removed_count"] == 1 and dry["purged_count"] == 0
    assert doomed.is_dir()

    code = cli.main(["trash", "prune", "--root", str(root), "--json"])
    real = json.loads(capsys.readouterr().out)
    assert code == 0 and real["purged_count"] == 1
    assert not doomed.exists()
    assert real["removed"][0]["age_days"] > 85


def test_the_api_exposes_the_window_and_a_prune_route(config):
    config.ensure()
    real_now = datetime.now(timezone.utc)
    _entry(config, real_now - timedelta(days=90))
    _entry(config, real_now - timedelta(hours=1), rel="newer.md")
    client = TestClient(create_app(config))
    headers = {"Authorization": "Bearer test-token"}

    assert client.get("/api/trash").status_code == 401

    listing = client.get("/api/trash", headers=headers).json()
    assert listing["retention"]["retention_days"] == 30
    assert listing["retention"]["environment_variable"] == "DOSSIER_TRASH_RETENTION_DAYS"
    # The start-up pass ran with the real clock, so a 90-day-old entry is gone
    # before any route is called, and the report says so.
    assert listing["startup_prune"]["purged_count"] == 1
    assert [row["rel"] for row in listing["entries"]] == ["newer.md"]
    assert listing["last_prune"] is not None

    again = client.post("/api/trash/prune", headers=headers, json={"dry_run": True}).json()
    assert again["dry_run"] is True and again["removed_count"] == 0

    bad = client.post("/api/trash/prune", headers=headers, json={"retention_days": "soon"})
    assert bad.status_code == 400


def _config_for(root: Path):
    """An AppConfig on `root`, matching the `config` fixture the suite uses."""
    from dossier.config import AppConfig
    return AppConfig.create(root, root / ".dossier" / "x.sqlite", "test-token")
