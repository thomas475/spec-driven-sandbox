package com.specdriven.notes.ui.theme

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable

private val NotesDarkColors = darkColorScheme(
    primary = NotesPrimary,
    background = NotesBackground,
    surface = NotesSurface,
    onBackground = NotesOnBackground,
    onSurface = NotesOnBackground,
    error = NotesError,
)

@Composable
fun NotesTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = NotesDarkColors,
        content = content,
    )
}

