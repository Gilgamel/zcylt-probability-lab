"""Static configuration and seed data for ProbabilityLab."""

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
LOG_DIR = BASE_DIR / "logs"
EXPORT_DIR = BASE_DIR / "exports"
DATABASE_PATH = DATA_DIR / "probability.db"
DATABASE_URL = f"sqlite:///{DATABASE_PATH}"

MATERIAL_PRODUCTION = "MATERIAL_PRODUCTION"
HORSE_SEARCH = "HORSE_SEARCH"
BIRD_RANDOM = "BIRD_RANDOM"

CATEGORIES = {
    MATERIAL_PRODUCTION: "官匠营",
    HORSE_SEARCH: "马厩",
    BIRD_RANDOM: "灵禽院",
}
MATERIALS = ("玉料", "金精", "宝珠", "兽骨", "锦缎", "熟皮", "绢布", "丝线", "钢材")
HORSE_BREEDS = ("浴火烈马", "踏水飞马", "穿林骏马", "裂岩铁马")
BIRD_SPECIES = ("铁羽雁", "九炎鹊", "出云鹤", "暗铁鸦")
ITEMS_BY_CATEGORY = {
    MATERIAL_PRODUCTION: MATERIALS,
    HORSE_SEARCH: HORSE_BREEDS,
    BIRD_RANDOM: BIRD_SPECIES,
}

SKILL_LEVELS = (9, 10, 11, 12)
QUALITIES = ("GREEN", "BLUE", "PURPLE", "ORANGE")
QUALITY_LABELS = {
    "GREEN": "绿品",
    "BLUE": "蓝品",
    "PURPLE": "紫品",
    "ORANGE": "橙品",
    "OTHER": "其他 / 未说明",
}

# These are official displayed values and are seeded into ProbabilityTarget.
# The horse values intentionally total 99%; never normalize them at storage time.
DISPLAYED_PROBABILITIES = {
    HORSE_SEARCH: {"GREEN": 0.41, "BLUE": 0.50, "PURPLE": 0.07, "ORANGE": 0.01},
    BIRD_RANDOM: {"BLUE": 0.79, "PURPLE": 0.20, "ORANGE": 0.01},
}

DEFAULTS = {
    "default_quantity": "18",
    "default_iterations": "100000",
    "default_random_seed": "42",
    "theme": "dark",
    "sufficiency_a_moe": "0.005",
    "sufficiency_b_moe": "0.010",
    "sufficiency_c_moe": "0.020",
    "target_margin_of_error": "0.005",
}

HORSE_PROBABILITY_WARNING = (
    "马厩提示概率合计为 99%，请确认游戏是否存在四舍五入、"
    "未显示的小数概率或其他结果。"
)

for directory in (DATA_DIR, LOG_DIR, EXPORT_DIR):
    directory.mkdir(parents=True, exist_ok=True)
