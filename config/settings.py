"""Static application settings."""

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
LOG_DIR = BASE_DIR / "logs"
EXPORT_DIR = BASE_DIR / "exports"
DATABASE_PATH = DATA_DIR / "probability.db"
DATABASE_URL = f"sqlite:///{DATABASE_PATH}"

MATERIALS = ("玉料", "金精", "宝珠", "兽骨", "锦缎", "熟皮", "绢布", "丝线", "钢材")
SKILL_LEVELS = (9, 10, 11, 12)
DEFAULTS = {
    "default_quantity": "18",
    "default_iterations": "100000",
    "theme": "dark",
}

for directory in (DATA_DIR, LOG_DIR, EXPORT_DIR):
    directory.mkdir(parents=True, exist_ok=True)
