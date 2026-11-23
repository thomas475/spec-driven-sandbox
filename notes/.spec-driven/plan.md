# Notes App Implementation Plan

## Purpose

This plan turns the constitution and the feature specifications under `specs/` into an implementation sequence. The decisions below are final for the first release unless a feature specification or the constitution is amended first.

## 1. Locked Project Decisions

### Application Baseline

- App name: `Notes`
- Namespace and application ID: `com.specdriven.notes`
- One `app` module using Kotlin DSL build files
- Minimum SDK: 29 (Android 10)
- Compile and target SDK: 35
- Java and Kotlin JVM toolchain: 17
- Debug APK output: `app/build/outputs/apk/debug/app-debug.apk`
- No release signing, publishing, product flavors, or multi-module split in the first release

### Build and Dependencies

- Pin all plugin and library versions in `gradle/libs.versions.toml`; dynamic versions are forbidden.
- Use the Gradle wrapper and Android Gradle Plugin with a mutually supported stable version pair.
- Use the Kotlin Compose compiler plugin and the Compose BOM to keep Compose libraries aligned.
- Runtime libraries: Compose BOM, Material 3, Activity Compose, Lifecycle Runtime Compose, Lifecycle ViewModel Compose, Room Runtime, Room KTX, and Kotlin coroutines.
- Code generation: KSP for Room.
- Tests: JUnit, Kotlin coroutines test, AndroidX Test, Room Testing, Compose UI Test, and the Gradle Managed Devices plugin support supplied by AGP.
- Do not add Hilt, Navigation Compose, WorkManager, Retrofit, analytics, logging services, or other frameworks.
- Construct the database, repository, and ViewModel factory manually from `NotesApplication`.

### Android Configuration

- `NotesApplication` creates the Room database and the single repository instance.
- `MainActivity` hosts one Compose screen and uses `adjustResize` for the software keyboard.
- The manifest declares no network permissions.
- Disable Android cloud backup and device-to-device transfer for app data so drafts remain local.
- Use one always-dark theme in the first release; there is no theme toggle or system-theme switching.
- Export Room schemas into `app/schemas/` and commit them.

## 2. Source Layout

All production code remains under `app/src/main/java/com/specdriven/notes/`:

```text
NotesApplication.kt
MainActivity.kt
data/
  DraftRepository.kt
  RoomDraftRepository.kt
  local/
    DraftDao.kt
    DraftEntity.kt
    NotesDatabase.kt
    WorkspaceEntity.kt
domain/
  Draft.kt
  DraftName.kt
  Workspace.kt
ui/
  NotesAction.kt
  NotesScreen.kt
  NotesUiState.kt
  NotesViewModel.kt
  NotesViewModelFactory.kt
  components/
    DraftTab.kt
    Editor.kt
    ErrorBanner.kt
  theme/
    Color.kt
    Theme.kt
    Type.kt
```

Use `app/src/test/` for pure domain and ViewModel tests. Use `app/src/androidTest/` for Room, Compose, lifecycle, accessibility, and persistence tests.

## 3. Domain and Storage Model

### Draft

`Draft` contains:

- `id: String`: UUID generated once and never reused
- `name: String`: trimmed, non-empty display name
- `content: String`: unformatted Unicode text; an empty string is an empty draft
- `displayOrder: Long`: monotonically increasing creation order
- `createdAt: Long`: UTC epoch milliseconds
- `updatedAt: Long`: UTC epoch milliseconds, changed by content saves and renames

Whitespace-only content is considered non-empty because deleting it would discard user input. Draft names may duplicate. Identity and all actions use `id`, never name or tab position.

### Workspace

`Workspace` contains one value: `selectedDraftId`. Room stores it in a singleton `workspace` row with key `1`.

### Room Schema Version 1

`drafts` table:

| Column | Type | Constraint |
|---|---|---|
| `id` | TEXT | Primary key |
| `name` | TEXT | Not null |
| `content` | TEXT | Not null |
| `display_order` | INTEGER | Not null, unique |
| `created_at` | INTEGER | Not null |
| `updated_at` | INTEGER | Not null |

`workspace` table:

| Column | Type | Constraint |
|---|---|---|
| `id` | INTEGER | Primary key; always `1` |
| `selected_draft_id` | TEXT | Not null |

The repository maintains the workspace reference transactionally instead of using a foreign key, because selected-draft replacement and final-draft recreation must happen in one controlled transaction.

### Naming Rules

- Automatic names use the exact format `Untitled N`, where `N` is a positive integer.
- Find the lowest positive integer not present among exact automatic-name matches.
- Renaming an automatic name frees its number for later reuse.
- Trim leading and trailing whitespace from manual names.
- Reject a manual name when the trimmed result is empty.
- Do not impose a uniqueness rule or first-release length limit; the UI truncates long tab labels visually without changing stored names.

## 4. Repository Contract and Transactions

`DraftRepository` exposes observable state and suspend operations:

```kotlin
val drafts: Flow<List<Draft>>
val workspace: Flow<Workspace>

suspend fun initialize()
suspend fun createDraft(): String
suspend fun renameDraft(id: String, name: String)
suspend fun selectDraft(id: String)
suspend fun saveContent(id: String, content: String)
suspend fun deleteDraft(id: String)
```

Repository rules:

- `initialize` creates `Untitled 1` and the workspace row in one transaction only when no drafts exist.
- `createDraft` calculates the next name and `max(displayOrder) + 1`, inserts the draft, and selects it in one transaction.
- `renameDraft` validates and trims the name before updating it.
- `selectDraft` succeeds only when the requested ID exists.
- `saveContent` updates only the requested ID and its `updatedAt` value.
- `deleteDraft` targets one immutable ID. Repeating the request cannot affect another draft.
- Deleting an unselected draft leaves the current selection unchanged.
- Deleting the selected draft chooses the next draft to its right, or the previous draft when no right-hand draft exists.
- Deleting the only draft creates a fresh `Untitled 1` draft with a new UUID and selects it within the same transaction.
- Any invalid stored selection is repaired to the first draft by `displayOrder`.
- Structural operations are serialized and Room transactions provide atomicity.

Inject an ID generator and clock into `RoomDraftRepository` with production defaults. Tests use deterministic implementations.

## 5. ViewModel State and Actions

### Screen State

`NotesUiState` contains:

- Ordered draft summaries for the tab strip
- Selected draft ID
- Selected draft `TextFieldValue`
- Per-draft editor buffers keyed by draft ID
- Dialog state: none, rename, or confirm deletion, always carrying the target draft ID
- Optional persistence error containing the failed operation and retry action
- Initialization and structural-operation progress flags

The ViewModel merges Room flows with unsaved editor buffers. A database emission must never overwrite a newer dirty buffer.

### User Actions

`NotesAction` covers:

- Create draft
- Select draft by ID
- Change editor value for a draft ID
- Request, confirm, or cancel deletion by draft ID
- Open, submit, or cancel rename by draft ID
- Retry failed persistence operation
- Flush pending saves when the app stops
- Dismiss an error after the operation has recovered or the user explicitly dismisses it

All events carry draft IDs where relevant. The ViewModel ignores actions for IDs that no longer exist.

### Save Coordination

- Update the selected draft's in-memory `TextFieldValue` synchronously for every edit.
- Maintain one debounce job per dirty draft so tab switching cannot redirect a save.
- Save 500 milliseconds after the latest edit, satisfying the one-second requirement.
- Continue a pending save after switching tabs.
- On activity `onStop`, cancel debounce delays and launch an immediate flush for all dirty drafts.
- Clear a dirty buffer only after the repository confirms that exact content was saved.
- If content changes while a save is running, retain the newer buffer and schedule another save.
- Preserve per-draft `TextFieldValue`, including cursor and text selection, in the ViewModel across orientation changes.
- Persist only text, not cursor position, across process death.

## 6. User Interface Decisions

### Main Screen

Use a full-height `Column` with:

1. A fixed tab/action row
2. A conditional persistence error banner
3. The editor filling all remaining space

There is no navigation graph, drawer, bottom bar, landing page, or settings screen.

### Tab Row

- Use a `LazyRow` for tabs, with fixed add and rename icon buttons outside the scrolling area.
- Display tabs in `displayOrder`.
- Each tab shows an ellipsized name and a close icon.
- Use a clear selected background and indicator; selection is never color-only.
- Use 96 dp minimum and 200 dp maximum tab width.
- Selecting a tab scrolls it fully into view with `animateScrollToItem`.
- Add creates and selects a new draft.
- Rename opens a dialog for the selected draft, prefilled with its current name.
- Close immediately deletes an empty draft; non-empty content opens a confirmation dialog naming the draft.

### Editor

- Use Compose `BasicTextField` with `TextFieldValue`, multiline input, a monospaced font, and a vertical scroll state.
- Fill the available space and use comfortable internal padding without a visible text-field outline.
- Use `imePadding` and activity resize behavior so the keyboard does not permanently cover the cursor.
- Keep the tab row outside the editor's vertical scroll container.

### Dialogs and Errors

- Rename dialog: text field, Cancel, and Rename. Show inline validation for a blank name.
- Delete dialog: draft name, explicit permanent-deletion message, Cancel, and Delete.
- Error banner: concise operation-specific message, Retry when possible, and Dismiss.
- A failed create shows no new tab.
- A failed selection keeps the previous tab selected.
- A failed rename keeps the previous name.
- A failed deletion keeps the draft and content.
- A failed content save keeps the editor buffer and marks it dirty until retry succeeds.

### Theme and Accessibility

- Use an explicit dark Material 3 color scheme, dark system bars, and a monospaced editor style.
- All icon buttons have content descriptions containing the target where useful.
- Interactive targets are at least 48 dp.
- Dialogs, selected tabs, and errors expose meaningful semantics.
- The error banner uses live-region semantics so assistive technology announces persistence failures.
- Test with long names, duplicate names, large font scale, portrait, and landscape.

## 7. Error and Reliability Model

Define repository failures as app-level categories rather than leaking Room exceptions:

- `InvalidName`
- `DraftNotFound`
- `StorageReadFailed`
- `StorageWriteFailed`

Rules:

- Validation errors are shown inline and are not retried automatically.
- Storage failures are logged locally to Logcat without draft content or names.
- Failed structural operations remain visually uncommitted and can be retried.
- Failed content saves preserve dirty buffers and expose Retry.
- The app does not claim success with toasts or state changes before a transaction completes.
- Initialization failure shows a full-screen retry state because no safe editor state exists.
- Unexpected invalid workspace data is repaired; unreadable database failures are surfaced, not replaced with destructive migration.
- No operation silently drops text, changes another draft by position, or falls back to a different target ID.

## 8. Test Plan

### Local Unit Tests

Cover:

- Lowest-available `Untitled N` generation, including gaps, duplicates, and renamed drafts
- Name trimming and blank-name rejection
- Empty versus whitespace-only deletion behavior
- ViewModel initialization and state merging
- Per-draft debounce and tab switching during pending saves
- Edit during an active save
- Flush on stop
- Every structural success and failure path
- Retry behavior and stale-ID actions
- Cursor and selection retention across ViewModel-preserving recreation

Use fake repositories, a fake clock, deterministic UUIDs, and `kotlinx-coroutines-test` virtual time.

### Room Instrumentation Tests

Use an isolated in-memory database to cover:

- Initial draft/workspace transaction
- Creation order and automatic naming
- Rename, select, save, and delete operations
- Right-neighbor and left-neighbor selection after deletion
- Atomic final-draft replacement
- Repeated deletion by the same ID
- Invalid selected-ID repair
- Database close and reopen restoration using a temporary on-device file
- Exported schema validation; add a migration test for every schema version after version 1

### Compose and Device Tests

Map directly to the feature acceptance criteria:

- Clean launch shows dark theme, `Untitled 1`, selected tab, and empty editor.
- Create enough drafts to overflow, scroll, select, and auto-reveal tabs.
- Rename valid and invalid names.
- Close empty drafts and exercise cancel/confirm deletion for non-empty drafts.
- Enter multiline Unicode text and exercise selection, copy, cut, and paste.
- Type different text in multiple tabs and verify isolation.
- Recreate the activity in portrait and landscape and verify content and selection.
- Move the activity to the background immediately after typing, then restore and verify the flushed text.
- Close and relaunch the activity against the same database and verify names, order, content, deletion, and selection.
- Inject repository failures and verify safe UI state plus Retry.
- Inspect semantics for icon labels, dialogs, errors, and selected tabs.
- Verify 48 dp targets and usability at large font scale.

### Gradle Managed Device

Define `pixel2Api29`:

- Device profile: Pixel 2
- API level: 29
- System image: AOSP x86_64
- Orientation tests cover portrait and landscape on this device.
- Run without a display through Gradle Managed Devices.

Required verification commands:

```bash
./gradlew testDebugUnitTest
./gradlew pixel2Api29DebugAndroidTest
./gradlew lintDebug
./gradlew assembleDebug
```

## 9. Delivery Phases

### Phase 0 — Toolchain and Project Scaffold

- [ ] Locate or install the Android SDK command-line tools and emulator on the server.
- [ ] Set a server-local `ANDROID_SDK_ROOT`; do not commit machine paths.
- [ ] Confirm the SDK has platform 35, build tools, platform tools, emulator, and the API 29 x86_64 image.
- [ ] Verify `/dev/kvm` permissions and run the emulator acceleration check.
- [ ] Configure Gradle to use JDK 17 even if the server shell defaults to another JDK.
- [ ] Create wrapper, root build, version catalog, settings, and `app` module files.
- [ ] Add the manifest, application, activity, theme, and empty Compose screen.
- [ ] Configure Room schema export and the `pixel2Api29` managed device.
- [ ] Confirm `assembleDebug` produces the expected APK.

Exit: an empty dark app builds, installs on the managed device, and launches headlessly.

### Phase 1 — Domain and Persistence

- [ ] Add domain models, Room entities, DAO, database version 1, and repository interface.
- [ ] Implement naming, validation, initialization, selection repair, and all repository transactions.
- [ ] Add manual application-level construction and ViewModel factory wiring.
- [ ] Add unit tests for naming and validation.
- [ ] Add Room tests for every repository rule and database restoration.

Exit: repository tests prove draft safety and all structural rules without UI involvement.

### Phase 2 — ViewModel and Save Coordination

- [ ] Add immutable UI state, actions, dialogs, error types, and editor buffers.
- [ ] Combine repository flows with dirty in-memory buffers.
- [ ] Implement keyed 500 ms saves, concurrent-edit handling, stop flushing, failures, and retry.
- [ ] Serialize structural actions and reject stale IDs.
- [ ] Add comprehensive coroutine-based ViewModel tests.

Exit: unit tests prove that edits cannot cross draft IDs or disappear during normal lifecycle transitions.

### Phase 3 — Feature UI

- [ ] Build the tab row, add/rename actions, close controls, and auto-scroll behavior.
- [ ] Build the plain-text editor and preserve `TextFieldValue` per draft.
- [ ] Build rename and deletion dialogs with validation and immutable target IDs.
- [ ] Add the error banner and full-screen initialization retry state.
- [ ] Apply dark theme, responsive layout, keyboard insets, and accessibility semantics.
- [ ] Connect activity stop events to the ViewModel flush action.

Exit: all product behavior is usable manually on the API 29 managed device.

### Phase 4 — Acceptance and Reliability

- [ ] Implement Compose/device tests for every acceptance criterion in all five feature specs.
- [ ] Add restart, background flush, orientation, long-content, Unicode, large-font, and failure-injection coverage.
- [ ] Verify no `INTERNET` permission, backup path, analytics, or external service is present.
- [ ] Run lint and resolve app-owned warnings affecting correctness or accessibility.
- [ ] Confirm Room schema JSON is committed and no destructive fallback exists.

Exit: unit, Room, Compose, lifecycle, reliability, and accessibility checks pass headlessly.

### Phase 5 — Debug APK Handoff

- [ ] Run the complete verification command set from a clean checkout.
- [ ] Install `app-debug.apk` on the managed device with `adb install -r` and perform a smoke launch.
- [ ] Record exact tool and dependency versions in the version catalog and README.
- [ ] Document server SDK location setup and the managed-device command without committing local paths.
- [ ] Confirm the APK path and checksum for handoff.

Exit: the installable debug APK and reproducible build/test instructions are available on the server.

## 10. Traceability

| Feature specification | Primary implementation | Primary verification |
|---|---|---|
| Draft management | Repository transactions, naming rules, dialogs | Domain, Room, and Compose tests |
| Tab navigation | Ordered Room flow, `LazyRow`, ID-based actions | ViewModel and Compose overflow tests |
| Plain-text editor | Per-draft `TextFieldValue` buffers | ViewModel isolation and editor device tests |
| Local persistence | Room, debounce, stop flush, retry | Room reopen, lifecycle, and failure tests |
| Editor appearance | Dark theme, layout, semantics | Compose accessibility and orientation tests |

## Definition of Done

The first release is complete only when:

- Every acceptance criterion in every feature specification has an automated test or a documented reason it requires a manual check.
- All four required Gradle commands pass on the server.
- No known path silently loses draft text or deletes a non-target draft.
- The app works offline and contains no external-service integration or network permission.
- A clean build produces an installable debug APK at the documented path.
- README setup instructions match the verified server workflow.
