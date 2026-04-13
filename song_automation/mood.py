from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Literal

logger = logging.getLogger(__name__)

Activity = Literal["cooking", "prayer", "work", "rest", "celebration", "exercise", "guests"]


@dataclass(slots=True)
class MoodState:
    energy: int = 3
    valence: int = 3
    activity: Activity | None = None
    updated_at: datetime | None = None
    tags: set[str] = field(default_factory=set)

    @property
    def is_stale(self) -> bool:
        if self.updated_at is None:
            return True
        return datetime.now().astimezone() - self.updated_at > timedelta(hours=2)

    def derive_tags(self) -> set[str]:
        """Convert mood dimensions into tags for resolver scoring."""
        tags: set[str] = set()

        if self.energy <= 2:
            tags.add("calm")
            tags.add("soft")
        elif self.energy >= 4:
            tags.add("energetic")
            tags.add("upbeat")

        if self.valence <= 2:
            tags.add("melancholic")
            tags.add("reflective")
        elif self.valence >= 4:
            tags.add("happy")
            tags.add("bright")

        if self.activity:
            tags.add(self.activity)

        self.tags = tags
        return tags


class MoodService:
    """Manages the current mood state for the system."""

    def __init__(self) -> None:
        self._current = MoodState()

    @property
    def current(self) -> MoodState:
        return self._current

    def update(
        self,
        energy: int | None = None,
        valence: int | None = None,
        activity: Activity | None = None,
    ) -> MoodState:
        if energy is not None:
            self._current.energy = max(1, min(5, energy))
        if valence is not None:
            self._current.valence = max(1, min(5, valence))
        if activity is not None:
            self._current.activity = activity
        self._current.updated_at = datetime.now().astimezone()
        self._current.derive_tags()
        logger.info(
            "Mood updated: energy=%d valence=%d activity=%s tags=%s",
            self._current.energy,
            self._current.valence,
            self._current.activity,
            sorted(self._current.tags),
        )
        return self._current

    def clear(self) -> None:
        self._current = MoodState()

    def to_dict(self) -> dict:
        return {
            "energy": self._current.energy,
            "valence": self._current.valence,
            "activity": self._current.activity,
            "tags": sorted(self._current.tags),
            "updated_at": self._current.updated_at.isoformat() if self._current.updated_at else None,
            "is_stale": self._current.is_stale,
        }
