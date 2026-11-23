package com.specdriven.notes.ui

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.sizeIn
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.selection.selectable
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.text.TextRange
import androidx.compose.ui.text.input.TextFieldValue
import androidx.compose.ui.unit.dp
import androidx.compose.ui.platform.testTag
import com.specdriven.notes.domain.Draft

@Composable
fun NotesScreen(
    state: NotesUiState,
    onAction: (NotesAction) -> Unit,
    modifier: Modifier = Modifier,
) {
    Column(
        modifier = modifier
            .fillMaxSize()
            .background(MaterialTheme.colorScheme.background)
            .testTag("notes-root"),
    ) {
        if (state.error?.operation == NotesOperation.INITIALIZE) {
            InitializationFailure(onRetry = { onAction(NotesAction.RetryError) })
        } else if (state.isLoading) {
            Box(
                modifier = Modifier.fillMaxSize(),
                contentAlignment = Alignment.Center,
            ) {
                CircularProgressIndicator()
            }
        } else {
            DraftTabBar(
                drafts = state.drafts,
                selectedDraftId = state.selectedDraftId,
                onSelect = { onAction(NotesAction.SelectDraft(it)) },
                onClose = { draftId ->
                    val content = state.editorValues[draftId]?.text
                        ?: state.drafts.firstOrNull { it.id == draftId }?.content
                        .orEmpty()
                    onAction(
                        if (content.isEmpty()) {
                            NotesAction.ConfirmDelete(draftId)
                        } else {
                            NotesAction.OpenDeleteConfirmation(draftId)
                        },
                    )
                },
                onAdd = { onAction(NotesAction.CreateDraft) },
                onRename = {
                    state.selectedDraftId?.let { onAction(NotesAction.OpenRename(it)) }
                },
            )
            state.error?.let { error ->
                ErrorBanner(
                    error = error,
                    onRetry = { onAction(NotesAction.RetryError) },
                    onDismiss = { onAction(NotesAction.DismissError) },
                )
            }
            PlainTextEditor(
                draftId = state.selectedDraftId,
                value = state.selectedEditorValue,
                onValueChange = { draftId, value ->
                    onAction(NotesAction.ChangeEditor(draftId, value))
                },
            )
        }
    }
    NotesDialogHost(state = state, onAction = onAction)
}

@Composable
private fun InitializationFailure(onRetry: () -> Unit) {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(24.dp)
            .semantics {
                liveRegion = LiveRegionMode.Assertive
                contentDescription = "Drafts could not be loaded"
            }
            .testTag("initialization-error"),
        verticalArrangement = Arrangement.Center,
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Text(
            text = "Drafts could not be loaded",
            style = MaterialTheme.typography.titleLarge,
            color = MaterialTheme.colorScheme.error,
        )
        TextButton(
            onClick = onRetry,
            modifier = Modifier
                .sizeIn(minWidth = 48.dp, minHeight = 48.dp)
                .testTag("initialization-retry"),
        ) {
            Text("Retry")
        }
    }
}

@Composable
private fun ErrorBanner(
    error: NotesUiError,
    onRetry: () -> Unit,
    onDismiss: () -> Unit,
) {
    val message = when (error.operation) {
        NotesOperation.INITIALIZE -> "Drafts could not be loaded"
        NotesOperation.CREATE -> "Draft could not be created"
        NotesOperation.RENAME -> "Draft could not be renamed"
        NotesOperation.SELECT -> "Draft could not be selected"
        NotesOperation.DELETE -> "Draft could not be deleted"
        NotesOperation.SAVE -> "Changes could not be saved"
    }
    Surface(
        modifier = Modifier
            .fillMaxWidth()
            .semantics {
                liveRegion = LiveRegionMode.Assertive
                contentDescription = message
            }
            .testTag("error-banner"),
        color = MaterialTheme.colorScheme.errorContainer,
        contentColor = MaterialTheme.colorScheme.onErrorContainer,
    ) {
        Row(
            modifier = Modifier.padding(start = 16.dp, end = 4.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text(
                text = message,
                modifier = Modifier.weight(1f),
                maxLines = 2,
                overflow = TextOverflow.Ellipsis,
            )
            TextButton(
                onClick = onRetry,
                modifier = Modifier
                    .sizeIn(minWidth = 48.dp, minHeight = 48.dp)
                    .testTag("retry-error"),
            ) {
                Text("Retry")
            }
            TextButton(
                onClick = onDismiss,
                modifier = Modifier
                    .sizeIn(minWidth = 48.dp, minHeight = 48.dp)
                    .testTag("dismiss-error"),
            ) {
                Text("Dismiss")
            }
        }
    }
}

@Composable
private fun NotesDialogHost(
    state: NotesUiState,
    onAction: (NotesAction) -> Unit,
) {
    when (val dialog = state.dialog) {
        NotesDialog.None -> Unit
        is NotesDialog.Rename -> {
            val draft = state.drafts.firstOrNull { it.id == dialog.draftId } ?: return
            var name by remember(dialog.draftId, draft.name) {
                mutableStateOf(
                    TextFieldValue(draft.name, TextRange(draft.name.length)),
                )
            }
            val valid = name.text.trim().isNotEmpty()
            AlertDialog(
                modifier = Modifier.testTag("rename-dialog"),
                onDismissRequest = { onAction(NotesAction.CloseDialog) },
                title = { Text("Rename draft") },
                text = {
                    OutlinedTextField(
                        value = name,
                        onValueChange = { name = it },
                        modifier = Modifier.testTag("rename-input"),
                        singleLine = true,
                        isError = !valid,
                        supportingText = {
                            if (!valid) Text("Name cannot be blank")
                        },
                    )
                },
                confirmButton = {
                    TextButton(
                        onClick = {
                            onAction(NotesAction.SubmitRename(dialog.draftId, name.text))
                        },
                        enabled = valid,
                        modifier = Modifier.testTag("confirm-rename"),
                    ) {
                        Text("Rename")
                    }
                },
                dismissButton = {
                    TextButton(
                        onClick = { onAction(NotesAction.CloseDialog) },
                        modifier = Modifier.testTag("cancel-rename"),
                    ) {
                        Text("Cancel")
                    }
                },
            )
        }
        is NotesDialog.ConfirmDeletion -> {
            val draft = state.drafts.firstOrNull { it.id == dialog.draftId } ?: return
            AlertDialog(
                modifier = Modifier.testTag("delete-dialog"),
                onDismissRequest = { onAction(NotesAction.CloseDialog) },
                title = { Text("Delete ${draft.name}?") },
                text = { Text("This draft will be permanently deleted.") },
                confirmButton = {
                    TextButton(
                        onClick = { onAction(NotesAction.ConfirmDelete(dialog.draftId)) },
                        modifier = Modifier.testTag("confirm-delete"),
                    ) {
                        Text("Delete")
                    }
                },
                dismissButton = {
                    TextButton(
                        onClick = { onAction(NotesAction.CloseDialog) },
                        modifier = Modifier.testTag("cancel-delete"),
                    ) {
                        Text("Cancel")
                    }
                },
            )
        }
    }
}

@Composable
private fun DraftTabBar(
    drafts: List<Draft>,
    selectedDraftId: String?,
    onSelect: (String) -> Unit,
    onClose: (String) -> Unit,
    onAdd: () -> Unit,
    onRename: () -> Unit,
) {
    val listState = rememberLazyListState()
    val selectedIndex = drafts.indexOfFirst { it.id == selectedDraftId }

    LaunchedEffect(selectedDraftId, drafts.size) {
        if (selectedIndex >= 0) {
            listState.animateScrollToItem(selectedIndex)
        }
    }

    Row(
        modifier = Modifier
            .fillMaxWidth()
            .background(MaterialTheme.colorScheme.surface)
            .heightIn(min = 56.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        LazyRow(
            modifier = Modifier
                .weight(1f)
                .testTag("tab-strip"),
            state = listState,
            horizontalArrangement = Arrangement.spacedBy(4.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            items(items = drafts, key = Draft::id) { draft ->
                DraftTab(
                    draft = draft,
                    selected = draft.id == selectedDraftId,
                    onSelect = { onSelect(draft.id) },
                    onClose = { onClose(draft.id) },
                )
            }
        }
        TabActionButton(
            label = "+",
            description = "Add draft",
            testTag = "add-draft",
            onClick = onAdd,
        )
        TabActionButton(
            label = "✎",
            description = "Rename selected draft",
            testTag = "rename-draft",
            enabled = selectedDraftId != null,
            onClick = onRename,
        )
    }
}

@Composable
private fun DraftTab(
    draft: Draft,
    selected: Boolean,
    onSelect: () -> Unit,
    onClose: () -> Unit,
) {
    val colors = MaterialTheme.colorScheme
    Surface(
        modifier = Modifier
            .widthIn(min = 96.dp, max = 200.dp)
            .heightIn(min = 48.dp)
            .clip(MaterialTheme.shapes.small)
            .selectable(
                selected = selected,
                role = Role.Tab,
                onClick = onSelect,
            )
            .testTag("draft-tab-${draft.id}"),
        color = if (selected) colors.secondaryContainer else colors.surfaceVariant,
        contentColor = if (selected) colors.onSecondaryContainer else colors.onSurfaceVariant,
        border = if (selected) BorderStroke(1.dp, colors.primary) else null,
    ) {
        Row(
            modifier = Modifier.padding(start = 12.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text(
                text = draft.name,
                modifier = Modifier.weight(1f),
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
            IconButton(
                onClick = onClose,
                modifier = Modifier
                    .size(48.dp)
                    .semantics { contentDescription = "Close ${draft.name}" }
                    .testTag("close-draft-${draft.id}"),
            ) {
                Text(text = "×")
            }
        }
    }
}

@Composable
private fun TabActionButton(
    label: String,
    description: String,
    testTag: String,
    enabled: Boolean = true,
    onClick: () -> Unit,
) {
    IconButton(
        onClick = onClick,
        enabled = enabled,
        modifier = Modifier
            .sizeIn(minWidth = 48.dp, minHeight = 48.dp)
            .semantics { contentDescription = description }
            .testTag(testTag),
    ) {
        Text(
            text = label,
            maxLines = 1,
            overflow = TextOverflow.Ellipsis,
        )
    }
}
