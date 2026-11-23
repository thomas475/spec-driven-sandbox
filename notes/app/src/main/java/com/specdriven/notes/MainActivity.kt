package com.specdriven.notes

import android.os.Bundle
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.viewModels
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import com.specdriven.notes.data.document.DocumentReference
import com.specdriven.notes.ui.theme.NotesTheme
import com.specdriven.notes.ui.NotesAction
import com.specdriven.notes.ui.NotesPickerRequest
import com.specdriven.notes.ui.NotesScreen
import com.specdriven.notes.ui.NotesUiState
import com.specdriven.notes.ui.NotesViewModel
import com.specdriven.notes.ui.NotesViewModelFactory

class MainActivity : ComponentActivity() {
    private val notesViewModel: NotesViewModel by viewModels {
        val notesApplication = application as NotesApplication
        NotesViewModelFactory(
            repository = notesApplication.repository,
            documentGateway = notesApplication.documentGateway,
        )
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            val state by notesViewModel.uiState.collectAsStateWithLifecycle()
            NotesApp(
                state = state,
                onAction = notesViewModel::onAction,
            )
        }
    }

    override fun onStop() {
        notesViewModel.onAction(NotesAction.AppStopped)
        super.onStop()
    }
}

@Composable
fun NotesApp(
    state: NotesUiState,
    onAction: (NotesAction) -> Unit,
) {
    DocumentPickerLaunchers(
        pickerRequest = state.pickerRequest,
        onAction = onAction,
    )
    NotesTheme {
        NotesScreen(state = state, onAction = onAction)
    }
}

@Composable
internal fun DocumentPickerLaunchers(
    pickerRequest: NotesPickerRequest?,
    onAction: (NotesAction) -> Unit,
) {
    var pendingImportOperationId by rememberSaveable { mutableStateOf<Long?>(null) }
    var pendingExportOperationId by rememberSaveable { mutableStateOf<Long?>(null) }
    val importLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.OpenDocument(),
    ) { uri ->
        val operationId = pendingImportOperationId ?: return@rememberLauncherForActivityResult
        pendingImportOperationId = null
        onAction(
            NotesAction.ImportDocumentResult(
                operationId = operationId,
                document = uri?.let { DocumentReference.fromUriString(it.toString()) },
            ),
        )
    }
    val exportLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.CreateDocument(TEXT_MIME_TYPE),
    ) { uri ->
        val operationId = pendingExportOperationId ?: return@rememberLauncherForActivityResult
        pendingExportOperationId = null
        onAction(
            NotesAction.ExportDocumentResult(
                operationId = operationId,
                document = uri?.let { DocumentReference.fromUriString(it.toString()) },
            ),
        )
    }

    DocumentPickerRequestEffect(
        pickerRequest = pickerRequest,
        launchImport = { operationId, mimeTypes ->
            pendingImportOperationId = operationId
            try {
                importLauncher.launch(mimeTypes)
            } catch (_: RuntimeException) {
                pendingImportOperationId = null
                onAction(NotesAction.ImportDocumentResult(operationId, null))
            }
        },
        launchExport = { operationId, suggestedFileName ->
            pendingExportOperationId = operationId
            try {
                exportLauncher.launch(suggestedFileName)
            } catch (_: RuntimeException) {
                pendingExportOperationId = null
                onAction(NotesAction.ExportDocumentResult(operationId, null))
            }
        },
        onConsumed = { operationId ->
            onAction(NotesAction.PickerRequestConsumed(operationId))
        },
    )
}

@Composable
internal fun DocumentPickerRequestEffect(
    pickerRequest: NotesPickerRequest?,
    launchImport: (Long, Array<String>) -> Unit,
    launchExport: (Long, String) -> Unit,
    onConsumed: (Long) -> Unit,
) {
    LaunchedEffect(pickerRequest?.operationId) {
        val request = pickerRequest ?: return@LaunchedEffect
        when (request) {
            is NotesPickerRequest.ImportText -> {
                launchImport(request.operationId, arrayOf(TEXT_MIME_TYPE))
            }
            is NotesPickerRequest.ExportText -> {
                launchExport(request.operationId, request.suggestedFileName)
            }
        }
        onConsumed(request.operationId)
    }
}

private const val TEXT_MIME_TYPE = "text/plain"
