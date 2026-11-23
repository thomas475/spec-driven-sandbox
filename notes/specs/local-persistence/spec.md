# Local Persistence

## Goal

Keep drafts safe on the device across backgrounding, closing, process death, and reopening the app.

## Requirements

- Store draft IDs, names, content, creation order, timestamps, and selected draft locally.
- Persist text changes within one second of the latest edit.
- Flush pending edits when the app moves to the background or its activity stops.
- Persist draft creation, rename, selection, and confirmed deletion immediately.
- Restore drafts in order and restore the selected draft after restart.
- Work without an account or network connection.

## Error Cases

- A failed save keeps the latest text in memory and shows a recoverable error.
- A failed create, rename, selection, or delete operation must not be reported as successful.
- Missing or invalid selected-draft data falls back to the first available draft.
- Database migrations must preserve released user data; destructive migration is forbidden.

## Acceptance Criteria

1. Content entered in multiple drafts is restored after closing and reopening the app.
2. An edit followed immediately by backgrounding is restored when the app returns.
3. Draft names, order, and selected draft are restored after process recreation.
4. Confirmed deletion remains deleted after restart; canceled deletion remains present.
5. Core draft operations work with networking disabled.
6. A simulated save failure preserves the unsaved editor text and exposes a retryable error.

