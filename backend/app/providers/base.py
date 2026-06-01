from abc import ABC, abstractmethod

import pandas as pd


class CarbonProvider(ABC):
    """Returns a Series of gCO2/kWh indexed by 30-min UTC slot starts."""

    @abstractmethod
    async def fetch(self, region_id: int, hours: int = 48) -> pd.Series:
        ...


class PriceProvider(ABC):
    """Returns a Series of p/kWh indexed by 30-min UTC slot starts."""

    @abstractmethod
    async def fetch(self, region_code: str, hours: int = 48) -> pd.Series:
        ...


class WeatherProvider(ABC):
    """Returns a DataFrame with weather variables indexed by 30-min slot starts."""

    @abstractmethod
    async def fetch(self, lat: float, lon: float, hours: int = 48) -> pd.DataFrame:
        ...
