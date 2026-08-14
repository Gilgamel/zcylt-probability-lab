"""Static configuration and seed data for ProbabilityLab."""

from pathlib import Path

from config.domain import (
    BIRD_RANDOM,
    BIRD_SPECIES,
    CATEGORIES,
    DEFAULTS,
    DISPLAYED_PROBABILITIES,
    HORSE_BREEDS,
    HORSE_PROBABILITY_WARNING,
    HORSE_SEARCH,
    ITEMS_BY_CATEGORY,
    MATERIAL_PRODUCTION,
    MATERIALS,
    QUALITIES,
    QUALITY_LABELS,
    SKILL_LEVELS,
)

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
LOG_DIR = BASE_DIR / "logs"
EXPORT_DIR = BASE_DIR / "exports"
DATABASE_PATH = DATA_DIR / "probability.db"
DATABASE_URL = f"sqlite:///{DATABASE_PATH}"

for directory in (DATA_DIR, LOG_DIR, EXPORT_DIR):
    directory.mkdir(parents=True, exist_ok=True)
