# Current Workspace State

## Summary

This workspace contains a fully implemented intelligent music automation system
spanning Phases 0 through 8 of the master plan. It includes time-based scheduling,
calendar/holiday awareness, weather context, mood input, adaptive learning,
room modes, quiet hours, a mobile-first dashboard with WebSocket, decision tracing,
analytics, and backup/restore tooling.

## What Exists

### Workspace Foundation (Phase 0)
- Git repository with `.gitignore`
- `AGENTS.md` developer guide
- Scoped rule files for code style, config safety, testing, and architecture

### Production Hardening (Phase 1)
- mpv health watchdog with auto-restart and decision re-application
- Structured logging across all modules
- Dashboard auth token fix (JS sends `X-Auth-Token` header)
- Volume ramp using background thread over `ramp_minutes`
- Expanded test suite (overnight slots, config reload, override lifecycle, weather degradation)

### Decision Intelligence (Phase 2)
- `decision_traces` table in SQLite with full candidate scores and context snapshots
- `/decisions` API endpoint for querying decision history
- Dashboard shows "Why This Playlist?" reasons and decision timeline
- Lightweight in-process domain event bus (`domain_events.py`)

### Transition Engine (Phase 3)
- Slot-specific transition presets in config (fade times, curve type, max jump)
- Curve-based volume fading (linear, ease_in, ease_out, logarithmic)
- Anti-jolt safety (max volume jump per step)
- Dual-player crossfade foundation (feature-flagged behind `features.dual_player`)

### Adaptive Learning (Phase 4)
- `feedback_events` and `preference_weights` tables
- Skip detection via mpv `playlist-pos` monitoring
- Bounded preference scoring (max +/- 15 points, rules always dominate)
- Time-based decay function for learned weights
- `/feedback`, `/preferences` API endpoints

### Context Enrichment (Phase 5)
- Mood input via `/mood` API (energy 1-5, valence 1-5, activity)
- Mood tags derived and injected into resolver scoring
- Weather bucket normalization (clear, rain, hot, cold, windy, stormy, pleasant, etc.)
- Time-of-day enrichment (early_morning, morning, afternoon, evening, night, late_night)
- Season awareness (spring, summer, autumn, winter based on hemisphere)

### Mobile-First Control (Phase 6)
- Separated static dashboard (HTML/CSS/JS in `static/`)
- WebSocket endpoint (`/ws`) for real-time status push (2s interval)
- Mood selector with energy/valence sliders and activity chips
- Decision timeline with candidate scores
- Schedule viewer showing active slot

### Production Dashboard Overhaul (Phase 10)
- Spotify-inspired dark UI with unified transport bar
- True instant pause/resume via mpv IPC (`POST /pause`, `POST /resume`)
- Live track progress bar with title, elapsed/total time
- Single volume control in transport bar (removed duplicate)
- Sidebar search across playlists and tags with keyboard navigation
- Playlist tag filtering on Playlists page
- Collapsible "Why this playlist?" card
- Consolidated Room Mode + Mood into single Context card
- Queue view with current track highlighting (removed fake drag-reorder)
- CSS-only bar charts for analytics (sessions per day, most played)
- Proper loading states, error toasts, empty states with CTAs
- Keyboard shortcut hints in sidebar footer
- Three-state volume icon (muted/low/high)
- Connection status indicator with live/offline states
- `prefers-reduced-motion` media query support

### World-Class Feature Parity (Phase 11)
- **Now Playing fullscreen panel**: expandable from transport bar with animated gradient background that shifts hue based on playlist tags, large track title, playlist context, progress bar, full playback controls, like/dislike buttons
- **Smart Play**: when no schedule slot is active, picks the best playlist using mood, room mode, and freshness scoring (`POST /smart-play`)
- **Shuffle/Repeat toggles**: visible in transport bar and now-playing panel, cycle repeat modes (off/all/one), toggle shuffle (`POST /shuffle`, `POST /repeat`)
- **Like/Dislike**: rate tracks from transport bar, now-playing panel, or queue items; feeds directly into adaptive learning (`POST /feedback/like`, `POST /feedback/dislike`)
- **Sleep Timer**: set countdown (15 min to 2 hours) after which playback fades out and stops gracefully; live countdown display (`POST /sleep-timer`, `GET /sleep-timer`, `DELETE /sleep-timer`)
- **Recently Played**: Home page shows last 5 unique playlists with one-tap replay (`GET /recently-played`)
- **Playlist Detail View**: click playlist card to see all tracks, health score, play-all button in a modal
- **Track name marquee**: long track names scroll smoothly in the transport bar using CSS animation
- **Transport glow**: subtle green glow on transport bar when playing
- **Gradient shift**: now-playing panel background gradient shifts based on playlist tag hashes
- **Enhanced keyboard shortcuts**: L (like), S (shuffle), R (repeat), N (now playing panel), Escape (close panels)
- **Queue like buttons**: per-track like buttons in the queue view

### Smart Environment (Phase 7)
- `SignalProvider` protocol for pluggable sensor adapters
- `DevicePresenceProvider` placeholder for Bluetooth/WiFi detection
- `RoomModeService` with configurable modes (prayer, cooking, guests, quiet, celebration, sleep)
- Room mode tags injected into resolver scoring
- Quiet hours with volume capping or playback stop
- `/room` API endpoint

### Analytics and Operations (Phase 8)
- Listening analytics (daily/weekly summaries, playlist counts, override frequency)
- Health report (mpv restarts, config reload history, error log)
- Config change history
- Event log with severity filtering
- Backup/restore script (`scripts/backup.py`) with SQLite backup, JSON export
- `/analytics/*` API endpoints

### Playlist Health and Stale Management (Phase 9)
- Track-level health scoring (0-100) based on play count, skip rate, recency
- Stale track detection (not played in 60+ days, never played, high skip rate)
- Quarantine workflow: move low-health tracks to `_quarantine/` subfolder (never auto-delete)
- Restore from quarantine via API
- `/playlist-health`, `/quarantine` API endpoints
- Integrated into controller for automatic tracking

## Module Map

```
song_automation/
  main.py             CLI entry point
  config.py           Pydantic models (AppConfig + all sub-configs)
  config_loader.py    YAML load, validate, hot-reload
  context.py          ContextService: time + holidays + weather + buckets + seasons
  resolver.py         Slot matching, candidate scoring, mood/learning integration
  controller.py       MusicController: reconcile loop, watchdog, ramp, events
  playback.py         PlaybackGateway protocol + DryRun, Mpv, DualPlayer
  storage.py          SQLite: sessions, overrides, events
  domain.py           Core dataclasses
  domain_events.py    In-process pub/sub event bus
  decision_store.py   Decision trace persistence
  feedback.py         Feedback capture and preference learning
  mood.py             Mood input handling
  environment.py      Sensor adapters, room modes, quiet hours
  playlist_health.py  Track health scoring, stale detection, quarantine
  analytics.py        Listening analytics and health metrics
  logging_config.py   Structured logging setup
  api.py              FastAPI routes + WebSocket + static files
```

## API Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/` | Dashboard (static HTML) |
| GET | `/health` | Health check |
| GET | `/status` | Current playback status + track info |
| GET | `/preview` | Preview next decision |
| POST | `/reconcile` | Force reconciliation |
| POST | `/pause` | Instantly pause mpv (no fade) |
| POST | `/resume` | Instantly resume from paused position |
| GET | `/track-info` | Current track title, position, duration |
| POST | `/override` | Apply manual override |
| DELETE | `/override` | Clear override |
| POST | `/skip` | Skip to next track |
| POST | `/previous` | Go to previous track |
| POST | `/smart-play` | Pick best playlist using mood/room context |
| POST | `/volume` | Set volume (0-100) |
| POST | `/shuffle` | Toggle shuffle mode |
| POST | `/repeat` | Cycle repeat mode (off/all/one) |
| POST | `/sleep-timer` | Set sleep timer |
| GET | `/sleep-timer` | Get sleep timer status |
| DELETE | `/sleep-timer` | Cancel sleep timer |
| GET | `/decisions` | Decision trace history |
| POST | `/feedback` | Submit feedback signal |
| POST | `/feedback/like` | Like current track |
| POST | `/feedback/dislike` | Dislike current track |
| GET | `/preferences` | View learned preferences |
| DELETE | `/preferences` | Reset preferences |
| GET | `/mood` | Current mood state |
| POST | `/mood` | Set mood |
| DELETE | `/mood` | Clear mood |
| GET | `/room` | Current room mode |
| POST | `/room` | Set room mode |
| GET | `/queue` | Current playlist tracks |
| GET | `/playlists` | All configured playlists |
| GET | `/recently-played` | Last N unique playlists played |
| GET | `/schedule` | Today's schedule slots |
| GET | `/analytics/listening` | Listening summary |
| GET | `/analytics/health` | Health report |
| GET | `/analytics/config-history` | Config change log |
| GET | `/analytics/events` | Event log |
| GET | `/playlist-health` | All playlist health scores |
| GET | `/playlist-health/{id}` | Detailed track-level health |
| GET | `/quarantine` | List quarantined tracks |
| POST | `/quarantine/{id}` | Quarantine stale tracks |
| POST | `/quarantine/restore` | Restore quarantined track |
| WS | `/ws` | Real-time status push (2s interval) |
