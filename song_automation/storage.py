from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from song_automation.domain import OverrideRecord


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Storage:
    def __init__(self, root: str | Path) -> None:
        root_path = Path(root)
        root_path.mkdir(parents=True, exist_ok=True)
        self.db_path = root_path / "controller.db"
        self.connection = sqlite3.connect(self.db_path, check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        self._initialize()

    def _initialize(self) -> None:
        self.connection.execute("PRAGMA journal_mode=WAL")
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS playback_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                started_at TEXT NOT NULL,
                ended_at TEXT,
                slot_id TEXT,
                playlist_id TEXT,
                trigger_reason TEXT NOT NULL,
                outcome TEXT NOT NULL
            )
            """
        )
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS overrides (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                playlist_id TEXT,
                stop_playback INTEGER NOT NULL DEFAULT 0,
                note TEXT,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL
            )
            """
        )
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                occurred_at TEXT NOT NULL,
                event_type TEXT NOT NULL,
                severity TEXT NOT NULL,
                payload_json TEXT
            )
            """
        )
        self.connection.commit()

    def log_event(self, event_type: str, severity: str = "INFO", payload: dict | None = None) -> None:
        self.connection.execute(
            """
            INSERT INTO events (occurred_at, event_type, severity, payload_json)
            VALUES (?, ?, ?, ?)
            """,
            (utc_now().isoformat(), event_type, severity, json.dumps(payload or {}, sort_keys=True)),
        )
        self.connection.commit()

    def start_session(self, slot_id: str | None, playlist_id: str | None, trigger_reason: str) -> None:
        self.connection.execute(
            """
            INSERT INTO playback_sessions (started_at, slot_id, playlist_id, trigger_reason, outcome)
            VALUES (?, ?, ?, ?, ?)
            """,
            (utc_now().isoformat(), slot_id, playlist_id, trigger_reason, "running"),
        )
        self.connection.commit()

    def finish_open_sessions(self, outcome: str) -> None:
        self.connection.execute(
            """
            UPDATE playback_sessions
            SET ended_at = ?, outcome = ?
            WHERE ended_at IS NULL
            """,
            (utc_now().isoformat(), outcome),
        )
        self.connection.commit()

    def create_override(
        self,
        playlist_id: str | None,
        stop_playback: bool,
        note: str | None,
        expires_at: datetime,
    ) -> None:
        self.connection.execute(
            """
            INSERT INTO overrides (playlist_id, stop_playback, note, created_at, expires_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (playlist_id, int(stop_playback), note, utc_now().isoformat(), expires_at.astimezone(timezone.utc).isoformat()),
        )
        self.connection.commit()

    def clear_overrides(self) -> None:
        self.connection.execute("DELETE FROM overrides")
        self.connection.commit()

    def clear_expired_overrides(self, now_utc: datetime) -> None:
        self.connection.execute("DELETE FROM overrides WHERE expires_at < ?", (now_utc.isoformat(),))
        self.connection.commit()

    def get_active_override(self, now_utc: datetime) -> OverrideRecord | None:
        row = self.connection.execute(
            """
            SELECT playlist_id, stop_playback, note, expires_at
            FROM overrides
            WHERE expires_at >= ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (now_utc.isoformat(),),
        ).fetchone()
        if row is None:
            return None

        return OverrideRecord(
            playlist_id=row["playlist_id"],
            stop_playback=bool(row["stop_playback"]),
            note=row["note"],
            expires_at=datetime.fromisoformat(row["expires_at"]),
        )

    def recent_playlist_ids(self, limit: int) -> list[str]:
        rows = self.connection.execute(
            """
            SELECT playlist_id
            FROM playback_sessions
            WHERE playlist_id IS NOT NULL
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [str(row["playlist_id"]) for row in rows]
