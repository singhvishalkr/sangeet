# Sangeet

An intelligent, local-first music automation system that turns any always-on machine into a context-aware DJ. It plays the right music at the right time based on schedule, day of week, festivals, weather, mood, and learned preferences -- with zero cloud dependency.

```
Morning 7:30 AM  →  Gayatri Mantra (gentle fade-in, volume ramp)
Monday?          →  Shiv bhajans get priority
Raining outside? →  Sufi and old classics tonight
Janmashtami?     →  Krishna bhajans all day, automatically
Weekend?         →  Punjabi bangers and Bollywood hits
```

## Architecture

```
┌─────────────┐    ┌──────────┐    ┌──────────┐    ┌─────────┐
│   Config     │───▶│ Context  │───▶│ Resolver │───▶│ mpv     │
│   (YAML)     │    │ (time,   │    │ (score,  │    │ (audio) │
│              │    │  weather, │    │  rank,   │    │         │
│              │    │  holiday) │    │  pick)   │    │         │
└─────────────┘    └──────────┘    └──────────┘    └─────────┘
                         │               │               │
                    ┌────▼───────────────▼───────────────▼────┐
                    │            SQLite (WAL)                  │
                    │  sessions · overrides · events · traces  │
                    └─────────────────────────────────────────┘
                         │
                    ┌────▼────┐
                    │ FastAPI │  ← Dashboard + REST API
                    │ :8765   │     (status, override, analytics)
                    └─────────┘
```

**Decision flow** (sacred order -- never reordered):

1. System safety / stop conditions
2. Active manual override
3. Calendar / festival override
4. Active schedule slot
5. Weather scoring
6. Freshness / anti-repeat scoring
7. Learned preference adjustments (bounded)
8. Fallback stop

Every decision carries a `reasons[]` list for full traceability.

## Quick Start

### Prerequisites

- **Python 3.12+**
- **mpv** ([install](https://mpv.io/installation/)) -- the audio engine
- **yt-dlp** (optional) -- for downloading songs from YouTube

### Install

```bash
git clone https://github.com/singhvishalkr/sangeet.git
cd sangeet
python -m venv .venv

# Windows
.venv\Scripts\activate

# Linux/macOS
source .venv/bin/activate

pip install -e ".[dev]"
```

### Configure

```bash
cp config/automation.example.yaml config/automation.yaml
```

Edit `config/automation.yaml` with your:
- **Location** (latitude/longitude for weather and holidays)
- **Playlist paths** (point to your M3U files or audio folders)
- **Schedule** (when you want music to play)
- **Languages/tags** (customize for your taste)

### Run

```bash
# Dry-run (no audio, just see decisions)
sangeet --config config/automation.yaml --dry-run

# Real playback
sangeet --config config/automation.yaml

# Without the web dashboard
sangeet --config config/automation.yaml --no-api
```

Dashboard at **http://127.0.0.1:8765** when API is enabled.

### Dashboard

The dashboard is a production-grade, Spotify-inspired dark UI built with vanilla HTML/CSS/JS (no framework dependencies). Features include:

- **Now Playing hero** with live track title, playlist name, and tags
- **Now Playing fullscreen panel** -- click the transport bar to expand a fullscreen view with large track title, animated gradient background (shifts hue based on playlist tags), playlist context, and progress bar. Like/dislike buttons feed the adaptive learning system.
- **Transport bar** with play/pause/skip, shuffle/repeat toggles, track progress bar, elapsed/total time, volume control, and like button
- **True pause/resume** that instantly pauses mpv (no fade-out, no override workaround)
- **Smart Play** -- when no schedule slot is active, pressing play picks the best playlist based on your current mood, room mode, and freshness scoring
- **Shuffle and Repeat** -- toggle shuffle and cycle repeat modes (off / all / one) from the transport bar or keyboard
- **Like/Dislike** -- rate tracks from the transport bar, now-playing panel, or queue. Feedback feeds directly into the adaptive learning system.
- **Sleep Timer** -- set a countdown (15 min to 2 hours) after which playback fades out and stops gracefully
- **Recently Played** -- the Home page shows your last 5 playlists with one-tap replay
- **Playlist Detail View** -- click any playlist card to see all tracks, health score, and a play-all button
- **Sidebar search** across playlists and tags with keyboard navigation (press `/` to focus)
- **Playlist browser** with tag-based filtering
- **Queue view** showing current track highlighted, with per-track like buttons
- **Analytics** with CSS-only bar charts for sessions per day and most-played playlists
- **Context panel** combining room mode and mood controls in one card
- **Track name marquee** -- long track names scroll smoothly in the transport bar
- **Keyboard shortcuts**: Space/K (play/pause), Up/Down (volume), M (mute), Shift+Left/Right (prev/next), L (like), S (shuffle), R (repeat), N (now playing panel), / (search), Escape (close panels)
- **Smooth live progress** -- client-side interpolation renders progress bar at 60fps between WebSocket syncs (no more frozen progress)
- **Real-time WebSocket updates** every 1 second for snappy status sync
- **Discover tab** -- trending songs per category (Bollywood, Punjabi, Devotional, Chill, Haryanvi, Indie) auto-scanned from YouTube via yt-dlp. One-tap add to any playlist.
- **Playback speed** -- 0.5x to 2x speed control from the settings drawer
- **Equalizer presets** -- Flat, Bass Boost, Treble, Vocal, Night Mode, Live -- applied via mpv audio filters
- **Crossfade setting** -- configurable 0-12s crossfade between tracks
- **Settings drawer** -- slide-out panel (press P) for speed, EQ, and crossfade controls
- **Keyboard shortcuts overlay** -- press ? to see all shortcuts in a clean overlay
- **Mobile responsive** at 360px, 768px, and 1024px+ breakpoints

### Download Songs (optional)

```bash
# Edit scripts/download_library.py with your song preferences, then:
python scripts/download_library.py

# Generate M3U playlists from downloaded files:
python scripts/generate_playlists.py
```

## Features

| Feature | Status | Description |
|---------|--------|-------------|
| Time-based scheduling | Stable | Play specific playlists at specific times |
| Weekday themes | Stable | Monday = Shiv, Tuesday = Hanuman, Friday = Devi, etc. |
| Holiday detection | Stable | Auto-detects Indian festivals via `holidays` library |
| Weather-aware | Stable | Sufi on rainy nights, chill when hot, cozy when cold |
| Smart rotation | Stable | Never repeats the same playlist; freshness scoring |
| Volume ramping | Stable | Gentle fade-in over configurable minutes |
| Quiet hours | Stable | Auto-cap volume or stop playback at night |
| Room modes | Stable | Switch context via API (prayer, cooking, guests, etc.) |
| Adaptive learning | Stable | Learns from skips and plays; bounded weight adjustments |
| Playlist health | Stable | Track-level health scoring; stale track quarantine |
| REST API | Stable | Full control surface for status, override, analytics |
| Web dashboard | Stable | Production-grade Spotify-style dark UI with real-time updates |
| True pause/resume | Stable | Instant mpv pause/resume (no fade, no override hack) |
| Track progress | Stable | Live track title, position, duration in transport bar |
| Search | Stable | Sidebar search across playlists and tags with keyboard nav |
| Playlist filters | Stable | Filter playlists by tag on the Playlists page |
| Analytics charts | Stable | CSS-only bar charts for sessions per day and top playlists |
| Now Playing panel | Stable | Fullscreen expandable view with gradient background, controls, like/dislike |
| Smart Play | Stable | Mood/context-aware playlist selection when no schedule is active |
| Shuffle/Repeat | Stable | Toggle shuffle and cycle repeat modes from transport bar |
| Like/Dislike | Stable | Rate tracks to feed adaptive learning; available everywhere |
| Sleep Timer | Stable | Countdown timer that gracefully stops playback |
| Recently Played | Stable | Quick-replay last 5 playlists from Home page |
| Playlist Detail | Stable | Full track list, health score, play-all from modal view |
| Track marquee | Stable | Smooth scrolling for long track names in transport |
| Decision tracing | Stable | Every decision logged with full reasoning chain |
| Smooth progress | Stable | 60fps client-side interpolation for progress bar and time display |
| Trending discovery | Stable | Background scanner finds trending songs per category via yt-dlp |
| Playback speed | Stable | 0.5x to 2x speed control via mpv |
| Equalizer presets | Stable | 6 EQ presets applied via mpv audio filters |
| Crossfade | Stable | Configurable crossfade between tracks |
| Settings drawer | Stable | Slide-out panel for speed, EQ, and crossfade |
| Keyboard overlay | Stable | Press ? to see all shortcuts |
| Lyrics (romanized) | Stable | Auto-fetch and transliterate lyrics to English |
| Auto-start | Stable | Windows startup shortcut for zero-intervention operation |

## Configuration Reference

All user-specific settings live in `config/automation.yaml`. The example file (`config/automation.example.yaml`) is fully commented with every option explained.

Key sections you'll customize:

| Section | What to change |
|---------|---------------|
| `location` | Your latitude, longitude, country, subdivision |
| `playlists` | Paths to your M3U files, tags, volume profiles |
| `schedule` | Start/end times, which days, which playlists |
| `weekday_themes` | Which deity/genre gets priority on which day |
| `holiday_rules` | Festival-specific playlist overrides |
| `weather_rules` | Weather-triggered tag boosts |
| `quiet_hours` | When to reduce volume or stop |

## Stack

| Layer | Technology |
|-------|-----------|
| Language | Python 3.12+ |
| Playback | mpv (JSON IPC over named pipe) |
| Scheduler | APScheduler (BackgroundScheduler) |
| API | FastAPI + Uvicorn |
| Config | YAML + Pydantic v2 validation |
| Database | SQLite (WAL mode) |
| Weather | Open-Meteo (free, no API key) |
| Holidays | `holidays` library |
| Tests | pytest |

## Module Map

```
song_automation/
  main.py              CLI entry point
  config.py            Pydantic models for all configuration
  config_loader.py     YAML load, validate, hot-reload on file change
  context.py           Time + holidays + weather → DecisionContext
  resolver.py          Slot matching, candidate scoring, rule application
  controller.py        Reconcile loop, orchestration, volume ramping
  playback.py          mpv IPC gateway + dry-run mock
  storage.py           SQLite: sessions, overrides, events
  domain.py            Core dataclasses (no business logic)
  domain_events.py     In-process pub/sub event bus
  decision_store.py    Decision trace persistence
  feedback.py          Skip/play signal capture, preference learning
  playlist_health.py   Track health scoring, stale detection, quarantine
  mood.py              Mood state management
  environment.py       Room modes, quiet hours, signal providers
  analytics.py         Listening summaries, health reports
  discovery.py         Trending song scanner (yt-dlp search + cache)
  logging_config.py    Structured logging setup
  api.py               FastAPI routes + WebSocket + dashboard
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/status` | Current playback state, track info, and last decision |
| GET | `/preview` | What would play if a switch happened now |
| POST | `/pause` | Instantly pause mpv (no fade) |
| POST | `/resume` | Instantly resume mpv from paused position |
| GET | `/track-info` | Current track title, position, duration |
| POST | `/override` | Force a playlist or stop playback |
| DELETE | `/override` | Clear active override |
| POST | `/skip` | Skip to next track |
| POST | `/previous` | Go to previous track |
| POST | `/smart-play` | Pick best playlist using mood/room context |
| POST | `/volume` | Set playback volume (0-100) |
| POST | `/shuffle` | Toggle shuffle mode |
| POST | `/repeat` | Cycle repeat mode (off/all/one) |
| POST | `/sleep-timer` | Set sleep timer (minutes) |
| GET | `/sleep-timer` | Get sleep timer status |
| DELETE | `/sleep-timer` | Cancel sleep timer |
| GET | `/decisions` | Recent decision traces with reasoning |
| POST | `/feedback` | Submit skip/like/dislike signal |
| POST | `/feedback/like` | Like current track |
| POST | `/feedback/dislike` | Dislike current track (auto-skips) |
| GET | `/preferences` | View learned preference weights |
| GET/POST/DELETE | `/mood` | Get, set, or clear current mood |
| GET/POST | `/room` | Get or set room mode |
| GET | `/queue` | Current playlist tracks with positions |
| GET | `/playlists` | All configured playlists with metadata |
| GET | `/recently-played` | Last N unique playlists played |
| GET | `/schedule` | Today's schedule slots |
| GET | `/analytics/listening` | Listening summary (last N days) |
| GET | `/analytics/health` | System health report |
| GET | `/analytics/events` | Event log with severity filter |
| GET | `/playlist-health` | Health scores for all playlists |
| GET | `/playlist-health/{id}` | Detailed track-level health for a playlist |
| GET/POST | `/playback-speed` | Get or set playback speed (0.25-4.0x) |
| GET/POST | `/equalizer` | Get or set EQ preset (flat/bass_boost/treble/vocal/night_mode/live) |
| GET/POST | `/crossfade` | Get or set crossfade duration (0-12s) |
| GET | `/discover/trending` | Trending songs per category from YouTube |
| POST | `/discover/add-to-playlist` | Download a song and add to a playlist |
| GET | `/keyboard-shortcuts` | List all keyboard shortcuts |
| POST | `/seek` | Seek to position in current track |

## Auto-Start (Windows)

The system is designed to run 24/7 on an always-on machine. A startup shortcut in `%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\` launches the automation on every login.

For manual setup:

```bash
# Run the startup script registration
powershell -ExecutionPolicy Bypass -File scripts/register_task.ps1
```

## Remote Access (Free Hosting)

Sangeet runs on your local machine (it needs mpv for audio). To access the dashboard from your phone or anywhere else, use one of these free options:

### Option 1: Cloudflare Tunnel (recommended -- free, no sign-up)

One command, instant public URL. No account needed for quick tunnels:

```bash
# Install cloudflared: https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/
cloudflared tunnel --url http://localhost:8765
```

This prints a public `https://xxx.trycloudflare.com` URL you can open on any device. Runs as long as the terminal is open. For a permanent tunnel with a custom domain, create a free Cloudflare account and follow their [tunnel guide](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/).

### Option 2: Tailscale (best for private access)

Creates a private encrypted network between your devices. Free for personal use (up to 100 devices):

```bash
# Install: https://tailscale.com/download
# Sign in on your laptop and phone, then access:
# http://<your-laptop-tailscale-ip>:8765
```

No ports exposed to the internet. Works through firewalls and NAT.

### Option 3: Bind to LAN

For same-WiFi access (e.g., phone on home network), change the API host in your config:

```yaml
api:
  host: 0.0.0.0    # Listen on all interfaces (default is 127.0.0.1)
  port: 8765
```

Then open `http://<your-laptop-ip>:8765` from your phone. Find your IP with `ipconfig` (Windows) or `ifconfig` (Mac/Linux).

## Documentation

Detailed docs in `docs/`:

1. [`01-phased-roadmap.md`](docs/01-phased-roadmap.md) -- Development phases
2. [`02-system-design.md`](docs/02-system-design.md) -- Architecture and design decisions
3. [`03-current-workspace-state.md`](docs/03-current-workspace-state.md) -- What's implemented
4. [`04-workspace-conventions.md`](docs/04-workspace-conventions.md) -- Workspace conventions

## Contributing

1. All changes must be additive and feature-flagged
2. Every decision must carry `reasons[]` for traceability
3. Module size: 120-250 lines ideal, 350 max
4. Config changes must not break existing setups
5. Test with `pytest` before submitting

## License

MIT
