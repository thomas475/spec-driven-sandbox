package com.specdriven.notes.ui

import androidx.compose.ui.text.input.TextFieldValue

sealed interface NotesAction {
    data object CreateDraft : NotesAction
    data class SelectDraft(val draftId: String) : NotesAction
    data class ChangeEditor(val draftId: String, val value: TextFieldValue) : NotesAction
    data class OpenRename(val draftId: String) : NotesAction
    data class SubmitRename(val draftId: String, val name: String) : NotesAction
    data class OpenDeleteConfirmation(val draftId: String) : NotesAction
    data class ConfirmDelete(val draftId: String) : NotesAction
    data object AppStopped : NotesAction
    data object RetryError : NotesAction
    data object CloseDialog : NotesAction
    data object DismissError : NotesAction
}
