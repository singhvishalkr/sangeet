from __future__ import annotations

import logging
from datetime import datetime
from typing import Protocol

from song_automation.config import AppConfig, RoomMode

logger = logging.getLogger(__name__)


class SignalProvider(Protocol):
    """Abstract interface for environment signal providers."""

    @property
    def name(self) -> str: ...

    def poll(self) -> dict: ...

    @property
    def available(self) -> bool: ...


class DevicePresenceProvider:
    """Detects presence based on known Bluetooth/WiFi device addresses.

    Placeholder implementation -- actual BT/WiFi scanning requires
    platform-specific libraries (e.g., pybluez, scapy).
    """

    def __init__(self, known_devices: list[str] | None = None) -> None:
        self._known_devices = known_devices or []
        self._someone_home = True

    @property
    def name(self) -> str:
        return "device_presence"

    @property
    def available(self) -> bool:
        return len(self._known_devices) > 0

    def poll(self) -> dict:
        return {"someone_home": self._someone_home, "devices": []}

    def set_presence(self, present: bool) -> None:
        self._someone_home = present


class RoomModeService:
    """Manages the current room mode and derives context tags."""

    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self._current_mode: RoomMode = config.room_modes.default_mode
        self._providers: list[SignalProvider] = []

    @property
    def current_mode(self) -> RoomMode:
        return self._current_mode

    def set_mode(self, mode: RoomMode) -> None:
        if mode != self._current_mode:
            logger.info("Room mode changed: %s -> %s", self._current_mode, mode)
        self._current_mode = mode

    def get_mode_tags(self) -> set[str]:
        """Get preferred tags for the current room mode."""
        tag_map = self._config.room_modes.mode_tag_overrides
        return set(tag_map.get(self._current_mode, []))

    def register_provider(self, provider: SignalProvider) -> None:
        self._providers.append(provider)
        logger.info("Registered signal provider: %s", provider.name)

    def poll_providers(self) -> dict:
        results = {}
        for provider in self._providers:
            if not provider.available:
                continue
            try:
                results[provider.name] = provider.poll()
            except Exception:
                logger.warning("Signal provider %s failed", provider.name, exc_info=True)
        return results

    def is_quiet_hours(self, now: datetime) -> bool:
        """Check if current time falls within quiet hours."""
        qh = self._config.quiet_hours
        if not qh.enabled:
            return False

        current_minutes = now.hour * 60 + now.minute
        start_parts = qh.start.split(":")
        end_parts = qh.end.split(":")
        start_minutes = int(start_parts[0]) * 60 + int(start_parts[1])
        end_minutes = int(end_parts[0]) * 60 + int(end_parts[1])

        if start_minutes <= end_minutes:
            return start_minutes <= current_minutes < end_minutes
        return current_minutes >= start_minutes or current_minutes < end_minutes

    def to_dict(self) -> dict:
        return {
            "current_mode": self._current_mode,
            "mode_tags": sorted(self.get_mode_tags()),
            "providers": [p.name for p in self._providers],
        }
