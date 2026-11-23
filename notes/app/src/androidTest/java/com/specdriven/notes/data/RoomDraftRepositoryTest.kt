package com.specdriven.notes.data

import androidx.room.Room
import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import com.specdriven.notes.data.local.DraftEntity
import com.specdriven.notes.data.local.NotesDatabase
import com.specdriven.notes.data.local.WorkspaceEntity
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertThrows
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class RoomDraftRepositoryTest {
    private lateinit var database: NotesDatabase
    private lateinit var repository: RoomDraftRepository
    private var nextId = 0
    private var currentTime = 1000L

    @Before
    fun setUp() {
        database = Room.inMemoryDatabaseBuilder(
            ApplicationProvider.getApplicationContext(),
            NotesDatabase::class.java,
        ).build()
        repository = RoomDraftRepository(
            database = database,
            idGenerator = IdGenerator { "id-${++nextId}" },
            clock = Clock { ++currentTime },
        )
    }

    @After
    fun tearDown() {
        database.close()
    }

    @Test
    fun initializeCreatesOneSelectedDraftAndIsIdempotent() = runBlocking {
        repository.initialize()
        repository.initialize()

        val drafts = repository.drafts.first()
        assertEquals(1, drafts.size)
        assertEquals("Untitled 1", drafts.single().name)
        assertEquals(drafts.single().id, repository.workspace.first().selectedDraftId)
    }

    @Test
    fun initializeRepairsInvalidSelectionWithoutChangingDrafts() = runBlocking {
        val dao = database.draftDao()
        dao.insertDraft(draft(id = "first", name = "Project", order = 4))
        dao.insertDraft(draft(id = "second", name = "Other", order = 8))
        dao.upsertWorkspace(WorkspaceEntity(selectedDraftId = "missing"))

        repository.initialize()

        assertEquals(listOf("first", "second"), repository.drafts.first().map { it.id })
        assertEquals("first", repository.workspace.first().selectedDraftId)
    }

    @Test
    fun initializePreservesExistingValidSelection() = runBlocking {
        val dao = database.draftDao()
        dao.insertDraft(draft(id = "first", name = "Project", order = 4))
        dao.insertDraft(draft(id = "second", name = "Other", order = 8))
        dao.upsertWorkspace(WorkspaceEntity(selectedDraftId = "second"))

        repository.initialize()

        assertEquals(listOf("first", "second"), repository.drafts.first().map { it.id })
        assertEquals("second", repository.workspace.first().selectedDraftId)
    }

    @Test
    fun createDraftUsesLowestAvailableNameAppendsAndSelects() = runBlocking {
        repository.initialize()
        repository.createDraft()
        val secondId = repository.createDraft()
        database.draftDao().updateName("id-2", "Project", 2000)

        val reusedId = repository.createDraft()
        val drafts = repository.drafts.first()

        assertEquals(listOf("Untitled 1", "Project", "Untitled 3", "Untitled 2"), drafts.map { it.name })
        assertEquals(listOf(0L, 1L, 2L, 3L), drafts.map { it.displayOrder })
        assertEquals(reusedId, repository.workspace.first().selectedDraftId)
        assertNotEquals(secondId, reusedId)
    }

    @Test
    fun concurrentCreationProducesDistinctNamesIdsAndOrders() = runBlocking {
        repository.initialize()

        val ids = coroutineScope {
            List(3) { async { repository.createDraft() } }.awaitAll()
        }
        val drafts = repository.drafts.first()

        assertEquals(3, ids.distinct().size)
        assertEquals(listOf("Untitled 1", "Untitled 2", "Untitled 3", "Untitled 4"), drafts.map { it.name })
        assertEquals(listOf(0L, 1L, 2L, 3L), drafts.map { it.displayOrder })
    }

    @Test
    fun renameTrimsAllowsDuplicatesAndChangesOnlyNameAndUpdatedAt() = runBlocking {
        repository.initialize()
        val secondId = repository.createDraft()
        val before = repository.drafts.first().first { it.id == secondId }

        repository.renameDraft(secondId, "  Untitled 1  ")

        val after = repository.drafts.first().first { it.id == secondId }
        assertEquals("Untitled 1", after.name)
        assertEquals(before.id, after.id)
        assertEquals(before.content, after.content)
        assertEquals(before.displayOrder, after.displayOrder)
        assertEquals(before.createdAt, after.createdAt)
        assertNotEquals(before.updatedAt, after.updatedAt)
    }

    @Test
    fun renameRejectsBlankAndMissingDraftsWithoutChangingState() = runBlocking {
        repository.initialize()
        val before = repository.drafts.first()

        assertThrows(DraftRepositoryException.InvalidName::class.java) {
            runBlocking { repository.renameDraft(before.single().id, " \n\t ") }
        }
        assertThrows(DraftRepositoryException.DraftNotFound::class.java) {
            runBlocking { repository.renameDraft("missing", "Valid") }
        }

        assertEquals(before, repository.drafts.first())
    }

    @Test
    fun selectionRequiresExistingIdAndNeverChangesDraftData() = runBlocking {
        repository.initialize()
        val secondId = repository.createDraft()
        val before = repository.drafts.first()

        repository.selectDraft(before.first().id)

        assertEquals(before.first().id, repository.workspace.first().selectedDraftId)
        assertEquals(before, repository.drafts.first())
        assertThrows(DraftRepositoryException.DraftNotFound::class.java) {
            runBlocking { repository.selectDraft("missing") }
        }
        assertEquals(before.first().id, repository.workspace.first().selectedDraftId)
        assertNotEquals(secondId, repository.workspace.first().selectedDraftId)
    }

    @Test
    fun renamingAutomaticDraftFreesItsNumberForCreation() = runBlocking {
        repository.initialize()
        val secondId = repository.createDraft()

        repository.renameDraft(secondId, "Project")
        val replacementId = repository.createDraft()

        val replacement = repository.drafts.first().first { it.id == replacementId }
        assertEquals("Untitled 2", replacement.name)
    }

    @Test
    fun deletingUnselectedDraftPreservesSelectionAndSurvivorOrder() = runBlocking {
        repository.initialize()
        val secondId = repository.createDraft()
        val thirdId = repository.createDraft()
        repository.selectDraft(secondId)

        repository.deleteDraft(thirdId)

        assertEquals(secondId, repository.workspace.first().selectedDraftId)
        assertEquals(listOf("id-1", secondId), repository.drafts.first().map { it.id })
        assertEquals(listOf(0L, 1L), repository.drafts.first().map { it.displayOrder })
    }

    @Test
    fun deletingSelectedDraftChoosesRightThenLeftNeighbor() = runBlocking {
        repository.initialize()
        val secondId = repository.createDraft()
        val thirdId = repository.createDraft()
        repository.selectDraft(secondId)

        repository.deleteDraft(secondId)

        assertEquals(thirdId, repository.workspace.first().selectedDraftId)
        repository.deleteDraft(thirdId)
        assertEquals("id-1", repository.workspace.first().selectedDraftId)
    }

    @Test
    fun deletingOnlyDraftCreatesFreshSelectedUntitledOne() = runBlocking {
        repository.initialize()
        val originalId = repository.drafts.first().single().id

        repository.deleteDraft(originalId)

        val replacement = repository.drafts.first().single()
        assertNotEquals(originalId, replacement.id)
        assertEquals("Untitled 1", replacement.name)
        assertEquals(0L, replacement.displayOrder)
        assertEquals(replacement.id, repository.workspace.first().selectedDraftId)
    }

    @Test
    fun repeatedDeletionCannotDeleteAnotherDraft() = runBlocking {
        repository.initialize()
        val deletedId = repository.createDraft()
        repository.createDraft()
        repository.deleteDraft(deletedId)
        val survivors = repository.drafts.first()

        assertThrows(DraftRepositoryException.DraftNotFound::class.java) {
            runBlocking { repository.deleteDraft(deletedId) }
        }

        assertEquals(survivors, repository.drafts.first())
    }

    @Test
    fun deletionFreesAutomaticNameWithoutReorderingSurvivors() = runBlocking {
        repository.initialize()
        val secondId = repository.createDraft()
        val thirdId = repository.createDraft()

        repository.deleteDraft(secondId)
        val replacementId = repository.createDraft()

        val drafts = repository.drafts.first()
        assertEquals(listOf("id-1", thirdId, replacementId), drafts.map { it.id })
        assertEquals(listOf("Untitled 1", "Untitled 3", "Untitled 2"), drafts.map { it.name })
        assertEquals(listOf(0L, 2L, 3L), drafts.map { it.displayOrder })
    }

    @Test
    fun saveContentUpdatesOnlyTargetAndRejectsMissingId() = runBlocking {
        repository.initialize()
        val firstId = repository.drafts.first().single().id
        val secondId = repository.createDraft()
        val secondBefore = repository.drafts.first().first { it.id == secondId }

        repository.saveContent(firstId, "Saved text")

        val drafts = repository.drafts.first()
        assertEquals("Saved text", drafts.first { it.id == firstId }.content)
        assertEquals(secondBefore, drafts.first { it.id == secondId })
        assertThrows(DraftRepositoryException.DraftNotFound::class.java) {
            runBlocking { repository.saveContent("missing", "Text") }
        }
        Unit
    }

    private fun draft(id: String, name: String, order: Long) = DraftEntity(
        id = id,
        name = name,
        content = "",
        displayOrder = order,
        createdAt = 10,
        updatedAt = 10,
    )
}
