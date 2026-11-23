package com.specdriven.notes

import android.content.Context
import android.net.Uri
import androidx.compose.ui.text.input.TextFieldValue
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.ViewModelStore
import androidx.room.Room
import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import com.specdriven.notes.data.Clock
import com.specdriven.notes.data.IdGenerator
import com.specdriven.notes.data.RoomDraftRepository
import com.specdriven.notes.data.document.AndroidDocumentGateway
import com.specdriven.notes.data.document.DocumentReference
import com.specdriven.notes.data.document.DocumentTooLargeException
import com.specdriven.notes.data.document.InvalidTextEncodingException
import com.specdriven.notes.data.document.TextDocumentName
import com.specdriven.notes.data.local.NotesDatabase
import com.specdriven.notes.ui.NotesAction
import com.specdriven.notes.ui.NotesErrorCause
import com.specdriven.notes.ui.NotesPickerRequest
import com.specdriven.notes.ui.NotesUiState
import com.specdriven.notes.ui.NotesViewModel
import com.specdriven.notes.ui.NotesViewModelFactory
import java.nio.charset.StandardCharsets
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withTimeout
import org.junit.After
import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class TextFileTransferAcceptanceTest {
    private val context: Context = ApplicationProvider.getApplicationContext()
    private val databaseName = "text-file-transfer-acceptance.db"
    private val gateway = AndroidDocumentGateway(context.contentResolver)
    private var database: NotesDatabase? = null
    private var viewModelStore: ViewModelStore? = null
    private var nextId = 0
    private var currentTime = 2_000L

    @Before
    fun setUp() {
        context.deleteDatabase(databaseName)
        context.contentResolver.delete(uri("written"), null, null)
    }

    @After
    fun tearDown() {
        viewModelStore?.clear()
        viewModelStore = null
        database?.close()
        context.deleteDatabase(databaseName)
        context.contentResolver.delete(uri("written"), null, null)
    }

    @Test
    fun importEditExportAndFlushUseExactVisibleTextAcrossRealBoundaries() = runBlocking {
        val repository = openRepository()
        val viewModel = createViewModel(repository)
        awaitState(viewModel) { !it.isLoading && it.drafts.size == 1 }

        viewModel.onAction(NotesAction.RequestImportText)
        val importRequest = awaitPicker<NotesPickerRequest.ImportText>(viewModel)
        val importedContent = "First\r\nΚαλημέρα 👋  "
        viewModel.onAction(
            NotesAction.ImportDocumentResult(
                operationId = importRequest.operationId,
                document = reference(
                    path = "read/bom",
                    name = "  Journal.TXT  ",
                    value = importedContent,
                ),
            ),
        )
        val importedState = awaitState(viewModel) {
            it.drafts.size == 2 &&
                it.importProgress == null &&
                it.selectedDraft?.name == "Journal"
        }
        val imported = requireNotNull(importedState.selectedDraft)
        assertEquals("Journal", imported.name)
        assertEquals(importedContent, imported.content)

        val latestVisibleText = "Edited before debounce\n終わり  "
        viewModel.onAction(
            NotesAction.ChangeEditor(imported.id, TextFieldValue(latestVisibleText)),
        )
        viewModel.onAction(NotesAction.RequestExportText)
        val exportRequest = awaitPicker<NotesPickerRequest.ExportText>(viewModel)
        assertEquals("Journal.txt", exportRequest.suggestedFileName)
        viewModel.onAction(
            NotesAction.ExportDocumentResult(
                operationId = exportRequest.operationId,
                document = reference("write"),
            ),
        )
        awaitState(viewModel) { it.exportProgress == null }

        assertArrayEquals(
            latestVisibleText.toByteArray(StandardCharsets.UTF_8),
            requireNotNull(context.contentResolver.openInputStream(uri("written"))).use {
                it.readBytes()
            },
        )
        assertTrue(imported.id in viewModel.uiState.value.dirtyDraftIds)

        viewModel.onAction(NotesAction.AppStopped)
        awaitState(viewModel) { imported.id !in it.dirtyDraftIds }
        assertEquals(
            latestVisibleText,
            repository.drafts.first().first { it.id == imported.id }.content,
        )
    }

    @Test
    fun importedDraftPersistsAfterDatabaseReopenWithExactNameContentAndSelection() = runBlocking {
        var repository = openRepository()
        repository.initialize()
        val document = gateway.readText(
            reference(
                path = "read/text",
                name = "  Persisted.txt  ",
                value = "Line one\nLine two  ",
            ),
        )
        val importedId = repository.createImportedDraft(
            name = TextDocumentName.importedDraftName(document.displayName),
            content = document.content,
        )

        database?.close()
        database = null
        repository = openRepository()
        repository.initialize()

        val imported = repository.drafts.first().first { it.id == importedId }
        assertEquals("Persisted", imported.name)
        assertEquals("Line one\nLine two  ", imported.content)
        assertEquals(importedId, repository.workspace.first().selectedDraftId)
    }

    @Test
    fun emptyUnnamedAndBoundaryDocumentsFollowImportContract() = runBlocking {
        val repository = openRepository()
        repository.initialize()
        val empty = gateway.readText(reference("read/text"))
        assertNull(empty.displayName)
        assertEquals("", empty.content)
        val emptyId = repository.createImportedDraft(
            name = TextDocumentName.importedDraftName(empty.displayName),
            content = empty.content,
        )
        val emptyDraft = repository.drafts.first().first { it.id == emptyId }
        assertEquals("Untitled 2", emptyDraft.name)
        assertEquals("", emptyDraft.content)
        assertEquals(emptyId, repository.workspace.first().selectedDraftId)

        val exactLimit = gateway.readText(reference("read/exact-limit", name = "Limit.txt"))
        assertEquals(1_048_576, exactLimit.content.length)

        assertThrows(InvalidTextEncodingException::class.java) {
            runBlocking { gateway.readText(reference("read/malformed")) }
        }
        assertThrows(DocumentTooLargeException::class.java) {
            runBlocking { gateway.readText(reference("read/oversize")) }
        }
        Unit
    }

    @Test
    fun cancellationFailuresDismissAndRetryNeverCorruptLocalDraft() = runBlocking {
        val repository = openRepository()
        val viewModel = createViewModel(repository)
        val initialState = awaitState(viewModel) { !it.isLoading && it.drafts.size == 1 }
        val initialDraft = requireNotNull(initialState.selectedDraft)

        viewModel.onAction(NotesAction.RequestImportText)
        val canceledImport = awaitPicker<NotesPickerRequest.ImportText>(viewModel)
        viewModel.onAction(NotesAction.ImportDocumentResult(canceledImport.operationId, null))
        awaitState(viewModel) { it.importProgress == null }
        assertEquals(listOf(initialDraft.id), viewModel.uiState.value.drafts.map { it.id })

        viewModel.onAction(NotesAction.RequestImportText)
        val failedImport = awaitPicker<NotesPickerRequest.ImportText>(viewModel)
        viewModel.onAction(
            NotesAction.ImportDocumentResult(
                failedImport.operationId,
                reference("read/malformed"),
            ),
        )
        awaitState(viewModel) { it.error?.cause == NotesErrorCause.INVALID_TEXT_ENCODING }
        assertEquals(listOf(initialDraft.id), viewModel.uiState.value.drafts.map { it.id })

        viewModel.onAction(NotesAction.RetryError)
        val retryImport = awaitPicker<NotesPickerRequest.ImportText>(viewModel)
        viewModel.onAction(
            NotesAction.ImportDocumentResult(
                retryImport.operationId,
                reference("read/text", value = "Recovered"),
            ),
        )
        awaitState(viewModel) { it.drafts.size == 2 && it.error == null }

        viewModel.onAction(NotesAction.RequestExportText)
        val failedExport = awaitPicker<NotesPickerRequest.ExportText>(viewModel)
        viewModel.onAction(
            NotesAction.ExportDocumentResult(failedExport.operationId, reference("failure")),
        )
        awaitState(viewModel) { it.error?.cause == NotesErrorCause.DOCUMENT_WRITE_FAILED }
        viewModel.onAction(NotesAction.DismissError)
        awaitState(viewModel) { it.error == null }

        viewModel.onAction(NotesAction.RequestExportText)
        val retryExport = awaitPicker<NotesPickerRequest.ExportText>(viewModel)
        viewModel.onAction(
            NotesAction.ExportDocumentResult(retryExport.operationId, reference("write")),
        )
        awaitState(viewModel) { it.exportProgress == null }
        assertEquals("Recovered", viewModel.uiState.value.selectedEditorValue.text)
    }

    private fun openRepository(): RoomDraftRepository {
        database = Room.databaseBuilder(context, NotesDatabase::class.java, databaseName).build()
        return RoomDraftRepository(
            database = requireNotNull(database),
            idGenerator = IdGenerator { "transfer-${++nextId}" },
            clock = Clock { ++currentTime },
        )
    }

    private fun createViewModel(repository: RoomDraftRepository): NotesViewModel {
        val store = ViewModelStore()
        viewModelStore = store
        return ViewModelProvider(
            store,
            NotesViewModelFactory(repository, gateway),
        )[NotesViewModel::class.java]
    }

    private suspend inline fun <reified T : NotesPickerRequest> awaitPicker(
        viewModel: NotesViewModel,
    ): T = awaitState(viewModel) { it.pickerRequest is T }.pickerRequest as T

    private suspend fun awaitState(
        viewModel: NotesViewModel,
        predicate: (NotesUiState) -> Boolean,
    ): NotesUiState = withTimeout(5_000) {
        viewModel.uiState.first(predicate)
    }

    private fun reference(
        path: String,
        name: String? = null,
        value: String? = null,
    ): DocumentReference {
        val builder = uri(path).buildUpon()
        name?.let { builder.appendQueryParameter("name", it) }
        value?.let { builder.appendQueryParameter("value", it) }
        return DocumentReference.fromUriString(builder.build().toString())
    }

    private fun uri(path: String): Uri =
        Uri.parse("content://com.specdriven.notes.test.documents/$path")

}
