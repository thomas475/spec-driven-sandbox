package com.specdriven.notes.ui

import androidx.compose.ui.text.input.TextFieldValue
import com.specdriven.notes.data.document.DocumentGateway
import com.specdriven.notes.data.document.DocumentReadFailedException
import com.specdriven.notes.data.document.DocumentReference
import com.specdriven.notes.data.document.DocumentTooLargeException
import com.specdriven.notes.data.document.ImportedTextDocument
import com.specdriven.notes.data.document.InvalidTextEncodingException
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.delay
import kotlinx.coroutines.test.advanceUntilIdle
import kotlinx.coroutines.test.runCurrent
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class NotesImportViewModelTest {
    @get:Rule
    val mainDispatcherRule = MainDispatcherRule()

    @Test
    fun importRequestIsConsumedOnceAndCancellationIsSilent() = runTest(mainDispatcherRule.dispatcher) {
        val repository = FakeDraftRepository()
        val viewModel = NotesViewModel(repository, FakeDocumentGateway())
        advanceUntilIdle()

        viewModel.onAction(NotesAction.RequestImportText)
        val request = viewModel.uiState.value.pickerRequest as NotesPickerRequest.ImportText
        assertEquals(
            NotesTransferProgress(request.operationId, NotesTransferPhase.AWAITING_PICKER),
            viewModel.uiState.value.importProgress,
        )

        viewModel.onAction(NotesAction.PickerRequestConsumed(request.operationId))
        assertNull(viewModel.uiState.value.pickerRequest)
        viewModel.onAction(NotesAction.ImportDocumentResult(request.operationId, null))

        assertNull(viewModel.uiState.value.importProgress)
        assertNull(viewModel.uiState.value.error)
        assertEquals(listOf("draft-1"), repository.drafts.value.map { it.id })
    }

    @Test
    fun successfulImportCreatesSelectedNamedDraftWithExactContent() =
        runTest(mainDispatcherRule.dispatcher) {
            val repository = FakeDraftRepository()
            val gateway = FakeDocumentGateway().apply {
                nextRead = ImportedTextDocument(
                    displayName = "  Imported.TXT  ",
                    content = "First\r\nΚαλημέρα 👋  ",
                )
            }
            val viewModel = NotesViewModel(repository, gateway)
            advanceUntilIdle()

            val operationId = requestImport(viewModel)
            viewModel.onAction(
                NotesAction.ImportDocumentResult(operationId, reference("successful-import")),
            )
            advanceUntilIdle()

            val imported = repository.drafts.value.last()
            assertEquals("Imported", imported.name)
            assertEquals("First\r\nΚαλημέρα 👋  ", imported.content)
            assertEquals(imported.id, repository.workspace.value.selectedDraftId)
            assertNull(viewModel.uiState.value.importProgress)
            assertNull(viewModel.uiState.value.error)
        }

    @Test
    fun importMapsEveryReadFailureWithoutChangingDraftsOrSelection() =
        runTest(mainDispatcherRule.dispatcher) {
            val failures = listOf(
                DocumentReadFailedException(IllegalStateException()) to
                    NotesErrorCause.DOCUMENT_READ_FAILED,
                InvalidTextEncodingException(IllegalArgumentException()) to
                    NotesErrorCause.INVALID_TEXT_ENCODING,
                DocumentTooLargeException(1_048_576) to
                    NotesErrorCause.DOCUMENT_TOO_LARGE,
            )

            failures.forEachIndexed { index, (failure, expectedCause) ->
                val repository = FakeDraftRepository()
                val gateway = FakeDocumentGateway().apply { readFailure = failure }
                val viewModel = NotesViewModel(repository, gateway)
                advanceUntilIdle()
                val selectionBefore = repository.workspace.value

                val operationId = requestImport(viewModel)
                viewModel.onAction(
                    NotesAction.ImportDocumentResult(operationId, reference("failure-$index")),
                )
                advanceUntilIdle()

                assertEquals(listOf("draft-1"), repository.drafts.value.map { it.id })
                assertEquals(selectionBefore, repository.workspace.value)
                assertEquals(expectedCause, viewModel.uiState.value.error?.cause)
                assertEquals(NotesRetry.ImportText, viewModel.uiState.value.error?.retry)
                assertNull(viewModel.uiState.value.importProgress)
            }
        }

    @Test
    fun failedImportedDraftCreationCanDismissOrRetryWithNewPicker() =
        runTest(mainDispatcherRule.dispatcher) {
            val repository = FakeDraftRepository().apply { importFailuresRemaining = 1 }
            val gateway = FakeDocumentGateway()
            val viewModel = NotesViewModel(repository, gateway)
            advanceUntilIdle()

            val firstOperationId = requestImport(viewModel)
            viewModel.onAction(
                NotesAction.ImportDocumentResult(firstOperationId, reference("first")),
            )
            advanceUntilIdle()
            assertEquals(
                NotesErrorCause.IMPORTED_DRAFT_CREATION_FAILED,
                viewModel.uiState.value.error?.cause,
            )

            viewModel.onAction(NotesAction.DismissError)
            assertNull(viewModel.uiState.value.error)
            gateway.nextRead = ImportedTextDocument("Retry.txt", "Recovered")
            viewModel.onAction(NotesAction.RequestImportText)
            val retryRequest = viewModel.uiState.value.pickerRequest as NotesPickerRequest.ImportText
            assertTrue(retryRequest.operationId > firstOperationId)
            viewModel.onAction(
                NotesAction.ImportDocumentResult(retryRequest.operationId, reference("retry")),
            )
            advanceUntilIdle()

            assertEquals("Recovered", repository.drafts.value.last().content)
            assertNull(viewModel.uiState.value.error)
        }

    @Test
    fun retryErrorRequestsFreshPickerAfterReadFailure() = runTest(mainDispatcherRule.dispatcher) {
        val gateway = FakeDocumentGateway().apply {
            readFailure = DocumentReadFailedException(IllegalStateException())
        }
        val viewModel = NotesViewModel(FakeDraftRepository(), gateway)
        advanceUntilIdle()

        val firstOperationId = requestImport(viewModel)
        viewModel.onAction(
            NotesAction.ImportDocumentResult(firstOperationId, reference("failure")),
        )
        advanceUntilIdle()
        gateway.readFailure = null

        viewModel.onAction(NotesAction.RetryError)

        val retryRequest = viewModel.uiState.value.pickerRequest as NotesPickerRequest.ImportText
        assertTrue(retryRequest.operationId > firstOperationId)
        assertNull(viewModel.uiState.value.error)
    }

    @Test
    fun duplicateMismatchedAndConcurrentImportActionsAreIgnored() =
        runTest(mainDispatcherRule.dispatcher) {
            val gateway = FakeDocumentGateway(readDelayMillis = 100)
            val viewModel = NotesViewModel(FakeDraftRepository(), gateway)
            advanceUntilIdle()

            val operationId = requestImport(viewModel)
            viewModel.onAction(NotesAction.RequestImportText)
            assertEquals(operationId, viewModel.uiState.value.pickerRequest?.operationId)
            viewModel.onAction(
                NotesAction.ImportDocumentResult(operationId + 100, reference("mismatch")),
            )
            assertEquals(0, gateway.readCalls.size)

            val result = NotesAction.ImportDocumentResult(operationId, reference("accepted"))
            viewModel.onAction(result)
            viewModel.onAction(result)
            runCurrent()
            assertEquals(1, gateway.readCalls.size)
            assertEquals(NotesTransferPhase.PROCESSING, viewModel.uiState.value.importProgress?.phase)
            advanceUntilIdle()
            assertEquals(1, gateway.readCalls.size)
        }

    @Test
    fun importLeavesDirtyEditorBufferAndItsSaveCoordinationIntact() =
        runTest(mainDispatcherRule.dispatcher) {
            val repository = FakeDraftRepository()
            val gateway = FakeDocumentGateway()
            val viewModel = NotesViewModel(repository, gateway)
            advanceUntilIdle()
            viewModel.onAction(
                NotesAction.ChangeEditor("draft-1", TextFieldValue("Unsaved local text")),
            )

            val operationId = requestImport(viewModel)
            viewModel.onAction(
                NotesAction.ImportDocumentResult(operationId, reference("import")),
            )
            runCurrent()

            assertEquals(
                "Unsaved local text",
                viewModel.uiState.value.editorValues["draft-1"]?.text,
            )
            assertTrue("draft-1" in viewModel.uiState.value.dirtyDraftIds)
            advanceUntilIdle()
            assertEquals("Unsaved local text", repository.saveCalls.last().second)
            assertFalse("draft-1" in viewModel.uiState.value.dirtyDraftIds)
        }

    private fun requestImport(viewModel: NotesViewModel): Long {
        viewModel.onAction(NotesAction.RequestImportText)
        return requireNotNull(viewModel.uiState.value.pickerRequest).operationId
    }

    private fun reference(value: String): DocumentReference =
        DocumentReference.fromUriString("content://test/$value")
}

internal class FakeDocumentGateway(
    private val readDelayMillis: Long = 0,
    private val writeDelayMillis: Long = 0,
) : DocumentGateway {
    var nextRead = ImportedTextDocument("Imported.txt", "Imported content")
    var readFailure: Exception? = null
    val readCalls = mutableListOf<DocumentReference>()
    var writeFailure: Exception? = null
    val writeCalls = mutableListOf<Pair<DocumentReference, String>>()

    override suspend fun readText(document: DocumentReference): ImportedTextDocument {
        readCalls += document
        delay(readDelayMillis)
        readFailure?.let { throw it }
        return nextRead
    }

    override suspend fun writeText(document: DocumentReference, content: String) {
        delay(writeDelayMillis)
        writeFailure?.let { throw it }
        writeCalls += document to content
    }
}
