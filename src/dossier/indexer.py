from dataclasses import dataclass
from pathlib import Path
from .db import index_path
from .bundles import load_rules,stem_key,classify_role
@dataclass
class CrawlStats: seen:int=0; indexed:int=0; skipped:int=0; errors:int=0
def crawl(config,conn,progress_cb=None):
 stats=CrawlStats(); rules=load_rules(config.root); found=set()
 for p in config.root.rglob('*'):
  if not p.is_file() or any(x in {'.dossier','.git','__pycache__','node_modules'} for x in p.parts): continue
  rel=p.relative_to(config.root).as_posix(); found.add(rel); stats.seen+=1
  try:
   if index_path(conn,p,rel,stem_key(rel,rules),classify_role(rel,rules)): stats.indexed+=1
  except Exception: stats.errors+=1
  if progress_cb: progress_cb(stats)
 for row in conn.execute('select rel from files').fetchall():
  if row['rel'] not in found: conn.execute('delete from files where rel=?',(row['rel'],)); conn.execute('delete from files_fts where rel=?',(row['rel'],))
 conn.commit(); return stats
async def watch(config,conn,on_change):
 from watchfiles import awatch
 async for changes in awatch(config.root,debounce=400):
  rules=load_rules(config.root)
  for _,s in changes:
   p=Path(s)
   if any(x in p.parts for x in ('.dossier','.git','__pycache__','node_modules')): continue
   rel=p.relative_to(config.root).as_posix()
   if p.exists() and p.is_file(): index_path(conn,p,rel,stem_key(rel,rules),classify_role(rel,rules))
   else: conn.execute('delete from files where rel=?',(rel,)); conn.execute('delete from files_fts where rel=?',(rel,))
  conn.commit(); await on_change(changes)
