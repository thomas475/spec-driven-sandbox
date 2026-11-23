package com.specdriven.notes.ui

import androidx.compose.ui.text.input.TextFieldValue
import com.specdriven.notes.data.document.DocumentReference
import com.specdriven.notes.data.document.DocumentWriteFailedException
import kotlinx.coroutines.ExperimentalCoroutinesApi
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
class NotesExportViewModelTest {
    @get:Rule
    val mainDispatcherRule = MainDispatcherRule()

    @Test
    fun exportRequestSuggestsNameIsConsumedOnceAndCancellationIsSilent() =
        runTest(mainDispatcherRule.dispatcher) {
            val viewModel = NotesViewModel(FakeDraftRepository(), FakeDocumentGateway())
            advanceUntilIdle()

            viewModel.onAction(NotesAction.RequestExportText)
            val request = viewModel.uiState.value.pickerRequest as NotesPickerRequest.ExportText
            assertEquals("Untitled 1.txt", request.suggestedFileName)
            assertEquals(
                NotesTransferProgress(request.operationId, NotesTransferPhase.AWAITING_PICKER),
                viewModel.uiState.value.exportProgress,
            )

            viewModel.onAction(NotesAction.PickerRequestConsumed(request.operationId))
            assertNull(viewModel.uiState.value.pickerRequest)
            viewModel.onAction(NotesAction.ExportDocumentResult(request.operationId, null))

            assertNull(viewModel.uiState.value.exportProgress)
            assertNull(viewModel.uiState.value.error)
        }

    @Test
    fun exportWritesCapturedUnsavedUnicodeSnapshotWithoutClearingDirtyState() =
        runTest(mainDispatcherRule.dispatcher) {
            val repository = FakeDraftRepository()
            val gateway = FakeDocumentGateway()
            val viewModel = NotesViewModel(repository, gateway)
            advanceUntilIdle()
            val capturedText = "Unsaved\nΚαλημέρα 👋  "
            viewModel.onAction(
                NotesAction.ChangeEditor("draft-1", TextFieldValue(capturedText)),
            )

            val operationId = requestExport(viewModel)
            viewModel.onAction(
                NotesAction.ExportDocumentResult(operationId, reference("destination")),
            )
            runCurrent()

            assertEquals(capturedText, gateway.writeCalls.single().second)
            assertTrue("draft-1" in viewModel.uiState.value.dirtyDraftIds)
            assertEquals("", repository.drafts.value.single().content)
            assertNull(viewModel.uiState.value.exportProgress)
            assertNull(viewModel.uiState.value.error)
        }

    @Test
    fun tabSwitchAndLaterEditingCannotRedirectOrChangePendingExport() =
        runTest(mainDispatcherRule.dispatcher) {
            val repository = FakeDraftRepository()
            val gateway = FakeDocumentGateway()
            val viewModel = NotesViewModel(repository, gateway)
            advanceUntilIdle()
            viewModel.onAction(NotesAction.ChangeEditor("draft-1", TextFieldValue("Captured first")))
            val operationId = requestExport(viewModel)

            viewModel.onAction(NotesAction.ChangeEditor("draft-1", TextFieldValue("Later first")))
            viewModel.onAction(NotesAction.CreateDraft)
            advanceUntilIdle()
            viewModel.onAction(NotesAction.ChangeEditor("draft-2", TextFieldValue("Second draft")))
            viewModel.onAction(
                NotesAction.ExportDocumentResult(operationId, reference("destination")),
            )
            runCurrent()

            assertEquals("Captured first", gateway.writeCalls.single().second)
            assertEquals("draft-2", viewModel.uiState.value.selectedDraftId)
        }

    @Test
    fun duplicateMismatchedAndConcurrentExportActionsAreIgnored() =
        runTest(mainDispatcherRule.dispatcher) {
            val gateway = FakeDocumentGateway(writeDelayMillis = 100)
            val viewModel = NotesViewModel(FakeDraftRepository(), gateway)
            advanceUntilIdle()
            val operationId = requestExport(viewModel)

            viewModel.onAction(NotesAction.RequestExportText)
            assertEquals(operationId, viewModel.uiState.value.pickerRequest?.operationId)
            viewModel.onAction(
                NotesAction.ExportDocumentResult(operationId + 1, reference("mismatch")),
            )
            assertEquals(0, gateway.writeCalls.size)

            val result = NotesAction.ExportDocumentResult(
                operationId,
                reference("accepted"),
            )
            viewModel.onAction(result)
            viewModel.onAction(result)
            runCurrent()
            assertEquals(NotesTransferPhase.PROCESSING, viewModel.uiState.value.exportProgress?.phase)
            advanceUntilIdle()
            assertEquals(1, gateway.writeCalls.size)
        }

    @Test
    fun pickerResultForDeletedCapturedDraftIsIgnored() = runTest(mainDispatcherRule.dispatcher) {
        val gateway = FakeDocumentGateway()
        val viewModel = NotesViewModel(FakeDraftRepository(), gateway)
        advanceUntilIdle()
        viewModel.onAction(NotesAction.CreateDraft)
        advanceUntilIdle()
        viewModel.onAction(NotesAction.SelectDraft("draft-1"))
        advanceUntilIdle()
        val operationId = requestExport(viewModel)

        viewModel.onAction(NotesAction.ConfirmDelete("draft-1"))
        advanceUntilIdle()
        viewModel.onAction(
            NotesAction.ExportDocumentResult(operationId, reference("stale")),
        )
        advanceUntilIdle()

        assertTrue(gateway.writeCalls.isEmpty())
        assertNull(viewModel.uiState.value.exportProgress)
        assertNull(viewModel.uiState.value.error)
    }

    @Test
    fun failedExportPreservesDraftAndDirtyStateThenRetryCapturesLatestText() =
        runTest(mainDispatcherRule.dispatcher) {
            val repository = FakeDraftRepository()
            val gateway = FakeDocumentGateway().apply {
                writeFailure = DocumentWriteFailedException(IllegalStateException())
            }
            val viewModel = NotesViewModel(repository, gateway)
            advanceUntilIdle()
            viewModel.onAction(
                NotesAction.ChangeEditor("draft-1", TextFieldValue("First snapshot")),
            )
            val firstOperationId = requestExport(viewModel)
            viewModel.onAction(
                NotesAction.ExportDocumentResult(firstOperationId, reference("failure")),
            )
            runCurrent()

            assertEquals(NotesErrorCause.DOCUMENT_WRITE_FAILED, viewModel.uiState.value.error?.cause)
            assertEquals(NotesRetry.ExportText, viewModel.uiState.value.error?.retry)
            assertTrue("draft-1" in viewModel.uiState.value.dirtyDraftIds)
            assertEquals("", repository.drafts.value.single().content)

            viewModel.onAction(
                NotesAction.ChangeEditor("draft-1", TextFieldValue("Latest retry text")),
            )
            gateway.writeFailure = null
            viewModel.onAction(NotesAction.RetryError)
            val retryRequest = viewModel.uiState.value.pickerRequest as NotesPickerRequest.ExportText
            assertTrue(retryRequest.operationId > firstOperationId)
            viewModel.onAction(
                NotesAction.ExportDocumentResult(retryRequest.operationId, reference("retry")),
            )
            runCurrent()

            assertEquals("Latest retry text", gateway.writeCalls.single().second)
            assertNull(viewModel.uiState.value.error)
            assertTrue("draft-1" in viewModel.uiState.value.dirtyDraftIds)
        }

    @Test
    fun exportSuccessDoesNotInterfereWithIndependentSaveCompletion() =
        runTest(mainDispatcherRule.dispatcher) {
            val repository = FakeDraftRepository()
            val gateway = FakeDocumentGateway()
            val viewModel = NotesViewModel(repository, gateway)
            advanceUntilIdle()
            viewModel.onAction(NotesAction.ChangeEditor("draft-1", TextFieldValue("Save and export")))
            val operationId = requestExport(viewModel)
            viewModel.onAction(
                NotesAction.ExportDocumentResult(operationId, reference("destination")),
            )
            runCurrent()

            assertEquals("Save and export", gateway.writeCalls.single().second)
            assertTrue("draft-1" in viewModel.uiState.value.dirtyDraftIds)
            advanceUntilIdle()
            assertEquals("Save and export", repository.drafts.value.single().content)
            assertFalse("draft-1" in viewModel.uiState.value.dirtyDraftIds)
        }

    private fun requestExport(viewModel: NotesViewModel): Long {
        viewModel.onAction(NotesAction.RequestExportText)
        return requireNotNull(viewModel.uiState.value.pickerRequest).operationId
    }

    private fun reference(value: String): DocumentReference =
        DocumentReference.fromUriString("content://test/$value")
}
