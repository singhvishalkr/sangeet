# Phased Roadmap

## Program Goal

Turn one always-on laptop into a dependable personal music automation system that:

- plays the right content at the right time
- changes mood intelligently without feeling random
- responds to festivals, weekdays, weather, and manual intent
- stays easy to operate and maintain over long periods

The roadmap is intentionally phased so we build reliability before intelligence.

## Phase 1: Time-Based Automation

### Objective

Deliver a production-worthy base that plays scheduled playlists automatically with no manual intervention.

### User Value

- morning bhajans start automatically
- evening devotional playback happens on time
- cooking-time music starts without effort
- late-night music becomes softer

### Scope

- daily time slots
- weekday support
- playlist switching
- fade-out and fade-in
- reboot/logon recovery
- local runtime state
- manual override

### Architecture

- `mpv` playback engine
- local controller in Python
- APScheduler reconciliation loop
- SQLite runtime history
- YAML config for playlists and rules
- FastAPI local control surface

### Acceptance Criteria

- active slot is restored after restart
- no duplicate playback sessions on repeated reconciliation
- time-slot switching is smooth
- invalid config does not break the running system

### Execution Steps

1. finalize playlist files and folder paths
2. install Python environment and dependencies
3. install `mpv`
4. validate the sample YAML against the real playlist paths
5. run in `--dry-run` mode
6. run with real `mpv`
7. register the Windows scheduled task
8. test reboot recovery and slot transitions

## Phase 2: Calendar And Theme Intelligence

### Objective

Make the system culturally and contextually aware of the day.

### User Value

- Monday can feel like Shiv morning
- Friday can feel like Devi morning
- Sunday can feel more relaxed
- Diwali and Janmashtami can override the normal schedule

### Scope

- weekday themes
- Indian holiday resolution
- custom explicit festival rules
- slot-specific seasonal or spiritual variants

### Architecture

- day-level rule engine layered above base time slots
- holiday provider with local rule augmentation
- deterministic override precedence

### Design Rules

- holiday or festival rules should be explainable
- local curated rules should beat generic public holiday guesses
- calendar intelligence should change selection, not destabilize playback

### Acceptance Criteria

- special dates consistently select the intended playlists
- a normal weekday still falls back correctly when no theme applies
- holiday data outages do not stop phase 1 behavior

### Execution Steps

1. add curated festival list for your family and region
2. tag playlists by deity, mood, season, and celebration type
3. tune weekday boosts and exclusivity rules
4. test a simulated week and simulated festival dates

## Phase 3: Weather And Freshness Intelligence

### Objective

Make playlist choice feel less repetitive and more naturally aligned to the environment.

### User Value

- rainy evenings can feel cozy
- cooler nights can feel softer
- repeated playlists are avoided when alternatives exist

### Scope

- weather-aware rule boosts
- freshness bonuses
- recent-repeat penalties
- more varied daily listening without losing schedule predictability

### Architecture

- weather snapshot provider
- tag-based scoring rules
- session-history-based candidate ranking

### Smart Behavior

- not pure randomness
- not static every day
- not opaque ML

The system should feel curated, not chaotic.

### Acceptance Criteria

- immediate playlist repetition becomes rare
- rainy/cool/hot situations can influence slot selection
- failures in the weather provider gracefully degrade to phase 2 behavior

### Execution Steps

1. tune playlist tags for weather suitability
2. tune freshness penalties against session history
3. simulate multiple weeks of use
4. verify that scoring still picks sensible playlists

## Phase 4: Experience And Transition Engine

### Objective

Move from "functional switching" to "premium listening experience."

### User Value

- softer waking experience
- no harsh cut between devotional and cooking music
- more professional-feeling audio transitions

### Scope

- morning volume ramp
- slot-specific transition profiles
- anti-jolt volume safety caps
- true crossfade option for future dual-player mode
- transition scenes such as devotional -> ambient -> upbeat

### Technical Direction

- extend transition policy model
- optionally manage two player instances for real crossfade
- add track-aware switch windows if desired later

### Acceptance Criteria

- transitions are perceived as natural
- morning starts are gentle
- cooking slot feels energetic but not abrupt

### Execution Steps

1. add slot-specific transition presets
2. implement curve-based volume ramps
3. introduce optional dual-player experimentation behind a feature flag
4. tune by listening, not only by code review

## Phase 5: Central Brain And Real-Time Orchestration

### Objective

Replace scattered rule handling with a unified decision service inside the app.

### User Value

- one place to understand why the system chose a playlist
- easier future expansion to mobile and sensors
- cleaner mental model for overrides and automation

### Scope

- central decision engine
- normalized context snapshot
- ranked candidate explanations
- event-driven internal orchestration

### Architecture

- modular monolith, not microservices
- explicit event types
- explainability log per decision
- state machine for playback lifecycle

### Acceptance Criteria

- every selection can be traced to rules and signals
- manual override precedence remains deterministic
- new context signals can be added without rewriting the whole app

### Execution Steps

1. formalize domain events
2. introduce a decision trace model
3. separate signal collection from decision evaluation
4. add observability views for decisions and outcomes

## Phase 6: Adaptive Learning

### Objective

Use behavior feedback to gently personalize the music system.

### User Value

- the system learns what tends to get skipped
- the system favors content that works well in certain slots
- recommendations feel personal without becoming bizarre

### Scope

- skip events
- replay counts
- manual overrides
- simple likes/dislikes
- bounded ranking adjustments

### Architecture

- feedback table in SQLite first
- lightweight preference scoring model
- strict caps on auto-adjustment

### Important Principle

Do not let ML fully control the system at first. Learning should adjust ranking inside safe boundaries defined by rules.

### Acceptance Criteria

- learning improves variety and fit without producing obvious mistakes
- user can reset or disable learned preferences
- explainability still exists

### Execution Steps

1. capture interaction signals
2. create a preference profile per slot or tag
3. tune bounded weight adjustments
4. add reset/export/import tooling

## Phase 7: Smart Environment

### Objective

Let the system respond to real-world conditions beyond calendar and weather.

### User Value

- music can respond to occupancy, motion, or room mode
- quiet hours or no-one-home situations can be respected
- special home scenes can feel magical

### Scope

- occupancy sensors
- Bluetooth or device presence
- optional smart-home integrations
- room modes like prayer, cooking, guests, quiet, celebration

### Architecture

- sensor adapters
- signal normalization
- trust ranking for noisy sensors
- policy engine that combines sensor state with existing rules

### Acceptance Criteria

- sensors never make the system feel unstable
- false positives are tolerated safely
- privacy is preserved

### Execution Steps

1. add a single simple presence signal first
2. evaluate false-positive behavior
3. add explicit house modes before aggressive automation
4. only then expand sensor variety

## Phase 8: Mobile And Human Control Layer

### Objective

Give simple real-world control without breaking automation.

### User Value

- pause for one hour
- play devotional music now
- mark a playlist as loved or overused
- switch back to schedule automatically later

### Scope

- mobile-friendly web UI
- quick presets
- override TTL
- visibility into current decision and reasons

### Architecture

- local-first web app
- authenticated API
- WebSocket or polling for live updates

### Acceptance Criteria

- override is simple and safe
- schedule resumes automatically when TTL ends
- current state is understandable at a glance

## Phase 9: Analytics, Quality, And Long-Term Operations

### Objective

Make the system maintainable over months and years.

### Scope

- health dashboard
- audit trail
- backup and restore
- config versioning
- incident notes and recovery scripts

### Acceptance Criteria

- failures can be diagnosed
- database and config can be backed up
- upgrades do not feel risky

## Recommended Delivery Sequence

1. Phase 1
2. Phase 2
3. Phase 3
4. Phase 8
5. Phase 4
6. Phase 5
7. Phase 6
8. Phase 7
9. Phase 9

This order maximizes user value while controlling technical risk.
