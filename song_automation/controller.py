from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler

from song_automation.analytics import AnalyticsService
from song_automation.config_loader import ConfigError, ConfigRepository
from song_automation.playlist_health import PlaylistHealthService
from song_automation.context import ContextService
from song_automation.decision_store import DecisionStore
from song_automation.domain import PlaybackSnapshot, ResolvedDecision
from song_automation.environment import RoomModeService
from song_automation.feedback import FeedbackStore
from song_automation.mood import MoodService
from song_automation.domain_events import (
    CONFIG_RELOADED,
    DECISION_MADE,
    MPV_RESTARTED,
    OVERRIDE_APPLIED,
    OVERRIDE_CLEARED,
    PLAYLIST_STARTED,
    PLAYLIST_STOPPED,
    DomainEvent,
    event_bus,
)
from song_automation.discovery import DiscoveryScheduler, load_cached, scan_trending
from song_automation.playback import build_playback_gateway
from song_automation.resolver import Resolver
from song_automation.storage import Storage

logger = logging.getLogger(__name__)


class MusicController:
    def __init__(self, config_path: str | Path, dry_run_override: bool | None = None) -> None:
        self.config_repository = ConfigRepository(config_path)
        self.config = self.config_repository.load()
        if dry_run_override is not None:
            self.config.player.dry_run = dry_run_override

        self._lock = threading.RLock()
        self._scheduler = BackgroundScheduler(timezone=self.config.timezone)
        self._storage = Storage(Path("data"))
        self._decision_store = DecisionStore(self._storage.connection)
        self._feedback = FeedbackStore(self._storage.connection)
        self._analytics = AnalyticsService(self._storage.connection)
        self._playlist_health = PlaylistHealthService(self._storage.connection)
        self._mood = MoodService()
        self._room = RoomModeService(self.config)
        self._context = ContextService(self.config)
        self._resolver = Resolver(self.config, preference_fn=self._get_preference_weight)
        self._playback = build_playback_gateway(self.config.player, dual=self.config.features.dual_player)
        self._tz = ZoneInfo(self.config.timezone)
        self._last_transition_at: datetime | None = None
        self._last_decision: ResolvedDecision | None = None
        self._running = False
        self._ramp_thread: threading.Thread | None = None
        self._ramp_cancel = threading.Event()
        self._user_volume_override = False
        self._sleep_timer_target: datetime | None = None
        self._discovery = DiscoveryScheduler()

    @property
    def playback_snapshot(self) -> PlaybackSnapshot:
        return self._playback.snapshot

    def _get_preference_weight(self, playlist_id: str, slot_id: str | None) -> float:
        try:
            return self._feedback.get_weight(playlist_id, slot_id)
        except Exception:
            return 0.0

    def _emit(self, event_type: str, **payload) -> None:
        event_bus.publish(DomainEvent(
            event_type=event_type,
            timestamp=datetime.now(self._tz),
            payload=payload,
        ))

    def start(self) -> None:
        with self._lock:
            if self._running:
                return
            logger.info("Starting controller (tz=%s, reconcile=%ds)", self.config.timezone, self.config.defaults.reconcile_seconds)
            self._playback.ensure_started()
            if hasattr(self._playback, "on_skip"):
                self._playback.on_skip = self._on_track_skip
            self._scheduler.add_job(self.reconcile, "interval", seconds=self.config.defaults.reconcile_seconds, max_instances=1)
            self._scheduler.start()
            self._running = True
            self._storage.log_event("controller_started", payload={"timezone": self.config.timezone})
            self._discovery.start()
            self.reconcile(force=True, trigger_reason="startup")

    def stop(self) -> None:
        with self._lock:
            logger.info("Stopping controller")
            if self._running:
                self._scheduler.shutdown(wait=False)
                self._running = False
            self._discovery.stop()
            self._playback.shutdown()
            self._storage.finish_open_sessions("stopped")

    def reconcile(self, *, force: bool = False, trigger_reason: str = "tick") -> dict:
        with self._lock:
            self._reload_config_if_changed()
            self._check_playback_health()
            self._check_sleep_timer()
            if hasattr(self._playback, "check_track_skip"):
                self._playback.check_track_skip()

            now_local = datetime.now(self._tz)
            now_utc = now_local.astimezone(timezone.utc)
            self._storage.clear_expired_overrides(now_utc)

            context = self._context.build(now_local)
            if self.config.features.mood_context and not self._mood.current.is_stale:
                context.mood_tags = self._mood.current.tags
            if self.config.features.room_modes:
                context.mood_tags = context.mood_tags | self._room.get_mode_tags()

            if self._room.is_quiet_hours(now_local):
                active_override = None
                decision = ResolvedDecision(
                    action="stop" if self.config.quiet_hours.stop_playback else "play",
                    reason="quiet_hours",
                    reasons=["quiet hours active"],
                )
                if decision.action == "stop":
                    self._apply_decision(decision, trigger_reason="quiet_hours", transition_time=now_local)
                    self._last_decision = decision
                    return self.status_payload()

            active_override = self._storage.get_active_override(now_utc)
            recent_playlist_ids = self._storage.recent_playlist_ids(self.config.smart_rotation.recent_session_window)
            decision = self._resolver.resolve(context, active_override, recent_playlist_ids)

            if self._room.is_quiet_hours(now_local) and decision.action == "play" and decision.playlist:
                max_vol = self.config.quiet_hours.max_volume
                if decision.target_volume > max_vol:
                    decision.target_volume = max_vol
                    decision.reasons.append(f"quiet_hours:capped_to_{max_vol}")

            try:
                self._decision_store.record(decision, self._resolver.last_candidates, context)
            except Exception:
                logger.warning("Failed to record decision trace", exc_info=True)

            if not force and self._should_skip_transition(decision, now_local):
                return self.status_payload(preview=decision)

            self._apply_decision(decision, trigger_reason=trigger_reason, transition_time=now_local)
            self._last_decision = decision
            return self.status_payload()

    def preview(self) -> dict:
        with self._lock:
            now_local = datetime.now(self._tz)
            now_utc = now_local.astimezone(timezone.utc)
            context = self._context.build(now_local)
            active_override = self._storage.get_active_override(now_utc)
            recent_playlist_ids = self._storage.recent_playlist_ids(self.config.smart_rotation.recent_session_window)
            decision = self._resolver.resolve(context, active_override, recent_playlist_ids)
            return self.status_payload(preview=decision)

    def apply_override(
        self,
        *,
        playlist_id: str | None,
        stop_playback: bool,
        ttl_minutes: int,
        note: str | None,
    ) -> dict:
        with self._lock:
            expires_at = datetime.now(timezone.utc) + timedelta(minutes=ttl_minutes)
            self._storage.create_override(
                playlist_id=playlist_id,
                stop_playback=stop_playback,
                note=note,
                expires_at=expires_at,
            )
            self._storage.log_event(
                "override_applied",
                payload={
                    "playlist_id": playlist_id,
                    "stop_playback": stop_playback,
                    "ttl_minutes": ttl_minutes,
                },
            )
            self._emit(OVERRIDE_APPLIED, playlist_id=playlist_id, stop_playback=stop_playback)
            return self.reconcile(force=True, trigger_reason="override")

    def clear_override(self) -> dict:
        with self._lock:
            self._storage.clear_overrides()
            self._storage.log_event("override_cleared")
            self._emit(OVERRIDE_CLEARED)
            return self.reconcile(force=True, trigger_reason="override_cleared")

    def status_payload(self, preview: ResolvedDecision | None = None) -> dict:
        decision = preview or self._last_decision
        playlist_name = None
        playlist_tags: list[str] = []
        snap = self._playback.snapshot
        if snap.playlist_id == "__discover__":
            playlist_name = "Discover"
            playlist_tags = ["discover", "streaming"]
        elif decision and decision.playlist:
            playlist_name = decision.playlist.name
            playlist_tags = list(decision.playlist.tags)

        now_local = datetime.now(self._tz)
        snap = self._playback.snapshot
        track = snap.track
        try:
            self._playback.poll_track_info()
            track = snap.track
        except Exception:
            pass

        return {
            "controller_running": self._running,
            "server_time": now_local.isoformat(),
            "dry_run": self.config.player.dry_run,
            "current": {
                "playlist_id": snap.playlist_id,
                "playlist_name": playlist_name,
                "slot_id": snap.slot_id,
                "volume": snap.volume,
                "tags": playlist_tags,
                "started_at": snap.started_at.isoformat() if snap.started_at else None,
                "is_paused": snap.is_paused,
                "track_title": track.title,
                "track_position": round(track.position, 1) if track.position else 0,
                "track_duration": round(track.duration, 1) if track.duration else 0,
                "playlist_pos": track.playlist_pos,
                "playlist_count": track.playlist_count,
            },
            "decision": {
                "action": decision.action if decision else None,
                "slot_id": decision.slot.id if decision and decision.slot else None,
                "slot_name": decision.slot.name if decision and decision.slot else None,
                "playlist_id": decision.playlist.id if decision and decision.playlist else None,
                "playlist_name": playlist_name,
                "reason": decision.reason if decision else None,
                "reasons": decision.reasons if decision else [],
            },
            "room_mode": self._room.current_mode,
            "quiet_hours_active": self._room.is_quiet_hours(now_local),
            "sleep_timer": self.get_sleep_timer(),
        }

    def pause_playback(self) -> dict:
        """Instantly pause mpv — no fade, no override. Resumes from same position."""
        with self._lock:
            self._playback.pause()
            self._storage.log_event("playback_paused")
            return self.status_payload()

    def resume_playback(self) -> dict:
        """Instantly resume mpv from paused position."""
        with self._lock:
            self._playback.resume()
            self._storage.log_event("playback_resumed")
            return self.status_payload()

    def get_track_info(self) -> dict:
        """Poll mpv for current track metadata."""
        info = self._playback.poll_track_info()
        return {
            "title": info.title,
            "position": round(info.position, 1),
            "duration": round(info.duration, 1),
            "playlist_pos": info.playlist_pos,
            "playlist_count": info.playlist_count,
        }

    def smart_play(self) -> dict:
        """Pick the best playlist using mood/room context even when no schedule slot is active.

        Always considers mood and room mode tags regardless of feature flags,
        since the user is explicitly requesting an intelligent pick.
        """
        with self._lock:
            now_local = datetime.now(self._tz)
            context = self._context.build(now_local)

            tags: set[str] = set()
            if not self._mood.current.is_stale:
                tags |= self._mood.current.tags
            tags |= self._room.get_mode_tags()

            recent = self._storage.recent_playlist_ids(self.config.smart_rotation.recent_session_window)
            enabled = [p for p in self.config.playlists if p.enabled]
            if not enabled:
                return self.status_payload()

            scored: list[tuple[int, str]] = []
            for p in enabled:
                score = 0
                playlist_tags = set(p.tags)
                if tags:
                    matches = tags & playlist_tags
                    score += len(matches) * 15
                if p.id not in recent:
                    score += self.config.smart_rotation.freshness_bonus
                elif recent and recent[0] == p.id:
                    score -= self.config.smart_rotation.same_playlist_penalty
                scored.append((score, p.id))

            scored.sort(key=lambda x: x[0], reverse=True)
            logger.info(
                "Smart play: room=%s, tags=%s, top3=%s",
                self._room.current_mode,
                sorted(tags),
                [(s, pid) for s, pid in scored[:3]],
            )

            best_id = scored[0][1] if scored else None
            if best_id:
                return self.apply_override(
                    playlist_id=best_id,
                    stop_playback=False,
                    ttl_minutes=120,
                    note="smart_play",
                )
            return self.status_payload()

    def set_sleep_timer(self, minutes: int) -> dict:
        """Schedule playback to stop after the given minutes."""
        with self._lock:
            target = datetime.now(self._tz) + timedelta(minutes=minutes)
            self._sleep_timer_target = target
            self._storage.log_event("sleep_timer_set", payload={"minutes": minutes})
            return {"ok": True, "stops_at": target.isoformat(), "minutes": minutes}

    def clear_sleep_timer(self) -> dict:
        with self._lock:
            self._sleep_timer_target = None
            self._storage.log_event("sleep_timer_cleared")
            return {"ok": True}

    def get_sleep_timer(self) -> dict:
        target = getattr(self, "_sleep_timer_target", None)
        if target is None:
            return {"active": False}
        now = datetime.now(self._tz)
        remaining = max(0, (target - now).total_seconds())
        return {"active": remaining > 0, "remaining_seconds": round(remaining), "stops_at": target.isoformat()}

    def _check_sleep_timer(self) -> None:
        target = getattr(self, "_sleep_timer_target", None)
        if target is None:
            return
        now = datetime.now(self._tz)
        if now >= target:
            self._sleep_timer_target = None
            if self._playback.snapshot.playlist_id:
                self._playback.fade_to(0, 10)
                self._playback.stop()
                self._storage.finish_open_sessions("sleep_timer")
                self._storage.log_event("sleep_timer_triggered")

    def set_user_volume(self, volume: int) -> None:
        """User manually set volume -- cancel any active ramp and respect their choice."""
        self._user_volume_override = True
        self._cancel_ramp()
        self._playback.set_volume(volume)
        self._playback.snapshot.volume = volume

    def _on_track_skip(self, playlist_id: str, elapsed: float) -> None:
        logger.info("Track skip detected: playlist=%s, elapsed=%.1fs", playlist_id, elapsed)
        slot_id = self._playback.snapshot.slot_id
        self._feedback.record(
            signal="skip",
            playlist_id=playlist_id,
            slot_id=slot_id,
            payload={"elapsed_seconds": round(elapsed, 1)},
        )

    def _check_playback_health(self) -> None:
        if self._playback.is_healthy():
            return
        logger.warning("Playback process unhealthy — restarting mpv")
        self._storage.log_event("mpv_restart", severity="WARNING", payload={"reason": "health_check_failed"})
        try:
            self._playback.ensure_started()
            self._emit(MPV_RESTARTED)
        except Exception:
            logger.exception("Failed to restart mpv")
            return
        if self._last_decision and self._last_decision.action == "play":
            logger.info("Re-applying last decision after mpv restart")
            self._apply_decision(
                self._last_decision,
                trigger_reason="mpv_recovery",
                transition_time=datetime.now(self._tz),
            )

    def _reload_config_if_changed(self) -> None:
        try:
            updated = self.config_repository.reload_if_changed()
        except ConfigError as exc:
            self._storage.log_event("config_reload_failed", severity="ERROR", payload={"error": str(exc)})
            return

        if updated is self.config:
            return

        self.config = updated
        self._context = ContextService(self.config)
        self._resolver = Resolver(self.config, preference_fn=self._get_preference_weight)
        self._storage.log_event("config_reloaded")
        self._emit(CONFIG_RELOADED)

    def _should_skip_transition(self, decision: ResolvedDecision, now_local: datetime) -> bool:
        current = self._playback.snapshot
        if decision.action == "stop" and current.playlist_id is None:
            return True
        if decision.action == "play" and current.playlist_id == (decision.playlist.id if decision.playlist else None):
            return True
        if self._last_transition_at is None:
            return False
        minimum_gap = timedelta(minutes=self.config.defaults.min_switch_interval_minutes)
        if now_local - self._last_transition_at < minimum_gap:
            if self._last_decision and self._last_decision.slot and decision.slot and self._last_decision.slot.id == decision.slot.id:
                return True
        return False

    def _apply_decision(self, decision: ResolvedDecision, *, trigger_reason: str, transition_time: datetime) -> None:
        current = self._playback.snapshot
        transition = decision.transition or self.config.defaults.transition

        if decision.action == "stop":
            self._cancel_ramp()
            if current.playlist_id is not None:
                self._playback.fade_to(0, transition.fade_out_seconds, transition.curve)
                self._playback.stop()
                self._storage.finish_open_sessions("stopped")
                self._storage.log_event("playback_stopped", payload={"reason": decision.reason})
            self._playback.snapshot.slot_id = None
            self._last_transition_at = transition_time
            self._user_volume_override = False
            return

        if decision.playlist is None:
            return

        same_playlist = current.playlist_id == decision.playlist.id

        if current.playlist_id and not same_playlist:
            self._playback.fade_to(0, transition.fade_out_seconds, transition.curve)
            self._storage.finish_open_sessions("replaced")

        if same_playlist and self._user_volume_override:
            logger.info("Keeping user volume override (%d) for same playlist", current.volume)
            self._playback.snapshot.slot_id = decision.slot.id if decision.slot else None
            self._last_transition_at = transition_time
            return

        self._cancel_ramp()

        if not same_playlist:
            self._user_volume_override = False
            self._playback.load_playlist(decision.playlist)
            self._playback.set_volume(decision.playlist.volume_profile.start)
        else:
            if not self._user_volume_override:
                pass

        self._playback.snapshot.slot_id = decision.slot.id if decision.slot else None
        self._playback.snapshot.started_at = transition_time
        self._playback.snapshot.last_reason = decision.reason

        if not same_playlist:
            ramp_minutes = decision.playlist.volume_profile.ramp_minutes
            if ramp_minutes > 0 and decision.playlist.volume_profile.start != decision.target_volume:
                self._start_ramp(
                    from_volume=decision.playlist.volume_profile.start,
                    to_volume=decision.target_volume,
                    duration_minutes=ramp_minutes,
                )

        self._storage.start_session(
            slot_id=decision.slot.id if decision.slot else None,
            playlist_id=decision.playlist.id,
            trigger_reason=trigger_reason,
        )
        self._storage.log_event(
            "playlist_started",
            payload={
                "slot_id": decision.slot.id if decision.slot else None,
                "playlist_id": decision.playlist.id,
                "reason": decision.reason,
                "details": decision.reasons,
            },
        )
        self._last_transition_at = transition_time

    def _start_ramp(self, *, from_volume: int, to_volume: int, duration_minutes: int) -> None:
        self._ramp_cancel.clear()
        step_interval = 15
        total_seconds = duration_minutes * 60
        steps = max(total_seconds // step_interval, 1)

        def _ramp_worker() -> None:
            for step in range(1, steps + 1):
                if self._ramp_cancel.wait(timeout=step_interval):
                    return
                if self._user_volume_override:
                    logger.info("Volume ramp stopped: user set volume manually")
                    return
                next_vol = round(from_volume + (to_volume - from_volume) * (step / steps))
                try:
                    self._playback.set_volume(next_vol)
                except Exception:
                    logger.warning("Volume ramp step failed", exc_info=True)
                    return
            logger.info("Volume ramp complete: %d -> %d over %d min", from_volume, to_volume, duration_minutes)

        self._ramp_thread = threading.Thread(target=_ramp_worker, daemon=True, name="volume-ramp")
        self._ramp_thread.start()

    def _cancel_ramp(self) -> None:
        self._ramp_cancel.set()
        if self._ramp_thread and self._ramp_thread.is_alive():
            self._ramp_thread.join(timeout=5)
        self._ramp_thread = None

    def _get_trending_suggestions(self) -> dict:
        """Return cached trending data instantly; trigger background scan if stale."""
        cached = load_cached()
        if cached:
            return cached
        import threading
        threading.Thread(target=scan_trending, daemon=True).start()
        return {"categories": {}, "last_scan": None, "scanning": True}

    def _add_trending_song(self, playlist_id: str, url: str, background: bool = False) -> dict:
        """Download a song via yt-dlp and add to an m3u playlist.

        If background=True, starts download in a thread and returns immediately.
        """
        import subprocess
        import threading

        playlist = next((p for p in self.config.playlists if p.id == playlist_id), None)
        if not playlist:
            return {"ok": False, "error": f"Playlist {playlist_id} not found"}

        music_dir = Path(playlist.source.value).parent
        music_dir.mkdir(parents=True, exist_ok=True)

        def _do_download():
            before_files = set(music_dir.glob("*.mp3"))
            try:
                result = subprocess.run(
                    [
                        "yt-dlp",
                        "--extract-audio",
                        "--audio-format", "mp3",
                        "--audio-quality", "0",
                        "-o", str(music_dir / "%(title)s.%(ext)s"),
                        "--no-playlist",
                        "--no-overwrites",
                        url,
                    ],
                    capture_output=True, text=True, timeout=180,
                )
                if result.returncode != 0:
                    err = result.stderr.strip()
                    if "already been downloaded" in (result.stdout + result.stderr).lower():
                        return {"ok": True, "message": "Song already exists in library"}
                    return {"ok": False, "error": err[:500] if err else "Download failed"}

                after_files = set(music_dir.glob("*.mp3"))
                new_files = after_files - before_files
                if new_files:
                    filepath = str(next(iter(new_files)))
                else:
                    for line in reversed(result.stdout.strip().split("\n")):
                        line = line.strip()
                        if line and Path(line).exists():
                            filepath = line
                            break
                    else:
                        all_mp3 = sorted(music_dir.glob("*.mp3"), key=lambda f: f.stat().st_mtime, reverse=True)
                        if all_mp3:
                            filepath = str(all_mp3[0])
                        else:
                            logger.warning("yt-dlp succeeded but no mp3 found. stdout: %s", result.stdout[-300:])
                            return {"ok": False, "error": "Download completed but file not found."}

                m3u_path = Path(playlist.source.value)
                existing = m3u_path.read_text(encoding="utf-8") if m3u_path.exists() else ""
                if filepath not in existing:
                    with open(m3u_path, "a", encoding="utf-8") as f:
                        f.write(f"\n{filepath}")
                self._storage.log_event("trending_song_added", payload={
                    "playlist_id": playlist_id, "url": url, "file": filepath,
                })
                return {"ok": True, "file": filepath, "playlist_id": playlist_id}
            except FileNotFoundError:
                return {"ok": False, "error": "yt-dlp not installed. Run: pip install yt-dlp"}
            except subprocess.TimeoutExpired:
                return {"ok": False, "error": "Download timed out (3 min limit)"}
            except Exception as exc:
                logger.exception("Failed to add trending song: %s", url)
                return {"ok": False, "error": str(exc)}

        if background:
            def _bg():
                r = _do_download()
                logger.info("Background download complete: %s → %s", url, r.get("ok"))
            threading.Thread(target=_bg, daemon=True).start()
            return {"ok": True, "status": "downloading", "message": "Download started in background"}
        return _do_download()
