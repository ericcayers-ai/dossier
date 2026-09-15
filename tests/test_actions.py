import json
import sys

import pytest

from dossier.actions import run_action


def test_action_uses_argv_and_requires_confirmation(config):
    config.dossier_dir.mkdir(parents=True, exist_ok=True)
    (config.dossier_dir / "actions.json").write_text(json.dumps([
        {"id": "print", "label": "Print", "applies_to": ["*"], "argv": [sys.executable, "-c", "print('literal;safe')"], "confirm": False, "writes": False},
        {"id": "write", "label": "Write", "applies_to": ["*"], "argv": [sys.executable, "-c", "print('write')"], "confirm": True, "writes": True},
    ]))
    (config.root / "notes.md").write_text("notes")
    result = run_action(config, "print", "notes.md")
    assert result.returncode == 0
    assert "literal;safe" in result.stdout
    with pytest.raises(PermissionError):
        run_action(config, "write", "notes.md")
    assert run_action(config, "write", "notes.md", confirmed=True).returncode == 0
