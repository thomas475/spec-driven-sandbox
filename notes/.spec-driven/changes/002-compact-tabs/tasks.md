# Compact Tabs Change Tasks

## Purpose

Keep the existing tab design and name truncation while preventing a wide tab from partially covering its close control at the right edge of the visible tab strip.

## Task 1 — Specify Visible Close Control

**Status:** Complete

- Add the close-control visibility requirement and acceptance criterion to `specs/tab-navigation/spec.md`.

## Task 2 — Reduce Maximum Tab Width

**Status:** Complete

- Reduce the maximum tab width by 24 dp without changing minimum touch targets, truncation, scrolling, or fixed action buttons.

## Task 3 — Verify Narrow Layout

**Status:** Complete

- Add a Compose layout test proving the complete 48 dp close control remains inside the visible tab strip on a 320 dp-wide layout.
- Run the affected Compose tests and debug build.

## Verification

- `NotesScreenTest` and `NotesAccessibilityTest`: 10 tests passed on the API 29 managed device.
- `assembleDebug`: passed; updated APK available at `app/build/outputs/apk/debug/app-debug.apk`.
