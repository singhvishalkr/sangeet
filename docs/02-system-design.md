# System Design

## Architectural Position

This project should be built as a **local-first modular monolith**.

That is the right answer because:

- one laptop is the main execution environment
- reliability matters more than distributed scale
- audio playback needs local interactive-session execution
- operations should stay simple
- advanced intelligence can still be layered in later

Microservices would add complexity without solving the main problem.

## Research-Backed Technology Choices

### Playback

Primary choice: `mpv`

Why:

- official IPC support via `--input-ipc-server`
- named-pipe support on Windows
- programmatic property and command control
- suitable for fade and playlist operations

### Scheduler

Primary choice: `APScheduler`

Why:

- recurring triggers
- background scheduler mode
- persistent-store support when needed
- good fit for periodic reconciliation and scheduled tasks

### Startup

Primary choice: `Windows Task Scheduler`

Why:

- native startup/logon trigger support
- interactive-session execution support
- simpler and safer than building a custom service

Important:
Do not run the audio controller as `SYSTEM` for normal playback. Microsoft documents that `SYSTEM` tasks do not have interactive logon rights, so users cannot see or interact with those programs. For audio workloads, the controller should run in the logged-in interactive user session.

### API Layer

Primary choice: `FastAPI`

Why:

- light local control surface
- auto docs when needed
- good fit for local mobile UI and later WebSocket support

### Runtime State

Primary choice: `SQLite`

Why:

- single-node reliability
- embedded simplicity
- WAL support for robustness
- enough for sessions, overrides, events, and learning data

### Holiday Data

Primary choice: `holidays`

Why:

- local computation
- country and subdivision support
- good fallback when cloud calendar data is absent

### Weather Data

Primary choice: `Open-Meteo`

Why:

- no API key required for personal use
- simple JSON API
- enough resolution and current conditions for this use case

## Core System Components

### 1. Config Layer

Responsibilities:

- load YAML
- validate references
- reject invalid changes
- preserve deterministic rules

### 2. Context Layer

Responsibilities:

- resolve local time and timezone
- load holiday context
- fetch weather context
- normalize signals into a stable decision context

### 3. Decision Layer

Responsibilities:

- identify active slot
- rank playlist candidates
- apply override precedence
- explain why a winner was chosen

### 4. Playback Layer

Responsibilities:

- start and maintain `mpv`
- switch playlists
- adjust volume
- perform fades
- stop playback safely

### 5. State Layer

Responsibilities:

- session history
- events and audit trail
- overrides
- future learning data

### 6. Control Layer

Responsibilities:

- expose status
- allow manual override
- allow pause and resume-to-schedule
- later provide richer mobile controls

## Decision Flow

Every playback decision should follow this order:

1. system safety and stop conditions
2. active manual override
3. calendar or festival override
4. active schedule slot
5. weather scoring
6. freshness and anti-repeat scoring
7. fallback stop or default

This ordering keeps decisions explainable and stable.

## Data Model

### Core Tables

- `playback_sessions`
- `overrides`
- `events`

### Future Tables

- `feedback_events`
- `decision_traces`
- `preference_weights`
- `sensor_signals`

## Non-Functional Requirements

### Reliability

- restart-safe
- idempotent reconciliation
- no duplicate player launches
- config validation before apply
- graceful degradation when internet APIs fail

### Explainability

- every decision should include reasons
- advanced phases should not become opaque

### Maintainability

- small, focused modules
- explicit boundaries
- low hidden coupling

### Safety

- no fragile browser scraping as the core system
- no hidden destructive automation
- manual override always available

## Deployment Model

### Local Laptop Deployment

Recommended:

- one Python process
- one `mpv` process
- one SQLite file
- one Task Scheduler entry
- one local API endpoint

### Why Not A Service Mesh Or Cloud-Heavy Setup

- unnecessary complexity
- worse debuggability
- less resilient to local internet outages
- not aligned with the single-device problem

## Failure Handling Strategy

### If `mpv` crashes

- detect loss of process or IPC
- restart `mpv`
- re-evaluate desired state
- restore the active slot

### If weather API fails

- log the failure
- ignore weather context temporarily
- continue with time/calendar decisioning

### If holiday rule is wrong

- local curated override file should win
- add explicit date rules where needed

### If config is invalid

- reject reload
- retain last known good config
- log the reason

## Rollout Strategy

### Rollout 1

- dry-run with preview decisions only
- verify scheduling and scoring

### Rollout 2

- enable real playback
- test only one morning and one evening slot

### Rollout 3

- enable all base slots
- run for one week

### Rollout 4

- enable calendar rules
- verify with simulated dates

### Rollout 5

- enable weather rules and smart rotation

### Rollout 6

- introduce mobile-first usage and feedback collection

## Product Experience Principles

### Predictable First

Users should trust the system before it becomes highly adaptive.

### Curated, Not Random

Variation should feel tasteful, not noisy.

### Local First

The system should still be useful when the internet is down.

### Explainable Intelligence

You should always be able to answer:

- why is this playing?
- what would play next?
- why did it change?

## Sources

- `mpv` manual: https://mpv.io/manual/stable
- APScheduler documentation: https://apscheduler.readthedocs.io/en/master/userguide.html
- Windows Task Scheduler `schtasks /create`: https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/schtasks-create
- FastAPI documentation: https://fastapi.tiangolo.com/
- Open-Meteo docs: https://open-meteo.com/en/docs
- Open-Meteo about: https://open-meteo.com/en/about
- `holidays` documentation: https://holidays.readthedocs.io/
- SQLite WAL: https://sqlite.org/wal.html
