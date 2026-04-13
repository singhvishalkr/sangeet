from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

from song_automation.config import PlaylistConfig, ScheduleSlot, TransitionConfig


DecisionAction = Literal["play", "stop"]


@dataclass(slots=True)
class WeatherSnapshot:
    temperature_c: float
    precipitation: float
    cloud_cover: int
    wind_speed_kmh: float
    is_day: bool
    tags: set[str] = field(default_factory=set)


@dataclass(slots=True)
class OverrideRecord:
    playlist_id: str | None
    stop_playback: bool
    note: str | None
    expires_at: datetime


@dataclass(slots=True)
class DecisionContext:
    now: datetime
    holiday_names: list[str]
    weather: WeatherSnapshot | None
    mood_tags: set[str] = field(default_factory=set)
    time_period: str = ""
    season: str = ""


@dataclass(slots=True)
class CandidateScore:
    playlist: PlaylistConfig
    score: int
    reasons: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ResolvedDecision:
    action: DecisionAction
    reason: str
    slot: ScheduleSlot | None = None
    playlist: PlaylistConfig | None = None
    transition: TransitionConfig | None = None
    target_volume: int = 0
    reasons: list[str] = field(default_factory=list)


@dataclass(slots=True)
class TrackInfo:
    title: str | None = None
    position: float = 0.0
    duration: float = 0.0
    playlist_pos: int = -1
    playlist_count: int = 0


@dataclass(slots=True)
class PlaybackSnapshot:
    running: bool = False
    playlist_id: str | None = None
    slot_id: str | None = None
    volume: int = 0
    started_at: datetime | None = None
    last_reason: str | None = None
    is_paused: bool = False
    track: TrackInfo = field(default_factory=TrackInfo)


@dataclass(slots=True)
class DecisionTrace:
    timestamp: datetime
    action: DecisionAction
    slot_id: str | None
    playlist_id: str | None
    reason: str
    reasons: list[str] = field(default_factory=list)
    candidates: list[dict] = field(default_factory=list)
    context_snapshot: dict = field(default_factory=dict)
