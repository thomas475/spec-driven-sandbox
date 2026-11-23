package com.specdriven.notes

import android.content.Context
import androidx.room.Room
import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import com.specdriven.notes.data.Clock
import com.specdriven.notes.data.IdGenerator
import com.specdriven.notes.data.RoomDraftRepository
import com.specdriven.notes.data.local.NotesDatabase
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotEquals
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class CrossFeatureAcceptanceTest {
    private val context: Context = ApplicationProvider.getApplicationContext()
    private val databaseName = "cross-feature-acceptance.db"
    private var database: NotesDatabase? = null
    private var nextId = 0
    private var currentTime = 1_000L

    @After
    fun cleanUp() {
        database?.close()
        context.deleteDatabase(databaseName)
    }

    @Test
    fun completeWorkspaceSurvivesReopenSelectionAndDeletion() = runBlocking {
        var repository = openRepository()
        repository.initialize()
        val firstId = repository.drafts.first().single().id
        val secondId = repository.createDraft()
        repository.renameDraft(secondId, "  Project  ")
        repository.saveContent(firstId, "first\nΚαλημέρα 👋")
        repository.saveContent(secondId, "second draft")
        repository.selectDraft(secondId)

        repository = reopenRepository()
        repository.initialize()
        assertEquals(listOf(firstId, secondId), repository.drafts.first().map { it.id })
        assertEquals(listOf("Untitled 1", "Project"), repository.drafts.first().map { it.name })
        assertEquals(
            listOf("first\nΚαλημέρα 👋", "second draft"),
            repository.drafts.first().map { it.content },
        )
        assertEquals(secondId, repository.workspace.first().selectedDraftId)

        repository.deleteDraft(secondId)
        repository.saveContent(firstId, "latest acknowledged text")
        repository = reopenRepository()
        repository.initialize()
        assertEquals(listOf(firstId), repository.drafts.first().map { it.id })
        assertEquals("latest acknowledged text", repository.drafts.first().single().content)
        assertEquals(firstId, repository.workspace.first().selectedDraftId)

        repository.deleteDraft(firstId)
        val replacement = repository.drafts.first().single()
        assertNotEquals(firstId, replacement.id)
        assertEquals("Untitled 1", replacement.name)
        assertEquals(replacement.id, repository.workspace.first().selectedDraftId)

        repository = reopenRepository()
        repository.initialize()
        assertEquals(replacement.id, repository.drafts.first().single().id)
        assertEquals(replacement.id, repository.workspace.first().selectedDraftId)
    }

    private fun openRepository(): RoomDraftRepository {
        database = Room.databaseBuilder(context, NotesDatabase::class.java, databaseName).build()
        return RoomDraftRepository(
            database = requireNotNull(database),
            idGenerator = IdGenerator { "acceptance-${++nextId}" },
            clock = Clock { ++currentTime },
        )
    }

    private fun reopenRepository(): RoomDraftRepository {
        database?.close()
        return openRepository()
    }
}
