from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import holidays
import httpx

from song_automation.config import AppConfig
from song_automation.domain import DecisionContext, WeatherSnapshot

logger = logging.getLogger(__name__)


WEEKDAY_NAMES = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")


def weekday_name(value: datetime) -> str:
    return WEEKDAY_NAMES[value.weekday()]


@dataclass(slots=True)
class CachedWeather:
    fetched_at: datetime
    payload: WeatherSnapshot | None


class HolidayProvider:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self._calendar = holidays.country_holidays(
            self.config.location.country,
            subdiv=self.config.location.subdivision,
        )

    def get_holidays(self, current_date: date) -> list[str]:
        holiday_name = self._calendar.get(current_date)
        if holiday_name is None:
            return []
        if isinstance(holiday_name, list):
            return [str(item) for item in holiday_name]
        return [str(holiday_name)]


class WeatherProvider:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self._cache: CachedWeather | None = None

    def get_weather(self, now_local: datetime) -> WeatherSnapshot | None:
        if not self.config.features.weather_context:
            return None
        if self.config.location.latitude is None or self.config.location.longitude is None:
            return None
        if self._cache and now_local - self._cache.fetched_at < timedelta(minutes=20):
            return self._cache.payload

        params = {
            "latitude": self.config.location.latitude,
            "longitude": self.config.location.longitude,
            "current": "temperature_2m,precipitation,cloud_cover,wind_speed_10m,is_day",
            "timezone": self.config.timezone,
        }

        response = httpx.get("https://api.open-meteo.com/v1/forecast", params=params, timeout=15.0)
        response.raise_for_status()
        current = response.json()["current"]

        snapshot = WeatherSnapshot(
            temperature_c=float(current["temperature_2m"]),
            precipitation=float(current["precipitation"]),
            cloud_cover=int(current["cloud_cover"]),
            wind_speed_kmh=float(current["wind_speed_10m"]),
            is_day=bool(current["is_day"]),
            tags=self._classify_tags(
                temperature_c=float(current["temperature_2m"]),
                precipitation=float(current["precipitation"]),
                cloud_cover=int(current["cloud_cover"]),
                wind_speed_kmh=float(current["wind_speed_10m"]),
                is_day=bool(current["is_day"]),
            ),
        )
        self._cache = CachedWeather(fetched_at=now_local, payload=snapshot)
        return snapshot

    @staticmethod
    def _classify_tags(
        *,
        temperature_c: float,
        precipitation: float,
        cloud_cover: int,
        wind_speed_kmh: float,
        is_day: bool,
    ) -> set[str]:
        tags: set[str] = {"day" if is_day else "night"}

        if precipitation > 0.0:
            tags.add("rainy")
            if precipitation >= 2.0:
                tags.add("wet")

        if cloud_cover >= 70:
            tags.add("cloudy")
        elif cloud_cover <= 20:
            tags.add("clear")

        if wind_speed_kmh >= 25:
            tags.add("breezy")

        if temperature_c <= 20:
            tags.add("cool")
        elif temperature_c >= 32:
            tags.add("hot")
        else:
            tags.add("mild")

        return tags


WEATHER_BUCKETS = {
    "clear": lambda w: w.cloud_cover <= 20 and w.precipitation == 0,
    "rain": lambda w: w.precipitation > 0.3,
    "drizzle": lambda w: 0 < w.precipitation <= 0.3,
    "stormy": lambda w: w.precipitation > 2.0 and w.wind_speed_kmh > 30,
    "hot": lambda w: w.temperature_c >= 35,
    "warm": lambda w: 28 <= w.temperature_c < 35,
    "pleasant": lambda w: 20 <= w.temperature_c < 28,
    "cool": lambda w: 12 <= w.temperature_c < 20,
    "cold": lambda w: w.temperature_c < 12,
    "windy": lambda w: w.wind_speed_kmh >= 25,
    "cloudy": lambda w: w.cloud_cover >= 70,
}


def classify_weather_buckets(weather: WeatherSnapshot) -> set[str]:
    return {name for name, check in WEATHER_BUCKETS.items() if check(weather)}


def derive_time_period(hour: int) -> str:
    if hour < 5:
        return "late_night"
    if hour < 7:
        return "early_morning"
    if hour < 12:
        return "morning"
    if hour < 16:
        return "afternoon"
    if hour < 19:
        return "evening"
    if hour < 22:
        return "night"
    return "late_night"


def derive_season(month: int, southern_hemisphere: bool = False) -> str:
    seasons = {
        (12, 1, 2): "winter",
        (3, 4, 5): "spring",
        (6, 7, 8): "summer",
        (9, 10, 11): "autumn",
    }
    for months, season in seasons.items():
        if month in months:
            if southern_hemisphere:
                opposite = {"winter": "summer", "summer": "winter", "spring": "autumn", "autumn": "spring"}
                return opposite[season]
            return season
    return "unknown"


class ContextService:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.tz = ZoneInfo(config.timezone)
        self.holidays = HolidayProvider(config)
        self.weather = WeatherProvider(config)

    def build(self, now_local: datetime | None = None) -> DecisionContext:
        current = now_local or datetime.now(self.tz)
        if current.tzinfo is None:
            current = current.replace(tzinfo=self.tz)
        try:
            weather = self.weather.get_weather(current)
        except Exception:
            logger.warning("Weather fetch failed, degrading gracefully", exc_info=True)
            weather = None

        if weather:
            weather.tags = weather.tags | classify_weather_buckets(weather)

        lat = self.config.location.latitude or 0
        southern = lat < 0

        return DecisionContext(
            now=current,
            holiday_names=self.holidays.get_holidays(current.date()) if self.config.features.calendar_rules else [],
            weather=weather,
            time_period=derive_time_period(current.hour),
            season=derive_season(current.month, southern_hemisphere=southern),
        )
