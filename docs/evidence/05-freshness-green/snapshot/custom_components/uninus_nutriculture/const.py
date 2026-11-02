"""Public parameters and fixed shadow contract."""
DOMAIN = "uninus_nutriculture"
# default, native minimum, maximum, step, unit
SPECS = {
    "level_low": (2.25, 0, 10, 0.01, "m"),
    "level_high": (2.4, 0, 10, 0.01, "m"),
    "ph_low": (5.4, 0, 14, 0.1, None),
    "ph_high": (5.8, 0, 14, 0.1, None),
    "ec_low": (0.8, 0, 20, 0.01, "mS/cm"),
    "ec_high": (0.9, 0, 20, 0.01, "mS/cm"),
    "refill_timeout": (190, 1, 1440, 1, "min"),
    "ec_timeout": (90, 1, 1440, 1, "min"),
    "ph_timeout": (190, 1, 1440, 1, "min"),
    "mix_duration": (10, 1, 1440, 1, "min"),
}
SOURCE_KEYS = ("ph", "ec", "level")
