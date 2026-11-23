package com.specdriven.notes.ui

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.ui.test.assertCountEquals
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.assertIsSelected
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onAllNodesWithText
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.performClick
import androidx.test.ext.junit.runners.AndroidJUnit4
import com.specdriven.notes.domain.Draft
import com.specdriven.notes.ui.theme.NotesTheme
import org.junit.Assert.assertEquals
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class NotesScreenTest {
    @get:Rule
    val composeRule = createComposeRule()

    @Test
    fun tabsKeepOrderDuplicatesAndSelectedState() {
        val drafts = listOf(
            draft("one", "Same", 0),
            draft("two", "Same", 1),
            draft("three", "Last", 2),
        )

        composeRule.setContent {
            NotesTheme {
                NotesScreen(readyState(drafts, "one"), onAction = {})
            }
        }

        composeRule.onAllNodesWithText("Same").assertCountEquals(2)
        composeRule.onNodeWithTag("draft-tab-one").assertIsSelected()
    }

    @Test
    fun controlsDispatchImmutableDraftTargets() {
        val actions = mutableListOf<NotesAction>()
        val drafts = listOf(draft("one", "One", 0), draft("two", "Two", 1))

        composeRule.setContent {
            NotesTheme {
                NotesScreen(readyState(drafts, "two"), onAction = actions::add)
            }
        }

        composeRule.onNodeWithTag("add-draft").performClick()
        composeRule.onNodeWithTag("rename-draft").performClick()
        composeRule.onNodeWithTag("draft-tab-one").performClick()
        composeRule.onNodeWithTag("close-draft-one").performClick()

        assertEquals(
            listOf(
                NotesAction.CreateDraft,
                NotesAction.OpenRename("two"),
                NotesAction.SelectDraft("one"),
                NotesAction.ConfirmDelete("one"),
            ),
            actions,
        )
    }

    @Test
    fun newlySelectedOverflowTabScrollsIntoView() {
        val drafts = (0 until 12).map { draft("id-$it", "Draft number $it", it.toLong()) }
        var state by mutableStateOf(readyState(drafts, "id-0"))
        composeRule.setContent {
            NotesTheme {
                NotesScreen(state, onAction = {})
            }
        }

        composeRule.runOnIdle { state = readyState(drafts, "id-11") }

        composeRule.onNodeWithTag("draft-tab-id-11").assertIsDisplayed().assertIsSelected()
    }

    private fun readyState(drafts: List<Draft>, selectedId: String) = NotesUiState(
        isLoading = false,
        drafts = drafts,
        selectedDraftId = selectedId,
    )

    private fun draft(id: String, name: String, order: Long) = Draft(
        id = id,
        name = name,
        content = "",
        displayOrder = order,
        createdAt = order,
        updatedAt = order,
    )
}
