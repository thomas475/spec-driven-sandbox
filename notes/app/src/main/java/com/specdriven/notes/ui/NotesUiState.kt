package com.specdriven.notes.ui

import androidx.compose.ui.text.input.TextFieldValue
import com.specdriven.notes.domain.Draft

data class NotesUiState(
    val isLoading: Boolean = true,
    val drafts: List<Draft> = emptyList(),
    val selectedDraftId: String? = null,
    val editorValues: Map<String, TextFieldValue> = emptyMap(),
    val dirtyDraftIds: Set<String> = emptySet(),
    val dialog: NotesDialog = NotesDialog.None,
    val error: NotesUiError? = null,
) {
    val selectedDraft: Draft?
        get() = drafts.firstOrNull { it.id == selectedDraftId }

    val selectedEditorValue: TextFieldValue
        get() = selectedDraftId?.let(editorValues::get) ?: TextFieldValue()
}

sealed interface NotesDialog {
    data object None : NotesDialog
    data class Rename(val draftId: String) : NotesDialog
    data class ConfirmDeletion(val draftId: String) : NotesDialog
}

data class NotesUiError(
    val operation: NotesOperation,
    val draftId: String? = null,
    val retry: NotesRetry,
)

sealed interface NotesRetry {
    data object Initialize : NotesRetry
    data object Create : NotesRetry
    data class Rename(val draftId: String, val name: String) : NotesRetry
    data class Select(val draftId: String) : NotesRetry
    data class Delete(val draftId: String) : NotesRetry
    data class Save(val draftId: String) : NotesRetry
}

enum class NotesOperation {
    INITIALIZE,
    CREATE,
    RENAME,
    SELECT,
    DELETE,
    SAVE,
}
