# Notes App Implementation Tasks

These tasks implement `.spec-driven/plan.md` in dependency order. Complete each task with its new tests and interaction/regression tests passing before starting the next dependent task.

## Task 1 — Toolchain and Project Scaffold

**Status:** Complete

**Depends on:** None

**Implement**

- Install or locate the Android SDK tools, emulator, API 35 platform, API 29 x86_64 image, and JDK 17.
- Create the Gradle wrapper, Kotlin DSL root build, version catalog, `app` module, and `pixel2Api29` managed device.
- Pin all plugin and dependency versions; do not use dynamic versions.

**New tests**

- Run `./gradlew help` to prove the build scripts load.
- Run the emulator acceleration check and record the result.
- Run `./gradlew assembleDebug` and confirm the expected APK exists.

**Interaction/regression tests**

- Provision the managed device to verify the API 29 image resolves.
- Confirm no SDK path, JDK path, build output, or machine-local property is tracked.

**Done when:** A clean command-line build produces an empty debug APK and the managed device can be provisioned.

## Task 2 — Application Shell and Dark Theme

**Status:** Complete

**Depends on:** Task 1

**Implement**

- Add `NotesApplication`, `MainActivity`, a Compose root, and the always-dark Material 3 theme.
- Configure IDs, SDK levels, `adjustResize`, disabled backup/device transfer, and no network permission.
- Add the initial full-screen editor-shaped shell without feature behavior.

**New tests**

- Launch `MainActivity` and find the Compose root.
- Verify first launch uses the dark color scheme.

**Interaction/regression tests**

- Inspect the merged manifest for disabled backup and absence of `INTERNET`.
- Re-run `assembleDebug` and the launch smoke test.

**Done when:** The dark app shell launches on API 29 with the required manifest constraints.

## Task 3 — Room Schema and DAO

**Status:** Complete

**Depends on:** Task 2

**Implement**

- Add `DraftEntity`, `WorkspaceEntity`, `DraftDao`, and Room schema version 1 exactly as planned.
- Add ordered draft/workspace flows and internal write operations required by repository transactions.
- Export schema JSON to `app/schemas/`; do not enable destructive migration.

**New tests**

- Test draft insert, content update, rename, ordered query, workspace update, and deletion in memory.
- Verify duplicate display order fails while duplicate names succeed.
- Verify the exported schema matches the entities.

**Interaction/regression tests**

- Close and reopen a file-backed database and verify every field survives.
- Re-run app launch to ensure database creation does not break startup.

**Done when:** Schema version 1 supports all required data safely and reproducibly.

## Task 4 — Repository Initialization and Observation

**Status:** Complete

**Depends on:** Task 3

**Implement**

- Add domain models, `DraftRepository`, and `RoomDraftRepository`.
- Implement ordered draft/workspace flows, atomic first-run initialization, and invalid-selection repair.
- Inject deterministic clock and UUID generators for tests.

**New tests**

- Verify an empty database creates and selects `Untitled 1` atomically.
- Verify repeated initialization does not duplicate drafts or reset valid selection.
- Verify a missing selected ID repairs to the first draft.

**Interaction/regression tests**

- Reopen initialized databases and ensure initialization preserves existing state.
- Re-run DAO tests against the repository-created database.

**Done when:** The repository always exposes a valid workspace containing at least one draft.

## Task 5 — Atomic Draft Creation and Naming

**Status:** Complete

**Depends on:** Task 4

**Implement**

- Implement lowest-available `Untitled N` calculation.
- Atomically create the draft at `max(displayOrder) + 1` and select it.
- Serialize structural writes that could race naming or ordering.

**New tests**

- Cover sequential names, gaps, user-created duplicates, and freed automatic names.
- Verify creation inserts and selects in one transaction.
- Verify concurrent creation yields distinct IDs, names, and display orders.

**Interaction/regression tests**

- Verify creation neither changes existing content nor reorders existing drafts.
- Reopen a database with several created drafts and verify order and selection.

**Done when:** Every new draft has the correct available name and appears last and selected.

## Task 6 — Rename and Selection Transactions

**Status:** Complete

**Depends on:** Task 5

**Implement**

- Implement trimmed, non-empty renaming without uniqueness restrictions.
- Implement tab selection by immutable draft ID and reject missing IDs.
- Map validation and missing-target failures to app-level errors.

**New tests**

- Cover valid rename, edge trimming, blank rejection, duplicates, and missing IDs.
- Verify selection persists only for an existing ID.
- Verify rename changes `updatedAt` but not content, ID, or order.

**Interaction/regression tests**

- Verify renaming `Untitled N` frees its number for creation.
- Verify selection never changes content or ordering.

**Done when:** Rename and selection are atomic, ID-based, and fully validated.

## Task 7 — Safe Draft Deletion

**Status:** Complete

**Depends on:** Task 6

**Implement**

- Delete only by immutable draft ID.
- Preserve selection for unselected deletion; choose right then left for selected deletion.
- Atomically replace the final deleted draft with a new selected `Untitled 1`.

**New tests**

- Cover unselected, selected-middle, selected-last, and only-draft deletion.
- Verify final replacement receives a new UUID.
- Verify repeated deletion of one ID cannot delete another draft.

**Interaction/regression tests**

- Verify deletion frees automatic names without reordering survivors.
- Reopen after each scenario and verify drafts and selection.

**Done when:** Deletion cannot leave zero drafts, invalid selection, or remove a non-target draft.

## Task 8 — ViewModel State and Actions

**Status:** Complete

**Depends on:** Tasks 4–7

**Implement**

- Add immutable `NotesUiState`, `NotesAction`, dialog/error states, initialization state, and the ViewModel factory.
- Observe repository flows and expose ordered tabs with a valid selected draft.
- Serialize structural actions and retain immutable target IDs.

**New tests**

- Cover loading, initialized, and initialization-failure states.
- Verify repository changes update ordered tabs and selection.
- Verify stale IDs produce safe errors without state corruption.

**Interaction/regression tests**

- Exercise create, rename, selection, and deletion through the ViewModel against a fake repository.
- Re-run repository transaction tests to confirm the state layer does not alter domain rules.

**Done when:** Every structural user action has one deterministic state transition.

## Task 9 — Per-Draft Editor Buffers

**Status:** Complete

**Depends on:** Task 8

**Implement**

- Store `TextFieldValue` buffers by draft ID and update them immediately on input.
- Merge repository content with dirty buffers without overwriting newer text.
- Preserve cursor and text selection while switching tabs and recreating the activity.

**New tests**

- Verify multiline and Unicode input updates the correct draft immediately.
- Verify each draft restores its own text, cursor, and selection.
- Verify old repository emissions cannot replace dirty text.

**Interaction/regression tests**

- Edit one draft while selection changes repeatedly and verify no text crosses IDs.
- Create and delete drafts while other draft buffers remain intact.

**Done when:** In-memory editing is immediate and isolated by immutable draft ID.

## Task 10 — Debounced Content Persistence

**Status:** Complete

**Depends on:** Task 9

**Implement**

- Add keyed 500 ms debounce jobs per draft.
- Preserve newer input when content changes during an active save.
- Clear dirty state only after the exact content is confirmed saved.

**New tests**

- With virtual time, verify no early save and a save at 500 ms.
- Verify separate drafts debounce independently.
- Verify edits during a running save trigger a later save of newest content.

**Interaction/regression tests**

- Perform structural actions while other drafts have pending saves and verify neither side is lost.
- Re-run buffer isolation and database reopen tests.

**Done when:** Editing persists within one second without stale or cross-draft writes.

## Task 11 — Lifecycle Flush, Failures, and Retry

**Status:** Complete

**Depends on:** Task 10

**Implement**

- Flush every dirty buffer immediately from activity `onStop`.
- Map storage failures to safe state without leaking Room exceptions.
- Retain failed content and support retry for content and structural operations.
- Add a full-screen retry state for initialization failure.

**New tests**

- Verify `onStop` cancels delays and flushes all dirty drafts.
- Verify failed saves retain text and dirty state until retry succeeds.
- Verify failed structural operations leave prior committed state intact.

**Interaction/regression tests**

- Edit, background immediately, recreate, and verify latest text.
- Fail one save, edit another draft, retry, and verify both contents.

**Done when:** Backgrounding and recoverable failures cannot silently discard acknowledged text.

## Task 12 — Scrolling Tab Strip and Draft Actions

**Status:** Complete

**Depends on:** Tasks 8 and 11

**Implement**

- Add the ordered `LazyRow` tab strip, selected styling, bounded widths, close controls, Add, and Rename.
- Dispatch all tab actions by draft ID.
- Scroll newly selected and created tabs fully into view.

**New tests**

- Verify tab count, order, selected styling, and duplicate names.
- Verify Add creates/selects and Rename targets the selected draft.
- Verify overflow scrolling and off-screen selection visibility.

**Interaction/regression tests**

- Select tabs with pending saves and keep editor and tab state synchronized.
- Delete tabs around the selection and show the correct replacement.

**Done when:** Users can reliably create, identify, select, and reach every draft.

## Task 13 — Plain-Text Editor UI

**Status:** Complete

**Depends on:** Tasks 9–12

**Implement**

- Add the multiline monospaced `BasicTextField`, vertical scrolling, padding, and keyboard insets.
- Keep the tab strip outside the editor scroll container.
- Bind changes and `TextFieldValue` only to the selected draft ID.

**New tests**

- Cover entry, selection, copy, cut, and paste with multiline Unicode text.
- Verify long documents and lines remain editable and scrollable.
- Verify tabs stay visible while content scrolls.

**Interaction/regression tests**

- Paste and immediately switch tabs; keep content on the original draft.
- Rotate with the keyboard open; preserve text, selection, cursor, and access.

**Done when:** Standard Android editing works without losing draft identity.

## Task 14 — Rename and Deletion Dialogs

**Status:** Complete

**Depends on:** Tasks 7, 8, and 12

**Implement**

- Add rename dialog with prefilled name, blank validation, Cancel, and Rename.
- Close empty drafts immediately; require confirmation for any non-empty content, including whitespace.
- Bind every dialog to the immutable target ID and show the draft name in deletion confirmation.

**New tests**

- Verify valid/invalid rename and cancel behavior.
- Verify empty immediate close and non-empty cancel/confirm paths.
- Verify repeated confirmation cannot delete a replacement draft.

**Interaction/regression tests**

- Change selection while a dialog exists and keep the original target.
- Confirm deletion with a pending save and leave other drafts unchanged.

**Done when:** Rename and deletion match every draft-management requirement and error case.

## Task 15 — Error UI, Accessibility, and Responsive Layout

**Status:** Complete

**Depends on:** Tasks 11–14

**Implement**

- Add operation-specific error banner with Retry, Dismiss, and live-region semantics.
- Finish colors for text, cursor, selection, tabs, dialogs, and errors.
- Add content descriptions, selected semantics, and 48 dp touch targets.
- Handle long names, large font scale, both orientations, and keyboard overlap.

**New tests**

- Verify every failure type presents recoverable UI without false success.
- Inspect semantics for icons, selected tabs, dialogs, errors, and retry.
- Verify touch bounds and usability at large font scale in both orientations.

**Interaction/regression tests**

- Present errors during rename/deletion and keep focus and targets safe.
- Run editor, overflow, dialog, and lifecycle tests in both orientations.

**Done when:** Core flows remain readable, operable, accessible, and recoverable.

## Task 16 — Cross-Feature Acceptance Suite

**Status:** Complete

**Depends on:** Tasks 3–15

**Implement**

- Add fixtures for clean launch, recreation, database reopen, relaunch, and injected failures.
- Automate all acceptance criteria across the five feature specifications.

**New tests**

- Create, rename, edit, select, close, relaunch, and verify complete restored state.
- Edit several tabs, background immediately, relaunch, and verify latest text.
- Verify confirmed and canceled deletion outcomes after relaunch.
- Run core operations without networking.

**Interaction/regression tests**

- Repeat flows with duplicate names, Unicode, long names/documents, and reused name gaps.
- Combine save failure, retry, tab switching, backgrounding, and relaunch.

**Done when:** Every acceptance criterion is automated or explicitly documented as manual.

## Task 17 — Headless Managed-Device Stabilization

**Status:** Complete

**Depends on:** Task 16

**Implement**

- Finalize `pixel2Api29`, isolate test data, and replace timing assumptions with deterministic synchronization.
- Document the exact headless command and server prerequisites.

**New tests**

- Run `./gradlew pixel2Api29DebugAndroidTest` repeatedly from clean state.
- Verify orientation, keyboard, database reopen, and accessibility tests pass headlessly.

**Interaction/regression tests**

- Run unit, Room, and device suites together to expose order dependencies.
- Recreate the managed device and repeat the suite.

**Done when:** The complete suite passes headlessly and independently of execution order.

## Task 18 — Quality Gate and Debug APK Handoff

**Status:** Complete

**Depends on:** Tasks 1–17

**Implement**

- Resolve app-owned correctness, accessibility, and reliability findings.
- Update `README.md` with verified SDK, KVM, build, test, install, and APK instructions.
- Record pinned versions and final Room schema; produce the APK and checksum.

**New tests**

- From clean checkout, run `testDebugUnitTest`, `pixel2Api29DebugAndroidTest`, `lintDebug`, and `assembleDebug`.
- Install with `adb install -r` and perform a clean-launch smoke test.

**Interaction/regression tests**

- Run a final scenario covering create, rename, edit, switch, background, relaunch, cancel deletion, confirm deletion, and final-draft replacement.
- Confirm no network permission, external service, destructive migration fallback, or backup path exists.

**Done when:** The reproducible server build passes every gate and yields the documented installable debug APK.
