import pytest
from dossier.config import AppConfig
@pytest.fixture
def config(tmp_path): return AppConfig.create(tmp_path, tmp_path/'.dossier'/'x.sqlite', 'test-token')
