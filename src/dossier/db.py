from dataclasses import dataclass
import sqlite3, json, time, hashlib, re
from .extract import extract_text
@dataclass
class FileRecord:
 rel:str; ext:str; size:int; mtime_ns:int; sha256:str; kind:str='file'; stem_key:str=''; role:str='other'; meta:dict|None=None; extract_error:str|None=None

def open_db(path):
 c=sqlite3.connect(str(path),check_same_thread=False); c.row_factory=sqlite3.Row; c.execute('PRAGMA journal_mode=WAL')
 # One connection is shared by the watch task and every request (api/app.py).
 # WAL without a busy timeout turns a concurrent write into an immediate
 # `database is locked` error; five seconds makes the wait a wait, not a failure.
 c.execute('PRAGMA busy_timeout=5000')
 c.executescript("CREATE TABLE IF NOT EXISTS files(rel TEXT PRIMARY KEY,ext TEXT,size INTEGER,mtime_ns INTEGER,sha256 TEXT,kind TEXT,stem_key TEXT,role TEXT,meta_json TEXT,indexed_at INTEGER,extract_error TEXT); CREATE INDEX IF NOT EXISTS files_stem ON files(stem_key); CREATE VIRTUAL TABLE IF NOT EXISTS files_fts USING fts5(rel UNINDEXED,body,tokenize='unicode61');")
 return c
def upsert_file(c,r:FileRecord, body=''):
 c.execute('INSERT INTO files VALUES(?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(rel) DO UPDATE SET ext=excluded.ext,size=excluded.size,mtime_ns=excluded.mtime_ns,sha256=excluded.sha256,kind=excluded.kind,stem_key=excluded.stem_key,role=excluded.role,meta_json=excluded.meta_json,indexed_at=excluded.indexed_at,extract_error=excluded.extract_error',(r.rel,r.ext,r.size,r.mtime_ns,r.sha256,r.kind,r.stem_key,r.role,json.dumps(r.meta or {}),int(time.time()),r.extract_error))
 c.execute('DELETE FROM files_fts WHERE rel=?',(r.rel,));
 if body: c.execute('INSERT INTO files_fts(rel,body) VALUES(?,?)',(r.rel,body))
def search(c,q,limit=50):
 """Full-text search that cannot raise on what a user typed.

 FTS5's MATCH argument is a query language, not a string: a bare `"` is an
 unterminated string, `a:b` is a column reference, `*` is a prefix marker and
 `OR` is an operator. Passing a search box straight into it made a search for
 `"hello` an unhandled `OperationalError` and a 500 from `/api/search`.

 So the words are extracted and each one is quoted as a phrase. A user searching
 `alpha OR beta` now gets documents containing both words rather than the board
 operator, which is the honest reading for a search box; an empty result is a
 result, and an error is not.
 """
 tokens=_fts_tokens(q)
 if not tokens: return []
 # A name you can see in the rail is the most specific thing you can type, so a
 # path match is answered first and in full. Ranked by bm25 over body text alone,
 # `_verify_report` returned `_verify_letters.py` ahead of `_verify_report.json`.
 name_rows=[]
 try:
  esc = chr(92)
  clause = ' AND '.join(["rel LIKE ? ESCAPE '" + esc + "'"] * len(tokens))
  name_rows=c.execute(
   f"SELECT rel,ext FROM files WHERE {clause} ORDER BY length(rel) LIMIT ?",
   tuple(f"%{_like_escape(token)}%" for token in tokens)+(limit,)).fetchall()
 except sqlite3.OperationalError:
  name_rows=[]
 # A query that already fills the page with path matches has nothing to gain from
 # ranking every body match too: `resume` matched ~400 filenames and spent 250ms in
 # bm25 to fill the same 50 rows.
 if len(name_rows) >= limit:
  return [{'rel':row['rel'],'ext':row['ext'],'snippet':'','kind':row['ext']} for row in name_rows][:limit]
 match=' '.join(f'"{token}"' for token in tokens)
 try:
  rows=c.execute("SELECT f.rel,f.ext,snippet(files_fts,1,'<mark>','</mark>','…',12) snippet FROM files_fts JOIN files f ON f.rel=files_fts.rel WHERE files_fts MATCH ? ORDER BY rank LIMIT ?",(match,limit)).fetchall()
 except sqlite3.OperationalError:
  rows=[]
 seen={row['rel'] for row in name_rows}
 head=[{'rel':row['rel'],'ext':row['ext'],'snippet':'','kind':row['ext']} for row in name_rows]
 tail=[{'rel':x['rel'],'ext':x['ext'],'snippet':x['snippet'],'kind':x['ext']} for x in rows if x['rel'] not in seen]
 return (head+tail)[:limit]

def _like_escape(text:str)->str:
    """Escape LIKE's own wildcards so a typed `%` or `_` is a character."""
    return text.replace(chr(92), chr(92) * 2).replace('%', chr(92) + '%').replace('_', chr(92) + '_')

#: At most this many terms reach FTS5. A pasted document is not a query, and an
#: unbounded AND of 5,000 terms is a denial-of-service on the index.
FTS_MAX_TERMS=32
_TOKEN=re.compile(r'[^\W_]+',re.UNICODE)
def _fts_tokens(text):
 return [token for token in _TOKEN.findall((text or '').casefold()) if token][:FTS_MAX_TERMS]
def index_path(c,path,rel,stem_key='',role='other'):
 s=path.stat(); old=c.execute('SELECT size,mtime_ns,sha256 FROM files WHERE rel=?',(rel,)).fetchone()
 # The cheap check comes first: hashing every file before asking whether it
 # changed made a crawl read the whole workspace even when nothing had moved.
 if old and old['size']==s.st_size and old['mtime_ns']==s.st_mtime_ns: return False
 h=hashlib.sha256(path.read_bytes()).hexdigest()
 body,meta=extract_text(path); r=FileRecord(rel,path.suffix.lower(),s.st_size,s.st_mtime_ns,h,stem_key=stem_key,role=role,meta=meta,extract_error=meta.get('error')); upsert_file(c,r,body); return True
