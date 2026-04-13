from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator


Weekday = Literal["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
SourceType = Literal["m3u", "file", "url"]


CurveType = Literal["linear", "ease_in", "ease_out", "logarithmic"]


class TransitionConfig(BaseModel):
    fade_out_seconds: int = Field(default=5, ge=0, le=120)
    fade_in_seconds: int = Field(default=8, ge=0, le=120)
    curve: CurveType = "linear"
    max_volume_jump: int = Field(default=15, ge=1, le=100)


class VolumeProfile(BaseModel):
    start: int = Field(default=20, ge=0, le=100)
    target: int = Field(default=40, ge=0, le=100)
    ramp_minutes: int = Field(default=5, ge=0, le=180)


class PlaylistSource(BaseModel):
    type: SourceType = "m3u"
    value: str = Field(min_length=1)


class PlaylistConfig(BaseModel):
    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    source: PlaylistSource
    tags: list[str] = Field(default_factory=list)
    shuffle: bool = True
    enabled: bool = True
    volume_profile: VolumeProfile = Field(default_factory=VolumeProfile)


class ScheduleSlot(BaseModel):
    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    start: str
    end: str
    weekdays: list[Weekday] = Field(default_factory=lambda: ["mon", "tue", "wed", "thu", "fri", "sat", "sun"])
    playlist_ids: list[str] = Field(default_factory=list)
    preferred_tags: list[str] = Field(default_factory=list)
    priority: int = Field(default=100, ge=0, le=1000)
    transition: TransitionConfig | None = None


class WeekdayThemeRule(BaseModel):
    weekdays: list[Weekday]
    slot_ids: list[str] = Field(default_factory=list)
    include_tags: list[str] = Field(default_factory=list)
    exclude_tags: list[str] = Field(default_factory=list)
    boost: int = Field(default=25, ge=0, le=200)


class HolidayRule(BaseModel):
    name_contains: str | None = None
    month: int | None = Field(default=None, ge=1, le=12)
    day: int | None = Field(default=None, ge=1, le=31)
    slot_ids: list[str] = Field(default_factory=list)
    playlist_ids: list[str] = Field(default_factory=list)
    include_tags: list[str] = Field(default_factory=list)
    boost: int = Field(default=60, ge=0, le=300)
    exclusive: bool = False

    @model_validator(mode="after")
    def validate_matcher(self) -> "HolidayRule":
        if not self.name_contains and not (self.month and self.day):
            raise ValueError("holiday rule must define name_contains or month/day")
        return self


class WeatherRule(BaseModel):
    slot_ids: list[str] = Field(default_factory=list)
    include_tags: list[str] = Field(default_factory=list)
    exclude_tags: list[str] = Field(default_factory=list)
    playlist_ids: list[str] = Field(default_factory=list)
    boost: int = Field(default=20, ge=0, le=200)
    temperature_below: float | None = None
    temperature_above: float | None = None
    precipitation_above: float | None = Field(default=None, ge=0, le=1)
    cloud_cover_above: int | None = Field(default=None, ge=0, le=100)
    wind_speed_above: float | None = Field(default=None, ge=0)
    daytime: bool | None = None


RoomMode = Literal["normal", "prayer", "cooking", "guests", "quiet", "celebration", "sleep"]


class QuietHoursConfig(BaseModel):
    enabled: bool = False
    start: str = "23:00"
    end: str = "06:00"
    max_volume: int = Field(default=20, ge=0, le=100)
    stop_playback: bool = False


class RoomModeConfig(BaseModel):
    default_mode: RoomMode = "normal"
    mode_tag_overrides: dict[str, list[str]] = Field(default_factory=lambda: {
        "prayer": ["devotional", "bhajan", "calm"],
        "cooking": ["cooking", "upbeat", "light"],
        "guests": ["light", "family", "energetic"],
        "quiet": ["calm", "soft"],
        "celebration": ["festival", "energetic", "family"],
        "sleep": ["calm", "soft", "night"],
    })


class SmartRotationConfig(BaseModel):
    recent_session_window: int = Field(default=8, ge=1, le=100)
    freshness_bonus: int = Field(default=8, ge=0, le=100)
    same_playlist_penalty: int = Field(default=60, ge=0, le=300)
    recent_reuse_penalty: int = Field(default=24, ge=0, le=300)


class FeatureFlags(BaseModel):
    time_automation: bool = True
    calendar_rules: bool = True
    weather_context: bool = True
    smart_rotation: bool = True
    dual_player: bool = False
    adaptive_learning: bool = False
    mood_context: bool = False
    room_modes: bool = False


class LocationConfig(BaseModel):
    country: str = "IN"
    subdivision: str | None = None
    latitude: float | None = None
    longitude: float | None = None


class PlayerConfig(BaseModel):
    executable: str = "mpv"
    pipe_name: str = "sangeet-mpv"
    dry_run: bool = False
    extra_args: list[str] = Field(default_factory=list)


class DefaultsConfig(BaseModel):
    reconcile_seconds: int = Field(default=30, ge=5, le=3600)
    min_switch_interval_minutes: int = Field(default=20, ge=0, le=1440)
    transition: TransitionConfig = Field(default_factory=TransitionConfig)


class ApiConfig(BaseModel):
    enabled: bool = True
    host: str = "127.0.0.1"
    port: int = Field(default=8765, ge=1, le=65535)
    auth_token: str | None = None


class AppConfig(BaseModel):
    timezone: str = "Asia/Calcutta"
    features: FeatureFlags = Field(default_factory=FeatureFlags)
    location: LocationConfig = Field(default_factory=LocationConfig)
    player: PlayerConfig = Field(default_factory=PlayerConfig)
    defaults: DefaultsConfig = Field(default_factory=DefaultsConfig)
    api: ApiConfig = Field(default_factory=ApiConfig)
    playlists: list[PlaylistConfig] = Field(default_factory=list)
    schedule: list[ScheduleSlot] = Field(default_factory=list)
    weekday_themes: list[WeekdayThemeRule] = Field(default_factory=list)
    holiday_rules: list[HolidayRule] = Field(default_factory=list)
    weather_rules: list[WeatherRule] = Field(default_factory=list)
    smart_rotation: SmartRotationConfig = Field(default_factory=SmartRotationConfig)
    quiet_hours: QuietHoursConfig = Field(default_factory=QuietHoursConfig)
    room_modes: RoomModeConfig = Field(default_factory=RoomModeConfig)
