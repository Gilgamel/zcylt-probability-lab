"""Stable game-domain identifiers, labels, and database seed values.

This module intentionally has no filesystem or Streamlit side effects. Keeping
domain constants separate from runtime settings also makes hot deployments safe
when an older ``config.settings`` module is still present in ``sys.modules``.
"""

MATERIAL_PRODUCTION = "MATERIAL_PRODUCTION"
HORSE_SEARCH = "HORSE_SEARCH"
BIRD_RANDOM = "BIRD_RANDOM"
# Retained only so historical targeted-cultivation rows remain readable/editable.
# New data entry supports random cultivation exclusively.
BIRD_TARGETED = "BIRD_TARGETED"

CATEGORIES = {
    MATERIAL_PRODUCTION: "官匠营",
    HORSE_SEARCH: "马厩",
    BIRD_RANDOM: "灵禽院",
}
MATERIALS = (
    "玉料",
    "金精",
    "宝珠",
    "兽骨",
    "锦缎",
    "熟皮",
    "绢布",
    "丝线",
    "钢材",
)
HORSE_BREEDS = ("浴火烈马", "踏水飞马", "穿林骏马", "裂岩铁马")
BIRD_SPECIES = ("铁羽雁", "九炎鹊", "出云鹤", "暗铁鸦")
ITEMS_BY_CATEGORY = {
    MATERIAL_PRODUCTION: MATERIALS,
    HORSE_SEARCH: HORSE_BREEDS,
    BIRD_RANDOM: BIRD_SPECIES,
    BIRD_TARGETED: BIRD_SPECIES,
}

SKILL_LEVELS = (9, 10, 11, 12)
SKILL_PROGRESSION_SEEDS = (
    (9, 10, 200),
    (10, 11, 800),
    (11, 12, 1600),
)
QUALITIES = ("GREEN", "BLUE", "PURPLE", "ORANGE")
QUALITY_LABELS = {
    "GREEN": "绿品",
    "BLUE": "蓝品",
    "PURPLE": "紫品",
    "ORANGE": "橙品",
    "OTHER": "其他 / 未说明",
}

# Official displayed values. Horse values intentionally total 99% and are
# stored exactly as displayed; simulation normalization is always explicit.
DISPLAYED_PROBABILITIES = {
    HORSE_SEARCH: {
        "GREEN": 0.41,
        "BLUE": 0.50,
        "PURPLE": 0.07,
        "ORANGE": 0.01,
    },
    BIRD_RANDOM: {"BLUE": 0.79, "PURPLE": 0.20, "ORANGE": 0.01},
}

DEFAULTS = {
    "default_material_quantity": "18",
    "default_material_level": "12",
    "default_horse_level": "10",
    "default_bird_level": "10",
    "default_monte_carlo_iterations": "100000",
    "confidence_level": "0.95",
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
