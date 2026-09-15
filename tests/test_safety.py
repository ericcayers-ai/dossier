import pytest
from dossier.safety import *
def test_escape(tmp_path):
 with pytest.raises(PathEscape): resolve_in_root(tmp_path,'../x')
 with pytest.raises(PathEscape): resolve_in_root(tmp_path,'C:/x')
def test_atomic_conflict(tmp_path):
 p=tmp_path/'a.txt'; p.write_bytes(b'a'); s=stamp(p); p.write_bytes(b'b')
 with pytest.raises(Conflict): atomic_write(p,b'c',s)
 assert not (tmp_path/'a.txt.tmp').exists()
def test_trash(config):
 p=config.root/'a.txt'; p.write_text('old'); q=trash(config,p); assert q.read_text()=='old'
