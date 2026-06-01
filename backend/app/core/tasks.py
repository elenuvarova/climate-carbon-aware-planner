from dataclasses import dataclass

DRYER_KWH = 3.5  # typical tumble-dryer energy per cycle


@dataclass(frozen=True)
class TaskTemplate:
    label: str
    kwh: float              # energy draw of the task itself
    avoided_kwh: float      # energy avoided if this mode chosen (e.g., dryer for air-dry)
    weather_profile: str | None  # "drying" | "ventilation" | None


TEMPLATES: dict[str, TaskTemplate] = {
    "laundry_airdry": TaskTemplate(
        label="Laundry (air-dry)",
        kwh=0.7,
        avoided_kwh=DRYER_KWH,
        weather_profile="drying",
    ),
    "laundry_dryer": TaskTemplate(
        label="Laundry + tumble dryer",
        kwh=4.2,
        avoided_kwh=0.0,
        weather_profile=None,
    ),
    "dishwasher": TaskTemplate(
        label="Dishwasher",
        kwh=1.5,
        avoided_kwh=0.0,
        weather_profile=None,
    ),
    "ev_charge": TaskTemplate(
        label="EV / device charging",
        kwh=8.0,
        avoided_kwh=0.0,
        weather_profile=None,
    ),
    "ventilation": TaskTemplate(
        label="Ventilate / open windows",
        kwh=0.0,
        avoided_kwh=0.0,
        weather_profile="ventilation",
    ),
}

# Weights per mode: (carbon, price, weather)
# Weather weight redistributed to carbon+price when task has no weather profile.
MODE_WEIGHTS: dict[str, dict[str, float]] = {
    "green":    {"carbon": 0.55, "price": 0.10, "weather": 0.35},
    "money":    {"carbon": 0.10, "price": 0.55, "weather": 0.35},
    "balanced": {"carbon": 0.33, "price": 0.33, "weather": 0.34},
}

# Fallback weights when there is no weather score
MODE_WEIGHTS_NO_WEATHER: dict[str, dict[str, float]] = {
    "green":    {"carbon": 0.85, "price": 0.15},
    "money":    {"carbon": 0.15, "price": 0.85},
    "balanced": {"carbon": 0.50, "price": 0.50},
}
