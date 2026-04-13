from __future__ import annotations

from datetime import datetime, timedelta, timezone

from song_automation.storage import Storage


def test_override_lifecycle(tmp_path) -> None:
    storage = Storage(tmp_path / "data")
    now = datetime.now(timezone.utc)
    future = now + timedelta(hours=1)
    past = now - timedelta(hours=1)

    storage.create_override(playlist_id="test", stop_playback=False, note="test", expires_at=future)
    active = storage.get_active_override(now)
    assert active is not None
    assert active.playlist_id == "test"

    storage.clear_expired_overrides(now)
    still_active = storage.get_active_override(now)
    assert still_active is not None

    storage.clear_expired_overrides(future + timedelta(seconds=1))
    gone = storage.get_active_override(future + timedelta(seconds=1))
    assert gone is None


def test_clear_overrides(tmp_path) -> None:
    storage = Storage(tmp_path / "data")
    now = datetime.now(timezone.utc)
    future = now + timedelta(hours=1)

    storage.create_override(playlist_id="a", stop_playback=False, note=None, expires_at=future)
    storage.create_override(playlist_id="b", stop_playback=False, note=None, expires_at=future)
    storage.clear_overrides()

    assert storage.get_active_override(now) is None


def test_session_tracking(tmp_path) -> None:
    storage = Storage(tmp_path / "data")

    storage.start_session(slot_id="morning", playlist_id="bhajans", trigger_reason="startup")
    recent = storage.recent_playlist_ids(5)
    assert recent == ["bhajans"]

    storage.finish_open_sessions("replaced")
    storage.start_session(slot_id="morning", playlist_id="shiv", trigger_reason="tick")
    recent = storage.recent_playlist_ids(5)
    assert recent == ["shiv", "bhajans"]


def test_event_logging(tmp_path) -> None:
    storage = Storage(tmp_path / "data")
    storage.log_event("test_event", payload={"key": "value"})

    row = storage.connection.execute("SELECT * FROM events ORDER BY id DESC LIMIT 1").fetchone()
    assert row["event_type"] == "test_event"
    assert row["severity"] == "INFO"
