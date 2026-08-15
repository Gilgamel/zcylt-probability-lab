"""Streamlit fail-closed behavior when database configuration is absent."""

import os
import subprocess
import sys
from pathlib import Path


def test_app_shows_configuration_error_without_creating_local_database() -> None:
    root = Path(__file__).resolve().parent.parent
    environment = os.environ.copy()
    environment.pop("DATABASE_URL", None)
    script = """
from streamlit.testing.v1 import AppTest
import database.db as db
db._streamlit_secret = lambda: ''
db._cached_engine.clear()
app = AppTest.from_file('app.py').run(timeout=30)
assert not app.exception, [item.value for item in app.exception]
messages = [item.value for item in app.error]
assert any('DATABASE_URL' in message for message in messages), messages
"""
    result = subprocess.run(
        [sys.executable, "-c", script], cwd=root, env=environment,
        capture_output=True, text=True, timeout=45, check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
