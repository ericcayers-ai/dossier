from dataclasses import dataclass
from pathlib import Path
import sqlite3, json, time, hashlib
from .extract import extract_text
@dataclass
class FileRecord:
 rel:str; ext:str; size:int; mtime_ns:int; sha256:str; kind:str='file'; stem_key:str=''; role:str='other'; meta:dict|None=None; extract_error:str|None=None

def open_db(path):
 c=sqlite3.connect(str(path),check_same_thread=False); c.row_factory=sqlite3.Row; c.execute('PRAGMA journal_mode=WAL')
 c.executescript("CREATE TABLE IF NOT EXISTS files(rel TEXT PRIMARY KEY,ext TEXT,size INTEGER,mtime_ns INTEGER,sha256 TEXT,kind TEXT,stem_key TEXT,role TEXT,meta_json TEXT,indexed_at INTEGER,extract_error TEXT); CREATE INDEX IF NOT EXISTS files_stem ON files(stem_key); CREATE VIRTUAL TABLE IF NOT EXISTS files_fts USING fts5(rel UNINDEXED,body,tokenize='unicode61');")
 return c
def upsert_file(c,r:FileRecord, body=''):
 c.execute('INSERT INTO files VALUES(?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(rel) DO UPDATE SET ext=excluded.ext,size=excluded.size,mtime_ns=excluded.mtime_ns,sha256=excluded.sha256,kind=excluded.kind,stem_key=excluded.stem_key,role=excluded.role,meta_json=excluded.meta_json,indexed_at=excluded.indexed_at,extract_error=excluded.extract_error',(r.rel,r.ext,r.size,r.mtime_ns,r.sha256,r.kind,r.stem_key,r.role,json.dumps(r.meta or {}),int(time.time()),r.extract_error))
 c.execute('DELETE FROM files_fts WHERE rel=?',(r.rel,));
 if body: c.execute('INSERT INTO files_fts(rel,body) VALUES(?,?)',(r.rel,body))
def search(c,q,limit=50): return [dict(x) for x in c.execute("SELECT f.rel,f.ext,snippet(files_fts,1,'<mark>','</mark>','…',12) snippet FROM files_fts JOIN files f ON f.rel=files_fts.rel WHERE files_fts MATCH ? LIMIT ?",(q,limit))]
def index_path(c,path,rel,stem_key='',role='other'):
 s=path.stat(); old=c.execute('SELECT size,mtime_ns,sha256 FROM files WHERE rel=?',(rel,)).fetchone(); h=hashlib.sha256(path.read_bytes()).hexdigest()
 if old and old['size']==s.st_size and old['mtime_ns']==s.st_mtime_ns: return False
 body,meta=extract_text(path); r=FileRecord(rel,path.suffix.lower(),s.st_size,s.st_mtime_ns,h,stem_key=stem_key,role=role,meta=meta,extract_error=meta.get('error')); upsert_file(c,r,body); return True
