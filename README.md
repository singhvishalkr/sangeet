<p align="center">
  <h1 align="center">Sangeet</h1>
  <p align="center">
    Intelligent music automation that plays the right song at the right time.
    <br />
    Schedule-aware · Weather-responsive · Self-learning · Zero cloud dependency.
    <br /><br />
    <a href="https://github.com/singhvishalkr/sangeet"><strong>GitHub</strong></a> · <a href="docs/02-system-design.md"><strong>Architecture</strong></a> · <a href="#api-reference"><strong>API Reference</strong></a> · <a href="#deployment"><strong>Deploy</strong></a>
  </p>
</p>

---

## What It Does

Sangeet turns any machine into a context-aware music system. It decides what to play based on a layered decision engine — not random shuffle.

```
07:30 AM weekday  →  Gayatri Mantra, gentle fade-in over 10 minutes
Monday morning    →  Shiv bhajans get +45 priority boost
Raining at night  →  Sufi ghazals and old classics
Janmashtami       →  Krishna bhajans all day, overrides everything
Saturday noon     →  Punjabi and Bollywood party mix
```

No cloud service. No subscription. Your music, your rules, running on your machine.

## System Architecture

```
┌──────────────┐     ┌────────────┐     ┌────────────┐     ┌──────────┐
│  Config       │────▶│  Context    │────▶│  Resolver   │────▶│  mpv      │
│  (YAML +      │     │  (time,     │     │  (score,    │     │  (JSON    │
│   Pydantic)   │     │   weather,  │     │   rank,     │     │   IPC)    │
│               │     │   holidays, │     │   select)   │     │          │
│               │     │   mood)     │     │             │     │          │
└──────────────┘     └────────────┘     └────────────┘     └──────────┘
        │                   │                  │                  │
   ┌────▼───────────────────▼──────────────────▼──────────────────▼────┐
   │                     SQLite (WAL mode)                             │
   │          sessions · overrides · events · decision traces          │
   └──────────────────────────────────────────────────────────────────┘
        │
   ┌────▼──────┐
   │  FastAPI   │  ← REST API (40+ endpoints) + WebSocket + Dashboard
   │  :8765     │
   └───────────┘
```

### Decision Engine (priority order — never reordered)

| Priority | Layer | Description |
|----------|-------|-------------|
| 1 | **Safety** | System stop conditions, health checks |
| 2 | **Manual Override** | User-initiated playlist or stop |
| 3 | **Calendar** | Festival/holiday rules (auto-detected) |
| 4 | **Schedule** | Time-slot matching with weekday awareness |
| 5 | **Weather** | Temperature, rain, cloud cover scoring |
| 6 | **Freshness** | Anti-repeat rotation, recency penalty |
| 7 | **Learning** | Bounded preference weights from skip/play signals |
| 8 | **Fallback** | Default stop or safe playlist |

Every decision produces a `reasons[]` trace for full auditability.

## Tech Stack

| Component | Technology | Why |
|-----------|-----------|-----|
| Runtime | Python 3.12+ | Type hints, performance, ecosystem |
| Audio | mpv (JSON IPC) | Battle-tested, codec-complete, scriptable |
| Scheduler | APScheduler | Reliable background job scheduling |
| API | FastAPI + Uvicorn | Async, auto-docs, WebSocket support |
| Config | YAML + Pydantic v2 | Human-readable config with strict validation |
| Database | SQLite (WAL) | Zero-config, concurrent reads, single-file |
| Weather | Open-Meteo | Free, no API key, global coverage |
| Holidays | `holidays` lib | 50+ country support, auto-updated |
| Frontend | Vanilla HTML/CSS/JS | Zero build step, zero dependencies |

## Quick Start

```bash
# Clone and install
git clone https://github.com/singhvishalkr/sangeet.git
cd sangeet
python -m venv .venv && .venv\Scripts\activate  # Windows
pip install -e ".[dev]"

# Configure
cp config/automation.example.yaml config/automation.yaml
# Edit config/automation.yaml with your playlists, location, schedule

# Run
sangeet --config config/automation.yaml             # Full system
sangeet --config config/automation.yaml --dry-run   # No audio, see decisions
sangeet --config config/automation.yaml --no-api    # Headless, no dashboard
```

Dashboard opens at **http://localhost:8765**.

## Dashboard

Production-grade, Spotify-inspired dark UI. No framework, no build step — pure HTML/CSS/JS served by FastAPI.

**Core Controls:**
Transport bar (play/pause/skip/previous), shuffle/repeat toggles, volume slider, seek bar, like/dislike

**Now Playing Panel:**
Fullscreen expandable view with animated gradient background, synced karaoke lyrics (via lrclib.net + Genius), progress bar, playlist context

**Intelligence:**
"Why this playlist?" reasoning card, decision timeline, mood/energy sliders, room mode selector (prayer, cooking, guests, quiet, celebration, sleep)

**Discovery:**
Trending songs per category via yt-dlp, one-tap add to any playlist, live YouTube search, stream without downloading

**Playback Settings:**
Speed (0.5x–2x), equalizer presets (flat, bass boost, treble, vocal, night mode, live), crossfade (0–12s)

**Analytics:**
Sessions per day, most-played playlists, system health, config change history, event log

**Other:**
Sleep timer, recently played, playlist detail with health scores, sidebar search, keyboard shortcuts (Space, M, L, S, R, N, /, ?), mobile responsive (360px+)

## Deployment

### Dashboard Only (free cloud hosting)

The dashboard and API can run on any free cloud platform that supports Python. Since the code is on GitHub, these platforms pull directly from your repo:

**[Render](https://render.com)** (recommended):
1. Connect your GitHub repo at [render.com](https://render.com)
2. Create a new **Web Service**, select `singhvishalkr/sangeet`
3. Set build command: `pip install -e .`
4. Set start command: `uvicorn song_automation.api:create_app --host 0.0.0.0 --port $PORT --factory`
5. Free tier gives you a permanent `https://sangeet-xxxx.onrender.com` URL

**[Railway](https://railway.app)**:
1. Connect GitHub repo at [railway.app](https://railway.app)
2. It auto-detects Python, set start command same as above
3. Free tier: 500 hours/month with a permanent URL

> **Note:** Cloud deployment runs the dashboard + API in dry-run mode (no mpv on cloud servers). For actual audio playback, run Sangeet locally on the machine connected to your speakers. The cloud deployment is useful for monitoring, controlling overrides, and viewing analytics from anywhere.

### Full System (local machine with audio)

For actual music playback, Sangeet runs on your local machine where mpv and speakers are connected:

```bash
# Start everything
sangeet --config config/automation.yaml
```

To access the dashboard from your phone on the same WiFi:

```yaml
# In config/automation.yaml
api:
  host: 0.0.0.0    # Listen on all network interfaces
  port: 8765
```

Then open `http://<your-machine-ip>:8765` from any device on the network.

### Auto-Start (Windows)

```powershell
powershell -ExecutionPolicy Bypass -File scripts/register_task.ps1
```

Registers a Windows Task Scheduler job that starts Sangeet on every login.

## Module Architecture

```
song_automation/
├── main.py              CLI entry point, arg parsing
├── config.py            Pydantic v2 models (AppConfig, 15+ sub-models)
├── config_loader.py     YAML loading, validation, hot-reload on file change
├── context.py           Signal collection: time, weather, holidays, seasons
├── resolver.py          Pure scoring engine: slot matching, candidate ranking
├── controller.py        Orchestrator: scheduler, reconcile loop, volume ramp
├── playback.py          mpv IPC gateway (named pipe), dry-run mock
├── storage.py           SQLite: sessions, overrides, events
├── domain.py            Core dataclasses (no business logic)
├── domain_events.py     In-process pub/sub event bus
├── decision_store.py    Decision trace persistence
├── feedback.py          Skip/play signal capture, preference weight learning
├── playlist_health.py   Track-level health scoring, quarantine workflow
├── mood.py              Mood state management (energy, valence, activity)
├── environment.py       Room modes, quiet hours, device presence
├── analytics.py         Listening summaries, health reports, event log
├── discovery.py         Trending song scanner (yt-dlp search + cache)
├── logging_config.py    Structured logging setup
└── api.py               FastAPI: 40+ REST endpoints, WebSocket, static files
```

**Design principles:**
- Each module owns exactly one concern
- No circular imports — dependency flows downward
- Config models (Pydantic) separated from domain models (dataclasses)
- Resolver is pure: no IO, no side effects, fully testable
- All features gated behind `config.features` flags

## API Reference

### Playback Control

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/pause` | Instant pause (no fade) |
| POST | `/resume` | Resume from paused position |
| POST | `/skip` | Next track |
| POST | `/previous` | Previous track |
| POST | `/seek?position=` | Seek to position (seconds) |
| POST | `/volume` | Set volume `{"volume": 0-100}` |
| POST | `/shuffle` | Toggle shuffle |
| POST | `/repeat` | Cycle: off → all → one |
| POST | `/smart-play` | Context-aware auto-pick |

### Override & Scheduling

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/override` | Force playlist or stop `{"playlist_id": "...", "ttl_minutes": 90}` |
| DELETE | `/override` | Clear override, resume schedule |
| GET | `/schedule` | Today's time slots |
| POST | `/sleep-timer` | Set countdown `{"minutes": 30}` |
| DELETE | `/sleep-timer` | Cancel timer |

### Status & Intelligence

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/status` | Full playback state + last decision |
| GET | `/decisions?limit=20` | Decision trace history with reasoning |
| GET | `/preview` | What would play if switched now |
| WS | `/ws` | Real-time status push (1s interval) |

### Mood & Context

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/mood` | Set mood `{"energy": 1-5, "valence": 1-5, "activity": "..."}` |
| POST | `/room?mode=` | Set room mode (prayer, cooking, guests, quiet, celebration, sleep) |
| POST | `/feedback/like` | Like track → boosts playlist weight |
| POST | `/feedback/dislike` | Dislike → penalizes + auto-skips |

### Library & Discovery

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/playlists` | All configured playlists with metadata |
| GET | `/queue` | Current playlist tracks |
| GET | `/recently-played` | Last N unique playlists |
| GET | `/playlist-health/{id}` | Track-level health scores |
| GET | `/discover/trending` | Trending songs by category |
| GET | `/discover/search?q=` | Live YouTube search |
| POST | `/discover/play?url=` | Stream URL directly |
| POST | `/discover/add-to-playlist` | Download and add to playlist |

### Analytics

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/analytics/listening?days=7` | Listening summary |
| GET | `/analytics/health` | System health (restarts, errors) |
| GET | `/analytics/events?limit=50` | Event log with severity filter |

### Playback Settings

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET/POST | `/playback-speed` | Speed (0.25x–4x) |
| GET/POST | `/equalizer` | EQ preset (flat, bass_boost, treble, vocal, night_mode, live) |
| GET/POST | `/crossfade` | Crossfade duration (0–12s) |

## Configuration

All settings live in `config/automation.yaml`. The [example config](config/automation.example.yaml) is fully documented.

| Section | Purpose |
|---------|---------|
| `location` | Coordinates for weather + holiday detection |
| `features` | Toggle any capability on/off |
| `player` | mpv path, pipe name, extra args |
| `playlists` | M3U paths, tags, volume profiles |
| `schedule` | Time slots, weekdays, preferred tags |
| `weekday_themes` | Day-specific tag boosts |
| `holiday_rules` | Festival overrides (auto-detected) |
| `weather_rules` | Weather-triggered scoring |
| `quiet_hours` | Volume cap or stop during night |
| `room_modes` | Tag overrides per room context |
| `smart_rotation` | Anti-repeat tuning |

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `GENIUS_API_TOKEN` | No | Genius API token for lyrics fetching. Get one at [genius.com/api-clients](https://genius.com/api-clients) |

## Contributing

1. All changes must be additive and feature-flagged
2. Every decision must carry `reasons[]` for traceability
3. Module size: 120–250 lines ideal, 350 max
4. Config changes must not break existing setups
5. Run `pytest` before submitting

## License

[Apache 2.0](LICENSE)
