"""Regression coverage for Streamlit Cloud hot-deployment imports."""

import subprocess
import sys
import textwrap
from pathlib import Path


def test_data_entry_loads_when_legacy_settings_module_is_cached() -> None:
    """V1.1 pages must not import new domain names from stale settings."""
    root = Path(__file__).resolve().parent.parent
    script = textwrap.dedent(
        """
        import sys
        import types
        from pathlib import Path
        from streamlit.testing.v1 import AppTest

        root = Path.cwd()
        legacy = types.ModuleType("config.settings")
        legacy.BASE_DIR = root
        legacy.DATA_DIR = root / "data"
        legacy.LOG_DIR = root / "logs"
        legacy.EXPORT_DIR = root / "exports"
        legacy.DATABASE_PATH = legacy.DATA_DIR / "probability.db"
        legacy.DATABASE_URL = f"sqlite:///{legacy.DATABASE_PATH}"
        legacy.MATERIALS = ("玉料",)
        legacy.SKILL_LEVELS = (9, 10, 11, 12)
        legacy.DEFAULTS = {
            "default_quantity": "18",
            "default_iterations": "100000",
            "theme": "dark",
        }
        sys.modules["config.settings"] = legacy

        app = AppTest.from_file("pages/2_Data_Entry.py").run(timeout=30)
        assert not app.exception, [item.value for item in app.exception]
        assert not app.error, [item.value for item in app.error]
        """
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=45,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
