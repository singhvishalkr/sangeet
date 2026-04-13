# Music Automation Strategy Report

## Executive Summary

The strongest base architecture for your use case is not a cloud-heavy smart-home stack and not a fragile browser automation setup. It is a local-first control system on the laptop that you already keep running 24x7:

- `mpv` as the playback engine
- `Python 3.12+` as the controller
- `APScheduler` for schedule orchestration
- `SQLite` for local state and audit history
- `YAML` for human-editable schedules and playlist policies
- `Windows Task Scheduler` to auto-start the controller after boot/logon

This is the best fit because your primary requirement is reliability over a long period with smooth, unattended switching between playlists. The architecture should start as a modular monolith on one machine, not as microservices. A "central brain" becomes useful later, after the base system is stable and the behavioral data exists.

## Problem Statement Restated

You want one always-on laptop to:

- play different playlists at different times of day
- switch automatically with no manual action
- stay reliable across weeks and months
- support smooth transitions instead of abrupt cuts
- grow into calendar-aware, mood-aware, and mobile-controlled behavior

Your examples imply this baseline:

- `07:00` or `07:30`: morning bhajans
- `19:00` for `30m`: evening bhajans
- `20:00`: cooking / light energetic music
- later at night: calmer music

## What World-Class Architecture Means Here

For a single-user, single-laptop, audio-only automation system, world-class architecture means:

- high reliability under simple operating conditions
- low operational overhead
- local autonomy when the internet is unavailable
- graceful recovery after reboot or crash
- explicit state and auditability
- a clean upgrade path from rule-based automation to adaptive intelligence

It does **not** mean starting with Kubernetes, message brokers, or many services. That would be over-architecture for the current problem.

## Option Evaluation

### Option A: Browser or streaming-app automation

Examples:

- Spotify desktop automation
- browser automation of YouTube Music / JioSaavn / web players

Pros:

- easy playlist curation
- familiar user experience

Cons:

- brittle after UI changes, popups, ads, auth expiry, or browser updates
- weak unattended reliability
- policy and API limitations on playback control

Research note:
Spotify's Player APIs only work for Premium users, target the currently active device, and explicitly warn that execution ordering is not guaranteed across player endpoints. That is a poor foundation for unattended household automation.

Verdict:
Do not use as the base control plane. If desired, use streaming services later as optional content sources, not as the automation backbone.

### Option B: VLC-driven automation

Pros:

- mature media player
- broad format support
- widely installed

Cons:

- workable, but the automation/control story is less clean for this use case than mpv
- for long-term unattended control, mpv's IPC model is cleaner and more script-friendly

Verdict:
Acceptable fallback if VLC is already deeply preferred, but not the top recommendation.

### Option C: mpv-driven local controller

Pros:

- official JSON IPC support
- Windows named-pipe support
- lightweight and scriptable
- stable fit for headless or semi-headless control
- volume/property control suitable for fade logic

Cons:

- less consumer-friendly UI than mainstream music apps
- requires a small custom controller

Verdict:
Best foundation for your base implementation.

## Recommended Target Architecture

### Phase 1: Time-Based Reliable Automation

This is the implementation priority.

Components:

- `Playback Adapter`: sends play/stop/load/volume commands to mpv via IPC
- `Schedule Engine`: decides what should be active now
- `State Store`: SQLite for active session, executed actions, failures, manual overrides
- `Policy Loader`: reads YAML config for slots, playlists, transitions, defaults
- `Bootstrap/Recovery`: on boot, re-evaluates "what should be playing right now?"
- `Watchdog`: detects dead player process and recreates it

Behavior:

- controller starts automatically after Windows boot/logon
- controller loads schedule config
- every minute, and on important events, it evaluates the desired playback state
- if the desired slot changed, it fades out current content, replaces playlist, fades in target content
- if the laptop reboots at `20:17`, the controller computes that the `20:00` slot is active and resumes the correct playlist

### Phase 2: Calendar-Aware Intelligence

Add a calendar resolver in front of the time rules.

Examples:

- Monday morning -> Shiv bhajans
- Friday morning -> Devi songs
- Sunday morning -> lighter devotional / relaxed tracks
- Diwali -> festive playlist
- Janmashtami -> Krishna bhajans

Recommended model:

- `base schedule` chooses the slot
- `calendar policy` chooses the variant for that slot
- `manual override` can still win temporarily

Data sources:

- offline holiday library for India as a starter
- curated override YAML for family-specific or regional events
- Google Calendar integration for custom personal events and special dates

### Phase 3: Context-Aware Music

Add contextual inputs:

- weather
- system idle / activity state
- time-of-day intensity curve
- battery / charging state
- optional room mode set from mobile

Examples:

- raining evening -> softer acoustic set
- active kitchen time -> upbeat playlist
- laptop on battery < `30%` -> skip heavy UI and keep audio-only mode
- system idle for long duration late night -> softer playback profile

### Phase 4: Smart Transition Engine

Upgrade from simple switching to experience design.

Capabilities:

- fade out current playlist
- fade in next playlist
- gradual morning volume ramp
- evening soft handover
- anti-jolt guardrails when current volume is too high
- optional two-player crossfade later

### Phase 5: Central Brain / Real-Time Rules Engine

At this stage, introduce a dedicated decision layer:

- event bus inside the app
- current context snapshot
- rule engine + ranking engine
- explainable decision logs: "played playlist X because slot=evening, weekday=Friday, holiday=Diwali"

Important architecture principle:
Keep this inside a modular monolith first. Only separate services if you later expand beyond one machine or add remote devices.

### Phase 6: Adaptive Learning

Capture signals:

- skips
- replay count
- manual overrides
- thumbs up/down
- volume changes
- "do not play this in the morning" exclusions

Use them to adjust ranking, not to fully replace rules. In a household music system, bounded learning is safer than unconstrained recommendation drift.

### Phase 7: Full Smart Environment

Possible advanced upgrades:

- motion or occupancy sensors
- room presence
- Bluetooth proximity
- voice assistants
- family member preference profiles
- multi-room playback

This phase is optional and should only happen after the first three phases are stable.

## Architecture Decision Matrix

| Area | Recommendation | Why |
| --- | --- | --- |
| OS scheduler | Windows Task Scheduler | Native, stable, no extra daemon needed |
| Playback engine | mpv | Official IPC and clean programmatic control |
| Controller runtime | Python 3.12+ | Fastest path to robust local automation |
| Scheduling library | APScheduler | Good recurring trigger model and persistent stores |
| State store | SQLite | Ideal for single-node local state |
| Config | YAML + validation | Easy to edit, easy to review |
| API later | FastAPI | Good for mobile/web override and WebSockets |
| Mobile UI later | Mobile-first web app | Faster than building Android/iOS native first |
| Logs | Structured JSON logs + rotating files | Easy debugging and operations |

## Why Python Wins the Base Build

As an architect, I would choose Python instead of Java, Go, or Node for phase 1.

Reasons:

- fastest time to a reliable local controller
- strong Windows automation ecosystem
- mature scheduling libraries
- simple integration with mpv IPC, SQLite, YAML, REST, and calendar APIs
- ideal for phased experimentation before hardening

Why not Java first:

- excellent for large backend systems, but adds more ceremony than this laptop-local controller needs

Why not Go first:

- strong binary distribution story, but slower iteration for this workflow and ecosystem integrations

Why not Node first:

- workable, but Python's scheduling and local automation ergonomics are better for this problem

## Base System Design

### Core Domain Objects

- `Playlist`
  - id
  - name
  - source type (`local_folder`, `m3u`, `url_set`)
  - tags (`bhajan`, `evening`, `cooking`, `night`)
- `ScheduleSlot`
  - id
  - start time
  - end time
  - weekdays
  - default playlist
  - transition policy
- `Override`
  - source (`mobile`, `manual`, `calendar`, `system`)
  - effective start/end
  - priority
  - playlist or stop action
- `PlaybackSession`
  - started at
  - ended at
  - resolved playlist
  - trigger reason
  - outcome

### Resolution Order

Every decision should follow a deterministic order:

`Safety / mute rules` -> `manual override` -> `festival override` -> `calendar/day rule` -> `time slot rule` -> `default fallback`

This keeps the system explainable and debuggable.

### Transition Logic

For phase 1:

1. compute target playlist
2. if target equals current target, do nothing
3. fade current volume from current level to `0`
4. replace playlist
5. start playback
6. fade to target slot volume

This is enough for a polished first version. True crossfade can come later.

## Reliability Requirements

These are non-negotiable for the base build:

- idempotent schedule evaluation
- restart-safe state
- startup recovery
- stale-player detection
- no duplicate simultaneous playback sessions
- durable logs
- config validation before applying changes

### Failure Scenarios and Response

| Scenario | Expected Response |
| --- | --- |
| Laptop reboots | Controller auto-starts and restores correct current slot |
| mpv crashes | Watchdog restarts player and re-applies current desired state |
| Invalid config edit | Reject config, keep last known good config |
| Internet unavailable | Local playlists continue to work |
| Calendar API unavailable | Fall back to local rules |
| Weather API unavailable | Ignore context input and continue base schedule |

## Content Strategy Recommendation

For long-term reliability, prefer this order:

1. local music library or downloaded playlists
2. local `m3u` playlists
3. selectively supported URLs
4. direct streaming-service control only as a later convenience layer

If your real goal is dependable household audio, local-first media wins.

## Proposed Folder Layout for the Actual Build

```text
sangeet/
  app/
    controller/
    playback/
    scheduling/
    policy/
    storage/
    api/
    observability/
  config/
    schedule.yaml
    playlists.yaml
    calendar_overrides.yaml
  data/
    controller.db
    logs/
  tests/
```

## Suggested Initial Functional Scope

Build only these features first:

- fixed daily schedule
- weekday support
- playlist switching
- fade in / fade out
- auto-start on boot/logon
- restart recovery
- logging
- one manual temporary override command

Do **not** build these in version 1:

- ML recommendation
- sensor fusion
- native mobile apps
- cloud backend
- multi-room sync

## Concrete Phase Plan

### Phase 1 Deliverable

Goal:
One laptop plays the right playlist at the right time every day without manual intervention.

Acceptance criteria:

- morning playlist starts at configured time
- evening playlist starts at configured time
- cooking playlist starts at configured time
- transitions are smooth
- reboot recovery works
- one month of stable logs shows no duplicate playback sessions

### Phase 2 Deliverable

Goal:
Day-of-week and festival-aware playlist variants.

Acceptance criteria:

- Monday/Friday/Sunday morning variants work
- Diwali and selected festivals can override base playlists
- curated local overrides beat API-based guesses

### Phase 3 Deliverable

Goal:
Context-aware adaptation and mobile override.

Acceptance criteria:

- mobile web UI can pause, skip, override current slot
- weather and idle state can modify playlist selection
- override expiry returns system to schedule automatically

## Final Recommendation

If I were designing this as a consultant and technical architect, I would approve this roadmap:

1. Build a **local-first modular monolith** on the existing Windows laptop.
2. Use **mpv + Python + APScheduler + SQLite + YAML** as the phase-1 stack.
3. Use **Windows Task Scheduler** only to launch and recover the controller, not to encode all business logic.
4. Keep music **local-first** for reliability.
5. Add **calendar intelligence** before mood AI.
6. Add **mobile override** before adaptive learning.
7. Introduce a "central brain" only after the base and calendar-aware layers are stable.

That is the highest-probability path to a system that feels premium, reliable, and extensible without becoming over-engineered.

## Sources

- mpv manual: https://mpv.io/manual/stable
- APScheduler user guide: https://apscheduler.readthedocs.io/en/master/userguide.html
- Windows Task Scheduler overview: https://learn.microsoft.com/en-us/windows/win32/taskschd/task-scheduler-start-page
- `schtasks /create` reference: https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/schtasks-create
- Spotify Player API reference: https://developer.spotify.com/documentation/web-api/reference/start-a-users-playback
- Spotify transfer playback: https://developer.spotify.com/documentation/web-api/reference/transfer-a-users-playback
- Spotify pause playback: https://developer.spotify.com/documentation/web-api/reference/pause-a-users-playback
- Google Calendar API overview: https://developers.google.com/workspace/calendar/api/guides/overview
- Google Calendar Events reference: https://developers.google.com/calendar/api/v3/reference/events
- `holidays` library docs: https://holidays.readthedocs.io/
- India holiday support in `holidays`: https://holidays.readthedocs.io/en/main/auto_gen_docs/india/
- FastAPI WebSockets: https://fastapi.tiangolo.com/advanced/websockets/
- SQLite WAL: https://sqlite.org/wal.html
- Windows `GetLastInputInfo`: https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-getlastinputinfo
- Windows `SetThreadExecutionState`: https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-setthreadexecutionstate
