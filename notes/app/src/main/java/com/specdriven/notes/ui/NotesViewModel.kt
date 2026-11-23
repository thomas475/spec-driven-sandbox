package com.specdriven.notes.ui

import androidx.compose.ui.text.input.TextFieldValue
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.specdriven.notes.data.DraftRepository
import com.specdriven.notes.data.document.DocumentGateway
import com.specdriven.notes.data.document.DocumentReadFailedException
import com.specdriven.notes.data.document.DocumentTooLargeException
import com.specdriven.notes.data.document.DocumentWriteFailedException
import com.specdriven.notes.data.document.InvalidTextEncodingException
import com.specdriven.notes.data.document.TextDocumentName
import com.specdriven.notes.domain.Draft
import kotlinx.coroutines.Job
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock

class NotesViewModel(
    private val repository: DraftRepository,
    private val documentGateway: DocumentGateway = UnavailableDocumentGateway,
) : ViewModel() {
    private val structuralMutex = Mutex()
    private val editorBuffers = mutableMapOf<String, EditorBuffer>()
    private val saveJobs = mutableMapOf<String, Job>()
    private val savingDraftIds = mutableSetOf<String>()
    private val flushAfterSaveDraftIds = mutableSetOf<String>()
    private var workspaceJob: Job? = null
    private var nextTransferOperationId = 0L
    private var pendingImportPickerOperationId: Long? = null
    private var pendingExportSnapshot: ExportSnapshot? = null
    private val _uiState = MutableStateFlow(NotesUiState())
    val uiState: StateFlow<NotesUiState> = _uiState.asStateFlow()

    init {
        observeWorkspace()
    }

    fun onAction(action: NotesAction) {
        when (action) {
            NotesAction.CreateDraft -> performStructural(
                operation = NotesOperation.CREATE,
                retry = NotesRetry.Create,
            ) {
                repository.createDraft()
            }
            NotesAction.RequestImportText -> requestImportText()
            is NotesAction.PickerRequestConsumed -> consumePickerRequest(action.operationId)
            is NotesAction.ImportDocumentResult -> completeImportPicker(action)
            NotesAction.RequestExportText -> requestExportText()
            is NotesAction.ExportDocumentResult -> completeExportPicker(action)
            is NotesAction.SelectDraft -> performStructural(
                operation = NotesOperation.SELECT,
                draftId = action.draftId,
                retry = NotesRetry.Select(action.draftId),
            ) {
                repository.selectDraft(action.draftId)
            }
            is NotesAction.ChangeEditor -> changeEditor(action.draftId, action.value)
            is NotesAction.OpenRename -> updateDialog(NotesDialog.Rename(action.draftId))
            is NotesAction.SubmitRename -> performStructural(
                operation = NotesOperation.RENAME,
                draftId = action.draftId,
                retry = NotesRetry.Rename(action.draftId, action.name),
            ) {
                repository.renameDraft(action.draftId, action.name)
                closeDialogFor(action.draftId)
            }
            is NotesAction.OpenDeleteConfirmation -> {
                updateDialog(NotesDialog.ConfirmDeletion(action.draftId))
            }
            is NotesAction.ConfirmDelete -> performStructural(
                operation = NotesOperation.DELETE,
                draftId = action.draftId,
                retry = NotesRetry.Delete(action.draftId),
            ) {
                repository.deleteDraft(action.draftId)
                closeDialogFor(action.draftId)
            }
            NotesAction.AppStopped -> flushDirtyContent()
            NotesAction.RetryError -> retryError()
            NotesAction.CloseDialog -> updateDialog(NotesDialog.None)
            NotesAction.DismissError -> _uiState.update { it.copy(error = null) }
        }
    }

    private fun observeWorkspace() {
        workspaceJob?.cancel()
        workspaceJob = viewModelScope.launch {
            try {
                repository.initialize()
                combine(repository.drafts, repository.workspace) { drafts, workspace ->
                    drafts to workspace
                }.collect { (drafts, workspace) ->
                    reconcileEditorBuffers(drafts)
                    val selectedId = workspace.selectedDraftId.takeIf { selectedId ->
                        drafts.any { it.id == selectedId }
                    } ?: drafts.firstOrNull()?.id
                    _uiState.update { state ->
                        state.copy(
                            isLoading = false,
                            drafts = drafts,
                            selectedDraftId = selectedId,
                            editorValues = editorBuffers.mapValues { it.value.value },
                            dirtyDraftIds = editorBuffers
                                .filterValues { it.isDirty }
                                .keys,
                            error = state.error?.takeUnless {
                                it.operation == NotesOperation.INITIALIZE
                            },
                        )
                    }
                }
            } catch (_: Exception) {
                _uiState.update {
                    it.copy(
                        isLoading = false,
                        error = NotesUiError(
                            operation = NotesOperation.INITIALIZE,
                            retry = NotesRetry.Initialize,
                        ),
                    )
                }
            }
        }
    }

    private fun performStructural(
        operation: NotesOperation,
        draftId: String? = null,
        retry: NotesRetry,
        block: suspend () -> Unit,
    ) {
        viewModelScope.launch {
            structuralMutex.withLock {
                try {
                    block()
                    _uiState.update { state ->
                        state.copy(error = state.error?.takeUnless { it.operation == operation })
                    }
                } catch (_: Exception) {
                    _uiState.update { state ->
                        state.copy(
                            error = NotesUiError(
                                operation = operation,
                                draftId = draftId,
                                retry = retry,
                            ),
                        )
                    }
                }
            }
        }
    }

    private fun updateDialog(dialog: NotesDialog) {
        _uiState.update { it.copy(dialog = dialog) }
    }

    private fun changeEditor(draftId: String, value: TextFieldValue) {
        if (_uiState.value.drafts.none { it.id == draftId }) {
            return
        }
        val existing = editorBuffers[draftId]
            ?: return
        val contentChanged = existing.value.text != value.text
        editorBuffers[draftId] = EditorBuffer(
            value = value,
            persistedContent = existing.persistedContent,
            isDirty = value.text != existing.persistedContent,
        )
        when {
            value.text == existing.persistedContent -> cancelPendingSave(draftId)
            contentChanged -> scheduleSave(draftId)
        }
        publishEditorBuffers()
    }

    private fun reconcileEditorBuffers(drafts: List<Draft>) {
        val draftIds = drafts.mapTo(mutableSetOf()) { it.id }
        val removedDraftIds = editorBuffers.keys - draftIds
        removedDraftIds.forEach(::cancelPendingSave)
        editorBuffers.keys.retainAll(draftIds)
        drafts.forEach { draft ->
            val existing = editorBuffers[draft.id]
            editorBuffers[draft.id] = when {
                existing == null -> EditorBuffer(
                    value = TextFieldValue(draft.content),
                    persistedContent = draft.content,
                    isDirty = false,
                )
                existing.isDirty -> existing
                existing.persistedContent != draft.content -> EditorBuffer(
                    value = TextFieldValue(draft.content),
                    persistedContent = draft.content,
                    isDirty = false,
                )
                else -> existing
            }
        }
    }

    private fun publishEditorBuffers() {
        _uiState.update { state ->
            state.copy(
                editorValues = editorBuffers.mapValues { it.value.value },
                dirtyDraftIds = editorBuffers.filterValues { it.isDirty }.keys,
            )
        }
    }

    private fun scheduleSave(draftId: String) {
        if (draftId in savingDraftIds) {
            return
        }
        saveJobs.remove(draftId)?.cancel()
        saveJobs[draftId] = viewModelScope.launch {
            delay(SAVE_DEBOUNCE_MILLIS)
            saveJobs.remove(draftId)
            persistLatestContent(draftId)
        }
    }

    private suspend fun persistLatestContent(draftId: String) {
        val contentToSave = editorBuffers[draftId]
            ?.takeIf { it.isDirty }
            ?.value
            ?.text
            ?: return
        savingDraftIds += draftId
        val succeeded = try {
            repository.saveContent(draftId, contentToSave)
            true
        } catch (_: Exception) {
            false
        } finally {
            savingDraftIds -= draftId
        }
        if (!succeeded) {
            _uiState.update { state ->
                state.copy(
                    error = NotesUiError(
                        operation = NotesOperation.SAVE,
                        draftId = draftId,
                        retry = NotesRetry.Save(draftId),
                    ),
                )
            }
            return
        }

        val latest = editorBuffers[draftId] ?: return
        if (latest.value.text == contentToSave) {
            flushAfterSaveDraftIds.remove(draftId)
            editorBuffers[draftId] = latest.copy(
                persistedContent = contentToSave,
                isDirty = false,
            )
            _uiState.update { state ->
                state.copy(
                    editorValues = editorBuffers.mapValues { it.value.value },
                    dirtyDraftIds = editorBuffers.filterValues { it.isDirty }.keys,
                    error = state.error?.takeUnless {
                        it.operation == NotesOperation.SAVE && it.draftId == draftId
                    },
                )
            }
        } else {
            if (flushAfterSaveDraftIds.remove(draftId)) {
                saveImmediately(draftId)
            } else {
                scheduleSave(draftId)
            }
        }
    }

    private fun cancelPendingSave(draftId: String) {
        if (draftId !in savingDraftIds) {
            saveJobs.remove(draftId)?.cancel()
        }
    }

    private fun flushDirtyContent() {
        editorBuffers
            .filterValues { it.isDirty }
            .keys
            .forEach { draftId ->
                if (draftId in savingDraftIds) {
                    flushAfterSaveDraftIds += draftId
                } else {
                    cancelPendingSave(draftId)
                    saveImmediately(draftId)
                }
            }
    }

    private fun saveImmediately(draftId: String) {
        saveJobs.remove(draftId)?.cancel()
        saveJobs[draftId] = viewModelScope.launch {
            saveJobs.remove(draftId)
            persistLatestContent(draftId)
        }
    }

    private fun retryError() {
        when (val retry = _uiState.value.error?.retry ?: return) {
            NotesRetry.Initialize -> {
                _uiState.update { it.copy(isLoading = true, error = null) }
                observeWorkspace()
            }
            NotesRetry.Create -> performStructural(
                operation = NotesOperation.CREATE,
                retry = retry,
            ) { repository.createDraft() }
            is NotesRetry.Rename -> performStructural(
                operation = NotesOperation.RENAME,
                draftId = retry.draftId,
                retry = retry,
            ) {
                repository.renameDraft(retry.draftId, retry.name)
                closeDialogFor(retry.draftId)
            }
            is NotesRetry.Select -> performStructural(
                operation = NotesOperation.SELECT,
                draftId = retry.draftId,
                retry = retry,
            ) { repository.selectDraft(retry.draftId) }
            is NotesRetry.Delete -> performStructural(
                operation = NotesOperation.DELETE,
                draftId = retry.draftId,
                retry = retry,
            ) {
                repository.deleteDraft(retry.draftId)
                closeDialogFor(retry.draftId)
            }
            is NotesRetry.Save -> saveImmediately(retry.draftId)
            NotesRetry.ImportText -> requestImportText()
            NotesRetry.ExportText -> requestExportText()
        }
    }

    private fun requestImportText() {
        val state = _uiState.value
        if (state.importProgress != null || state.pickerRequest != null) {
            return
        }
        val operationId = ++nextTransferOperationId
        pendingImportPickerOperationId = operationId
        _uiState.update {
            it.copy(
                pickerRequest = NotesPickerRequest.ImportText(operationId),
                importProgress = NotesTransferProgress(
                    operationId = operationId,
                    phase = NotesTransferPhase.AWAITING_PICKER,
                ),
                error = it.error?.takeUnless { error ->
                    error.operation == NotesOperation.IMPORT
                },
            )
        }
    }

    private fun consumePickerRequest(operationId: Long) {
        _uiState.update { state ->
            state.copy(
                pickerRequest = state.pickerRequest?.takeUnless {
                    it.operationId == operationId
                },
            )
        }
    }

    private fun completeImportPicker(action: NotesAction.ImportDocumentResult) {
        if (pendingImportPickerOperationId != action.operationId) {
            return
        }
        pendingImportPickerOperationId = null
        _uiState.update { state ->
            state.copy(
                pickerRequest = state.pickerRequest?.takeUnless {
                    it.operationId == action.operationId
                },
                importProgress = action.document?.let {
                    NotesTransferProgress(
                        operationId = action.operationId,
                        phase = NotesTransferPhase.PROCESSING,
                    )
                },
            )
        }
        val documentReference = action.document ?: return
        viewModelScope.launch {
            val importedDocument = try {
                documentGateway.readText(documentReference)
            } catch (exception: CancellationException) {
                throw exception
            } catch (exception: Exception) {
                val cause = when (exception) {
                    is DocumentTooLargeException -> NotesErrorCause.DOCUMENT_TOO_LARGE
                    is InvalidTextEncodingException -> NotesErrorCause.INVALID_TEXT_ENCODING
                    is DocumentReadFailedException -> NotesErrorCause.DOCUMENT_READ_FAILED
                    else -> NotesErrorCause.DOCUMENT_READ_FAILED
                }
                failImport(action.operationId, cause)
                return@launch
            }

            try {
                structuralMutex.withLock {
                    repository.createImportedDraft(
                        name = TextDocumentName.importedDraftName(importedDocument.displayName),
                        content = importedDocument.content,
                    )
                }
                _uiState.update { state ->
                    state.copy(
                        importProgress = state.importProgress?.takeUnless {
                            it.operationId == action.operationId
                        },
                        error = state.error?.takeUnless {
                            it.operation == NotesOperation.IMPORT
                        },
                    )
                }
            } catch (exception: CancellationException) {
                throw exception
            } catch (_: Exception) {
                failImport(
                    operationId = action.operationId,
                    cause = NotesErrorCause.IMPORTED_DRAFT_CREATION_FAILED,
                )
            }
        }
    }

    private fun failImport(operationId: Long, cause: NotesErrorCause) {
        _uiState.update { state ->
            state.copy(
                importProgress = state.importProgress?.takeUnless {
                    it.operationId == operationId
                },
                error = NotesUiError(
                    operation = NotesOperation.IMPORT,
                    retry = NotesRetry.ImportText,
                    cause = cause,
                ),
            )
        }
    }

    private fun requestExportText() {
        val state = _uiState.value
        if (state.exportProgress != null || state.pickerRequest != null) {
            return
        }
        val selectedDraft = state.selectedDraft ?: return
        val operationId = ++nextTransferOperationId
        val snapshot = ExportSnapshot(
            operationId = operationId,
            draftId = selectedDraft.id,
            suggestedFileName = TextDocumentName.suggestedExportName(selectedDraft.name),
            content = state.selectedEditorValue.text,
        )
        pendingExportSnapshot = snapshot
        _uiState.update {
            it.copy(
                pickerRequest = NotesPickerRequest.ExportText(
                    operationId = operationId,
                    suggestedFileName = snapshot.suggestedFileName,
                ),
                exportProgress = NotesTransferProgress(
                    operationId = operationId,
                    phase = NotesTransferPhase.AWAITING_PICKER,
                ),
                error = it.error?.takeUnless { error ->
                    error.operation == NotesOperation.EXPORT
                },
            )
        }
    }

    private fun completeExportPicker(action: NotesAction.ExportDocumentResult) {
        val snapshot = pendingExportSnapshot?.takeIf {
            it.operationId == action.operationId
        } ?: return
        pendingExportSnapshot = null
        val capturedDraftStillExists = _uiState.value.drafts.any { it.id == snapshot.draftId }
        _uiState.update { state ->
            state.copy(
                pickerRequest = state.pickerRequest?.takeUnless {
                    it.operationId == action.operationId
                },
                exportProgress = if (action.document != null && capturedDraftStillExists) {
                    NotesTransferProgress(
                        operationId = action.operationId,
                        phase = NotesTransferPhase.PROCESSING,
                    )
                } else {
                    null
                },
            )
        }
        val documentReference = action.document
            ?.takeIf { capturedDraftStillExists }
            ?: return
        viewModelScope.launch {
            try {
                documentGateway.writeText(documentReference, snapshot.content)
                _uiState.update { state ->
                    state.copy(
                        exportProgress = state.exportProgress?.takeUnless {
                            it.operationId == action.operationId
                        },
                        error = state.error?.takeUnless {
                            it.operation == NotesOperation.EXPORT
                        },
                    )
                }
            } catch (exception: CancellationException) {
                throw exception
            } catch (_: DocumentWriteFailedException) {
                failExport(action.operationId)
            } catch (_: Exception) {
                failExport(action.operationId)
            }
        }
    }

    private fun failExport(operationId: Long) {
        _uiState.update { state ->
            state.copy(
                exportProgress = state.exportProgress?.takeUnless {
                    it.operationId == operationId
                },
                error = NotesUiError(
                    operation = NotesOperation.EXPORT,
                    retry = NotesRetry.ExportText,
                    cause = NotesErrorCause.DOCUMENT_WRITE_FAILED,
                ),
            )
        }
    }

    private fun closeDialogFor(draftId: String) {
        _uiState.update { state ->
            val targetId = when (val dialog = state.dialog) {
                NotesDialog.None -> null
                is NotesDialog.Rename -> dialog.draftId
                is NotesDialog.ConfirmDeletion -> dialog.draftId
            }
            state.copy(dialog = if (targetId == draftId) NotesDialog.None else state.dialog)
        }
    }

    private companion object {
        const val SAVE_DEBOUNCE_MILLIS = 500L
    }
}

private object UnavailableDocumentGateway : DocumentGateway {
    override suspend fun readText(
        document: com.specdriven.notes.data.document.DocumentReference,
    ): com.specdriven.notes.data.document.ImportedTextDocument =
        throw DocumentReadFailedException(IllegalStateException("Document gateway unavailable"))

    override suspend fun writeText(
        document: com.specdriven.notes.data.document.DocumentReference,
        content: String,
    ) {
        throw DocumentWriteFailedException(IllegalStateException("Document gateway unavailable"))
    }
}

private data class ExportSnapshot(
    val operationId: Long,
    val draftId: String,
    val suggestedFileName: String,
    val content: String,
)

private data class EditorBuffer(
    val value: TextFieldValue,
    val persistedContent: String,
    val isDirty: Boolean,
)
