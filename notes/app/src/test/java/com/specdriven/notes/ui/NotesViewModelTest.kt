package com.specdriven.notes.ui

import androidx.compose.ui.text.TextRange
import androidx.compose.ui.text.input.TextFieldValue
import com.specdriven.notes.data.DraftRepository
import com.specdriven.notes.data.DraftRepositoryException
import com.specdriven.notes.domain.Draft
import com.specdriven.notes.domain.Workspace
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.test.advanceUntilIdle
import kotlinx.coroutines.test.advanceTimeBy
import kotlinx.coroutines.test.runCurrent
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Rule
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class NotesViewModelTest {
    @get:Rule
    val mainDispatcherRule = MainDispatcherRule()

    @Test
    fun initializationExposesDraftsAndSelection() = runTest(mainDispatcherRule.dispatcher) {
        val repository = FakeDraftRepository()
        val viewModel = NotesViewModel(repository)

        advanceUntilIdle()

        assertFalse(viewModel.uiState.value.isLoading)
        assertEquals(listOf("draft-1"), viewModel.uiState.value.drafts.map { it.id })
        assertEquals("draft-1", viewModel.uiState.value.selectedDraftId)
        assertNull(viewModel.uiState.value.error)
    }

    @Test
    fun structuralActionsUpdateStateAndRunSerially() = runTest(mainDispatcherRule.dispatcher) {
        val repository = FakeDraftRepository(operationDelayMillis = 10)
        val viewModel = NotesViewModel(repository)
        advanceUntilIdle()

        viewModel.onAction(NotesAction.CreateDraft)
        viewModel.onAction(NotesAction.CreateDraft)
        advanceUntilIdle()

        assertEquals(3, viewModel.uiState.value.drafts.size)
        assertEquals("draft-3", viewModel.uiState.value.selectedDraftId)
        assertEquals(1, repository.maximumConcurrentOperations)
    }

    @Test
    fun dialogActionsRetainImmutableTargetIds() = runTest(mainDispatcherRule.dispatcher) {
        val repository = FakeDraftRepository()
        val viewModel = NotesViewModel(repository)
        advanceUntilIdle()

        viewModel.onAction(NotesAction.OpenRename("draft-1"))
        assertEquals(NotesDialog.Rename("draft-1"), viewModel.uiState.value.dialog)

        viewModel.onAction(NotesAction.SubmitRename("draft-1", "Renamed"))
        advanceUntilIdle()

        assertEquals("Renamed", viewModel.uiState.value.drafts.single().name)
        assertEquals(NotesDialog.None, viewModel.uiState.value.dialog)
    }

    @Test
    fun staleSelectionLeavesCommittedStateAndExposesError() = runTest(mainDispatcherRule.dispatcher) {
        val repository = FakeDraftRepository()
        val viewModel = NotesViewModel(repository)
        advanceUntilIdle()

        viewModel.onAction(NotesAction.SelectDraft("missing"))
        advanceUntilIdle()

        assertEquals("draft-1", viewModel.uiState.value.selectedDraftId)
        assertEquals(
            NotesUiError(
                operation = NotesOperation.SELECT,
                draftId = "missing",
                retry = NotesRetry.Select("missing"),
            ),
            viewModel.uiState.value.error,
        )
    }

    @Test
    fun unicodeEditorInputUpdatesOnlyItsDraftImmediately() = runTest(mainDispatcherRule.dispatcher) {
        val repository = FakeDraftRepository()
        val viewModel = NotesViewModel(repository)
        advanceUntilIdle()
        viewModel.onAction(NotesAction.CreateDraft)
        advanceUntilIdle()
        val value = TextFieldValue("First line\nΚαλημέρα 👋", selection = TextRange(8))

        viewModel.onAction(NotesAction.ChangeEditor("draft-1", value))

        assertEquals(value, viewModel.uiState.value.editorValues["draft-1"])
        assertEquals("", viewModel.uiState.value.editorValues["draft-2"]?.text)
        assertEquals(setOf("draft-1"), viewModel.uiState.value.dirtyDraftIds)
    }

    @Test
    fun switchingDraftsPreservesEachValueCursorAndSelection() = runTest(mainDispatcherRule.dispatcher) {
        val repository = FakeDraftRepository()
        val viewModel = NotesViewModel(repository)
        advanceUntilIdle()
        viewModel.onAction(NotesAction.CreateDraft)
        advanceUntilIdle()
        val firstValue = TextFieldValue("First", selection = TextRange(2))
        val secondValue = TextFieldValue("Second", selection = TextRange(1, 5))
        viewModel.onAction(NotesAction.ChangeEditor("draft-1", firstValue))
        viewModel.onAction(NotesAction.ChangeEditor("draft-2", secondValue))

        viewModel.onAction(NotesAction.SelectDraft("draft-1"))
        advanceUntilIdle()
        assertEquals(firstValue, viewModel.uiState.value.selectedEditorValue)
        viewModel.onAction(NotesAction.SelectDraft("draft-2"))
        advanceUntilIdle()
        assertEquals(secondValue, viewModel.uiState.value.selectedEditorValue)
    }

    @Test
    fun repositoryEmissionCannotOverwriteDirtyBuffer() = runTest(mainDispatcherRule.dispatcher) {
        val repository = FakeDraftRepository()
        val viewModel = NotesViewModel(repository)
        advanceUntilIdle()
        val value = TextFieldValue("Unsaved", selection = TextRange(7))
        viewModel.onAction(NotesAction.ChangeEditor("draft-1", value))

        repository.emitPersistedContent("draft-1", "Older database value")
        runCurrent()

        assertEquals(value, viewModel.uiState.value.editorValues["draft-1"])
        assertEquals(setOf("draft-1"), viewModel.uiState.value.dirtyDraftIds)
    }

    @Test
    fun creationAndDeletionDoNotDisturbOtherEditorBuffers() = runTest(mainDispatcherRule.dispatcher) {
        val repository = FakeDraftRepository()
        val viewModel = NotesViewModel(repository)
        advanceUntilIdle()
        val firstValue = TextFieldValue("Keep me", selection = TextRange(4))
        viewModel.onAction(NotesAction.ChangeEditor("draft-1", firstValue))
        viewModel.onAction(NotesAction.CreateDraft)
        advanceUntilIdle()

        viewModel.onAction(NotesAction.ConfirmDelete("draft-2"))
        advanceUntilIdle()

        assertEquals(firstValue, viewModel.uiState.value.editorValues["draft-1"])
        assertNull(viewModel.uiState.value.editorValues["draft-2"])
    }

    @Test
    fun contentSavesAtFiveHundredMillisecondsButNotEarlier() = runTest(mainDispatcherRule.dispatcher) {
        val repository = FakeDraftRepository()
        val viewModel = NotesViewModel(repository)
        advanceUntilIdle()

        viewModel.onAction(
            NotesAction.ChangeEditor("draft-1", TextFieldValue("Debounced")),
        )
        advanceTimeBy(499)
        runCurrent()
        assertEquals(emptyList<Pair<String, String>>(), repository.saveCalls)

        advanceTimeBy(1)
        runCurrent()
        assertEquals(listOf("draft-1" to "Debounced"), repository.saveCalls)
        assertEquals(emptySet<String>(), viewModel.uiState.value.dirtyDraftIds)
    }

    @Test
    fun draftsDebounceAndSaveIndependently() = runTest(mainDispatcherRule.dispatcher) {
        val repository = FakeDraftRepository()
        val viewModel = NotesViewModel(repository)
        advanceUntilIdle()
        viewModel.onAction(NotesAction.CreateDraft)
        advanceUntilIdle()

        viewModel.onAction(NotesAction.ChangeEditor("draft-1", TextFieldValue("One")))
        advanceTimeBy(100)
        viewModel.onAction(NotesAction.ChangeEditor("draft-2", TextFieldValue("Two")))
        advanceTimeBy(400)
        runCurrent()
        assertEquals(listOf("draft-1" to "One"), repository.saveCalls)

        advanceTimeBy(100)
        runCurrent()
        assertEquals(
            listOf("draft-1" to "One", "draft-2" to "Two"),
            repository.saveCalls,
        )
    }

    @Test
    fun editDuringSaveQueuesNewestContentAfterCurrentSave() = runTest(mainDispatcherRule.dispatcher) {
        val repository = FakeDraftRepository(saveDelayMillis = 200)
        val viewModel = NotesViewModel(repository)
        advanceUntilIdle()
        viewModel.onAction(NotesAction.ChangeEditor("draft-1", TextFieldValue("First")))

        advanceTimeBy(500)
        runCurrent()
        viewModel.onAction(NotesAction.ChangeEditor("draft-1", TextFieldValue("Newest")))
        advanceTimeBy(200)
        runCurrent()
        assertEquals(listOf("draft-1" to "First"), repository.saveCalls)

        advanceTimeBy(500)
        runCurrent()
        advanceTimeBy(200)
        runCurrent()
        assertEquals(
            listOf("draft-1" to "First", "draft-1" to "Newest"),
            repository.saveCalls,
        )
        assertEquals(emptySet<String>(), viewModel.uiState.value.dirtyDraftIds)
    }

    @Test
    fun structuralActionsDoNotDiscardPendingContent() = runTest(mainDispatcherRule.dispatcher) {
        val repository = FakeDraftRepository()
        val viewModel = NotesViewModel(repository)
        advanceUntilIdle()
        viewModel.onAction(NotesAction.ChangeEditor("draft-1", TextFieldValue("Pending")))

        viewModel.onAction(NotesAction.CreateDraft)
        viewModel.onAction(NotesAction.SubmitRename("draft-1", "Renamed"))
        advanceTimeBy(500)
        advanceUntilIdle()

        assertEquals(listOf("draft-1" to "Pending"), repository.saveCalls)
        assertEquals("Pending", repository.drafts.value.first { it.id == "draft-1" }.content)
        assertEquals("Renamed", repository.drafts.value.first { it.id == "draft-1" }.name)
        assertEquals(2, repository.drafts.value.size)
    }

    @Test
    fun appStopFlushesEveryDirtyDraftWithoutWaitingForDebounce() = runTest(mainDispatcherRule.dispatcher) {
        val repository = FakeDraftRepository()
        val viewModel = NotesViewModel(repository)
        advanceUntilIdle()
        viewModel.onAction(NotesAction.CreateDraft)
        advanceUntilIdle()
        viewModel.onAction(NotesAction.ChangeEditor("draft-1", TextFieldValue("One")))
        viewModel.onAction(NotesAction.ChangeEditor("draft-2", TextFieldValue("Two")))

        viewModel.onAction(NotesAction.AppStopped)
        runCurrent()

        assertEquals(
            setOf("draft-1" to "One", "draft-2" to "Two"),
            repository.saveCalls.toSet(),
        )
        assertEquals(emptySet<String>(), viewModel.uiState.value.dirtyDraftIds)
    }

    @Test
    fun failedSaveKeepsDirtyTextUntilRetrySucceeds() = runTest(mainDispatcherRule.dispatcher) {
        val repository = FakeDraftRepository().apply {
            failNextSaveFor = "draft-1"
        }
        val viewModel = NotesViewModel(repository)
        advanceUntilIdle()
        viewModel.onAction(NotesAction.ChangeEditor("draft-1", TextFieldValue("Unsaved")))

        advanceTimeBy(500)
        runCurrent()

        assertEquals(setOf("draft-1"), viewModel.uiState.value.dirtyDraftIds)
        assertEquals(
            NotesUiError(
                operation = NotesOperation.SAVE,
                draftId = "draft-1",
                retry = NotesRetry.Save("draft-1"),
            ),
            viewModel.uiState.value.error,
        )

        viewModel.onAction(NotesAction.RetryError)
        runCurrent()

        assertEquals(listOf("draft-1" to "Unsaved"), repository.saveCalls)
        assertEquals(emptySet<String>(), viewModel.uiState.value.dirtyDraftIds)
        assertNull(viewModel.uiState.value.error)
    }

    @Test
    fun failedRenameLeavesCommittedStateAndRetryUsesOriginalTarget() = runTest(mainDispatcherRule.dispatcher) {
        val repository = FakeDraftRepository().apply {
            renameFailuresRemaining = 1
        }
        val viewModel = NotesViewModel(repository)
        advanceUntilIdle()
        viewModel.onAction(NotesAction.OpenRename("draft-1"))
        viewModel.onAction(NotesAction.SubmitRename("draft-1", "Renamed"))
        advanceUntilIdle()

        assertEquals("Untitled 1", viewModel.uiState.value.drafts.single().name)
        assertEquals(NotesDialog.Rename("draft-1"), viewModel.uiState.value.dialog)
        assertEquals(NotesRetry.Rename("draft-1", "Renamed"), viewModel.uiState.value.error?.retry)

        viewModel.onAction(NotesAction.RetryError)
        advanceUntilIdle()

        assertEquals("Renamed", viewModel.uiState.value.drafts.single().name)
        assertEquals(NotesDialog.None, viewModel.uiState.value.dialog)
        assertNull(viewModel.uiState.value.error)
    }

    @Test
    fun saveFailureDoesNotBlockAnotherDraftAndCanRecover() = runTest(mainDispatcherRule.dispatcher) {
        val repository = FakeDraftRepository().apply {
            failNextSaveFor = "draft-1"
        }
        val viewModel = NotesViewModel(repository)
        advanceUntilIdle()
        viewModel.onAction(NotesAction.CreateDraft)
        advanceUntilIdle()
        viewModel.onAction(NotesAction.ChangeEditor("draft-1", TextFieldValue("First")))
        viewModel.onAction(NotesAction.ChangeEditor("draft-2", TextFieldValue("Second")))

        advanceTimeBy(500)
        runCurrent()

        assertEquals("Second", repository.drafts.value.first { it.id == "draft-2" }.content)
        assertEquals(setOf("draft-1"), viewModel.uiState.value.dirtyDraftIds)
        viewModel.onAction(NotesAction.RetryError)
        runCurrent()
        assertEquals("First", repository.drafts.value.first { it.id == "draft-1" }.content)
        assertEquals(emptySet<String>(), viewModel.uiState.value.dirtyDraftIds)
    }

    @Test
    fun initializationFailureCanRetry() = runTest(mainDispatcherRule.dispatcher) {
        val repository = FakeDraftRepository(initializationFailuresRemaining = 1)
        val viewModel = NotesViewModel(repository)
        advanceUntilIdle()

        assertFalse(viewModel.uiState.value.isLoading)
        assertEquals(NotesRetry.Initialize, viewModel.uiState.value.error?.retry)

        viewModel.onAction(NotesAction.RetryError)
        advanceUntilIdle()

        assertFalse(viewModel.uiState.value.isLoading)
        assertEquals("draft-1", viewModel.uiState.value.selectedDraftId)
        assertNull(viewModel.uiState.value.error)
    }
}

private class FakeDraftRepository(
    private val operationDelayMillis: Long = 0,
    private val saveDelayMillis: Long = 0,
    var initializationFailuresRemaining: Int = 0,
) : DraftRepository {
    private val mutableDrafts = MutableStateFlow(listOf(draft("draft-1", "Untitled 1", 0)))
    private val mutableWorkspace = MutableStateFlow(Workspace("draft-1"))
    override val drafts = mutableDrafts.asStateFlow()
    override val workspace = mutableWorkspace.asStateFlow()
    private var activeOperations = 0
    var maximumConcurrentOperations = 0
        private set
    val saveCalls = mutableListOf<Pair<String, String>>()
    var failNextSaveFor: String? = null
    var renameFailuresRemaining: Int = 0

    override suspend fun initialize() {
        if (initializationFailuresRemaining > 0) {
            initializationFailuresRemaining -= 1
            error("Initialization failed")
        }
    }

    override suspend fun createDraft(): String = structuralOperation {
        val number = mutableDrafts.value.size + 1
        val id = "draft-$number"
        mutableDrafts.value = mutableDrafts.value + draft(id, "Untitled $number", number - 1L)
        mutableWorkspace.value = Workspace(id)
        id
    }

    override suspend fun renameDraft(id: String, name: String) = structuralOperation {
        if (renameFailuresRemaining > 0) {
            renameFailuresRemaining -= 1
            error("Rename failed")
        }
        if (mutableDrafts.value.none { it.id == id }) {
            throw DraftRepositoryException.DraftNotFound(id)
        }
        mutableDrafts.value = mutableDrafts.value.map {
            if (it.id == id) it.copy(name = name.trim(), updatedAt = it.updatedAt + 1) else it
        }
    }

    override suspend fun selectDraft(id: String) = structuralOperation {
        if (mutableDrafts.value.none { it.id == id }) {
            throw DraftRepositoryException.DraftNotFound(id)
        }
        mutableWorkspace.value = Workspace(id)
    }

    override suspend fun saveContent(id: String, content: String) {
        delay(saveDelayMillis)
        if (failNextSaveFor == id) {
            failNextSaveFor = null
            error("Save failed")
        }
        saveCalls += id to content
        mutableDrafts.value = mutableDrafts.value.map {
            if (it.id == id) it.copy(content = content, updatedAt = it.updatedAt + 1) else it
        }
    }

    override suspend fun deleteDraft(id: String) = structuralOperation {
        if (mutableDrafts.value.none { it.id == id }) {
            throw DraftRepositoryException.DraftNotFound(id)
        }
        mutableDrafts.value = mutableDrafts.value.filterNot { it.id == id }
        if (mutableWorkspace.value.selectedDraftId == id) {
            mutableWorkspace.value = Workspace(mutableDrafts.value.first().id)
        }
    }

    fun emitPersistedContent(id: String, content: String) {
        mutableDrafts.value = mutableDrafts.value.map {
            if (it.id == id) it.copy(content = content, updatedAt = it.updatedAt + 1) else it
        }
    }

    private suspend fun <T> structuralOperation(block: () -> T): T {
        activeOperations += 1
        maximumConcurrentOperations = maxOf(maximumConcurrentOperations, activeOperations)
        try {
            delay(operationDelayMillis)
            return block()
        } finally {
            activeOperations -= 1
        }
    }
}

private fun draft(id: String, name: String, displayOrder: Long) = Draft(
    id = id,
    name = name,
    content = "",
    displayOrder = displayOrder,
    createdAt = 1,
    updatedAt = 1,
)
