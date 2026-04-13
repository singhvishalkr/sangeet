from __future__ import annotations

import json
import logging
import math
import subprocess
import time
from typing import Protocol

from song_automation.config import CurveType, PlayerConfig, PlaylistConfig
from song_automation.domain import PlaybackSnapshot, TrackInfo

logger = logging.getLogger(__name__)

MAX_SAFE_JUMP = 15


def apply_curve(progress: float, curve: CurveType) -> float:
    """Map linear progress [0..1] through a volume curve."""
    if curve == "ease_in":
        return progress * progress
    if curve == "ease_out":
        return 1.0 - (1.0 - progress) ** 2
    if curve == "logarithmic":
        return math.log1p(progress * (math.e - 1)) / 1.0
    return progress


class PlaybackGateway(Protocol):
    def ensure_started(self) -> None: ...
    def load_playlist(self, playlist: PlaylistConfig) -> None: ...
    def set_volume(self, value: int) -> None: ...
    def fade_to(self, target: int, duration_seconds: int) -> None: ...
    def stop(self) -> None: ...
    def pause(self) -> None: ...
    def resume(self) -> None: ...
    def poll_track_info(self) -> TrackInfo: ...
    def shutdown(self) -> None: ...
    def is_healthy(self) -> bool: ...
    @property
    def snapshot(self) -> PlaybackSnapshot: ...


class DryRunPlaybackGateway:
    def __init__(self) -> None:
        self._snapshot = PlaybackSnapshot(running=True)

    @property
    def snapshot(self) -> PlaybackSnapshot:
        return self._snapshot

    def _get_property(self, name: str) -> object:
        return None

    def _send_command(self, command: list[object]) -> dict:
        return {"data": None}

    def ensure_started(self) -> None:
        self._snapshot.running = True

    def load_playlist(self, playlist: PlaylistConfig) -> None:
        self._snapshot.playlist_id = playlist.id
        self._snapshot.running = True

    def set_volume(self, value: int) -> None:
        self._snapshot.volume = max(0, min(100, value))

    def fade_to(self, target: int, duration_seconds: int) -> None:
        self._snapshot.volume = max(0, min(100, target))

    def pause(self) -> None:
        self._snapshot.is_paused = True

    def resume(self) -> None:
        self._snapshot.is_paused = False

    def poll_track_info(self) -> TrackInfo:
        return self._snapshot.track

    def stop(self) -> None:
        self._snapshot.playlist_id = None
        self._snapshot.volume = 0
        self._snapshot.is_paused = False

    def shutdown(self) -> None:
        self.stop()

    def is_healthy(self) -> bool:
        return True


SkipCallback = None  # type alias placeholder


class MpvPlaybackGateway:
    def __init__(self, config: PlayerConfig) -> None:
        self.config = config
        self.pipe_path = rf"\\.\pipe\{config.pipe_name}"
        self._process: subprocess.Popen[str] | None = None
        self._request_id = 1
        self._snapshot = PlaybackSnapshot()
        self._track_start_time: float | None = None
        self._last_playlist_pos: int | None = None
        self.on_skip: object | None = None

    @property
    def snapshot(self) -> PlaybackSnapshot:
        return self._snapshot

    def ensure_started(self) -> None:
        if self._process is not None and self._process.poll() is None:
            self._snapshot.running = True
            return

        args = [
            self.config.executable,
            "--input-ipc-server=" + self.pipe_path,
            *self.config.extra_args,
        ]
        self._process = subprocess.Popen(args, text=True)
        self._snapshot.running = True
        self._wait_for_pipe()

    def load_playlist(self, playlist: PlaylistConfig) -> None:
        self.ensure_started()
        command = ["loadlist", playlist.source.value, "replace"] if playlist.source.type == "m3u" else ["loadfile", playlist.source.value, "replace"]
        self._send_command(command)
        if playlist.shuffle:
            self._send_command(["playlist-shuffle"])
        try:
            self._send_command(["set_property", "pause", False])
        except Exception:
            pass
        self._snapshot.playlist_id = playlist.id
        self._snapshot.is_paused = False

    def set_volume(self, value: int) -> None:
        self.ensure_started()
        safe_value = max(0, min(100, value))
        self._send_command(["set_property", "volume", safe_value])
        self._snapshot.volume = safe_value

    def fade_to(self, target: int, duration_seconds: int, curve: CurveType = "linear") -> None:
        start = self._snapshot.volume
        safe_target = max(0, min(100, target))
        if duration_seconds <= 0:
            self._safe_set_volume(safe_target)
            return

        steps = max(duration_seconds * 2, 1)
        for step in range(1, steps + 1):
            progress = apply_curve(step / steps, curve)
            next_value = round(start + (safe_target - start) * progress)
            self._safe_set_volume(next_value)
            time.sleep(duration_seconds / steps)

    def _safe_set_volume(self, target: int) -> None:
        """Set volume with anti-jolt protection."""
        current = self._snapshot.volume
        diff = abs(target - current)
        if diff > MAX_SAFE_JUMP:
            direction = 1 if target > current else -1
            while abs(target - self._snapshot.volume) > MAX_SAFE_JUMP:
                intermediate = self._snapshot.volume + direction * MAX_SAFE_JUMP
                self.set_volume(intermediate)
                time.sleep(0.1)
        self.set_volume(target)

    def pause(self) -> None:
        if self._process is None:
            return
        self._send_command(["set_property", "pause", True])
        self._snapshot.is_paused = True

    def resume(self) -> None:
        if self._process is None:
            return
        self._send_command(["set_property", "pause", False])
        self._snapshot.is_paused = False

    def poll_track_info(self) -> TrackInfo:
        """Query mpv for current track metadata and position."""
        info = TrackInfo()
        if not self.is_healthy() or self._snapshot.playlist_id is None:
            return info
        props = {
            "media-title": "title",
            "time-pos": "position",
            "duration": "duration",
            "playlist-pos": "playlist_pos",
            "playlist-count": "playlist_count",
        }
        for mpv_prop, attr in props.items():
            try:
                resp = self._send_command(["get_property", mpv_prop])
                val = resp.get("data")
                if val is not None:
                    setattr(info, attr, val)
            except Exception:
                pass
        self._snapshot.track = info
        return info

    def stop(self) -> None:
        if self._process is None:
            return
        self._send_command(["stop"])
        self._snapshot.playlist_id = None
        self._snapshot.volume = 0
        self._snapshot.is_paused = False

    def shutdown(self) -> None:
        if self._process is None:
            return
        try:
            self._send_command(["quit"])
        except OSError:
            pass
        if self._process.poll() is None:
            self._process.terminate()
        self._snapshot.running = False

    def check_track_skip(self) -> None:
        """Poll mpv for track position changes; detect skips (< 30s plays)."""
        if not self.is_healthy() or self._snapshot.playlist_id is None:
            return
        try:
            response = self._send_command(["get_property", "playlist-pos"])
            pos = response.get("data")
            if pos is None:
                return
        except Exception:
            return

        now = time.time()
        if self._last_playlist_pos is None:
            self._last_playlist_pos = pos
            self._track_start_time = now
            return

        if pos != self._last_playlist_pos:
            elapsed = now - (self._track_start_time or now)
            if elapsed < 30 and self.on_skip:
                try:
                    self.on_skip(self._snapshot.playlist_id, elapsed)
                except Exception:
                    logger.warning("Skip callback failed", exc_info=True)
            self._last_playlist_pos = pos
            self._track_start_time = now

    def is_healthy(self) -> bool:
        if self._process is None:
            return False
        if self._process.poll() is not None:
            logger.warning("mpv process exited with code %s", self._process.returncode)
            self._snapshot.running = False
            return False
        return True

    def _wait_for_pipe(self) -> None:
        deadline = time.time() + 10
        while time.time() < deadline:
            try:
                with open(self.pipe_path, "r+b", buffering=0):
                    return
            except OSError:
                time.sleep(0.2)
        raise RuntimeError(f"mpv IPC pipe did not become ready: {self.pipe_path}")

    def _get_property(self, name: str) -> object:
        """Get a single mpv property value."""
        try:
            resp = self._send_command(["get_property", name])
            return resp.get("data")
        except Exception:
            return None

    def _send_command(self, command: list[object]) -> dict:
        payload = {"command": command, "request_id": self._request_id}
        self._request_id += 1

        with open(self.pipe_path, "r+b", buffering=0) as pipe:
            pipe.write((json.dumps(payload) + "\n").encode("utf-8"))
            pipe.flush()

            while True:
                line = pipe.readline()
                if not line:
                    raise RuntimeError("mpv IPC closed before replying")
                response = json.loads(line.decode("utf-8"))
                if response.get("request_id") == payload["request_id"]:
                    if response.get("error") not in (None, "success"):
                        raise RuntimeError(f"mpv command failed: {response}")
                    return response


class DualPlayerGateway:
    """Manages two MpvPlaybackGateway instances for true crossfade.

    Player A is the active player; Player B is the outgoing player.
    On playlist switch, the new playlist loads on the idle player while
    the old one fades out, then roles swap.
    """

    def __init__(self, config: PlayerConfig) -> None:
        config_a = config.model_copy(update={"pipe_name": config.pipe_name + "-a"})
        config_b = config.model_copy(update={"pipe_name": config.pipe_name + "-b"})
        self._player_a = MpvPlaybackGateway(config_a)
        self._player_b = MpvPlaybackGateway(config_b)
        self._active = self._player_a
        self._outgoing = self._player_b
        self._snapshot = PlaybackSnapshot()

    @property
    def snapshot(self) -> PlaybackSnapshot:
        return self._active.snapshot

    def ensure_started(self) -> None:
        self._player_a.ensure_started()
        self._player_b.ensure_started()

    def load_playlist(self, playlist: PlaylistConfig) -> None:
        self._active.load_playlist(playlist)

    def set_volume(self, value: int) -> None:
        self._active.set_volume(value)

    def fade_to(self, target: int, duration_seconds: int, curve: CurveType = "linear") -> None:
        self._active.fade_to(target, duration_seconds, curve)

    def crossfade_to(self, playlist: PlaylistConfig, duration_seconds: int, curve: CurveType = "linear") -> None:
        """Load new playlist on idle player, crossfade, then swap roles."""
        import threading

        new_player = self._outgoing
        old_player = self._active
        old_volume = old_player.snapshot.volume

        new_player.load_playlist(playlist)
        new_player.set_volume(0)

        def _fade_out():
            old_player.fade_to(0, duration_seconds, curve)

        def _fade_in():
            new_player.fade_to(old_volume, duration_seconds, curve)

        t_out = threading.Thread(target=_fade_out, daemon=True)
        t_in = threading.Thread(target=_fade_in, daemon=True)
        t_out.start()
        t_in.start()
        t_out.join()
        t_in.join()

        old_player.stop()
        self._active, self._outgoing = new_player, old_player

    def pause(self) -> None:
        self._active.pause()

    def resume(self) -> None:
        self._active.resume()

    def poll_track_info(self) -> TrackInfo:
        return self._active.poll_track_info()

    def stop(self) -> None:
        self._active.stop()

    def shutdown(self) -> None:
        self._player_a.shutdown()
        self._player_b.shutdown()

    def is_healthy(self) -> bool:
        return self._active.is_healthy()

    def _safe_set_volume(self, target: int) -> None:
        self._active._safe_set_volume(target)


def build_playback_gateway(config: PlayerConfig, dual: bool = False) -> PlaybackGateway:
    if config.dry_run:
        return DryRunPlaybackGateway()
    if dual:
        return DualPlayerGateway(config)
    return MpvPlaybackGateway(config)
