# Text File Transfer Verification

## Automated Coverage

- Pure JVM tests verify strict UTF-8, one leading byte-order mark, exact 1 MiB acceptance, first-byte-over rejection, exact content preservation, and import/export name derivation.
- API 29 provider tests verify `content://` reads, writes, open failures, malformed input, oversize input, and interrupted writes.
- Room tests verify final-form imported insertion, naming fallback, duplicates, ordering, selection, rollback, and database reopen.
- ViewModel tests verify picker identity, single consumption, cancellation, busy state, stale callbacks, import errors, export snapshots, dirty buffers, retry, tab changes, saves, and structural actions.
- Compose tests verify accessible menu labels, enabled states, MIME type, suggested file name, one launch per operation, errors, touch targets, long tabs, large font scale, portrait-compatible layout, and landscape layout.
- Acceptance tests connect the real API 29 `ContentResolver`, document gateway, ViewModel, Room repository, lifecycle flush, database reopen, and exact destination bytes.

## Completed Quality Gate

- `clean testDebugUnitTest pixel2Api29DebugAndroidTest lintDebug assembleDebug` passes, including all 50 API 29 device tests.
- The debug APK installs and cold-starts on the headless API 29 emulator.
- The installed app opens both system pickers, proposes `Appartement.txt` for the selected draft, handles cancellation, and preserves the draft across a forced-stop relaunch.
- The packaged manifest contains no internet, broad storage, or legacy external-storage permission.

## Manual Checks

The managed-device tests intentionally bypass Android DocumentsUI after verifying the exact activity-result contracts. Automating arbitrary system-provider UI is brittle and outside app control. Before release, manually verify on API 29 and one current Android version:

1. Choose a visible `.txt` file from DocumentsUI and confirm the imported name and text.
2. Cancel both pickers and confirm no error or draft change.
3. Export to an existing name and exercise the provider's overwrite confirmation.
4. Open a picker, rotate the device, finish the choice, and confirm the result is handled once.
5. Kill the app while a picker is open, return to the app, and confirm local drafts remain unchanged even if the pending transfer is canceled.
6. Repeat import and export with one third-party document provider if one is installed.
