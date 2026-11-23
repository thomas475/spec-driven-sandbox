# Plain-Text Editor

## Goal

Provide a responsive, distraction-free editor for arbitrary plain text.

## Requirements

- Edit multiline plain text, including Unicode characters.
- Use a monospaced typeface.
- Support standard Android cursor movement, selection, copy, cut, and paste.
- Scroll long content vertically.
- Update the selected draft's in-memory content immediately on input.
- Preserve editor content and the selected draft across orientation changes.

## Error Cases

- Pasting empty, multiline, or Unicode clipboard content must not crash the editor.
- Very long lines and documents must remain editable and scrollable.
- Switching tabs during input must not apply text to the wrong draft.

## Acceptance Criteria

1. A user can enter, select, copy, cut, and paste multiline Unicode text.
2. Long content scrolls while remaining editable.
3. Text entered in one tab never appears in another tab.
4. Rotating between portrait and landscape preserves content and the selected draft.
5. The editor renders with a monospaced typeface.

