package com.specdriven.notes.ui

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.ui.text.input.TextFieldValue
import androidx.compose.ui.test.assertIsNotEnabled
import androidx.compose.ui.test.assertTextContains
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performTextClearance
import androidx.compose.ui.test.performTextInput
import androidx.test.ext.junit.runners.AndroidJUnit4
import com.specdriven.notes.domain.Draft
import com.specdriven.notes.ui.theme.NotesTheme
import org.junit.Assert.assertEquals
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class NotesDialogTest {
    @get:Rule
    val composeRule = createComposeRule()

    @Test
    fun renameIsPrefilledRejectsBlankAndKeepsTargetId() {
        val actions = mutableListOf<NotesAction>()
        val state = state(
            selectedId = "two",
            dialog = NotesDialog.Rename("one"),
        )
        composeRule.setContent {
            NotesTheme { NotesScreen(state, onAction = actions::add) }
        }

        composeRule.onNodeWithTag("rename-input").assertTextContains("One")
        composeRule.onNodeWithTag("rename-input").performTextClearance()
        composeRule.onNodeWithTag("confirm-rename").assertIsNotEnabled()
        composeRule.onNodeWithTag("rename-input").performTextInput("Renamed")
        composeRule.onNodeWithTag("confirm-rename").performClick()

        assertEquals(NotesAction.SubmitRename("one", "Renamed"), actions.last())
    }

    @Test
    fun renameAndDeleteCancelWithoutChangingTarget() {
        val renameActions = mutableListOf<NotesAction>()
        composeRule.setContent {
            NotesTheme {
                NotesScreen(
                    state(dialog = NotesDialog.Rename("one")),
                    onAction = renameActions::add,
                )
            }
        }
        composeRule.onNodeWithTag("cancel-rename").performClick()
        assertEquals(NotesAction.CloseDialog, renameActions.single())
    }

    @Test
    fun emptyDraftClosesImmediatelyButWhitespaceRequiresConfirmation() {
        val actions = mutableListOf<NotesAction>()
        var screenState by mutableStateOf(state(firstContent = ""))
        composeRule.setContent {
            NotesTheme {
                NotesScreen(screenState, onAction = actions::add)
            }
        }
        composeRule.onNodeWithTag("close-draft-one").performClick()
        assertEquals(NotesAction.ConfirmDelete("one"), actions.single())

        composeRule.runOnIdle {
            actions.clear()
            screenState = state(firstContent = "   ")
        }
        composeRule.onNodeWithTag("close-draft-one").performClick()
        assertEquals(
            NotesAction.OpenDeleteConfirmation("one"),
            actions.single(),
        )
    }

    @Test
    fun deleteDialogNamesAndDeletesItsImmutableTarget() {
        val actions = mutableListOf<NotesAction>()
        composeRule.setContent {
            NotesTheme {
                NotesScreen(
                    state(selectedId = "two", dialog = NotesDialog.ConfirmDeletion("one")),
                    onAction = actions::add,
                )
            }
        }

        composeRule.onNodeWithText("Delete One?").assertExists()
        composeRule.onNodeWithTag("confirm-delete").performClick()
        assertEquals(NotesAction.ConfirmDelete("one"), actions.single())
    }

    private fun state(
        selectedId: String = "one",
        firstContent: String = "text",
        dialog: NotesDialog = NotesDialog.None,
    ): NotesUiState {
        val drafts = listOf(
            Draft("one", "One", firstContent, 0, 0, 0),
            Draft("two", "Two", "second", 1, 1, 1),
        )
        return NotesUiState(
            isLoading = false,
            drafts = drafts,
            selectedDraftId = selectedId,
            editorValues = mapOf(
                "one" to TextFieldValue(firstContent),
                "two" to TextFieldValue("second"),
            ),
            dialog = dialog,
        )
    }
}
