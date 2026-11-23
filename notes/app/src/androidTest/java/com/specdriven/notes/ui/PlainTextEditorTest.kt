package com.specdriven.notes.ui

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.ui.text.TextRange
import androidx.compose.ui.text.input.TextFieldValue
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performTextInput
import androidx.test.ext.junit.runners.AndroidJUnit4
import com.specdriven.notes.domain.Draft
import com.specdriven.notes.ui.theme.NotesTheme
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class PlainTextEditorTest {
    @get:Rule
    val composeRule = createComposeRule()

    @Test
    fun multilineUnicodeInputUpdatesSelectedDraft() {
        val actions = mutableListOf<NotesAction>()
        var state by mutableStateOf(editorState())
        composeRule.setContent {
            NotesTheme {
                NotesScreen(state, onAction = { action ->
                    actions += action
                    if (action is NotesAction.ChangeEditor) {
                        state = state.copy(
                            editorValues = state.editorValues + (action.draftId to action.value),
                        )
                    }
                })
            }
        }

        composeRule.onNodeWithTag("editor").performTextInput("first\nΚαλημέρα 👋")

        val change = actions.filterIsInstance<NotesAction.ChangeEditor>().last()
        assertEquals("one", change.draftId)
        assertEquals("first\nΚαλημέρα 👋", change.value.text)
    }

    @Test
    fun longDocumentRemainsEditableWithoutScrollingAwayTabs() {
        val longText = (1..200).joinToString("\n") { "line $it ${"x".repeat(100)}" }
        var state by mutableStateOf(
            editorState(
                firstValue = TextFieldValue(longText, TextRange(longText.length)),
            ),
        )
        composeRule.setContent {
            NotesTheme {
                NotesScreen(state, onAction = { action ->
                    if (action is NotesAction.ChangeEditor) {
                        state = state.copy(
                            editorValues = state.editorValues + (action.draftId to action.value),
                        )
                    }
                })
            }
        }

        composeRule.onNodeWithTag("editor").performTextInput("\nlast line")

        composeRule.onNodeWithTag("draft-tab-one").assertIsDisplayed()
        assertTrue(state.editorValues.getValue("one").text.endsWith("last line"))
    }

    @Test
    fun switchingTabsKeepsInputOnOriginalDraft() {
        val actions = mutableListOf<NotesAction>()
        var state by mutableStateOf(editorState())
        composeRule.setContent {
            NotesTheme {
                NotesScreen(state, onAction = { action ->
                    actions += action
                    state = when (action) {
                        is NotesAction.ChangeEditor -> state.copy(
                            editorValues = state.editorValues + (action.draftId to action.value),
                        )
                        is NotesAction.SelectDraft -> state.copy(selectedDraftId = action.draftId)
                        else -> state
                    }
                })
            }
        }

        composeRule.onNodeWithTag("editor").performTextInput("draft one")
        composeRule.onNodeWithTag("draft-tab-two").performClick()
        composeRule.onNodeWithTag("editor").performTextInput("draft two")

        assertEquals("draft one", state.editorValues.getValue("one").text)
        assertEquals("draft two", state.editorValues.getValue("two").text)
        assertEquals(
            listOf("one", "two"),
            actions.filterIsInstance<NotesAction.ChangeEditor>().map { it.draftId }.distinct(),
        )
    }

    private fun editorState(
        firstValue: TextFieldValue = TextFieldValue(),
    ): NotesUiState {
        val drafts = listOf(
            Draft("one", "One", "", 0, 0, 0),
            Draft("two", "Two", "", 1, 1, 1),
        )
        return NotesUiState(
            isLoading = false,
            drafts = drafts,
            selectedDraftId = "one",
            editorValues = mapOf(
                "one" to firstValue,
                "two" to TextFieldValue(),
            ),
        )
    }
}
