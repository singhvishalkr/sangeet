from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)


class AnalyticsService:
    """Provides listening analytics, health metrics, and operational insights."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._conn = connection

    def listening_summary(self, days: int = 7) -> dict:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

        total_sessions = self._conn.execute(
            "SELECT COUNT(*) as cnt FROM playback_sessions WHERE started_at >= ?",
            (cutoff,),
        ).fetchone()["cnt"]

        playlist_counts = self._conn.execute(
            """
            SELECT playlist_id, COUNT(*) as cnt
            FROM playback_sessions
            WHERE started_at >= ? AND playlist_id IS NOT NULL
            GROUP BY playlist_id
            ORDER BY cnt DESC
            """,
            (cutoff,),
        ).fetchall()

        slot_counts = self._conn.execute(
            """
            SELECT slot_id, COUNT(*) as cnt
            FROM playback_sessions
            WHERE started_at >= ? AND slot_id IS NOT NULL
            GROUP BY slot_id
            ORDER BY cnt DESC
            """,
            (cutoff,),
        ).fetchall()

        override_count = self._conn.execute(
            "SELECT COUNT(*) as cnt FROM events WHERE event_type='override_applied' AND occurred_at >= ?",
            (cutoff,),
        ).fetchone()["cnt"]

        return {
            "period_days": days,
            "total_sessions": total_sessions,
            "playlists": [{"playlist_id": r["playlist_id"], "count": r["cnt"]} for r in playlist_counts],
            "slots": [{"slot_id": r["slot_id"], "count": r["cnt"]} for r in slot_counts],
            "override_count": override_count,
        }

    def health_report(self) -> dict:
        recent_errors = self._conn.execute(
            """
            SELECT occurred_at, event_type, payload_json
            FROM events
            WHERE severity IN ('ERROR', 'WARNING')
            ORDER BY id DESC
            LIMIT 20
            """,
        ).fetchall()

        mpv_restarts = self._conn.execute(
            "SELECT COUNT(*) as cnt FROM events WHERE event_type='mpv_restart'"
        ).fetchone()["cnt"]

        config_reloads = self._conn.execute(
            "SELECT COUNT(*) as cnt FROM events WHERE event_type='config_reloaded'"
        ).fetchone()["cnt"]

        config_failures = self._conn.execute(
            "SELECT COUNT(*) as cnt FROM events WHERE event_type='config_reload_failed'"
        ).fetchone()["cnt"]

        weather_failures = self._conn.execute(
            "SELECT COUNT(*) as cnt FROM events WHERE event_type LIKE '%weather%' AND severity='WARNING'"
        ).fetchone()["cnt"]

        return {
            "mpv_restarts": mpv_restarts,
            "config_reloads": config_reloads,
            "config_failures": config_failures,
            "weather_failures": weather_failures,
            "recent_errors": [
                {
                    "occurred_at": r["occurred_at"],
                    "event_type": r["event_type"],
                    "payload": json.loads(r["payload_json"]) if r["payload_json"] else {},
                }
                for r in recent_errors
            ],
        }

    def config_change_history(self, limit: int = 20) -> list[dict]:
        rows = self._conn.execute(
            """
            SELECT occurred_at, event_type, payload_json
            FROM events
            WHERE event_type IN ('config_reloaded', 'config_reload_failed')
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [
            {
                "occurred_at": r["occurred_at"],
                "event_type": r["event_type"],
                "payload": json.loads(r["payload_json"]) if r["payload_json"] else {},
            }
            for r in rows
        ]

    def event_log(self, limit: int = 50, severity: str | None = None) -> list[dict]:
        if severity:
            rows = self._conn.execute(
                "SELECT occurred_at, event_type, severity, payload_json FROM events WHERE severity=? ORDER BY id DESC LIMIT ?",
                (severity, limit),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT occurred_at, event_type, severity, payload_json FROM events ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [
            {
                "occurred_at": r["occurred_at"],
                "event_type": r["event_type"],
                "severity": r["severity"],
                "payload": json.loads(r["payload_json"]) if r["payload_json"] else {},
            }
            for r in rows
        ]
