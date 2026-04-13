from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from song_automation.config import (
    AppConfig,
    DefaultsConfig,
    FeatureFlags,
    HolidayRule,
    PlaylistConfig,
    PlaylistSource,
    ScheduleSlot,
    SmartRotationConfig,
    TransitionConfig,
    VolumeProfile,
    WeatherRule,
    WeekdayThemeRule,
)
from song_automation.domain import DecisionContext, OverrideRecord, WeatherSnapshot
from song_automation.resolver import Resolver, is_slot_active


IST = ZoneInfo("Asia/Calcutta")


def build_config(**overrides) -> AppConfig:
    kwargs: dict = dict(
        timezone="Asia/Calcutta",
        features=FeatureFlags(
            time_automation=True,
            calendar_rules=True,
            weather_context=True,
            smart_rotation=True,
        ),
        defaults=DefaultsConfig(transition=TransitionConfig(fade_out_seconds=1, fade_in_seconds=1)),
        smart_rotation=SmartRotationConfig(
            recent_session_window=8,
            freshness_bonus=6,
            same_playlist_penalty=60,
            recent_reuse_penalty=20,
        ),
        playlists=[
            PlaylistConfig(
                id="general",
                name="General",
                source=PlaylistSource(type="m3u", value="general.m3u"),
                tags=["devotional", "morning"],
                volume_profile=VolumeProfile(start=20, target=30, ramp_minutes=5),
            ),
            PlaylistConfig(
                id="shiv",
                name="Shiv",
                source=PlaylistSource(type="m3u", value="shiv.m3u"),
                tags=["devotional", "morning", "shiv"],
                volume_profile=VolumeProfile(start=20, target=30, ramp_minutes=5),
            ),
            PlaylistConfig(
                id="rainy",
                name="Rainy",
                source=PlaylistSource(type="m3u", value="rainy.m3u"),
                tags=["cooking", "rainy", "cozy"],
                volume_profile=VolumeProfile(start=20, target=30, ramp_minutes=5),
            ),
            PlaylistConfig(
                id="night_calm",
                name="Night Calm",
                source=PlaylistSource(type="m3u", value="night.m3u"),
                tags=["night", "calm", "soft"],
                volume_profile=VolumeProfile(start=16, target=28, ramp_minutes=8),
            ),
        ],
        schedule=[
            ScheduleSlot(
                id="morning",
                name="Morning",
                start="07:00",
                end="08:00",
                playlist_ids=["general", "shiv"],
                preferred_tags=["devotional", "morning"],
            ),
            ScheduleSlot(
                id="cooking",
                name="Cooking",
                start="20:00",
                end="21:00",
                playlist_ids=["rainy"],
                preferred_tags=["cooking"],
            ),
            ScheduleSlot(
                id="overnight",
                name="Overnight",
                start="23:00",
                end="01:00",
                playlist_ids=["night_calm"],
                preferred_tags=["night", "calm"],
            ),
        ],
        weekday_themes=[
            WeekdayThemeRule(weekdays=["mon"], slot_ids=["morning"], include_tags=["shiv"], boost=40),
        ],
        holiday_rules=[
            HolidayRule(name_contains="Janmashtami", slot_ids=["morning"], playlist_ids=["shiv"], boost=90, exclusive=True),
        ],
        weather_rules=[
            WeatherRule(slot_ids=["cooking"], precipitation_above=0.1, include_tags=["rainy"], boost=30),
        ],
    )
    kwargs.update(overrides)
    return AppConfig(**kwargs)


# --- Override tests ---

def test_manual_override_wins() -> None:
    config = build_config()
    resolver = Resolver(config)
    now = datetime(2026, 4, 13, 7, 10, tzinfo=IST)
    context = DecisionContext(now=now, holiday_names=[], weather=None)

    decision = resolver.resolve(
        context=context,
        active_override=OverrideRecord(playlist_id="shiv", stop_playback=False, note=None, expires_at=now),
        recent_playlist_ids=[],
    )

    assert decision.action == "play"
    assert decision.playlist is not None
    assert decision.playlist.id == "shiv"


def test_stop_override_stops_playback() -> None:
    config = build_config()
    resolver = Resolver(config)
    now = datetime(2026, 4, 13, 7, 10, tzinfo=IST)
    context = DecisionContext(now=now, holiday_names=[], weather=None)

    decision = resolver.resolve(
        context=context,
        active_override=OverrideRecord(playlist_id=None, stop_playback=True, note="quiet", expires_at=now),
        recent_playlist_ids=[],
    )

    assert decision.action == "stop"
    assert decision.reason == "manual_override_stop"


# --- Weekday theme tests ---

def test_monday_prefers_shiv_playlist() -> None:
    config = build_config()
    resolver = Resolver(config)
    now = datetime(2026, 4, 13, 7, 10, tzinfo=IST)
    context = DecisionContext(now=now, holiday_names=[], weather=None)

    decision = resolver.resolve(context=context, active_override=None, recent_playlist_ids=[])

    assert decision.playlist is not None
    assert decision.playlist.id == "shiv"


def test_tuesday_no_weekday_boost() -> None:
    config = build_config()
    resolver = Resolver(config)
    now = datetime(2026, 4, 14, 7, 10, tzinfo=IST)
    context = DecisionContext(now=now, holiday_names=[], weather=None)

    decision = resolver.resolve(context=context, active_override=None, recent_playlist_ids=[])
    assert decision.playlist is not None
    assert decision.action == "play"


# --- Holiday tests ---

def test_holiday_rule_can_be_exclusive() -> None:
    config = build_config()
    resolver = Resolver(config)
    now = datetime(2026, 8, 16, 7, 10, tzinfo=IST)
    context = DecisionContext(now=now, holiday_names=["Janmashtami"], weather=None)

    decision = resolver.resolve(context=context, active_override=None, recent_playlist_ids=[])

    assert decision.playlist is not None
    assert decision.playlist.id == "shiv"


# --- Weather tests ---

def test_weather_rule_boosts_rainy_playlist() -> None:
    config = build_config()
    resolver = Resolver(config)
    now = datetime(2026, 4, 13, 20, 15, tzinfo=IST)
    context = DecisionContext(
        now=now,
        holiday_names=[],
        weather=WeatherSnapshot(
            temperature_c=24,
            precipitation=0.8,
            cloud_cover=80,
            wind_speed_kmh=10,
            is_day=False,
            tags={"rainy", "cloudy", "night"},
        ),
    )

    decision = resolver.resolve(context=context, active_override=None, recent_playlist_ids=[])

    assert decision.playlist is not None
    assert decision.playlist.id == "rainy"


def test_weather_none_degrades_gracefully() -> None:
    config = build_config()
    resolver = Resolver(config)
    now = datetime(2026, 4, 13, 20, 15, tzinfo=IST)
    context = DecisionContext(now=now, holiday_names=[], weather=None)

    decision = resolver.resolve(context=context, active_override=None, recent_playlist_ids=[])

    assert decision.action == "play"
    assert decision.playlist is not None


# --- Rotation tests ---

def test_recent_reuse_penalty_avoids_immediate_repeat() -> None:
    config = build_config()
    resolver = Resolver(config)
    now = datetime(2026, 4, 14, 7, 10, tzinfo=IST)
    context = DecisionContext(now=now, holiday_names=[], weather=None)

    decision = resolver.resolve(context=context, active_override=None, recent_playlist_ids=["shiv"])

    assert decision.playlist is not None
    assert decision.playlist.id == "general"


def test_freshness_bonus_for_unplayed_playlist() -> None:
    config = build_config()
    resolver = Resolver(config)
    now = datetime(2026, 4, 14, 7, 10, tzinfo=IST)
    context = DecisionContext(now=now, holiday_names=[], weather=None)

    decision = resolver.resolve(context=context, active_override=None, recent_playlist_ids=[])
    assert decision.playlist is not None
    assert any("freshness" in r for r in decision.reasons)


# --- Slot activation tests ---

def test_slot_active_normal_range() -> None:
    slot = ScheduleSlot(id="s", name="S", start="07:00", end="08:00", playlist_ids=["general"])
    now = datetime(2026, 4, 13, 7, 30, tzinfo=IST)
    assert is_slot_active(slot, now) is True


def test_slot_inactive_outside_range() -> None:
    slot = ScheduleSlot(id="s", name="S", start="07:00", end="08:00", playlist_ids=["general"])
    now = datetime(2026, 4, 13, 6, 30, tzinfo=IST)
    assert is_slot_active(slot, now) is False


def test_slot_active_overnight_before_midnight() -> None:
    slot = ScheduleSlot(id="s", name="S", start="23:00", end="01:00", playlist_ids=["general"])
    now = datetime(2026, 4, 13, 23, 30, tzinfo=IST)
    assert is_slot_active(slot, now) is True


def test_slot_active_overnight_after_midnight() -> None:
    slot = ScheduleSlot(id="s", name="S", start="23:00", end="01:00", playlist_ids=["general"])
    now = datetime(2026, 4, 14, 0, 30, tzinfo=IST)
    assert is_slot_active(slot, now) is True


def test_slot_inactive_overnight_midday() -> None:
    slot = ScheduleSlot(id="s", name="S", start="23:00", end="01:00", playlist_ids=["general"])
    now = datetime(2026, 4, 13, 12, 0, tzinfo=IST)
    assert is_slot_active(slot, now) is False


def test_slot_weekday_filtering() -> None:
    slot = ScheduleSlot(id="s", name="S", start="07:00", end="08:00", weekdays=["mon"], playlist_ids=["general"])
    monday = datetime(2026, 4, 13, 7, 30, tzinfo=IST)
    tuesday = datetime(2026, 4, 14, 7, 30, tzinfo=IST)
    assert is_slot_active(slot, monday) is True
    assert is_slot_active(slot, tuesday) is False


# --- No active slot ---

def test_no_active_slot_returns_stop() -> None:
    config = build_config()
    resolver = Resolver(config)
    now = datetime(2026, 4, 13, 12, 0, tzinfo=IST)
    context = DecisionContext(now=now, holiday_names=[], weather=None)

    decision = resolver.resolve(context=context, active_override=None, recent_playlist_ids=[])

    assert decision.action == "stop"
    assert decision.reason == "no_active_slot"


# --- Feature flag tests ---

def test_time_automation_disabled_returns_stop() -> None:
    config = build_config(features=FeatureFlags(time_automation=False))
    resolver = Resolver(config)
    now = datetime(2026, 4, 13, 7, 30, tzinfo=IST)
    context = DecisionContext(now=now, holiday_names=[], weather=None)

    decision = resolver.resolve(context=context, active_override=None, recent_playlist_ids=[])

    assert decision.action == "stop"
    assert decision.reason == "no_active_slot"


# --- Overnight slot resolution ---

def test_overnight_slot_resolves_playlist() -> None:
    config = build_config()
    resolver = Resolver(config)
    now = datetime(2026, 4, 13, 23, 30, tzinfo=IST)
    context = DecisionContext(now=now, holiday_names=[], weather=None)

    decision = resolver.resolve(context=context, active_override=None, recent_playlist_ids=[])

    assert decision.action == "play"
    assert decision.playlist is not None
    assert decision.playlist.id == "night_calm"
    assert decision.slot is not None
    assert decision.slot.id == "overnight"
