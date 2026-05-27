import os
import pytest

@pytest.fixture(autouse=True)
def temp_cache_db(tmp_path):
    """Point cache at a fresh temp DB for every test."""
    db_file = str(tmp_path / "test_cache.db")
    os.environ["CACHE_DB_PATH"] = db_file
    yield db_file
    os.environ.pop("CACHE_DB_PATH", None)
