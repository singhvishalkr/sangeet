# Phase 1 Implementation Runbook

## Objective

Deliver the simplest production-worthy version:

- time-based playlist automation
- smooth switching
- reliable restart behavior
- no manual intervention during normal operation

## Recommended Stack

- OS: `Windows 10/11`
- Player: `mpv`
- Controller: `Python 3.12+`
- Scheduler: `APScheduler`
- Config: `YAML`
- State store: `SQLite`
- Startup: `Windows Task Scheduler`

## Phase 1 Scope

### In Scope

- multiple daily slots
- weekday filtering
- playlist source selection
- fade in / fade out
- controller auto-start
- crash recovery
- reboot recovery
- logging and audit trail

### Out of Scope

- weather-based selection
- holiday/festival logic
- mobile app
- machine learning
- multi-device sync

## Reference Runtime Flow

1. Windows boots or user logs in.
2. Task Scheduler launches the controller.
3. Controller validates config.
4. Controller opens SQLite and logs startup.
5. Controller starts or reconnects to mpv IPC.
6. Controller evaluates the current active slot.
7. Controller applies playback state.
8. Controller re-evaluates periodically and on config reload.

## Operational Design

### Single Source of Truth

Use config files for desired behavior and SQLite for runtime truth:

- YAML defines "what should happen"
- SQLite records "what happened"

### Recovery Model

The controller should always be able to answer:

- what slot should be active now?
- what playlist should be playing now?
- is the current player session healthy?

That makes the system restart-safe without depending on in-memory state.

## Suggested SQLite Tables

### `playback_sessions`

- `id`
- `started_at`
- `ended_at`
- `resolved_slot_id`
- `resolved_playlist_id`
- `trigger_reason`
- `status`

### `overrides`

- `id`
- `source`
- `playlist_id`
- `start_at`
- `end_at`
- `priority`
- `status`

### `events`

- `id`
- `occurred_at`
- `event_type`
- `severity`
- `payload_json`

## Controller Modules

### `config_loader`

Responsibilities:

- parse YAML
- validate schema
- reject invalid config
- support last-known-good fallback

### `schedule_resolver`

Responsibilities:

- compute active slot from local time
- decide target playlist
- expose reason metadata

### `playback_adapter`

Responsibilities:

- start mpv with IPC enabled
- send commands
- query current state
- detect broken pipe / dead process

### `transition_manager`

Responsibilities:

- fade out
- switch playlist
- fade in
- enforce max volume caps

### `recovery_manager`

Responsibilities:

- restore target state after startup
- avoid duplicate player instances
- restart player on failure

### `audit_logger`

Responsibilities:

- structured logs
- operational trail for debugging
- daily log rotation

## Phase 1 mpv Strategy

Start mpv in a controlled way:

- dedicated profile for automation
- IPC enabled
- minimal UI
- no reliance on manual keyboard input

Recommended launch characteristics:

- `--idle=yes`
- `--input-ipc-server=...`
- `--no-config` or dedicated config dir
- controller-managed volume

## Transition Policy

### Default Transition

- fade out over `4-6s`
- replace playlist
- start playback
- fade in over `6-12s`

### Morning Volume Ramp

Morning devotional playback should not begin aggressively.

Recommendation:

- start at `20-25%`
- ramp to `35-45%` over `10-15m`

### Evening Policy

- slightly quicker fade-in
- keep volume ceiling lower than cooking slot

### Cooking Slot Policy

- higher energy playlist
- slightly higher default cap
- no abrupt hard cut from devotional content

## Scheduling Model

Use a controller loop plus APScheduler:

- APScheduler manages periodic checks and scheduled tasks
- controller loop handles reconciliation and health

Do not encode every business rule directly as separate Windows scheduled tasks. That becomes hard to reason about and hard to extend.

## Task Scheduler Usage

Use Windows Task Scheduler only for:

- `ONSTART` startup
- optional `ONLOGON` backup start
- optional watchdog relaunch every few hours if process is absent

Do not use it as the rule engine.

## Proposed Base Schedule

The sample config included alongside this report assumes:

- morning bhajans: `07:00-08:00`
- evening bhajans: `19:00-19:30`
- cooking / light energetic set: `20:00-21:30`
- night calm set: `22:30-23:30`

These are placeholders and should be finalized during implementation.

## Observability

Capture these events at minimum:

- controller_started
- config_loaded
- config_rejected
- slot_changed
- playlist_started
- playlist_stopped
- fade_started
- fade_completed
- player_restarted
- override_applied
- override_expired

## Reliability Guardrails

### Guardrail 1: Last Known Good Config

Never apply a broken schedule file directly.

### Guardrail 2: Health Checks

Every minute, verify:

- mpv process exists
- IPC responds
- expected playlist is active

### Guardrail 3: Idempotent Reconciliation

Repeated evaluation must not restart the same playlist unnecessarily.

### Guardrail 4: Local Time Authority

Use the laptop's configured time zone as the source of truth and store timestamps in UTC plus local display values.

## Test Plan

### Functional Tests

- slot activation at exact boundary
- no activation outside slot window
- weekday filtering works
- overlapping slot resolution is deterministic

### Reliability Tests

- restart controller during active playback
- kill mpv process and verify recovery
- reboot laptop during active slot
- corrupt config and verify last-known-good fallback

### UX Tests

- transition sounds smooth
- morning ramp is not harsh
- evening handoff feels natural

## What To Build Immediately After Phase 1

The best next upgrade is not ML. It is calendar-aware intelligence:

1. weekday-specific variants
2. festival overrides
3. mobile override UI

That sequence gives the highest practical value.
