"""Playlist health scoring and stale track management.

Tracks playlist-level and track-level health metrics based on play history,
skip rates, and recency. Provides quarantine recommendations for stale or
poorly-performing tracks without auto-deleting anything.
"""
from __future__ import annotations

import json
import logging
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

STALE_THRESHOLD_DAYS = 60
LOW_HEALTH_THRESHOLD = 25
QUARANTINE_DIR_NAME = "_quarantine"


@dataclass(slots=True)
class TrackHealth:
    path: str
    play_count: int = 0
    skip_count: int = 0
    last_played: datetime | None = None
    health_score: int = 100
    reasons: list[str] = field(default_factory=list)

    @property
    def is_stale(self) -> bool:
        if self.last_played is None:
            return self.play_count == 0
        days_since = (datetime.now(timezone.utc) - self.last_played).days
        return days_since > STALE_THRESHOLD_DAYS

    @property
    def skip_rate(self) -> float:
        total = self.play_count + self.skip_count
        if total == 0:
            return 0.0
        return self.skip_count / total


@dataclass(slots=True)
class PlaylistHealthReport:
    playlist_id: str
    total_tracks: int
    healthy_tracks: int
    stale_tracks: int
    low_health_tracks: int
    missing_tracks: int
    overall_score: int
    track_details: list[TrackHealth] = field(default_factory=list)


class PlaylistHealthService:
    """Analyzes playlist health and manages stale track quarantine."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._conn = connection
        self._ensure_tables()

    def _ensure_tables(self) -> None:
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS track_plays (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                occurred_at TEXT NOT NULL,
                playlist_id TEXT NOT NULL,
                track_path TEXT NOT NULL,
                action TEXT NOT NULL,
                duration_seconds REAL
            )
            """
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS quarantined_tracks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                quarantined_at TEXT NOT NULL,
                original_path TEXT NOT NULL,
                playlist_id TEXT,
                reason TEXT NOT NULL,
                health_score INTEGER
            )
            """
        )
        self._conn.commit()

    def record_play(self, playlist_id: str, track_path: str, action: str = "play", duration: float | None = None) -> None:
        self._conn.execute(
            "INSERT INTO track_plays (occurred_at, playlist_id, track_path, action, duration_seconds) VALUES (?, ?, ?, ?, ?)",
            (datetime.now(timezone.utc).isoformat(), playlist_id, track_path, action, duration),
        )
        self._conn.commit()

    def analyze_playlist(self, playlist_id: str, track_paths: list[str]) -> PlaylistHealthReport:
        """Score every track in a playlist and produce a health report."""
        details: list[TrackHealth] = []
        missing = 0

        for path_str in track_paths:
            p = Path(path_str)
            th = TrackHealth(path=path_str)

            if not p.exists():
                th.health_score = 0
                th.reasons.append("file_missing")
                missing += 1
                details.append(th)
                continue

            plays = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM track_plays WHERE track_path=? AND action='play'",
                (path_str,),
            ).fetchone()["cnt"]
            skips = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM track_plays WHERE track_path=? AND action='skip'",
                (path_str,),
            ).fetchone()["cnt"]
            last = self._conn.execute(
                "SELECT occurred_at FROM track_plays WHERE track_path=? ORDER BY id DESC LIMIT 1",
                (path_str,),
            ).fetchone()

            th.play_count = plays
            th.skip_count = skips
            if last:
                th.last_played = datetime.fromisoformat(last["occurred_at"])

            th.health_score = self._compute_score(th)
            details.append(th)

        stale = sum(1 for t in details if t.is_stale)
        low_health = sum(1 for t in details if t.health_score < LOW_HEALTH_THRESHOLD)
        healthy = sum(1 for t in details if t.health_score >= 50)
        overall = round(sum(t.health_score for t in details) / max(len(details), 1))

        return PlaylistHealthReport(
            playlist_id=playlist_id,
            total_tracks=len(track_paths),
            healthy_tracks=healthy,
            stale_tracks=stale,
            low_health_tracks=low_health,
            missing_tracks=missing,
            overall_score=overall,
            track_details=details,
        )

    def get_quarantine_candidates(self, playlist_id: str, track_paths: list[str]) -> list[TrackHealth]:
        """Return tracks that should be considered for removal."""
        report = self.analyze_playlist(playlist_id, track_paths)
        return [t for t in report.track_details if t.health_score < LOW_HEALTH_THRESHOLD]

    def quarantine_track(self, track_path: str, playlist_id: str | None, reason: str, health_score: int) -> bool:
        """Move a track to the quarantine folder and record it."""
        src = Path(track_path)
        if not src.exists():
            return False

        quarantine_dir = src.parent / QUARANTINE_DIR_NAME
        quarantine_dir.mkdir(exist_ok=True)
        dest = quarantine_dir / src.name

        try:
            src.rename(dest)
        except OSError:
            logger.warning("Failed to quarantine %s", track_path, exc_info=True)
            return False

        self._conn.execute(
            "INSERT INTO quarantined_tracks (quarantined_at, original_path, playlist_id, reason, health_score) VALUES (?, ?, ?, ?, ?)",
            (datetime.now(timezone.utc).isoformat(), track_path, playlist_id, reason, health_score),
        )
        self._conn.commit()
        logger.info("Quarantined: %s (reason=%s, score=%d)", src.name, reason, health_score)
        return True

    def restore_track(self, original_path: str) -> bool:
        """Restore a quarantined track to its original location."""
        src = Path(original_path)
        quarantine_path = src.parent / QUARANTINE_DIR_NAME / src.name
        if not quarantine_path.exists():
            return False

        try:
            quarantine_path.rename(src)
        except OSError:
            logger.warning("Failed to restore %s", original_path, exc_info=True)
            return False

        self._conn.execute("DELETE FROM quarantined_tracks WHERE original_path=?", (original_path,))
        self._conn.commit()
        logger.info("Restored: %s", src.name)
        return True

    def list_quarantined(self) -> list[dict]:
        rows = self._conn.execute(
            "SELECT quarantined_at, original_path, playlist_id, reason, health_score FROM quarantined_tracks ORDER BY quarantined_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]

    def _compute_score(self, track: TrackHealth) -> int:
        """Compute a 0-100 health score for a track."""
        score = 50  # baseline

        # Recency bonus/penalty
        if track.last_played:
            days_ago = (datetime.now(timezone.utc) - track.last_played).days
            if days_ago <= 7:
                score += 20
                track.reasons.append("recently_played")
            elif days_ago <= 30:
                score += 10
            elif days_ago > STALE_THRESHOLD_DAYS:
                score -= 25
                track.reasons.append("stale")
        else:
            score -= 15
            track.reasons.append("never_played")

        # Play count bonus
        if track.play_count >= 10:
            score += 15
            track.reasons.append("popular")
        elif track.play_count >= 3:
            score += 5

        # Skip penalty
        if track.skip_rate > 0.6:
            score -= 30
            track.reasons.append("high_skip_rate")
        elif track.skip_rate > 0.3:
            score -= 15
            track.reasons.append("moderate_skip_rate")

        return max(0, min(100, score))
