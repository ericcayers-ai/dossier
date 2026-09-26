from dataclasses import dataclass
from pathlib import Path
from datetime import datetime, timezone
import hashlib, os, shutil

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
def _matches(path, expect):
    if not path.exists(): return expect is None
    return stamp(path)==expect
def trash(config, path:Path)->Path:
    path=resolve_in_root(config.root, str(path.resolve().relative_to(config.root)))
    if not path.exists(): return path
    rel=path.relative_to(config.root)
    out=config.dossier_dir/'trash'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')/rel
    out.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(path,out); return out
def atomic_write(path:Path,data:bytes,expect:FileStamp|None=None)->FileStamp:
    path=path.resolve(); path.parent.mkdir(parents=True,exist_ok=True)
    if not _matches(path,expect): raise Conflict("file changed on disk")
    tmp=path.with_suffix(path.suffix+'.tmp')
    try:
        with open(tmp,'wb') as f: f.write(data); f.flush(); os.fsync(f.fileno())
        if not _matches(path,expect): raise Conflict("file changed on disk")
        os.replace(tmp,path); return stamp(path)
    finally:
        if tmp.exists(): tmp.unlink()
