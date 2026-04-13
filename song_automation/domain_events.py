from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class DomainEvent:
    event_type: str
    timestamp: datetime
    payload: dict[str, Any] = field(default_factory=dict)


EventHandler = Callable[[DomainEvent], None]


class EventBus:
    """Lightweight synchronous in-process pub/sub for domain events."""

    def __init__(self) -> None:
        self._handlers: dict[str, list[EventHandler]] = defaultdict(list)

    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        self._handlers[event_type].append(handler)

    def publish(self, event: DomainEvent) -> None:
        handlers = self._handlers.get(event.event_type, [])
        for handler in handlers:
            try:
                handler(event)
            except Exception:
                logger.warning(
                    "Event handler failed for %s", event.event_type, exc_info=True
                )

    def clear(self) -> None:
        self._handlers.clear()


# Singleton bus for the application
event_bus = EventBus()


# Standard event type constants
PLAYLIST_STARTED = "playlist_started"
PLAYLIST_STOPPED = "playlist_stopped"
OVERRIDE_APPLIED = "override_applied"
OVERRIDE_CLEARED = "override_cleared"
CONFIG_RELOADED = "config_reloaded"
WEATHER_UPDATED = "weather_updated"
MPV_RESTARTED = "mpv_restarted"
DECISION_MADE = "decision_made"
