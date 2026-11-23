# Tab Navigation

## Goal

Let users see, select, and move among multiple open drafts without losing their place.

## Requirements

- Show one tab per draft above the editor in creation order.
- Visually distinguish the selected tab.
- Selecting a tab displays that draft's current name and content.
- Scroll the tab strip horizontally when tabs exceed the available width.
- Keep a newly selected tab visible within the tab strip.
- Keep the tab strip fixed while editor content scrolls vertically.

## Error Cases

- If the selected draft no longer exists, select the first available draft.
- Ignore selection actions for draft IDs that no longer exist.
- Long or duplicate draft names must not prevent selecting the correct draft.

## Acceptance Criteria

1. Selecting each of several tabs displays the matching draft content.
2. The selected tab is visually identifiable at all times.
3. Enough tabs to exceed screen width can be reached by horizontal scrolling.
4. Selecting an off-screen tab scrolls it into view.
5. Vertically scrolling a long draft leaves the tab strip visible.

