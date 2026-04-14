from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import unicodedata
import urllib.parse
import urllib.request
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from song_automation.controller import MusicController

_lyrics_logger = logging.getLogger(__name__ + ".lyrics")


class OverrideRequest(BaseModel):
    playlist_id: str | None = None
    stop_playback: bool = False
    ttl_minutes: int = Field(default=90, ge=1, le=1440)
    note: str | None = None


class FeedbackRequest(BaseModel):
    signal: str
    playlist_id: str | None = None
    slot_id: str | None = None
    track_info: str | None = None


class VolumeRequest(BaseModel):
    volume: int = Field(ge=0, le=100)


class MoodRequest(BaseModel):
    energy: int | None = Field(default=None, ge=1, le=5)
    valence: int | None = Field(default=None, ge=1, le=5)
    activity: str | None = None


class SleepTimerRequest(BaseModel):
    minutes: int = Field(ge=1, le=480)


class PlaybackSpeedRequest(BaseModel):
    speed: float = Field(ge=0.25, le=4.0)


class CrossfadeRequest(BaseModel):
    seconds: int = Field(ge=0, le=12)


class EqPresetRequest(BaseModel):
    preset: str


_ws_clients: set[WebSocket] = set()


async def _broadcast_status(controller: MusicController) -> None:
    """Periodically push status to all WebSocket clients."""
    while True:
        await asyncio.sleep(1)
        if not _ws_clients:
            continue
        try:
            payload = json.dumps(controller.status_payload())
        except Exception:
            continue
        disconnected = set()
        for client in _ws_clients.copy():
            try:
                await client.send_text(payload)
            except Exception:
                disconnected.add(client)
        _ws_clients -= disconnected


def create_app(controller: MusicController) -> FastAPI:
    @asynccontextmanager
    async def lifespan(_: FastAPI):
        controller.start()
        broadcast_task = asyncio.create_task(_broadcast_status(controller))
        try:
            yield
        finally:
            broadcast_task.cancel()
            controller.stop()

    app = FastAPI(title="Sangeet", lifespan=lifespan)

    static_dir = Path(__file__).resolve().parent.parent / "static"
    if static_dir.is_dir():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    def auth_dependency(x_auth_token: str | None = Header(default=None)) -> None:
        expected = controller.config.api.auth_token
        if expected and x_auth_token != expected:
            raise HTTPException(status_code=401, detail="missing or invalid auth token")

    @app.get("/", response_class=HTMLResponse)
    def dashboard() -> str:
        html_path = static_dir / "index.html"
        if html_path.is_file():
            return html_path.read_text(encoding="utf-8")
        return "<h1>Sangeet</h1><p>Static files not found. Check the static/ directory.</p>"

    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket) -> None:
        await websocket.accept()
        _ws_clients.add(websocket)
        try:
            payload = json.dumps(controller.status_payload())
            await websocket.send_text(payload)
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            pass
        finally:
            _ws_clients.discard(websocket)

    @app.get("/health")
    def health() -> dict:
        return {"ok": True}

    @app.get("/status")
    def status(_: None = Depends(auth_dependency)) -> dict:
        return controller.status_payload()

    @app.get("/preview")
    def preview(_: None = Depends(auth_dependency)) -> dict:
        return controller.preview()

    @app.post("/reconcile")
    def reconcile(_: None = Depends(auth_dependency)) -> dict:
        return controller.reconcile(force=True, trigger_reason="api_reconcile")

    @app.post("/override")
    def override(request: OverrideRequest, _: None = Depends(auth_dependency)) -> dict:
        if request.stop_playback and request.playlist_id:
            raise HTTPException(status_code=400, detail="stop_playback and playlist_id are mutually exclusive")
        if not request.stop_playback and not request.playlist_id:
            raise HTTPException(status_code=400, detail="playlist_id is required unless stop_playback is true")
        return controller.apply_override(
            playlist_id=request.playlist_id,
            stop_playback=request.stop_playback,
            ttl_minutes=request.ttl_minutes,
            note=request.note,
        )

    @app.delete("/override")
    def clear_override(_: None = Depends(auth_dependency)) -> dict:
        return controller.clear_override()

    @app.get("/decisions")
    def decisions(limit: int = 20, _: None = Depends(auth_dependency)) -> list[dict]:
        traces = controller._decision_store.recent(min(limit, 100))
        return [
            {
                "timestamp": t.timestamp.isoformat(),
                "action": t.action,
                "slot_id": t.slot_id,
                "playlist_id": t.playlist_id,
                "reason": t.reason,
                "reasons": t.reasons,
                "candidates": t.candidates,
                "context": t.context_snapshot,
            }
            for t in traces
        ]

    @app.post("/feedback")
    def submit_feedback(request: FeedbackRequest, _: None = Depends(auth_dependency)) -> dict:
        controller._feedback.record(
            signal=request.signal,
            playlist_id=request.playlist_id,
            slot_id=request.slot_id,
            track_info=request.track_info,
        )
        return {"ok": True}

    @app.get("/preferences")
    def get_preferences(_: None = Depends(auth_dependency)) -> dict:
        return controller._feedback.export_data()

    @app.delete("/preferences")
    def reset_preferences(_: None = Depends(auth_dependency)) -> dict:
        controller._feedback.reset()
        return {"ok": True, "message": "All preference weights reset"}

    @app.get("/mood")
    def get_mood(_: None = Depends(auth_dependency)) -> dict:
        return controller._mood.to_dict()

    @app.post("/mood")
    def set_mood(request: MoodRequest, _: None = Depends(auth_dependency)) -> dict:
        controller._mood.update(
            energy=request.energy,
            valence=request.valence,
            activity=request.activity,
        )
        return controller._mood.to_dict()

    @app.delete("/mood")
    def clear_mood(_: None = Depends(auth_dependency)) -> dict:
        controller._mood.clear()
        return {"ok": True, "message": "Mood cleared"}

    @app.get("/room")
    def get_room(_: None = Depends(auth_dependency)) -> dict:
        return controller._room.to_dict()

    @app.post("/room")
    def set_room_mode(mode: str, _: None = Depends(auth_dependency)) -> dict:
        controller._room.set_mode(mode)
        return controller._room.to_dict()

    @app.post("/volume")
    def set_volume(request: VolumeRequest, _: None = Depends(auth_dependency)) -> dict:
        controller.set_user_volume(request.volume)
        return {"ok": True, "volume": request.volume}

    @app.post("/pause")
    def pause_playback(_: None = Depends(auth_dependency)) -> dict:
        return controller.pause_playback()

    @app.post("/resume")
    def resume_playback(_: None = Depends(auth_dependency)) -> dict:
        return controller.resume_playback()

    @app.get("/track-info")
    def track_info(_: None = Depends(auth_dependency)) -> dict:
        return controller.get_track_info()

    @app.post("/skip")
    def skip_track(_: None = Depends(auth_dependency)) -> dict:
        try:
            controller._playback._send_command(["playlist-next"])
        except Exception:
            pass
        return {"ok": True}

    @app.post("/seek")
    def seek_track(position: float, _: None = Depends(auth_dependency)) -> dict:
        try:
            controller._playback._send_command(["set_property", "time-pos", position])
            return {"ok": True, "position": position}
        except Exception:
            return {"ok": False}

    @app.post("/previous")
    def previous_track(_: None = Depends(auth_dependency)) -> dict:
        try:
            controller._playback._send_command(["playlist-prev"])
        except Exception:
            pass
        return {"ok": True}

    @app.post("/smart-play")
    def smart_play(_: None = Depends(auth_dependency)) -> dict:
        return controller.smart_play()

    @app.post("/sleep-timer")
    def set_sleep_timer(request: SleepTimerRequest, _: None = Depends(auth_dependency)) -> dict:
        return controller.set_sleep_timer(request.minutes)

    @app.delete("/sleep-timer")
    def clear_sleep_timer(_: None = Depends(auth_dependency)) -> dict:
        return controller.clear_sleep_timer()

    @app.get("/sleep-timer")
    def get_sleep_timer(_: None = Depends(auth_dependency)) -> dict:
        return controller.get_sleep_timer()

    @app.post("/feedback/like")
    def like_track(request: FeedbackRequest, _: None = Depends(auth_dependency)) -> dict:
        controller._feedback.record(
            signal="like",
            playlist_id=request.playlist_id,
            slot_id=request.slot_id,
            track_info=request.track_info,
        )
        return {"ok": True}

    @app.post("/feedback/dislike")
    def dislike_track(request: FeedbackRequest, _: None = Depends(auth_dependency)) -> dict:
        controller._feedback.record(
            signal="dislike",
            playlist_id=request.playlist_id,
            slot_id=request.slot_id,
            track_info=request.track_info,
        )
        return {"ok": True}

    @app.get("/recently-played")
    def recently_played(limit: int = 5, _: None = Depends(auth_dependency)) -> list[dict]:
        recent_ids = controller._storage.recent_playlist_ids(min(limit, 20))
        seen = set()
        result = []
        for pid in recent_ids:
            if pid in seen:
                continue
            seen.add(pid)
            playlist = next((p for p in controller.config.playlists if p.id == pid), None)
            if playlist:
                result.append({"id": playlist.id, "name": playlist.name, "tags": playlist.tags})
            if len(result) >= limit:
                break
        return result

    @app.post("/shuffle")
    def toggle_shuffle(_: None = Depends(auth_dependency)) -> dict:
        try:
            snap = controller._playback.snapshot
            current_shuffle = getattr(snap, "_shuffle_on", True)
            new_val = not current_shuffle
            controller._playback._send_command(["set_property", "shuffle", new_val])
            snap._shuffle_on = new_val
            return {"ok": True, "shuffle": new_val}
        except Exception:
            return {"ok": False, "shuffle": True}

    @app.post("/repeat")
    def toggle_repeat(_: None = Depends(auth_dependency)) -> dict:
        try:
            snap = controller._playback.snapshot
            modes = ["no", "inf", "force"]
            current = getattr(snap, "_loop_mode", "no")
            idx = (modes.index(current) + 1) % len(modes) if current in modes else 0
            new_mode = modes[idx]
            controller._playback._send_command(["set_property", "loop-playlist", new_mode])
            snap._loop_mode = new_mode
            return {"ok": True, "repeat": new_mode}
        except Exception:
            return {"ok": False, "repeat": "no"}

    @app.get("/queue")
    def get_queue(_: None = Depends(auth_dependency)) -> dict:
        playlist_id = controller._playback.snapshot.playlist_id
        if not playlist_id:
            return {"playlist_id": None, "tracks": []}
        playlist = next((p for p in controller.config.playlists if p.id == playlist_id), None)
        if not playlist:
            return {"playlist_id": playlist_id, "tracks": []}
        tracks = _read_m3u_tracks(playlist.source.value)
        return {
            "playlist_id": playlist_id,
            "playlist_name": playlist.name,
            "tracks": [{"index": i, "path": t, "name": Path(t).stem} for i, t in enumerate(tracks)],
        }

    @app.get("/playlists")
    def list_playlists(_: None = Depends(auth_dependency)) -> list[dict]:
        return [
            {
                "id": p.id,
                "name": p.name,
                "tags": p.tags,
                "shuffle": p.shuffle,
                "volume_start": p.volume_profile.start,
                "volume_target": p.volume_profile.target,
                "track_count": len(_read_m3u_tracks(p.source.value)),
            }
            for p in controller.config.playlists
        ]

    @app.get("/schedule")
    def get_schedule(_: None = Depends(auth_dependency)) -> dict:
        from datetime import datetime
        from zoneinfo import ZoneInfo

        tz = ZoneInfo(controller.config.timezone)
        now = datetime.now(tz)
        day_name = now.strftime("%a").lower()
        active_slot_id = controller._playback.snapshot.slot_id

        slots = []
        for s in controller.config.schedule:
            is_today = day_name in [str(w) for w in s.weekdays]
            slots.append({
                "id": s.id,
                "name": s.name,
                "start": s.start,
                "end": s.end,
                "weekdays": [str(w) for w in s.weekdays],
                "is_today": is_today,
                "is_active": s.id == active_slot_id,
                "playlist_ids": s.playlist_ids,
            })
        return {"day": day_name, "slots": slots}

    @app.get("/analytics/listening")
    def listening_analytics(days: int = 7, _: None = Depends(auth_dependency)) -> dict:
        return controller._analytics.listening_summary(min(days, 365))

    @app.get("/analytics/health")
    def health_analytics(_: None = Depends(auth_dependency)) -> dict:
        return controller._analytics.health_report()

    @app.get("/analytics/config-history")
    def config_history(limit: int = 20, _: None = Depends(auth_dependency)) -> list[dict]:
        return controller._analytics.config_change_history(min(limit, 100))

    @app.get("/analytics/events")
    def event_log(limit: int = 50, severity: str | None = None, _: None = Depends(auth_dependency)) -> list[dict]:
        return controller._analytics.event_log(min(limit, 200), severity)

    @app.get("/playlist-health/{playlist_id}")
    def playlist_health(playlist_id: str, _: None = Depends(auth_dependency)) -> dict:
        playlist = next((p for p in controller.config.playlists if p.id == playlist_id), None)
        if not playlist:
            raise HTTPException(status_code=404, detail=f"Playlist {playlist_id} not found")
        tracks = _read_m3u_tracks(playlist.source.value)
        report = controller._playlist_health.analyze_playlist(playlist_id, tracks)
        return {
            "playlist_id": report.playlist_id,
            "total_tracks": report.total_tracks,
            "healthy_tracks": report.healthy_tracks,
            "stale_tracks": report.stale_tracks,
            "low_health_tracks": report.low_health_tracks,
            "missing_tracks": report.missing_tracks,
            "overall_score": report.overall_score,
            "tracks": [
                {
                    "path": t.path,
                    "play_count": t.play_count,
                    "skip_count": t.skip_count,
                    "health_score": t.health_score,
                    "is_stale": t.is_stale,
                    "reasons": t.reasons,
                }
                for t in report.track_details
            ],
        }

    @app.get("/playlist-health")
    def all_playlist_health(_: None = Depends(auth_dependency)) -> list[dict]:
        results = []
        for playlist in controller.config.playlists:
            tracks = _read_m3u_tracks(playlist.source.value)
            report = controller._playlist_health.analyze_playlist(playlist.id, tracks)
            results.append({
                "playlist_id": report.playlist_id,
                "total_tracks": report.total_tracks,
                "overall_score": report.overall_score,
                "stale_tracks": report.stale_tracks,
                "missing_tracks": report.missing_tracks,
            })
        return results

    @app.get("/quarantine")
    def list_quarantined(_: None = Depends(auth_dependency)) -> list[dict]:
        return controller._playlist_health.list_quarantined()

    @app.post("/quarantine/{playlist_id}")
    def quarantine_stale(playlist_id: str, _: None = Depends(auth_dependency)) -> dict:
        playlist = next((p for p in controller.config.playlists if p.id == playlist_id), None)
        if not playlist:
            raise HTTPException(status_code=404, detail=f"Playlist {playlist_id} not found")
        tracks = _read_m3u_tracks(playlist.source.value)
        candidates = controller._playlist_health.get_quarantine_candidates(playlist_id, tracks)
        quarantined = []
        for t in candidates:
            reason = ", ".join(t.reasons) or "low_health"
            if controller._playlist_health.quarantine_track(t.path, playlist_id, reason, t.health_score):
                quarantined.append(t.path)
        return {"quarantined": len(quarantined), "tracks": quarantined}

    @app.post("/quarantine/restore")
    def restore_track(original_path: str, _: None = Depends(auth_dependency)) -> dict:
        ok = controller._playlist_health.restore_track(original_path)
        return {"ok": ok}

    @app.post("/playback-speed")
    def set_playback_speed(request: PlaybackSpeedRequest, _: None = Depends(auth_dependency)) -> dict:
        try:
            controller._playback._send_command(["set_property", "speed", request.speed])
            return {"ok": True, "speed": request.speed}
        except Exception:
            return {"ok": False}

    @app.get("/playback-speed")
    def get_playback_speed(_: None = Depends(auth_dependency)) -> dict:
        try:
            speed = controller._playback._get_property("speed")
            return {"speed": speed or 1.0}
        except Exception:
            return {"speed": 1.0}

    @app.post("/crossfade")
    def set_crossfade(request: CrossfadeRequest, _: None = Depends(auth_dependency)) -> dict:
        snap = controller._playback.snapshot
        snap._crossfade_seconds = request.seconds
        return {"ok": True, "seconds": request.seconds}

    @app.get("/crossfade")
    def get_crossfade(_: None = Depends(auth_dependency)) -> dict:
        snap = controller._playback.snapshot
        return {"seconds": getattr(snap, "_crossfade_seconds", 0)}

    @app.post("/equalizer")
    def set_equalizer(request: EqPresetRequest, _: None = Depends(auth_dependency)) -> dict:
        presets = {
            "flat": "",
            "bass_boost": "equalizer=f=60:width_type=o:width=2:g=6,equalizer=f=170:width_type=o:width=2:g=4",
            "treble_boost": "equalizer=f=6000:width_type=o:width=2:g=4,equalizer=f=12000:width_type=o:width=2:g=6",
            "vocal": "equalizer=f=300:width_type=o:width=2:g=-2,equalizer=f=2000:width_type=o:width=2:g=5,equalizer=f=4000:width_type=o:width=2:g=3",
            "night_mode": "equalizer=f=60:width_type=o:width=2:g=-4,equalizer=f=12000:width_type=o:width=2:g=-4",
            "live": "equalizer=f=1000:width_type=o:width=2:g=3,equalizer=f=4000:width_type=o:width=2:g=2,equalizer=f=8000:width_type=o:width=2:g=4",
        }
        if request.preset not in presets:
            raise HTTPException(status_code=400, detail=f"Unknown preset: {request.preset}. Available: {list(presets.keys())}")
        try:
            af_val = presets[request.preset]
            controller._playback._send_command(["set_property", "af", af_val])
            snap = controller._playback.snapshot
            snap._eq_preset = request.preset
            return {"ok": True, "preset": request.preset}
        except Exception:
            return {"ok": False}

    @app.get("/equalizer")
    def get_equalizer(_: None = Depends(auth_dependency)) -> dict:
        snap = controller._playback.snapshot
        return {"preset": getattr(snap, "_eq_preset", "flat")}

    @app.get("/discover/trending")
    def get_trending_songs(_: None = Depends(auth_dependency)) -> dict:
        """Return trending song suggestions per category from the discovery engine."""
        return controller._get_trending_suggestions()

    @app.get("/discover/search")
    def search_discover(q: str, max_results: int = 20, _: None = Depends(auth_dependency)) -> dict:
        """Live search YouTube for songs by user query."""
        from song_automation.discovery import search_songs
        results = search_songs(q, max_results=min(max_results, 50))
        return {"query": q, "songs": results}

    @app.post("/discover/add-to-playlist")
    def add_trending_to_playlist(
        playlist_id: str,
        url: str,
        bg: bool = True,
        _: None = Depends(auth_dependency),
    ) -> dict:
        """Download a trending song and add it to a playlist.

        bg=True (default) starts download in background for instant response.
        """
        return controller._add_trending_song(playlist_id, url, background=bg)

    @app.post("/discover/play")
    def discover_play_now(url: str, title: str = "", _: None = Depends(auth_dependency)) -> dict:
        """Stream a YouTube URL directly via mpv (no download needed)."""
        try:
            controller._playback.ensure_started()
            controller._playback._send_command(["loadfile", url, "replace"])
            controller._playback._send_command(["set_property", "pause", False])
            snap = controller._playback.snapshot
            snap.is_paused = False
            snap.playlist_id = "__discover__"
            snap.track.title = title or url.split("=")[-1]
            snap.track.position = 0
            snap.track.duration = 0
            snap.track.playlist_pos = 0
            snap.track.playlist_count = 1
            controller._storage.log_event("discover_play", payload={"url": url, "title": title})
            return {"ok": True, "title": snap.track.title, "url": url}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    @app.post("/discover/queue")
    def discover_add_to_queue(url: str, title: str = "", _: None = Depends(auth_dependency)) -> dict:
        """Add a YouTube URL to the current mpv queue."""
        try:
            controller._playback.ensure_started()
            controller._playback._send_command(["loadfile", url, "append"])
            snap = controller._playback.snapshot
            snap.track.playlist_count = (snap.track.playlist_count or 0) + 1
            controller._storage.log_event("discover_queue", payload={"url": url, "title": title})
            return {"ok": True}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    @app.get("/keyboard-shortcuts")
    def keyboard_shortcuts() -> list[dict]:
        return [
            {"key": "Space / K", "action": "Play / Pause"},
            {"key": "Shift+Right", "action": "Next track"},
            {"key": "Shift+Left", "action": "Previous track"},
            {"key": "Up / Down", "action": "Volume +/- 5"},
            {"key": "M", "action": "Mute / Unmute"},
            {"key": "L", "action": "Like current track"},
            {"key": "S", "action": "Toggle shuffle"},
            {"key": "R", "action": "Toggle repeat"},
            {"key": "N", "action": "Now Playing panel"},
            {"key": "/", "action": "Focus search"},
            {"key": "Escape", "action": "Close panels"},
            {"key": "?", "action": "Keyboard shortcuts"},
            {"key": "P", "action": "Playback speed"},
        ]

    @app.get("/lyrics")
    def get_lyrics(title: str | None = None, _: None = Depends(auth_dependency)) -> dict:
        """Fetch lyrics for the current or specified track.

        Tries multiple strategies in order:
        1. Parse artist/title from the track name
        2. Query lrclib.net (best for Bollywood/Indian music)
        3. Query lyrics.ovh
        4. Try with just the song title as a search query
        """
        if not title:
            snap = controller._playback.snapshot
            info = snap.track
            title = info.title
        if not title:
            return {"lyrics": None, "source": None, "title": None}

        clean = _clean_track_title(title)
        artist, song = _parse_artist_title(clean)

        short = _extract_short_title(clean)

        fetchers = [
            (_fetch_lyrics_lrclib_romanized, "lrclib.net (romanized)"),
            (_fetch_lyrics_genius_scrape, "genius"),
            (_fetch_lyrics_lrclib, "lrclib.net"),
            (_fetch_lyrics_ovh, "lyrics.ovh"),
        ]

        search_terms = []
        if artist and song:
            search_terms.append((artist, song))
        if song:
            search_terms.append(("", song))
        if short and short != song:
            search_terms.append(("", short))

        song_core = re.sub(r'\s*\|.*$', '', clean).strip()
        song_core = re.sub(r'\s*-\s*$', '', song_core).strip()
        if song_core and song_core not in {s for _, s in search_terms}:
            search_terms.append(("", song_core))

        if not search_terms:
            search_terms.append(("", clean))

        for fetcher, source_name in fetchers:
            for a, s in search_terms:
                result = fetcher(a, s)
                if result is None:
                    continue
                if isinstance(result, dict):
                    return {
                        "lyrics": result.get("plain", ""),
                        "synced": result.get("synced"),
                        "source": source_name,
                        "title": clean, "artist": a, "song": s,
                    }
                if isinstance(result, str) and len(result.strip()) > 20:
                    return {"lyrics": result, "synced": None, "source": source_name, "title": clean, "artist": a, "song": s}

        return {"lyrics": None, "synced": None, "source": None, "title": clean, "artist": artist, "song": song}

    return app


def _clean_track_title(raw: str) -> str:
    """Remove common noise from track titles: file extensions, quality tags, brackets."""
    name = raw
    name = re.sub(r'\.(mp3|m4a|flac|wav|ogg|opus|aac|wma)$', '', name, flags=re.IGNORECASE)
    name = re.sub(r'\[.*?\]', '', name)
    name = re.sub(r'\((?:Official|Audio|Video|Lyric|Lyrics|HD|HQ|4K|1080p|720p|Full|Song|Music|Extended|Remix).*?\)', '', name, flags=re.IGNORECASE)
    name = re.sub(r'(?:Official|Audio|Video|Lyric|Lyrics)\s*(?:Video|Song|Audio)?', '', name, flags=re.IGNORECASE)
    name = re.sub(r'\s*\|\s*Full\s.*$', '', name, flags=re.IGNORECASE)
    name = re.sub(r'\s{2,}', ' ', name).strip()
    name = name.strip(' |-_')
    return name


def _extract_short_title(name: str) -> str:
    """Extract the core song name from long YouTube-style titles.

    For "Artist - Song (Official Video)" -> "Song"
    For "Song | Movie | Artist" -> "Song"
    """
    parts = re.split(r'\s*[\|]\s*', name)
    if len(parts) >= 2:
        candidate = parts[0].strip()
        candidate = re.sub(r'\s*(Video|Audio|Full|Song|Lyric|Lyrics).*$', '', candidate, flags=re.IGNORECASE).strip()
        if len(candidate) >= 3:
            return candidate
    parts = re.split(r'\s*[-]\s*', name)
    if len(parts) == 2:
        left, right = parts[0].strip(), parts[1].strip()
        right = re.sub(r'\s*\(.*\)\s*$', '', right).strip()
        if len(right) >= 2:
            return right
        return left
    if len(parts) > 2:
        return parts[0].strip()
    return name.strip()


def _parse_artist_title(name: str) -> tuple[str, str]:
    """Try to split 'Artist - Title' or 'Title | Movie | Artist' patterns.

    For Indian music, common patterns:
    - "Song Name | Movie Name | Artist1 & Artist2 | Composer"
    - "Song Name - Artist Name"
    - "Artist - Song Name"
    """
    if ' - ' in name:
        parts = name.split(' - ', 1)
        return parts[0].strip(), parts[1].strip()

    pipe_parts = [p.strip() for p in name.split('|') if p.strip()]
    if len(pipe_parts) >= 3:
        song = re.sub(r'\s*(Video|Audio|Full|Song).*$', '', pipe_parts[0], flags=re.IGNORECASE).strip()
        artist_candidates = pipe_parts[2:]
        artist = artist_candidates[0] if artist_candidates else ""
        return artist, song
    if len(pipe_parts) == 2:
        return pipe_parts[1].strip(), pipe_parts[0].strip()

    for sep in [' _ ', ' ~ ']:
        if sep in name:
            parts = name.split(sep, 1)
            return parts[0].strip(), parts[1].strip()

    return "", name.strip()


def _title_matches(query: str, candidate: str) -> bool:
    """Fuzzy title match: checks if key words from query appear in candidate."""
    q = query.lower().strip()
    c = candidate.lower().strip()
    if q in c or c in q:
        return True
    q_words = set(re.findall(r'[a-z]{2,}', q))
    c_words = set(re.findall(r'[a-z]{2,}', c))
    if not q_words:
        return False
    overlap = q_words & c_words
    return len(overlap) >= min(len(q_words), 2)


def _fetch_lyrics_lrclib_romanized(artist: str, title: str) -> dict | None:
    """Query lrclib.net specifically looking for romanized (Latin script) lyrics.

    Returns dict with 'plain' and optional 'synced' (LRC format) keys.
    """
    try:
        params = {"track_name": title}
        if artist:
            params["artist_name"] = artist
        qs = urllib.parse.urlencode(params)
        url = f"https://lrclib.net/api/search?{qs}"
        req = urllib.request.Request(url, headers={"User-Agent": "Sangeet/1.0"})
        with urllib.request.urlopen(req, timeout=6) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if not isinstance(data, list) or not data:
                return None
            for item in data[:20]:
                track_name = item.get("trackName") or ""
                if not _title_matches(title, track_name):
                    continue
                plain = item.get("plainLyrics") or ""
                synced_raw = item.get("syncedLyrics") or ""
                lyrics_text = plain or _strip_lrc_timestamps(synced_raw)
                if lyrics_text and len(lyrics_text.strip()) > 20 and _is_latin(lyrics_text):
                    return {
                        "plain": lyrics_text.strip(),
                        "synced": synced_raw.strip() if synced_raw.strip() else None,
                    }
    except Exception as exc:
        _lyrics_logger.debug("lrclib romanized fetch failed: %s", exc)
    return None


def _fetch_lyrics_genius_scrape(artist: str, title: str) -> str | None:
    """Scrape Genius for lyrics. Genius typically has romanized lyrics for Indian songs."""
    try:
        search_q = f"{artist} {title}".strip() if artist else title
        search_url = f"https://api.genius.com/search?q={urllib.parse.quote(search_q)}"
        genius_token = os.environ.get("GENIUS_API_TOKEN", "")
        if not genius_token:
            return None
        req = urllib.request.Request(search_url, headers={
            "User-Agent": "Sangeet/1.0",
            "Authorization": f"Bearer {genius_token}",
        })
        with urllib.request.urlopen(req, timeout=6) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            hits = data.get("response", {}).get("hits", [])
            if not hits:
                return None
            song_url = hits[0].get("result", {}).get("url")
            if not song_url:
                return None
        page_req = urllib.request.Request(song_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(page_req, timeout=8) as resp:
            html = resp.read().decode("utf-8")
        lyrics_parts = []
        for match in re.finditer(r'data-lyrics-container="true"[^>]*>(.*?)</div>', html, re.DOTALL):
            part = match.group(1)
            part = re.sub(r'<br\s*/?>', '\n', part)
            part = re.sub(r'<[^>]+>', '', part)
            part = part.replace('&#x27;', "'").replace('&amp;', '&').replace('&quot;', '"')
            lyrics_parts.append(part.strip())
        if lyrics_parts:
            full = '\n\n'.join(lyrics_parts)
            if len(full.strip()) > 20 and _is_latin(full):
                return full.strip()
    except Exception as exc:
        _lyrics_logger.debug("genius scrape failed: %s", exc)
    return None


def _fetch_lyrics_lrclib(artist: str, title: str) -> dict | None:
    """Query lrclib.net -- returns any lyrics found, preferring Latin script.

    Returns dict with 'plain' and optional 'synced' keys.
    """
    try:
        params = {"track_name": title}
        if artist:
            params["artist_name"] = artist
        qs = urllib.parse.urlencode(params)
        url = f"https://lrclib.net/api/search?{qs}"
        req = urllib.request.Request(url, headers={"User-Agent": "Sangeet/1.0"})
        with urllib.request.urlopen(req, timeout=6) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if not isinstance(data, list) or not data:
                return None
            latin_match: dict | None = None
            any_match: dict | None = None
            for item in data[:20]:
                track_name = item.get("trackName") or ""
                plain = item.get("plainLyrics") or ""
                synced_raw = item.get("syncedLyrics") or ""
                lyrics_text = plain or _strip_lrc_timestamps(synced_raw)
                if not lyrics_text or len(lyrics_text.strip()) < 20:
                    continue
                if not _title_matches(title, track_name):
                    continue
                entry = {
                    "plain": lyrics_text.strip(),
                    "synced": synced_raw.strip() if synced_raw.strip() else None,
                }
                if _is_latin(lyrics_text) and not latin_match:
                    latin_match = entry
                if not any_match:
                    any_match = entry
            return latin_match or any_match
    except Exception as exc:
        _lyrics_logger.debug("lrclib fetch failed for '%s - %s': %s", artist, title, exc)
    return None


def _strip_lrc_timestamps(synced: str) -> str:
    """Remove [mm:ss.xx] timestamps from synced lyrics."""
    return re.sub(r'\[\d{2}:\d{2}\.\d{2,3}\]\s*', '', synced)


def _is_latin(text: str) -> bool:
    """Check if the majority of alphabetic characters are Latin."""
    latin = 0
    non_latin = 0
    for ch in text:
        cat = unicodedata.category(ch)
        if cat.startswith("L"):
            if ord(ch) < 0x0250:
                latin += 1
            else:
                non_latin += 1
    total = latin + non_latin
    return total == 0 or (latin / total) > 0.6


def _fetch_lyrics_ovh(artist: str, title: str) -> str | None:
    """Query the free lyrics.ovh API."""
    try:
        a = urllib.parse.quote(artist or "unknown", safe="")
        t = urllib.parse.quote(title, safe="")
        url = f"https://api.lyrics.ovh/v1/{a}/{t}"
        req = urllib.request.Request(url, headers={"User-Agent": "Sangeet/1.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            lyrics = data.get("lyrics", "")
            if lyrics and len(lyrics.strip()) > 20:
                return lyrics.strip()
    except Exception as exc:
        _lyrics_logger.debug("lyrics.ovh fetch failed for '%s - %s': %s", artist, title, exc)
    return None


def _read_m3u_tracks(m3u_path: str) -> list[str]:
    """Read track paths from an M3U file."""
    p = Path(m3u_path)
    if not p.exists():
        return []
    tracks = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            tracks.append(line)
    return tracks
