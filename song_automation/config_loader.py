from __future__ import annotations

import logging
from pathlib import Path

import yaml

from song_automation.config import AppConfig

logger = logging.getLogger(__name__)


class ConfigError(RuntimeError):
    """Raised when the configuration cannot be loaded safely."""


class ConfigRepository:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._config: AppConfig | None = None
        self._mtime_ns: int | None = None

    @property
    def config(self) -> AppConfig:
        if self._config is None:
            raise ConfigError("configuration has not been loaded yet")
        return self._config

    def load(self) -> AppConfig:
        if not self.path.exists():
            raise ConfigError(f"configuration file does not exist: {self.path}")

        raw = yaml.safe_load(self.path.read_text(encoding="utf-8")) or {}
        config = AppConfig.model_validate(raw)
        self._validate_references(config)
        self._config = config
        self._mtime_ns = self.path.stat().st_mtime_ns
        return config

    def reload_if_changed(self) -> AppConfig:
        current_mtime_ns = self.path.stat().st_mtime_ns
        if self._config is None or self._mtime_ns != current_mtime_ns:
            logger.info("Config file changed, reloading from %s", self.path)
            return self.load()
        return self._config

    @staticmethod
    def _validate_references(config: AppConfig) -> None:
        playlist_ids = [playlist.id for playlist in config.playlists]
        slot_ids = [slot.id for slot in config.schedule]

        if len(playlist_ids) != len(set(playlist_ids)):
            raise ConfigError("playlist ids must be unique")

        if len(slot_ids) != len(set(slot_ids)):
            raise ConfigError("slot ids must be unique")

        known_playlist_ids = set(playlist_ids)
        known_slot_ids = set(slot_ids)

        for slot in config.schedule:
            if not slot.playlist_ids:
                raise ConfigError(f"slot '{slot.id}' must define at least one playlist")
            unknown = set(slot.playlist_ids) - known_playlist_ids
            if unknown:
                raise ConfigError(f"slot '{slot.id}' references unknown playlists: {sorted(unknown)}")

        for rule in config.weekday_themes:
            unknown_slots = set(rule.slot_ids) - known_slot_ids
            if unknown_slots:
                raise ConfigError(f"weekday theme references unknown slots: {sorted(unknown_slots)}")

        for rule in config.holiday_rules:
            unknown_slots = set(rule.slot_ids) - known_slot_ids
            unknown_playlists = set(rule.playlist_ids) - known_playlist_ids
            if unknown_slots:
                raise ConfigError(f"holiday rule references unknown slots: {sorted(unknown_slots)}")
            if unknown_playlists:
                raise ConfigError(f"holiday rule references unknown playlists: {sorted(unknown_playlists)}")

        for rule in config.weather_rules:
            unknown_slots = set(rule.slot_ids) - known_slot_ids
            unknown_playlists = set(rule.playlist_ids) - known_playlist_ids
            if unknown_slots:
                raise ConfigError(f"weather rule references unknown slots: {sorted(unknown_slots)}")
            if unknown_playlists:
                raise ConfigError(f"weather rule references unknown playlists: {sorted(unknown_playlists)}")
