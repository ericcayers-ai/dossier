from dataclasses import dataclass
from pathlib import Path
import secrets

@dataclass(frozen=True)
class AppConfig:
    root: Path
    dossier_dir: Path
    db_path: Path
    token: str
    @classmethod
    def create(cls, root: Path, db_path: Path|None=None, token: str|None=None):
        root = root.resolve()
        d = root / ".dossier"
        return cls(root, d, db_path or d / "index.sqlite3", token or secrets.token_urlsafe(32))
    def ensure(self):
        self.dossier_dir.mkdir(parents=True, exist_ok=True)
        return self
