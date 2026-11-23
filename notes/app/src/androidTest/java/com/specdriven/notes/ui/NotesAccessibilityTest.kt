package com.specdriven.notes.ui

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.size
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.SemanticsProperties
import androidx.compose.ui.test.SemanticsMatcher
import androidx.compose.ui.test.assert
import androidx.compose.ui.test.assertContentDescriptionEquals
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.getUnclippedBoundsInRoot
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.performClick
import androidx.compose.ui.text.input.TextFieldValue
import androidx.compose.ui.unit.Density
import androidx.compose.ui.unit.dp
import androidx.test.ext.junit.runners.AndroidJUnit4
import com.specdriven.notes.domain.Draft
import com.specdriven.notes.ui.theme.NotesTheme
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class NotesAccessibilityTest {
    @get:Rule
    val composeRule = createComposeRule()

    @Test
    fun operationErrorsAreAnnouncedAndRecoverable() {
        val actions = mutableListOf<NotesAction>()
        var state by mutableStateOf(readyState(errorFor(NotesOperation.SAVE)))
        composeRule.setContent {
            NotesTheme { NotesScreen(state, onAction = actions::add) }
        }

        NotesOperation.entries.filterNot { it == NotesOperation.INITIALIZE }.forEach { operation ->
            composeRule.runOnIdle { state = readyState(errorFor(operation)) }
            composeRule.onNodeWithTag("error-banner")
                .assertIsDisplayed()
                .assert(
                    SemanticsMatcher.expectValue(
                        SemanticsProperties.LiveRegion,
                        LiveRegionMode.Assertive,
                    ),
                )
        }

        composeRule.onNodeWithTag("retry-error").performClick()
        composeRule.onNodeWithTag("dismiss-error").performClick()
        assertEquals(listOf(NotesAction.RetryError, NotesAction.DismissError), actions)
    }

    @Test
    fun initializationFailureUsesFullScreenRetry() {
        val actions = mutableListOf<NotesAction>()
        composeRule.setContent {
            NotesTheme {
                NotesScreen(
                    NotesUiState(
                        isLoading = false,
                        error = errorFor(NotesOperation.INITIALIZE),
                    ),
                    onAction = actions::add,
                )
            }
        }

        composeRule.onNodeWithTag("initialization-error").assertIsDisplayed()
        composeRule.onNodeWithTag("initialization-retry").performClick()
        assertEquals(NotesAction.RetryError, actions.single())
    }

    @Test
    fun controlsHaveDescriptionsAndMinimumTouchBounds() {
        composeRule.setContent {
            NotesTheme { NotesScreen(readyState(), onAction = {}) }
        }

        composeRule.onNodeWithTag("add-draft")
            .assertContentDescriptionEquals("Add draft")
        composeRule.onNodeWithTag("rename-draft")
            .assertContentDescriptionEquals("Rename selected draft")
        composeRule.onNodeWithTag("editor")
            .assertContentDescriptionEquals("Draft editor")

        listOf("add-draft", "rename-draft", "close-draft-one").forEach { tag ->
            val bounds = composeRule.onNodeWithTag(tag).getUnclippedBoundsInRoot()
            assertTrue("$tag width", bounds.right - bounds.left >= 48.dp)
            assertTrue("$tag height", bounds.bottom - bounds.top >= 48.dp)
        }
    }

    @Test
    fun coreLayoutRemainsUsableAtLargeFontInLandscape() {
        composeRule.setContent {
            CompositionLocalProvider(LocalDensity provides Density(1f, 2f)) {
                NotesTheme {
                    Box(Modifier.size(width = 640.dp, height = 320.dp)) {
                        NotesScreen(readyState(), onAction = {})
                    }
                }
            }
        }

        composeRule.onNodeWithTag("add-draft").assertIsDisplayed()
        composeRule.onNodeWithTag("rename-draft").assertIsDisplayed()
        composeRule.onNodeWithTag("editor").assertIsDisplayed()
    }

    private fun readyState(error: NotesUiError? = null) = NotesUiState(
        isLoading = false,
        drafts = listOf(Draft("one", "A very long draft name that truncates", "", 0, 0, 0)),
        selectedDraftId = "one",
        editorValues = mapOf("one" to TextFieldValue()),
        error = error,
    )

    private fun errorFor(operation: NotesOperation) = NotesUiError(
        operation = operation,
        retry = when (operation) {
            NotesOperation.INITIALIZE -> NotesRetry.Initialize
            NotesOperation.CREATE -> NotesRetry.Create
            NotesOperation.RENAME -> NotesRetry.Rename("one", "Name")
            NotesOperation.SELECT -> NotesRetry.Select("one")
            NotesOperation.DELETE -> NotesRetry.Delete("one")
            NotesOperation.SAVE -> NotesRetry.Save("one")
        },
    )
}
