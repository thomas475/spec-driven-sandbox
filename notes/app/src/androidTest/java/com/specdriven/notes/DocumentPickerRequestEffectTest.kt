package com.specdriven.notes

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.test.ext.junit.runners.AndroidJUnit4
import com.specdriven.notes.ui.NotesPickerRequest
import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class DocumentPickerRequestEffectTest {
    @get:Rule
    val composeRule = createComposeRule()

    @Test
    fun launchesEachOperationOnceWithExactMimeTypeAndSuggestedName() {
        var request by mutableStateOf<NotesPickerRequest?>(NotesPickerRequest.ImportText(7))
        var unrelatedRecomposition by mutableIntStateOf(0)
        val imports = mutableListOf<Pair<Long, Array<String>>>()
        val exports = mutableListOf<Pair<Long, String>>()
        val consumed = mutableListOf<Long>()
        composeRule.setContent {
            unrelatedRecomposition
            DocumentPickerRequestEffect(
                pickerRequest = request,
                launchImport = { operationId, mimeTypes ->
                    imports += operationId to mimeTypes
                },
                launchExport = { operationId, suggestedName ->
                    exports += operationId to suggestedName
                },
                onConsumed = consumed::add,
            )
        }
        composeRule.waitForIdle()

        assertEquals(1, imports.size)
        assertEquals(7L, imports.single().first)
        assertArrayEquals(arrayOf("text/plain"), imports.single().second)
        assertEquals(listOf(7L), consumed)

        composeRule.runOnIdle { unrelatedRecomposition += 1 }
        composeRule.waitForIdle()
        assertEquals(1, imports.size)

        composeRule.runOnIdle {
            request = NotesPickerRequest.ExportText(8, "Project.txt")
        }
        composeRule.waitForIdle()

        assertEquals(listOf(8L to "Project.txt"), exports)
        assertEquals(listOf(7L, 8L), consumed)
    }
}
