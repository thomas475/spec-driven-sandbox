package com.specdriven.notes.ui

import androidx.compose.ui.text.input.TextFieldValue
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.specdriven.notes.data.DraftRepository
import com.specdriven.notes.domain.Draft
import kotlinx.coroutines.Job
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
) : ViewModel() {
    private val structuralMutex = Mutex()
    private val editorBuffers = mutableMapOf<String, EditorBuffer>()
    private val saveJobs = mutableMapOf<String, Job>()
    private val savingDraftIds = mutableSetOf<String>()
    private val flushAfterSaveDraftIds = mutableSetOf<String>()
    private var workspaceJob: Job? = null
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

private data class EditorBuffer(
    val value: TextFieldValue,
    val persistedContent: String,
    val isDirty: Boolean,
)
