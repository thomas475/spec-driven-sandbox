# Draft Management

## Goal

Let users create, identify, rename, and deliberately delete local drafts while always retaining an editable draft.

## Requirements

- A clean first launch creates and selects one empty draft.
- Creating a draft assigns the lowest available `Untitled N` name and selects it.
- Users can rename a draft to any non-empty name; names do not need to be unique.
- Closing an empty draft deletes it immediately.
- Closing a non-empty draft requires confirmation before deletion.
- Canceling deletion leaves the draft unchanged and selected.
- Deleting the final draft immediately creates and selects a new empty draft.

## Error Cases

- Reject an empty or whitespace-only name without changing the existing name.
- If deletion fails, keep the draft visible with its content intact and show a recoverable error.
- Repeated close or confirm actions must not delete another draft.

## Acceptance Criteria

1. A clean install opens with one selected empty draft named `Untitled 1`.
2. Creating three drafts assigns `Untitled 2`, `Untitled 3`, and `Untitled 4`.
3. After deleting `Untitled 2`, the next new draft uses that available name.
4. A valid rename is displayed immediately; an invalid rename preserves the old name.
5. Empty drafts close immediately, while non-empty drafts support cancel and confirm paths.
6. Closing the last draft leaves one new selected empty draft.

