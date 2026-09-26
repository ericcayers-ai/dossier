import pytest

from dossier.safety import Conflict, PathEscape, atomic_write, resolve_in_root, stamp, trash


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
