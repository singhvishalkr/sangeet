from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, timezone

from song_automation.domain import CandidateScore, DecisionContext, DecisionTrace, ResolvedDecision

logger = logging.getLogger(__name__)


class DecisionStore:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._conn = connection
        self._ensure_table()

    def _ensure_table(self) -> None:
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS decision_traces (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                occurred_at TEXT NOT NULL,
                action TEXT NOT NULL,
                slot_id TEXT,
                playlist_id TEXT,
                reason TEXT NOT NULL,
                reasons_json TEXT NOT NULL,
                candidates_json TEXT NOT NULL,
                context_json TEXT NOT NULL
            )
            """
        )
        self._conn.commit()

    def record(
        self,
        decision: ResolvedDecision,
        candidates: list[CandidateScore],
        context: DecisionContext,
    ) -> None:
        now_utc = datetime.now(timezone.utc).isoformat()
        candidates_data = [
            {"playlist_id": c.playlist.id, "score": c.score, "reasons": c.reasons}
            for c in candidates
        ]
        context_data = {
            "now": context.now.isoformat(),
            "holiday_names": context.holiday_names,
            "weather": {
                "temperature_c": context.weather.temperature_c,
                "precipitation": context.weather.precipitation,
                "cloud_cover": context.weather.cloud_cover,
                "wind_speed_kmh": context.weather.wind_speed_kmh,
                "is_day": context.weather.is_day,
                "tags": sorted(context.weather.tags),
            } if context.weather else None,
        }
        self._conn.execute(
            """
            INSERT INTO decision_traces
                (occurred_at, action, slot_id, playlist_id, reason, reasons_json, candidates_json, context_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                now_utc,
                decision.action,
                decision.slot.id if decision.slot else None,
                decision.playlist.id if decision.playlist else None,
                decision.reason,
                json.dumps(decision.reasons),
                json.dumps(candidates_data),
                json.dumps(context_data),
            ),
        )
        self._conn.commit()

    def recent(self, limit: int = 20) -> list[DecisionTrace]:
        rows = self._conn.execute(
            """
            SELECT occurred_at, action, slot_id, playlist_id, reason,
                   reasons_json, candidates_json, context_json
            FROM decision_traces
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        traces = []
        for row in rows:
            traces.append(DecisionTrace(
                timestamp=datetime.fromisoformat(row["occurred_at"]),
                action=row["action"],
                slot_id=row["slot_id"],
                playlist_id=row["playlist_id"],
                reason=row["reason"],
                reasons=json.loads(row["reasons_json"]),
                candidates=json.loads(row["candidates_json"]),
                context_snapshot=json.loads(row["context_json"]),
            ))
        return traces
