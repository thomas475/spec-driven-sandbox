package com.specdriven.notes

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.viewModels
import androidx.compose.runtime.Composable
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.compose.runtime.getValue
import com.specdriven.notes.ui.theme.NotesTheme
import com.specdriven.notes.ui.NotesAction
import com.specdriven.notes.ui.NotesScreen
import com.specdriven.notes.ui.NotesUiState
import com.specdriven.notes.ui.NotesViewModel
import com.specdriven.notes.ui.NotesViewModelFactory

class MainActivity : ComponentActivity() {
    private val notesViewModel: NotesViewModel by viewModels {
        NotesViewModelFactory((application as NotesApplication).repository)
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
    NotesTheme {
        NotesScreen(state = state, onAction = onAction)
    }
}
