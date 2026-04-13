# Sangeet — Developer Guide

## Product Goal

A local-first, always-on intelligent music automation system that plays
the right playlist at the right time based on schedule, weekday themes, holidays,
weather, mood, and learned preferences. Playback is via mpv; the decision engine is
rule-based with bounded adaptive learning.

## Stack

| Layer       | Technology                        |
|-------------|-----------------------------------|
| Language    | Python 3.12+                      |
| Packaging   | setuptools (`pyproject.toml`)     |
| Playback    | mpv (JSON IPC over Windows pipe)  |
| Scheduler   | APScheduler (BackgroundScheduler) |
| API         | FastAPI + uvicorn                 |
| Config      | YAML + Pydantic v2                |
| Database    | SQLite (WAL mode)                 |
| Weather     | Open-Meteo (no API key)           |
| Holidays    | `holidays` library                |
| Tests       | pytest                            |

## How to Run

```bash
# Install
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"

# Dry-run (no mpv needed)
sangeet --config config/automation.example.yaml --dry-run

# Real playback (mpv must be on PATH)
sangeet --config config/automation.example.yaml

# Tests
pytest
```

## Module Map

```
song_automation/
  main.py              CLI entry point (argparse → controller or uvicorn)
  config.py            Pydantic models for AppConfig and all sub-configs
  config_loader.py     YAML load, validate, hot-reload on mtime change
  context.py           ContextService: time + holidays + weather → DecisionContext
  resolver.py          Slot matching, candidate scoring, rule application
  controller.py        MusicController: APScheduler reconcile loop, orchestration
  playback.py          PlaybackGateway protocol + DryRun and Mpv implementations
  storage.py           SQLite: sessions, overrides, events
  domain.py            Core dataclasses (no business logic)
  domain_events.py     Lightweight in-process pub/sub event bus
  decision_store.py    Decision trace persistence
  logging_config.py    Structured logging setup
  feedback.py          Feedback capture and preference learning
  playlist_health.py   Track health scoring, stale detection, quarantine
  mood.py              Mood input handling and context integration
  environment.py       Room modes, quiet hours, signal providers
  analytics.py         Listening summaries, health reports, operational insights
  discovery.py         Trending song discovery (yt-dlp search, cache, scheduler)
  api.py               FastAPI routes + WebSocket + dashboard
```

## Decision Flow (sacred order)

1. System safety / stop conditions
2. Active manual override
3. Calendar / festival override
4. Active schedule slot
5. Weather scoring
6. Freshness / anti-repeat scoring
7. Learned preference adjustments (bounded)
8. Fallback stop or default

Never reorder these layers. New signals slot into this chain; they do not replace it.

## Key Conventions

- **Feature flags**: every capability can be toggled in `config.features`
- **Additive changes**: prefer adding over rewriting; never break existing behavior
- **Module size**: 120–250 lines ideal, 350 max; split by responsibility
- **Testing**: deterministic, no flaky clocks, use dry-run playback
- **Config safety**: never commit secrets; validate before apply; reject bad reloads
- **Explainability**: every decision carries `reasons` list for traceability

## Config

The canonical sample config is `config/automation.example.yaml`. Real configs
(with actual playlist paths and auth tokens) go in `config/automation.yaml`
which is gitignored.

## Docs

Read in order: `docs/README.md` → `01-phased-roadmap.md` → `02-system-design.md`
→ `03-current-workspace-state.md` → `04-workspace-conventions.md`
