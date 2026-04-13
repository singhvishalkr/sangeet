# Workspace Conventions

## Goal

This project should remain easy to understand, change, and verify.

The conventions below are designed to reduce:

- oversized files
- hidden coupling
- duplicated logic
- high-context onboarding cost
- unsafe edits

## Folder Structure

Recommended structure:

```text
config/
docs/
scripts/
song_automation/
tests/
data/
deliverables/
```

### Folder Rules

- `config/`
  Only environment-free sample and template configs. No secrets.

- `docs/`
  Human-readable architecture, roadmap, and operations guidance.

- `scripts/`
  Small operational scripts only. Prefer single-purpose scripts.

- `song_automation/`
  Product code only. Each module should have a clear responsibility.

- `tests/`
  Test files paired to behavior or modules.

- `data/`
  Runtime artifacts only. Treat as generated state, not source-of-truth config.

- `deliverables/`
  Consultant-style reports and handoff artifacts.

## Module Size Guidelines

These are soft limits, not absolute laws.

### Python Files

- ideal: `120-250` lines
- acceptable: up to `350`
- review required: above `400`

If a file grows beyond that, split by responsibility rather than by arbitrary naming.

### Markdown Files

- ideal: `80-220` lines
- split when a document tries to serve too many audiences at once

### YAML Files

- keep logical sections small
- if config becomes too large, split into:
  - `automation.yaml`
  - `playlists.yaml`
  - `calendar_rules.yaml`
  - `weather_rules.yaml`

## Code Organization Rules

- one module, one primary concern
- keep pure decision logic separate from side effects
- keep config models separate from runtime domain models
- keep playback transport separate from orchestration
- keep storage calls small and explicit

## Naming Rules

- file names should be explicit and boring
- avoid ambiguous names like `utils.py` unless truly generic and tiny
- prefer `resolver.py`, `playback.py`, `storage.py`, `context.py`

## Testing Rules

- every behavior change should have a test
- scoring logic should be covered with deterministic tests
- integration tests should use dry-run playback where possible
- avoid flaky clock-dependent tests without fixed timestamps

## Documentation Rules

- every major module needs at least one clear entry in docs or README
- when adding a phase or feature, update the roadmap doc
- when changing architecture, update the system-design doc

## Editing Rules

- prefer additive changes over broad rewrites
- avoid mixing refactors with feature work unless necessary
- preserve explicit module boundaries
- do not silently change config semantics
- update docs when behavior changes

## Safe Evolution Rules

### Before Adding A New Signal

Ask:

- is this signal trustworthy?
- what happens when it is missing?
- what wins if it conflicts with an override?

### Before Adding A New Feature

Ask:

- does it belong in an existing module?
- will it increase hidden coupling?
- can it be feature-flagged?

### Before Splitting A Module

Ask:

- is the current file too large?
- are two responsibilities mixed?
- will the split make onboarding easier?

## Source Control Hygiene

Even though this workspace is a git repository, the code should still be written as if it were PR-reviewed:

- small changes
- clear module boundaries
- no dead code
- no commented-out code
- no hidden behavior in scripts

## Long-Term Refactor Triggers

Refactor when:

- one module owns config, IO, and decisioning together
- the resolver becomes too crowded with mixed concerns
- more than one feature starts sharing implicit state
- testing a module becomes hard because it touches too many systems

## Recommended Near-Term Refactors

These are not urgent today, but they should happen as phases 4+ are built:

- split decision scoring into submodules:
  - base slot scoring
  - calendar scoring
  - weather scoring
  - rotation scoring

- split API UI template from route definitions

- add dedicated logging module

- add explicit models for decision trace and feedback events
