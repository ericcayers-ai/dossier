from dataclasses import dataclass
from pathlib import Path
import json, subprocess
from .safety import resolve_in_root
@dataclass
class Action: id:str; label:str; applies_to:list; argv:list; cwd:str|None=None; confirm:bool=False; writes:bool=False
@dataclass
class ActionRun: action_id:str; returncode:int; stdout:str; stderr:str
def load_actions(config):
 p=config.dossier_dir/'actions.json'; data=json.loads(p.read_text()) if p.exists() else json.loads((Path(__file__).parents[2]/'templates/actions.json').read_text())
 return [Action(**x) for x in data]
def run_action(config,action_id,rel,confirmed=False):
 a=next((x for x in load_actions(config) if x.id==action_id),None)
 if not a: raise ValueError('unknown action')
 if a.writes and (not a.confirm or not confirmed): raise PermissionError('confirmation required')
 path=resolve_in_root(config.root,rel); vals={'path':str(path),'dir':str(path.parent),'stem':path.stem,'root':str(config.root)}
 argv=[x.format(**vals) for x in a.argv]
 cwd=Path(a.cwd.format(**vals)) if a.cwd else config.root
 if not cwd.resolve().is_relative_to(config.root): raise ValueError('cwd escapes root')
 r=subprocess.run(argv,cwd=cwd,capture_output=True,text=True,shell=False)
 return ActionRun(action_id,r.returncode,r.stdout,r.stderr)
