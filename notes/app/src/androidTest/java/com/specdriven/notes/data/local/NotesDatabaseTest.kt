package com.specdriven.notes.data.local

import android.content.Context
import android.database.sqlite.SQLiteConstraintException
import androidx.room.Room
import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import java.io.IOException
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertThrows
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class NotesDatabaseTest {
    private lateinit var database: NotesDatabase
    private lateinit var dao: DraftDao

    @Before
    fun createDatabase() {
        database = Room.inMemoryDatabaseBuilder(
            ApplicationProvider.getApplicationContext(),
            NotesDatabase::class.java,
        ).build()
        dao = database.draftDao()
    }

    @After
    @Throws(IOException::class)
    fun closeDatabase() {
        database.close()
    }

    @Test
    fun daoStoresOrdersUpdatesAndDeletesDrafts() = runBlocking {
        val later = draft(id = "later", name = "Same", order = 2)
        val earlier = draft(id = "earlier", name = "Same", order = 1)
        dao.insertDraft(later)
        dao.insertDraft(earlier)
        dao.upsertWorkspace(WorkspaceEntity(selectedDraftId = later.id))

        assertEquals(listOf("earlier", "later"), dao.observeDrafts().first().map { it.id })
        assertEquals(later.id, dao.observeWorkspace().first()?.selectedDraftId)

        dao.updateName(earlier.id, "Renamed", 20)
        dao.updateContent(earlier.id, "Text", 21)
        assertEquals("Renamed", dao.getDraft(earlier.id)?.name)
        assertEquals("Text", dao.getDraft(earlier.id)?.content)

        dao.deleteDraft(earlier.id)
        assertNull(dao.getDraft(earlier.id))
    }

    @Test
    fun duplicateDisplayOrderFails() {
        assertThrows(SQLiteConstraintException::class.java) {
            runBlocking {
                dao.insertDraft(draft(id = "first", name = "Same", order = 1))
                dao.insertDraft(draft(id = "second", name = "Same", order = 1))
            }
        }
    }

    @Test
    fun fileDatabaseRestoresAllFieldsAfterReopen() = runBlocking {
        val context = ApplicationProvider.getApplicationContext<Context>()
        val databaseName = "notes-reopen-test.db"
        context.deleteDatabase(databaseName)
        val expected = DraftEntity(
            id = "persistent",
            name = "Persistent draft",
            content = "Saved text",
            displayOrder = 7,
            createdAt = 100,
            updatedAt = 200,
        )

        val fileDatabase = Room.databaseBuilder(context, NotesDatabase::class.java, databaseName).build()
        try {
            fileDatabase.draftDao().insertDraft(expected)
            fileDatabase.draftDao().upsertWorkspace(WorkspaceEntity(selectedDraftId = expected.id))
        } finally {
            fileDatabase.close()
        }

        val reopened = Room.databaseBuilder(context, NotesDatabase::class.java, databaseName).build()
        try {
            assertEquals(expected, reopened.draftDao().getDraft(expected.id))
            assertEquals(expected.id, reopened.draftDao().getWorkspace()?.selectedDraftId)
        } finally {
            reopened.close()
        }
        context.deleteDatabase(databaseName)
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
