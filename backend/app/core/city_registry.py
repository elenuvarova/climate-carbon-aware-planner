"""City configuration registry.

Adding a new city requires only a new entry here — the scoring and scheduling
engine is unchanged; only the provider callables vary per city.
"""
from dataclasses import dataclass
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class City:
    name: str
    lat: float
    lon: float
    tz: ZoneInfo
    carbon_provider: str   # "uk" | "fr" | "be"
    price_provider: str | None  # "octopus" | None
    region_id: int | None  # UK Carbon Intensity API region (UK only)
    carbon_label: str      # shown in API response / UI


CITIES: dict[str, City] = {
    "london": City(
        name="London",
        lat=51.5072,
        lon=-0.1276,
        tz=ZoneInfo("Europe/London"),
        carbon_provider="uk",
        price_provider="octopus",
        region_id=13,
        carbon_label="UK Carbon Intensity API (48h regional forecast)",
    ),
    "paris": City(
        name="Paris",
        lat=48.8566,
        lon=2.3522,
        tz=ZoneInfo("Europe/Paris"),
        carbon_provider="fr",
        price_provider=None,
        region_id=None,
        carbon_label="RTE éco2mix via ODRE (cyclical proxy from last 48h actuals)",
    ),
    "antwerp": City(
        name="Antwerp",
        lat=51.2194,
        lon=4.4025,
        tz=ZoneInfo("Europe/Brussels"),
        carbon_provider="be",
        price_provider=None,
        region_id=None,
        carbon_label="Elia open data ods192 (consumption-based CO₂, cyclical proxy)",
    ),
}

DEFAULT_CITY = "london"


def get_city(city_id: str) -> City:
    return CITIES.get(city_id.lower(), CITIES[DEFAULT_CITY])
