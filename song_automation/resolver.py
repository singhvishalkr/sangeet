from __future__ import annotations

from datetime import datetime

from song_automation.config import AppConfig, HolidayRule, ScheduleSlot, WeatherRule, WeekdayThemeRule
from song_automation.context import weekday_name
from song_automation.domain import CandidateScore, DecisionContext, OverrideRecord, ResolvedDecision


def parse_minutes(clock_value: str) -> int:
    hour_text, minute_text = clock_value.split(":", maxsplit=1)
    return int(hour_text) * 60 + int(minute_text)


def is_slot_active(slot: ScheduleSlot, now_local: datetime) -> bool:
    if weekday_name(now_local) not in slot.weekdays:
        return False

    current_minutes = now_local.hour * 60 + now_local.minute
    start_minutes = parse_minutes(slot.start)
    end_minutes = parse_minutes(slot.end)

    if start_minutes <= end_minutes:
        return start_minutes <= current_minutes < end_minutes
    return current_minutes >= start_minutes or current_minutes < end_minutes


class Resolver:
    def __init__(self, config: AppConfig, preference_fn: object | None = None) -> None:
        self.config = config
        self.playlists = {playlist.id: playlist for playlist in config.playlists if playlist.enabled}
        self.slots = config.schedule
        self.last_candidates: list[CandidateScore] = []
        self._preference_fn = preference_fn

    def resolve(
        self,
        context: DecisionContext,
        active_override: OverrideRecord | None,
        recent_playlist_ids: list[str],
    ) -> ResolvedDecision:
        self.last_candidates = []

        if active_override is not None:
            if active_override.stop_playback:
                return ResolvedDecision(action="stop", reason="manual_override_stop", reasons=["manual override active"])
            playlist = self.playlists.get(active_override.playlist_id or "")
            if playlist is not None:
                return ResolvedDecision(
                    action="play",
                    reason="manual_override_play",
                    playlist=playlist,
                    target_volume=playlist.volume_profile.target,
                    transition=self.config.defaults.transition,
                    reasons=["manual override active"],
                )

        active_slot = next((slot for slot in self.slots if is_slot_active(slot, context.now)), None)
        if active_slot is None or not self.config.features.time_automation:
            return ResolvedDecision(action="stop", reason="no_active_slot", reasons=["no matching schedule slot"])

        candidate_ids = self._candidate_ids(active_slot, context)
        candidates = [self.playlists[playlist_id] for playlist_id in candidate_ids if playlist_id in self.playlists]
        scored_candidates = [
            self._score_candidate(active_slot, playlist.id, context, recent_playlist_ids)
            for playlist in candidates
        ]
        scored_candidates = [candidate for candidate in scored_candidates if candidate is not None]
        self.last_candidates = scored_candidates

        if not scored_candidates:
            return ResolvedDecision(
                action="stop",
                reason="no_eligible_playlist",
                slot=active_slot,
                reasons=["slot resolved but no eligible playlist remained after rule evaluation"],
            )

        winner = max(scored_candidates, key=lambda candidate: candidate.score)
        transition = active_slot.transition or self.config.defaults.transition
        return ResolvedDecision(
            action="play",
            reason="slot_resolution",
            slot=active_slot,
            playlist=winner.playlist,
            transition=transition,
            target_volume=winner.playlist.volume_profile.target,
            reasons=winner.reasons,
        )

    def _candidate_ids(self, slot: ScheduleSlot, context: DecisionContext) -> list[str]:
        ordered_ids: list[str] = []

        for playlist_id in slot.playlist_ids:
            if playlist_id not in ordered_ids:
                ordered_ids.append(playlist_id)

        if self.config.features.calendar_rules:
            for rule in self.config.holiday_rules:
                if rule.slot_ids and slot.id not in rule.slot_ids:
                    continue
                if rule.name_contains and not any(rule.name_contains.lower() in holiday.lower() for holiday in context.holiday_names):
                    continue
                if rule.month and rule.day and (context.now.month != rule.month or context.now.day != rule.day):
                    continue
                for playlist_id in rule.playlist_ids:
                    if playlist_id not in ordered_ids:
                        ordered_ids.append(playlist_id)

        if self.config.features.weather_context and context.weather is not None:
            for rule in self.config.weather_rules:
                if rule.slot_ids and slot.id not in rule.slot_ids:
                    continue
                if rule.playlist_ids:
                    for playlist_id in rule.playlist_ids:
                        if playlist_id not in ordered_ids:
                            ordered_ids.append(playlist_id)

        return ordered_ids

    def _score_candidate(
        self,
        slot: ScheduleSlot,
        playlist_id: str,
        context: DecisionContext,
        recent_playlist_ids: list[str],
    ) -> CandidateScore | None:
        playlist = self.playlists[playlist_id]
        score = slot.priority
        reasons = [f"Matched schedule slot (priority {slot.priority})"]

        tag_matches = set(slot.preferred_tags).intersection(playlist.tags)
        if tag_matches:
            tag_score = len(tag_matches) * 12
            score += tag_score
            friendly_tags = ", ".join(sorted(tag_matches))
            reasons.append(f"Tags match: {friendly_tags} (+{tag_score})")

        if self.config.features.calendar_rules:
            weekday_rule_score, weekday_reasons = self._apply_weekday_rules(slot, playlist_id, context, self.config.weekday_themes)
            score += weekday_rule_score
            reasons.extend(weekday_reasons)

            holiday_match = self._apply_holiday_rules(slot, playlist_id, context, self.config.holiday_rules)
            if holiday_match is None:
                return None
            holiday_score, holiday_reasons = holiday_match
            score += holiday_score
            reasons.extend(holiday_reasons)

        if self.config.features.weather_context and context.weather is not None:
            weather_score, weather_reasons = self._apply_weather_rules(slot, playlist_id, context, self.config.weather_rules)
            score += weather_score
            reasons.extend(weather_reasons)

        if self.config.features.smart_rotation:
            rotation_score, rotation_reasons = self._apply_rotation_rules(playlist_id, recent_playlist_ids)
            score += rotation_score
            reasons.extend(rotation_reasons)

        if self.config.features.mood_context and context.mood_tags:
            mood_matches = context.mood_tags.intersection(playlist.tags)
            if mood_matches:
                mood_score = len(mood_matches) * 10
                score += mood_score
                friendly_mood = ", ".join(sorted(mood_matches))
                reasons.append(f"Matches your mood: {friendly_mood} (+{mood_score})")

        if self.config.features.adaptive_learning and self._preference_fn:
            pref_weight = self._preference_fn(playlist_id, slot.id)
            if pref_weight != 0:
                bounded = max(-15, min(15, int(pref_weight)))
                score += bounded
                if bounded > 0:
                    reasons.append(f"You seem to enjoy this playlist (+{bounded})")
                else:
                    reasons.append(f"You've skipped this playlist before ({bounded})")

        return CandidateScore(playlist=playlist, score=score, reasons=reasons)

    def _apply_weekday_rules(
        self,
        slot: ScheduleSlot,
        playlist_id: str,
        context: DecisionContext,
        rules: list[WeekdayThemeRule],
    ) -> tuple[int, list[str]]:
        playlist = self.playlists[playlist_id]
        weekday = weekday_name(context.now)
        total = 0
        reasons: list[str] = []

        for rule in rules:
            if weekday not in rule.weekdays:
                continue
            if rule.slot_ids and slot.id not in rule.slot_ids:
                continue
            if rule.include_tags and not set(rule.include_tags).intersection(playlist.tags):
                continue
            if rule.exclude_tags and set(rule.exclude_tags).intersection(playlist.tags):
                continue
            total += rule.boost
            day_name = weekday.capitalize()
            reasons.append(f"{day_name} theme boost (+{rule.boost})")

        return total, reasons

    def _apply_holiday_rules(
        self,
        slot: ScheduleSlot,
        playlist_id: str,
        context: DecisionContext,
        rules: list[HolidayRule],
    ) -> tuple[int, list[str]] | None:
        playlist = self.playlists[playlist_id]
        total = 0
        reasons: list[str] = []

        for rule in rules:
            if rule.slot_ids and slot.id not in rule.slot_ids:
                continue

            matched = False
            if rule.name_contains:
                matched = any(rule.name_contains.lower() in holiday.lower() for holiday in context.holiday_names)
            elif rule.month and rule.day:
                matched = context.now.month == rule.month and context.now.day == rule.day

            if not matched:
                continue

            if rule.exclusive and rule.playlist_ids and playlist_id not in rule.playlist_ids:
                return None

            if rule.playlist_ids and playlist_id in rule.playlist_ids:
                total += rule.boost
                holiday_name = rule.name_contains or "Festival"
                reasons.append(f"Festival special: {holiday_name} (+{rule.boost})")

            if rule.include_tags and set(rule.include_tags).intersection(playlist.tags):
                total += rule.boost
                reasons.append(f"Festival mood match (+{rule.boost})")

        return total, reasons

    def _apply_weather_rules(
        self,
        slot: ScheduleSlot,
        playlist_id: str,
        context: DecisionContext,
        rules: list[WeatherRule],
    ) -> tuple[int, list[str]]:
        playlist = self.playlists[playlist_id]
        weather = context.weather
        if weather is None:
            return 0, []

        total = 0
        reasons: list[str] = []

        for rule in rules:
            if rule.slot_ids and slot.id not in rule.slot_ids:
                continue
            if rule.temperature_below is not None and not (weather.temperature_c < rule.temperature_below):
                continue
            if rule.temperature_above is not None and not (weather.temperature_c > rule.temperature_above):
                continue
            if rule.precipitation_above is not None and not (weather.precipitation > rule.precipitation_above):
                continue
            if rule.cloud_cover_above is not None and not (weather.cloud_cover > rule.cloud_cover_above):
                continue
            if rule.wind_speed_above is not None and not (weather.wind_speed_kmh > rule.wind_speed_above):
                continue
            if rule.daytime is not None and weather.is_day is not rule.daytime:
                continue
            if rule.playlist_ids and playlist_id not in rule.playlist_ids:
                continue
            if rule.include_tags and not set(rule.include_tags).intersection(playlist.tags):
                continue
            if rule.exclude_tags and set(rule.exclude_tags).intersection(playlist.tags):
                continue

            total += rule.boost
            weather_desc = ", ".join(sorted(weather.tags)) if weather.tags else "current weather"
            reasons.append(f"Weather-aware: {weather_desc} (+{rule.boost})")

        return total, reasons

    def _apply_rotation_rules(self, playlist_id: str, recent_playlist_ids: list[str]) -> tuple[int, list[str]]:
        total = 0
        reasons: list[str] = []
        rotation = self.config.smart_rotation

        if not recent_playlist_ids:
            total += rotation.freshness_bonus
            reasons.append(f"Fresh pick - not played recently (+{rotation.freshness_bonus})")
            return total, reasons

        if recent_playlist_ids[0] == playlist_id:
            total -= rotation.same_playlist_penalty
            reasons.append(f"Just played - avoiding repeat (-{rotation.same_playlist_penalty})")
            return total, reasons

        for index, recent_id in enumerate(recent_playlist_ids[: rotation.recent_session_window]):
            if recent_id != playlist_id:
                continue
            penalty = max(rotation.recent_reuse_penalty - index * 2, 4)
            total -= penalty
            sessions_ago = index + 1
            reasons.append(f"Played {sessions_ago} sessions ago (-{penalty})")
            break
        else:
            total += rotation.freshness_bonus
            reasons.append(f"Fresh pick - not played recently (+{rotation.freshness_bonus})")

        return total, reasons
