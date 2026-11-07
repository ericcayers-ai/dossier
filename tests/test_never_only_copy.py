"""`never-only-copy`: every overwrite leaves the superseded bytes in `.dossier/trash/`.

Two failure modes this file exists to catch, both observed on real runs:

* an overwrite that keeps no backup at all — a 1,789-row `all_jobs.json` replaced
  by `[]` with an empty trash;
* a backup *destination* that resolves to the source file, because the trash
  prefix was `/`-joined with an absolute path. On Windows that discards the
  prefix, `shutil.copy2(path, path)` reaches `CopyFile2` and fails with
  `PermissionError WinError 32`, so the *second* write to any file in the
  workspace died and the trash stayed empty.
"""

from __future__ import annotations

import json

import pytest

from dossier.config import AppConfig
from dossier.engine import corpus, tree
from dossier.safety import (list_trash, restore_from_trash, trash, trash_if_present,
                            trash_then_write_text)


def _backups(config: AppConfig, name: str):
    return sorted((config.dossier_dir / "trash").rglob(name))


def test_a_second_write_to_the_same_file_succeeds_and_keeps_one_backup(config):
    config.ensure()
    target = config.root / "notes.md"
    trash_then_write_text(config, target, "one")
    trash_then_write_text(config, target, "two")

    assert target.read_text(encoding="utf-8") == "two"
    backups = _backups(config, "notes.md")
    assert len(backups) == 1, f"expected exactly one superseded copy, got {backups}"
    assert backups[0].read_text(encoding="utf-8") == "one"


def test_every_overwrite_of_the_same_file_keeps_its_own_superseded_copy(config):
    config.ensure()
    target = config.root / "notes.md"
    for text in ("one", "two", "three"):
        trash_then_write_text(config, target, text)

    assert target.read_text(encoding="utf-8") == "three"
    kept = sorted(path.read_text(encoding="utf-8")
                  for path in _backups(config, "notes.md"))
    assert kept == ["one", "two"]
    assert all("trash" in str(path) for path in _backups(config, "notes.md"))


def test_tree_upsert_works_twice_and_backs_up_the_first_write(config):
    config.ensure()
    tree.upsert_node(config.root, {"id": "a", "type": "experience", "title": "First"})
    tree.upsert_node(config.root, {"id": "a", "type": "experience", "title": "Second"})

    stored = json.loads((config.dossier_dir / "tree.json").read_text(encoding="utf-8"))
    assert [node["title"] for node in stored["nodes"]] == ["Second"]
    backups = _backups(config, "tree.json")
    assert len(backups) == 1
    assert json.loads(backups[0].read_text(encoding="utf-8"))["nodes"][0]["title"] == "First"


def test_trash_never_targets_the_source_file(config):
    """The destination must stay under the trash root, never be the file itself."""
    config.ensure()
    target = config.root / "a" / "b.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("old", encoding="utf-8")

    kept = trash(config, target)
    assert kept != target
    assert config.dossier_dir / "trash" in kept.parents
    assert kept.relative_to(config.dossier_dir / "trash").as_posix().endswith("a/b.json")
    assert kept.read_text(encoding="utf-8") == "old"
    assert target.read_text(encoding="utf-8") == "old"


def test_a_superseded_corpus_row_set_is_recoverable(config):
    """F3: `corpus build` replaced a real aggregate with `[]` and kept nothing."""
    config.ensure()
    rows = [{"title": f"Job {index}", "employer": "Acme", "url": f"https://x/{index}"}
            for index in range(6)]
    target = config.root / "all_boards_data" / "all_jobs.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(rows, indent=2), encoding="utf-8")

    board = config.root / "seek_data"
    board.mkdir()
    (board / "all_jobs.json").write_text(json.dumps([
        {"title": "Only one", "employer": "Acme", "url": "https://x/1"},
    ]), encoding="utf-8")

    report = corpus.write(config.root)
    assert report["rows"] == 1
    assert len(json.loads(target.read_text(encoding="utf-8"))) == 1

    backups = _backups(config, "all_jobs.json")
    assert backups, "the superseded aggregate was not kept anywhere"
    assert len(json.loads(backups[-1].read_text(encoding="utf-8"))) == 6


def test_a_target_outside_the_workspace_is_still_backed_up(config):
    """A `--out` aimed outside the workspace is the user's file too."""
    config.ensure()
    outside = config.root.parent / "outside"
    outside.mkdir(exist_ok=True)
    target = outside / "export.md"
    target.write_text("first", encoding="utf-8")

    assert trash_if_present(config, target) is not None
    kept = _backups(config, "export.md")
    assert len(kept) == 1
    assert kept[0].read_text(encoding="utf-8") == "first"
    assert "_external" in kept[0].as_posix()


# -- the trash listing and restore the UI reads -----------------------------

def test_the_trash_listing_names_the_path_each_backup_restores_to(config):
    config.ensure()
    target = config.root / "notes.md"
    trash_then_write_text(config, target, "one")
    trash_then_write_text(config, target, "two")

    listing = list_trash(config)
    assert [entry["rel"] for entry in listing["entries"]] == ["notes.md"]
    entry = listing["entries"][0]
    assert entry["trash_rel"].startswith(".dossier/trash/")
    assert entry["name"] == "notes.md"
    assert entry["size"] == len("one")
    assert entry["trashed_at"], "a restorable entry must carry when it was trashed"
    assert listing["unmanaged"] == []
    assert listing["external"] == []


def test_an_external_backup_is_listed_but_not_offered_as_restorable(config):
    config.ensure()
    outside = config.root.parent / "elsewhere"
    outside.mkdir(exist_ok=True)
    (outside / "export.md").write_text("first", encoding="utf-8")
    trash_if_present(config, outside / "export.md")

    listing = list_trash(config)
    assert listing["entries"] == []
    assert len(listing["external"]) == 1
    assert listing["external"][0]["rel"] is None


def test_a_render_backup_is_reported_as_unmanaged_rather_than_guessed_at(config):
    """`render_stale`'s flat-named PDF backups have no honest reverse mapping."""
    config.ensure()
    stray = config.dossier_dir / "trash" / "render-backup-20261010" / "Tailored__resume.pdf"
    stray.parent.mkdir(parents=True, exist_ok=True)
    stray.write_bytes(b"%PDF-1.4\n")

    listing = list_trash(config)
    assert listing["entries"] == []
    assert [row["name"] for row in listing["unmanaged"]] == ["Tailored__resume.pdf"]
    assert listing["unmanaged"][0]["rel"] is None


def test_restore_puts_the_superseded_bytes_back_and_keeps_what_it_replaced(config):
    config.ensure()
    target = config.root / "notes.md"
    trash_then_write_text(config, target, "one")
    trash_then_write_text(config, target, "two")
    entry = list_trash(config)["entries"][0]

    result = restore_from_trash(config, entry["rel"], entry["trash_rel"])
    assert result["restored"] is True
    assert target.read_text(encoding="utf-8") == "one"
    # The file that was on disk when the restore ran is not lost.
    assert sorted(path.read_text(encoding="utf-8") for path in _backups(config, "notes.md")) == [
        "one", "two"]


def test_restore_refuses_a_path_outside_the_trash_folder(config):
    config.ensure()
    decoy = config.root / "decoy.md"
    decoy.write_text("not a backup", encoding="utf-8")
    target = config.root / "notes.md"
    target.write_text("current", encoding="utf-8")

    with pytest.raises(ValueError):
        restore_from_trash(config, "notes.md", "decoy.md")
    assert target.read_text(encoding="utf-8") == "current"


def test_restore_refuses_a_non_timestamped_trash_entry(config):
    config.ensure()
    stray = config.dossier_dir / "trash" / "render-backup-20261010" / "Tailored__resume.pdf"
    stray.parent.mkdir(parents=True, exist_ok=True)
    stray.write_bytes(b"%PDF-1.4\n")

    with pytest.raises(ValueError):
        restore_from_trash(config, "resume.pdf",
                           ".dossier/trash/render-backup-20261010/Tailored__resume.pdf")


def test_restore_reports_a_missing_backup_rather_than_inventing_one(config):
    config.ensure()
    with pytest.raises(FileNotFoundError):
        restore_from_trash(config, "notes.md")
