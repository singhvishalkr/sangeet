from __future__ import annotations

import pytest

from song_automation.config_loader import ConfigError, ConfigRepository


def test_load_valid_example_config(tmp_path) -> None:
    config_file = tmp_path / "test.yaml"
    config_file.write_text("""
timezone: Asia/Calcutta
playlists:
  - id: test_pl
    name: Test
    source:
      type: m3u
      value: test.m3u
    tags: [test]
schedule:
  - id: test_slot
    name: Test Slot
    start: "07:00"
    end: "08:00"
    playlist_ids: [test_pl]
""")
    repo = ConfigRepository(config_file)
    config = repo.load()
    assert config.timezone == "Asia/Calcutta"
    assert len(config.playlists) == 1
    assert len(config.schedule) == 1


def test_reject_missing_file(tmp_path) -> None:
    repo = ConfigRepository(tmp_path / "nonexistent.yaml")
    with pytest.raises(ConfigError, match="does not exist"):
        repo.load()


def test_reject_duplicate_playlist_ids(tmp_path) -> None:
    config_file = tmp_path / "bad.yaml"
    config_file.write_text("""
playlists:
  - id: dup
    name: A
    source: {type: m3u, value: a.m3u}
  - id: dup
    name: B
    source: {type: m3u, value: b.m3u}
schedule:
  - id: s
    name: S
    start: "07:00"
    end: "08:00"
    playlist_ids: [dup]
""")
    repo = ConfigRepository(config_file)
    with pytest.raises(ConfigError, match="playlist ids must be unique"):
        repo.load()


def test_reject_slot_referencing_unknown_playlist(tmp_path) -> None:
    config_file = tmp_path / "bad.yaml"
    config_file.write_text("""
playlists:
  - id: real
    name: Real
    source: {type: m3u, value: r.m3u}
schedule:
  - id: s
    name: S
    start: "07:00"
    end: "08:00"
    playlist_ids: [real, ghost]
""")
    repo = ConfigRepository(config_file)
    with pytest.raises(ConfigError, match="unknown playlists"):
        repo.load()


def test_reload_returns_same_if_unchanged(tmp_path) -> None:
    config_file = tmp_path / "test.yaml"
    config_file.write_text("""
playlists:
  - id: p
    name: P
    source: {type: m3u, value: p.m3u}
schedule:
  - id: s
    name: S
    start: "07:00"
    end: "08:00"
    playlist_ids: [p]
""")
    repo = ConfigRepository(config_file)
    first = repo.load()
    second = repo.reload_if_changed()
    assert first is second
