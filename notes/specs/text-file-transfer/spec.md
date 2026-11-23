# Text File Transfer

## Goal

Let users move plain-text content between the app and user-selected `.txt` files without weakening local draft safety or requiring broad storage access.

## Requirements

- Provide an Import action that opens Android's system document picker for one plain-text file.
- Accept UTF-8 text files up to 1 MiB; remove one leading UTF-8 byte-order mark and otherwise preserve content exactly, including line endings and trailing whitespace.
- After a complete successful read, create one new local draft containing the imported text, append it to the tab order, and select it.
- Derive the imported draft name from the provider's display name by removing one final case-insensitive `.txt` suffix and trimming surrounding whitespace.
- Use the lowest available `Untitled N` name when the imported display name is missing or becomes empty; imported names may duplicate existing names.
- Keep the imported draft independent of its source file and do not retain the source URI or future access permission.
- Provide an Export action for the selected draft that opens Android's system create-document picker with MIME type `text/plain`.
- Export the latest visible editor text as UTF-8 without a byte-order mark, including edits that have not yet reached Room.
- Suggest `<draft name>.txt`, without adding a second suffix when the name already ends in `.txt` case-insensitively.
- Treat export as a copy: exporting does not rename the draft, link it to the destination, or change its local persistence state.
- Use only the Storage Access Framework; do not request broad or legacy storage permissions.
- Treat canceling either system picker as a normal no-op without an error message.

## Error Cases

- If a selected file cannot be opened, read, decoded as UTF-8, or is larger than 1 MiB, create no draft and show a recoverable import error.
- If local creation of a fully read import fails, leave all existing drafts, content, order, and selection unchanged.
- If the selected export destination cannot be opened or fully written, keep the draft unchanged and show a recoverable export error without reporting success.
- A provider may leave a partial destination after a failed write; the app must not treat that file as authoritative or discard the local draft.
- Ignore duplicate completion callbacks and actions whose captured draft ID no longer exists.
- While an import or export is processing, prevent a second transfer of the same type from starting.

## Acceptance Criteria

1. Importing a UTF-8 `.txt` file creates and selects one new draft with matching text and a name derived from the file name.
2. Importing an empty file creates and selects an empty draft.
3. Importing a file with Unicode, multiline text, trailing whitespace, and either common line ending preserves that content exactly apart from one leading UTF-8 byte-order mark.
4. Canceling import creates no draft, changes no selection, and shows no error.
5. An unreadable, malformed UTF-8, or larger-than-1-MiB file creates no draft and exposes a retryable error.
6. Exporting writes the selected draft's latest visible text as UTF-8 to the chosen `.txt` destination, even when a debounced Room save is still pending.
7. Canceling or failing export leaves the selected draft and its dirty-save state unchanged; a failure exposes a retryable error.
8. Import and export complete without storage permissions, network access, or a persistent relationship between a draft and a document URI.
