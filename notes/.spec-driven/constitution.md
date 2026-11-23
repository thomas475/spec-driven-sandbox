# Notes App Constitution

**Version:** 1.1  
**Updated:** 2026-11-23

Feature specifications under `specs/` define product behavior. This document records the engineering decisions for delivering it.

## Technology

- Kotlin, Jetpack Compose, Material 3, and Gradle wrapper
- Android 10 (API 29) minimum
- Room, coroutines, and `Flow`
- One application module

## Architecture

- Unidirectional flow: Compose UI → ViewModel → repository → Room
- Compose renders immutable state and emits actions.
- The ViewModel owns screen state and save coordination.
- The repository exclusively owns Room access and transactions.

## Domain Model

- `Draft`: stable ID, name, plain-text content, display order, created timestamp, updated timestamp
- `Workspace`: selected draft ID
- IDs define identity; names may repeat.
- New drafts use the lowest available `Untitled N`.
- At least one draft always exists; non-empty deletion requires confirmation.

## External Services

- None: no accounts, analytics, ads, sync, or network dependency.
- User data stays in the local Room database.

## User Interface

- One primary screen: scrolling tab strip, plain-text editor, and minimal draft actions.
- Dark mode and a monospaced editor are the defaults.
- Use standard Android editing behavior and accessible controls.
- Preserve content and selection across orientation changes.

## Testing

- Unit tests cover domain rules and ViewModel transitions.
- Room tests cover persistence, restoration, and migrations.
- Compose/device tests cover feature-spec acceptance flows.
- Device tests run on the headless Gradle-managed emulator.

## Error Handling and Reliability

- Text changes persist within one second and flush when the app is backgrounded.
- Drafts and workspace state survive process and app restarts.
- Failed saves retain in-memory text and show a recoverable error.
- Database migrations are tested; destructive migration is forbidden.
- Creation and confirmed deletion are atomic.

## Scope and Engineering Discipline

- Build only the first-release behavior defined under `specs/`.
- Do not add sync, rich text, Markdown preview, filesystem editing, search, or tab reordering without changing the specification first.
- Prefer platform APIs and direct code over speculative abstractions.
- Add dependencies only for a current requirement.
- Every change must trace to a requirement and include proportionate tests.
- A milestone is complete only when tests pass and Gradle produces an installable debug APK.
