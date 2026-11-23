# Editor Appearance

## Goal

Present a focused, readable editor inspired by Sublime Text across supported screen orientations.

## Requirements

- Use a dark theme by default on first launch.
- Keep the editor and tab strip as the dominant interface.
- Provide readable contrast for text, cursor, selection, tabs, dialogs, and errors.
- Give interactive controls accessible labels and usable touch targets.
- Support portrait and landscape layouts without overlapping or hiding core controls.

## Error Cases

- Long draft names must not overlap adjacent actions or make tabs unusable.
- Large system font settings must not hide access to draft or editor actions.
- Keyboard appearance and orientation changes must not cover the active editing position permanently.

## Acceptance Criteria

1. A clean launch displays the dark theme without requiring configuration.
2. Text, cursor, selection, tabs, confirmation dialogs, and errors remain legible.
3. Screen-reader inspection exposes meaningful labels for non-text controls.
4. Core controls meet Android touch-target guidance.
5. Portrait and landscape modes retain a usable tab strip and editor.
