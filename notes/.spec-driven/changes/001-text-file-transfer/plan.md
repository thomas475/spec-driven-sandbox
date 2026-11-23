# Text File Transfer Change Plan

## Purpose

Implement `specs/text-file-transfer/spec.md` as a contained extension of the completed notes app. This change adds explicit `.txt` copy-in and copy-out flows while preserving Room as the authoritative store and retaining every existing draft-safety guarantee.

## Scope

### Included

- Import one user-selected UTF-8 `.txt` file into one new local draft
- Export the selected draft's latest visible text to one user-selected `.txt` destination
- Android system document pickers with no storage permission
- Import size and encoding validation
- Atomic imported-draft creation and selection
- Cancellation, operation progress, safe errors, dismissal, and retry
- Unit, Room, ViewModel, Compose, and managed-device coverage for new and affected behavior

### Excluded

- Editing a source file in place or remembering its URI
- Automatic synchronization between drafts and files
- Batch import or export, directory selection, file browsing, or recent-file history
- Encodings other than UTF-8
- Rich text, Markdown conversion, binary files, cloud APIs, or share intents
- Changes to the Room schema, minimum SDK, network policy, or backup policy

## Locked Decisions

- User-facing wording is `Import text file` and `Export selected draft`.
- Both operations use the Storage Access Framework through activity-result contracts.
- Import accepts at most 1,048,576 bytes and performs strict UTF-8 decoding.
- One leading UTF-8 byte-order mark is removed; all other decoded content is preserved exactly.
- Imported content is inserted in its final form and selected in one Room transaction.
- An imported file name loses one final case-insensitive `.txt` suffix; blank or missing names use normal `Untitled N` allocation.
- Export captures the selected draft ID, suggested name, and current editor text before opening the destination picker.
- Export writes the captured editor text as UTF-8 without a byte-order mark, regardless of pending Room debounce work.
- Picker cancellation is a silent no-op. Operation failure appears in the existing error banner and Retry captures the latest selected draft state before opening a new picker.
- No URI permission, URI string, external-file metadata, or transfer status is persisted across app restarts.

## Architecture

### Document Boundary

Introduce a small `DocumentGateway` interface and Android implementation under `data/document/`. It receives opaque `DocumentReference` values created from document URIs supplied by the system picker and owns all `ContentResolver` I/O. The gateway runs blocking work on `Dispatchers.IO`, bounds reads before decoding, truncates export destinations, maps platform failures to typed app errors, and never logs user content or URI details. Only the Android implementation parses the wrapped URI, keeping ViewModel unit tests independent of Android URI behavior.

Keep these rules in pure helpers where possible:

- strict UTF-8 decoding and byte-order-mark removal
- import byte-limit enforcement
- imported display-name conversion
- suggested export-name conversion

This keeps platform instrumentation focused on provider behavior while ordinary unit tests cover deterministic transformation rules.

### Room Boundary

Extend `DraftRepository` and `RoomDraftRepository` with `createImportedDraft(name, content)`. Reuse existing structural-operation serialization, automatic naming, ID generation, timestamps, ordering, and workspace transaction patterns. No schema migration is needed because imported drafts use the existing `Draft` model.

### State and Effects

Extend the ViewModel with:

- a pending transfer carrying a unique operation ID and transfer direction
- a captured export request containing draft ID, proposed name, and text snapshot
- busy flags used to prevent duplicate work
- one-shot UI requests to open import or export pickers
- completion actions containing the operation ID and returned URI or cancellation
- transfer-specific errors and retry intents

Picker requests are effects rather than durable domain state. The UI consumes each request once. Callbacks must match the pending operation ID; duplicate or late callbacks are ignored. Activity recreation may cancel a picker flow but must not change or lose any local draft.

### UI Integration

Add one overflow button after the existing Add and Rename controls. Its menu contains the two transfer actions. Items have explicit accessibility semantics and disable only when their own direction is already processing or export has no valid selected draft.

The Compose host owns `OpenDocument` and `CreateDocument("text/plain")` launchers. It launches them only in response to a consumed ViewModel request and returns the result through a typed action. The picker remains responsible for provider choice, destination naming, and overwrite confirmation.

## Operation Flows

### Import

1. User selects `Import text file`.
2. ViewModel creates a pending import operation and requests `OpenDocument` for `text/plain`.
3. Cancellation clears the pending operation without an error.
4. A returned URI is read and validated by `DocumentGateway`.
5. The ViewModel passes the derived name and decoded content to `createImportedDraft`.
6. Room atomically inserts and selects the appended draft.
7. Existing repository flows update tabs and editor state; the pending operation clears.
8. Any read or transaction failure clears progress, changes no existing state, and exposes a retryable import error.

### Export

1. User selects `Export selected draft`.
2. ViewModel captures selected draft ID, suggested name, and current editor buffer.
3. UI opens `CreateDocument("text/plain")` with the suggested name.
4. Cancellation clears the pending operation without an error.
5. A returned URI is passed with the captured content to `DocumentGateway.writeText`.
6. Success clears pending state without changing the draft or dirty-save state.
7. Failure leaves local state unchanged and exposes a retryable export error that captures the then-current selected draft and starts a new destination selection.

## Error and Reliability Rules

- Reading must stop after the first byte beyond the limit rather than allocating the full file.
- Malformed and unmappable UTF-8 are rejected; replacement characters are not inserted silently.
- Provider display names are optional and untrusted input used only for draft-name derivation.
- Import never exposes an empty intermediate draft or changes selection before its transaction succeeds.
- Export always uses the captured text snapshot, so tab changes and debounce completion cannot redirect or alter it.
- External providers may leave a partial file after a failed write; the app makes no atomicity claim for provider-owned storage.
- Error messages do not expose URI paths, provider details, draft text, or implementation exceptions.
- Existing content saves, lifecycle flushes, tab actions, and dialogs remain available unless they directly conflict with the active transfer.

## Verification Strategy

### Unit Tests

- Exact import byte boundary and first-byte-over rejection
- Valid ASCII, multiline Unicode, CRLF/LF, trailing whitespace, empty input, and leading byte-order mark
- Malformed and unmappable UTF-8 rejection
- Display names with `.txt`, mixed-case suffixes, multiple dots, whitespace, missing values, and empty stems
- Export suggestions with and without an existing `.txt` suffix
- ViewModel request consumption, snapshot capture, cancellation, duplicate/stale callback rejection, busy state, failures, dismissal, and retry

### Room Tests

- Named and automatic imported-draft creation
- Exact imported content, ordering, timestamps, and selected workspace
- Duplicate names and available automatic-name gaps
- Transaction rollback without observable partial state
- Reopen after import with exact restored content and selection

### Instrumentation and Compose Tests

- Controlled content provider reads and writes exact bytes
- Read, decode, oversize, open, and write failures map to safe UI errors
- Overflow menu semantics and enablement
- Successful import selects the appended tab and remains restored after relaunch
- Export uses unsaved visible text and does not clear dirty state
- Cancellation and retry paths
- Interaction with tab switching, pending saves, background flush, and orientation recreation
- Manifest remains free of network and storage permissions

## Delivery

Implement `.spec-driven/changes/001-text-file-transfer/tasks.md` in order, verifying each task before starting its dependent task. Finish by running:

```bash
./gradlew testDebugUnitTest
./gradlew pixel2Api29DebugAndroidTest
./gradlew lintDebug
./gradlew assembleDebug
```

The change is complete when every acceptance criterion has automated coverage or a documented manual rationale, the full existing suite still passes, and the updated debug APK is produced at `app/build/outputs/apk/debug/app-debug.apk`.
