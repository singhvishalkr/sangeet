"""Trending song discovery engine.

Periodically searches for trending songs per category using yt-dlp search,
caches results, and provides suggestions to the UI. Downloads happen on-demand
when the user explicitly adds a song to a playlist.
"""
from __future__ import annotations

import json
import logging
import subprocess
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

CACHE_FILE = Path("data/trending_cache.json")
SCAN_INTERVAL_HOURS = 6

SEARCH_QUERIES: dict[str, dict[str, Any]] = {
    "bollywood_hits": {
        "name": "Bollywood Hits",
        "queries": [
            "latest bollywood songs 2026",
            "trending hindi songs this week",
            "new bollywood party songs",
            "viral bollywood mashup 2026",
            "top hindi romantic songs new releases",
            "bollywood dance hits playlist 2026",
        ],
        "tags": ["bollywood", "hindi", "party"],
        "max_results": 50,
    },
    "punjabi_trending": {
        "name": "Punjabi Trending",
        "queries": [
            "trending punjabi songs 2026",
            "new punjabi songs this week",
            "latest punjabi party songs",
            "new punjabi sad songs 2026",
            "viral punjabi reels songs",
            "punjabi folk trending",
        ],
        "tags": ["punjabi", "party", "energetic"],
        "max_results": 50,
    },
    "devotional_new": {
        "name": "New Devotional",
        "queries": [
            "new bhajan songs 2026",
            "latest devotional songs hindi",
            "trending aarti songs",
            "latest krishna bhajan 2026",
            "hindi morning devotional songs",
            "new shiv bhajan trending",
        ],
        "tags": ["devotional", "bhajan"],
        "max_results": 50,
    },
    "chill_vibes": {
        "name": "Chill Vibes",
        "queries": [
            "trending lofi hindi songs",
            "new chill bollywood songs",
            "soulful hindi songs 2026",
            "acoustic hindi cover songs 2026",
            "relaxing bollywood instrumental",
            "indie folk hindi chill",
        ],
        "tags": ["chill", "soulful", "lofi"],
        "max_results": 50,
    },
    "haryanvi_hits": {
        "name": "Haryanvi Hits",
        "queries": [
            "trending haryanvi songs 2026",
            "new haryanvi dj songs",
            "haryanvi ragni popular 2026",
            "new haryanvi love songs",
            "haryanvi sapna chaudhary songs new",
        ],
        "tags": ["haryanvi", "party", "desi"],
        "max_results": 50,
    },
    "indie_picks": {
        "name": "Indie Picks",
        "queries": [
            "indian indie music 2026",
            "trending indie hindi songs",
            "indie rock hindi bands 2026",
            "underground hindi rap independent",
            "alternative hindi music playlist",
        ],
        "tags": ["indie", "lofi"],
        "max_results": 50,
    },
}


def _search_youtube(query: str, max_results: int = 15, timeout: int = 30) -> list[dict]:
    """Use yt-dlp to search YouTube and return metadata (no download)."""
    try:
        result = subprocess.run(
            [
                "yt-dlp",
                f"ytsearch{max_results}:{query}",
                "--dump-json",
                "--flat-playlist",
                "--no-download",
                "--quiet",
                "--socket-timeout", "10",
            ],
            capture_output=True, text=True, timeout=timeout,
        )
        songs = []
        for line in result.stdout.strip().split("\n"):
            if not line.strip():
                continue
            try:
                data = json.loads(line)
                vid_id = data.get("id", "")
                full_url = data.get("webpage_url") or ""
                if not full_url and vid_id:
                    full_url = f"https://www.youtube.com/watch?v={vid_id}"
                if not full_url:
                    raw = data.get("url", "")
                    full_url = raw if raw.startswith("http") else f"https://www.youtube.com/watch?v={raw}"
                songs.append({
                    "title": data.get("title", "Unknown"),
                    "url": full_url,
                    "id": vid_id,
                    "duration": data.get("duration"),
                    "channel": data.get("channel") or data.get("uploader", ""),
                    "view_count": data.get("view_count", 0),
                    "thumbnail": data.get("thumbnail", ""),
                })
            except json.JSONDecodeError:
                continue
        return songs
    except FileNotFoundError:
        logger.warning("yt-dlp not installed — trending discovery disabled")
        return []
    except subprocess.TimeoutExpired:
        logger.warning("yt-dlp search timed out for: %s", query)
        return []
    except Exception as exc:
        logger.warning("yt-dlp search failed: %s", exc)
        return []


def scan_trending() -> dict:
    """Run a full trending scan across all categories."""
    logger.info("Starting trending song scan...")
    categories = {}
    for cat_id, cat_config in SEARCH_QUERIES.items():
        all_songs: list[dict] = []
        seen_urls: set[str] = set()
        for query in cat_config["queries"]:
            results = _search_youtube(query, max_results=cat_config["max_results"])
            for song in results:
                if song["url"] not in seen_urls:
                    seen_urls.add(song["url"])
                    all_songs.append(song)
        all_songs.sort(key=lambda s: s.get("view_count", 0), reverse=True)
        categories[cat_id] = {
            "name": cat_config["name"],
            "tags": cat_config["tags"],
            "songs": all_songs[:cat_config["max_results"]],
            "last_updated": datetime.now().isoformat(),
        }
        logger.info("  %s: found %d songs", cat_id, len(all_songs[:cat_config["max_results"]]))

    result = {
        "categories": categories,
        "last_scan": datetime.now().isoformat(),
    }

    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    CACHE_FILE.write_text(json.dumps(result, indent=2), encoding="utf-8")
    logger.info("Trending scan complete. Cached to %s", CACHE_FILE)
    return result


def load_cached() -> dict | None:
    """Load cached trending data if fresh enough."""
    if not CACHE_FILE.exists():
        return None
    try:
        data = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
        last_scan = data.get("last_scan")
        if last_scan:
            scan_time = datetime.fromisoformat(last_scan)
            if datetime.now() - scan_time < timedelta(hours=SCAN_INTERVAL_HOURS):
                return data
    except Exception:
        pass
    return None


def search_songs(query: str, max_results: int = 10) -> list[dict]:
    """Live search for songs by user query. Uses smaller batch for speed."""
    logger.info("Live search: %s (max=%d)", query, max_results)
    return _search_youtube(query, max_results=min(max_results, 15), timeout=15)


class DiscoveryScheduler:
    """Background thread that periodically scans for trending songs."""

    def __init__(self) -> None:
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True, name="discovery-scanner")
        self._thread.start()
        logger.info("Discovery scheduler started (interval=%dh)", SCAN_INTERVAL_HOURS)

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5)

    def _run(self) -> None:
        cached = load_cached()
        if not cached:
            try:
                scan_trending()
            except Exception:
                logger.exception("Initial trending scan failed")

        while not self._stop_event.is_set():
            self._stop_event.wait(timeout=SCAN_INTERVAL_HOURS * 3600)
            if self._stop_event.is_set():
                break
            try:
                scan_trending()
            except Exception:
                logger.exception("Periodic trending scan failed")
