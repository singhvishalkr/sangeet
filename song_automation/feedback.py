from __future__ import annotations

import json
import logging
import math
import sqlite3
from datetime import datetime, timezone
from typing import Literal

logger = logging.getLogger(__name__)

FeedbackSignal = Literal["skip", "like", "dislike", "override_away", "full_play"]

MAX_WEIGHT_ADJUSTMENT = 15
DECAY_HALF_LIFE_DAYS = 30


class FeedbackStore:
    """Captures user feedback signals and derives bounded preference weights."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._conn = connection
        self._ensure_tables()

    def _ensure_tables(self) -> None:
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS feedback_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                occurred_at TEXT NOT NULL,
                signal TEXT NOT NULL,
                playlist_id TEXT,
                slot_id TEXT,
                track_info TEXT,
                payload_json TEXT
            )
            """
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS preference_weights (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scope_type TEXT NOT NULL,
                scope_id TEXT NOT NULL,
                playlist_id TEXT NOT NULL,
                weight REAL NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL,
                UNIQUE(scope_type, scope_id, playlist_id)
            )
            """
        )
        self._conn.commit()

    def record(
        self,
        signal: FeedbackSignal,
        playlist_id: str | None = None,
        slot_id: str | None = None,
        track_info: str | None = None,
        payload: dict | None = None,
    ) -> None:
        self._conn.execute(
            """
            INSERT INTO feedback_events (occurred_at, signal, playlist_id, slot_id, track_info, payload_json)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                datetime.now(timezone.utc).isoformat(),
                signal,
                playlist_id,
                slot_id,
                track_info,
                json.dumps(payload or {}),
            ),
        )
        self._conn.commit()

        if playlist_id:
            self._update_weight(signal, playlist_id, slot_id)

    def _update_weight(self, signal: FeedbackSignal, playlist_id: str, slot_id: str | None) -> None:
        delta = _signal_delta(signal)
        if delta == 0:
            return

        scope_type = "slot" if slot_id else "global"
        scope_id = slot_id or "global"
        now_iso = datetime.now(timezone.utc).isoformat()

        row = self._conn.execute(
            "SELECT weight FROM preference_weights WHERE scope_type=? AND scope_id=? AND playlist_id=?",
            (scope_type, scope_id, playlist_id),
        ).fetchone()

        if row:
            new_weight = max(-MAX_WEIGHT_ADJUSTMENT, min(MAX_WEIGHT_ADJUSTMENT, row["weight"] + delta))
            self._conn.execute(
                "UPDATE preference_weights SET weight=?, updated_at=? WHERE scope_type=? AND scope_id=? AND playlist_id=?",
                (new_weight, now_iso, scope_type, scope_id, playlist_id),
            )
        else:
            new_weight = max(-MAX_WEIGHT_ADJUSTMENT, min(MAX_WEIGHT_ADJUSTMENT, delta))
            self._conn.execute(
                "INSERT INTO preference_weights (scope_type, scope_id, playlist_id, weight, updated_at) VALUES (?, ?, ?, ?, ?)",
                (scope_type, scope_id, playlist_id, new_weight, now_iso),
            )
        self._conn.commit()

    def get_weight(self, playlist_id: str, slot_id: str | None = None) -> float:
        """Get the combined preference weight for a playlist (slot-specific + global)."""
        total = 0.0
        for scope_type, scope_id in [("global", "global"), ("slot", slot_id or "")]:
            if not scope_id:
                continue
            row = self._conn.execute(
                "SELECT weight FROM preference_weights WHERE scope_type=? AND scope_id=? AND playlist_id=?",
                (scope_type, scope_id, playlist_id),
            ).fetchone()
            if row:
                total += row["weight"]
        return max(-MAX_WEIGHT_ADJUSTMENT, min(MAX_WEIGHT_ADJUSTMENT, total))

    def get_all_weights(self) -> list[dict]:
        rows = self._conn.execute(
            "SELECT scope_type, scope_id, playlist_id, weight, updated_at FROM preference_weights ORDER BY updated_at DESC"
        ).fetchall()
        return [dict(row) for row in rows]

    def reset(self) -> None:
        self._conn.execute("DELETE FROM preference_weights")
        self._conn.commit()
        logger.info("All preference weights reset")

    def decay_weights(self) -> None:
        """Apply time-based decay to all weights, shrinking old preferences."""
        rows = self._conn.execute(
            "SELECT id, weight, updated_at FROM preference_weights"
        ).fetchall()
        now = datetime.now(timezone.utc)
        for row in rows:
            updated = datetime.fromisoformat(row["updated_at"])
            days_old = (now - updated).total_seconds() / 86400
            decay_factor = math.pow(0.5, days_old / DECAY_HALF_LIFE_DAYS)
            new_weight = round(row["weight"] * decay_factor, 2)
            if abs(new_weight) < 0.5:
                self._conn.execute("DELETE FROM preference_weights WHERE id=?", (row["id"],))
            else:
                self._conn.execute(
                    "UPDATE preference_weights SET weight=? WHERE id=?",
                    (new_weight, row["id"]),
                )
        self._conn.commit()

    def export_data(self) -> dict:
        weights = self.get_all_weights()
        events = self._conn.execute(
            "SELECT occurred_at, signal, playlist_id, slot_id FROM feedback_events ORDER BY id DESC LIMIT 200"
        ).fetchall()
        return {
            "weights": weights,
            "recent_events": [dict(e) for e in events],
        }


def _signal_delta(signal: FeedbackSignal) -> float:
    return {
        "skip": -2.0,
        "dislike": -4.0,
        "override_away": -1.5,
        "like": 3.0,
        "full_play": 0.5,
    }.get(signal, 0)
