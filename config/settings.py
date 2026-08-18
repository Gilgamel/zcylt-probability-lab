"""Non-secret application configuration for ProbabilityLab."""

from __future__ import annotations

import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

# The environment value is exposed for conventional configuration inspection.
# Database code still resolves Streamlit Secrets first at connection time.
DATABASE_URL = os.environ.get("DATABASE_URL", "")

DEFAULT_MATERIAL_QUANTITY = 18
DEFAULT_MATERIAL_LEVEL = 12
DEFAULT_HORSE_LEVEL = 10
DEFAULT_BIRD_LEVEL = 10
DEFAULT_MONTE_CARLO_ITERATIONS = 100_000
CONFIDENCE_LEVEL = 0.95
