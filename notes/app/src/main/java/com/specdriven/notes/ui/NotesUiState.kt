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
    val pickerRequest: NotesPickerRequest? = null,
    val importProgress: NotesTransferProgress? = null,
    val exportProgress: NotesTransferProgress? = null,
) {
    val selectedDraft: Draft?
        get() = drafts.firstOrNull { it.id == selectedDraftId }

    val selectedEditorValue: TextFieldValue
        get() = selectedDraftId?.let(editorValues::get) ?: TextFieldValue()
}

data class NotesTransferProgress(
    val operationId: Long,
    val phase: NotesTransferPhase,
)

enum class NotesTransferPhase {
    AWAITING_PICKER,
    PROCESSING,
}

sealed interface NotesPickerRequest {
    val operationId: Long

    data class ImportText(
        override val operationId: Long,
    ) : NotesPickerRequest

    data class ExportText(
        override val operationId: Long,
        val suggestedFileName: String,
    ) : NotesPickerRequest
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
    val cause: NotesErrorCause? = null,
)

sealed interface NotesRetry {
    data object Initialize : NotesRetry
    data object Create : NotesRetry
    data class Rename(val draftId: String, val name: String) : NotesRetry
    data class Select(val draftId: String) : NotesRetry
    data class Delete(val draftId: String) : NotesRetry
    data class Save(val draftId: String) : NotesRetry
    data object ImportText : NotesRetry
    data object ExportText : NotesRetry
}

enum class NotesErrorCause {
    DOCUMENT_READ_FAILED,
    INVALID_TEXT_ENCODING,
    DOCUMENT_TOO_LARGE,
    IMPORTED_DRAFT_CREATION_FAILED,
    DOCUMENT_WRITE_FAILED,
}

enum class NotesOperation {
    INITIALIZE,
    CREATE,
    RENAME,
    SELECT,
    DELETE,
    SAVE,
    IMPORT,
    EXPORT,
}
