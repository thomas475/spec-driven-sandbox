# Text File Transfer Implementation Tasks

These tasks implement `specs/text-file-transfer/spec.md` and `.spec-driven/changes/001-text-file-transfer/plan.md`. Complete each task with its new tests and interaction/regression tests passing before starting the next dependent task.

## Task 1 — Text Document Contracts and Helpers

**Status:** Complete

**Depends on:** None

**Implement**

- Add typed document results and transfer failures.
- Add strict bounded UTF-8 decoding with one leading byte-order-mark removal.
- Add pure imported-name and suggested-export-name helpers.

**New tests**

- Cover empty, ASCII, multiline Unicode, LF, CRLF, trailing whitespace, and byte-order-mark input.
- Verify malformed UTF-8 and byte 1,048,577 fail while byte 1,048,576 remains valid.
- Cover missing, blank, mixed-case `.txt`, repeated suffix, whitespace, and already-suffixed export names.

**Interaction/regression tests**

- Verify transformations never normalize valid content or mutate the supplied draft name.
- Run existing domain naming tests to confirm automatic draft naming is unchanged.

**Done when:** Pure tests define every byte, encoding, and naming rule without Android dependencies.

## Task 2 — Android Document Gateway

**Status:** Complete

**Depends on:** Task 1

**Implement**

- Add `DocumentGateway` and a `ContentResolver` implementation on `Dispatchers.IO`.
- Bound reads before decoding, query the optional provider display name, and write UTF-8 in truncating mode.
- Map provider, permission, decoding, size, and write failures without logging URI or content details.

**New tests**

- Read controlled `content://` documents and verify derived metadata plus exact decoded content.
- Write controlled destinations and verify exact UTF-8 bytes without a byte-order mark.
- Simulate missing streams, provider exceptions, oversize input, malformed input, and interrupted writes.

**Interaction/regression tests**

- Verify streams and cursors close on success and every failure path.
- Inspect the merged manifest to confirm no storage or network permission was introduced.

**Done when:** All external document I/O is bounded, testable, permission-free, and isolated behind one gateway.

## Task 3 — Atomic Imported-Draft Creation

**Status:** Complete

**Depends on:** Task 1

**Implement**

- Extend the repository contract with atomic imported-draft creation.
- Reuse structural serialization, UUIDs, timestamps, display order, and automatic-name allocation.
- Insert final name and content and select the new draft in one Room transaction.

**New tests**

- Cover explicit names, duplicate names, blank-name fallback, naming gaps, exact content, order, timestamps, and selection.
- Verify the imported draft is emitted only in final form.
- Force each transaction stage to fail and verify complete rollback.

**Interaction/regression tests**

- Reopen the database and verify imported name, content, order, and selection.
- Re-run create, rename, delete, selection-repair, and concurrent structural-operation tests.

**Done when:** Import can create and select one complete local draft without changing the Room schema or exposing partial state.

## Task 4 — Import ViewModel Flow

**Status:** Complete

**Depends on:** Tasks 2 and 3

**Implement**

- Add import request, picker result, pending-operation identity, busy state, and cancellation actions.
- Read a returned document, atomically create its draft, and clear progress only after repository success.
- Add specific import errors, dismissal, and retry that requests a new picker.

**New tests**

- Cover request consumption, cancellation, successful import, every gateway failure, repository failure, dismissal, and retry.
- Verify duplicate, mismatched, and late picker callbacks are ignored.
- Verify repeated import actions cannot start concurrent reads.

**Interaction/regression tests**

- Import while other drafts have dirty buffers and confirm their contents and debounce jobs remain intact.
- Verify failed import preserves drafts, order, selection, dialogs, and current editor value.

**Done when:** Import has one deterministic state transition from picker request to selected local draft or recoverable no-change failure.

## Task 5 — Export ViewModel Flow

**Status:** Complete

**Depends on:** Tasks 1, 2, and 4

**Implement**

- Capture export operation ID, selected draft ID, suggested file name, and latest editor text before requesting a destination.
- Write only the captured snapshot when the matching picker result arrives.
- Add cancellation, busy state, write failure, dismissal, and retry through a fresh destination picker.

**New tests**

- Verify exported content includes unsaved visible edits and exact multiline Unicode text.
- Verify tab switches, later edits, and completed debounce saves cannot change or redirect a pending snapshot.
- Cover cancellation, missing or deleted captured draft, duplicate callbacks, write failure, dismissal, and retry.

**Interaction/regression tests**

- Verify export success and failure leave Room dirty state, selection, draft name, and content unchanged.
- Exercise export while another draft saves and while structural actions complete.

**Done when:** Export always writes the intended captured text and has no side effects on local draft persistence.

## Task 6 — System Picker and Transfer UI

**Status:** Complete

**Depends on:** Tasks 4 and 5

**Implement**

- Add an accessible overflow action with Import and Export menu items beside existing tab actions.
- Register `OpenDocument` and `CreateDocument("text/plain")` launchers and consume each ViewModel picker request once.
- Return URI or cancellation results with operation identity and expose progress and errors through existing UI patterns.

**New tests**

- Verify menu labels, content descriptions, enabled states, and picker MIME types and suggested names.
- Verify each one-shot request launches exactly once across recomposition.
- Verify cancel, successful callback, error banner, Dismiss, and Retry UI paths.

**Interaction/regression tests**

- Exercise menu overflow with many tabs, long names, large font scale, portrait, and landscape.
- Re-run add, rename, close, tab overflow, editor, dialog, and accessibility tests with the new action present.

**Done when:** Users can discover and operate both system-picker flows without crowding or regressing the editor interface.

## Task 7 — Cross-Feature Transfer Acceptance

**Status:** Complete

**Depends on:** Tasks 1–6

**Implement**

- Add deterministic provider fixtures and end-to-end scenarios for all text-file-transfer acceptance criteria.
- Add relaunch, backgrounding, orientation, process recreation, and failure-injection coverage around transfers.
- Document any picker behavior that cannot be automated on the managed device and its manual verification procedure.

**New tests**

- Import named, unnamed, empty, Unicode, byte-order-mark, malformed, exact-limit, and oversize documents.
- Export persisted and dirty content and verify destination bytes exactly.
- Verify cancellation, read failure, transaction failure, write failure, dismissal, and retry.

**Interaction/regression tests**

- Import, edit, export, switch tabs, background immediately, relaunch, and verify both Room state and exported bytes.
- Combine transfers with duplicate names, automatic-name gaps, deletion dialogs, save failures, and final-draft replacement.

**Done when:** Every new acceptance criterion and affected existing safety guarantee is automated or has a justified manual check.

## Task 8 — Documentation, Quality Gate, and APK

**Status:** Complete

**Depends on:** Task 7

**Implement**

- Update README behavior and run instructions only where the completed feature changes them.
- Confirm specifications, architecture decisions, implementation, tests, and user-facing wording agree.
- Resolve app-owned lint, correctness, accessibility, and reliability findings and build the updated debug APK.

**New tests**

- Run `testDebugUnitTest`, `pixel2Api29DebugAndroidTest`, `lintDebug`, and `assembleDebug` from a clean project state.
- Install the APK and smoke-test import, export, cancellation, retry, and relaunch on API 29.

**Interaction/regression tests**

- Run the original full acceptance scenario plus import and export in the same session.
- Confirm the final manifest has no `INTERNET`, broad storage, or legacy external-storage permission and that no URI or user text is logged.

**Done when:** Documentation matches verified behavior, all quality gates pass, and the updated installable debug APK is available at the documented path.
