package com.specdriven.notes.data

import androidx.room.withTransaction
import com.specdriven.notes.data.local.DraftEntity
import com.specdriven.notes.data.local.NotesDatabase
import com.specdriven.notes.data.local.WorkspaceEntity
import com.specdriven.notes.domain.Draft
import com.specdriven.notes.domain.DraftName
import com.specdriven.notes.domain.Workspace
import java.util.UUID
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.filterNotNull
import kotlinx.coroutines.flow.map

fun interface IdGenerator {
    fun create(): String
}

fun interface Clock {
    fun currentTimeMillis(): Long
}

class RoomDraftRepository(
    private val database: NotesDatabase,
    private val idGenerator: IdGenerator = IdGenerator { UUID.randomUUID().toString() },
    private val clock: Clock = Clock { System.currentTimeMillis() },
) : DraftRepository {
    private val dao = database.draftDao()

    override val drafts: Flow<List<Draft>> = dao.observeDrafts().map { entities ->
        entities.map(DraftEntity::toDomain)
    }

    override val workspace: Flow<Workspace> = dao.observeWorkspace()
        .filterNotNull()
        .map { Workspace(selectedDraftId = it.selectedDraftId) }

    override suspend fun initialize() {
        database.withTransaction {
            val existingDrafts = dao.getDrafts()
            if (existingDrafts.isEmpty()) {
                val draft = newDraft(
                    name = "Untitled 1",
                    displayOrder = 0,
                )
                dao.insertDraft(draft)
                dao.upsertWorkspace(WorkspaceEntity(selectedDraftId = draft.id))
                return@withTransaction
            }

            val workspace = dao.getWorkspace()
            if (workspace == null || existingDrafts.none { it.id == workspace.selectedDraftId }) {
                dao.upsertWorkspace(WorkspaceEntity(selectedDraftId = existingDrafts.first().id))
            }
        }
    }

    override suspend fun createDraft(): String = database.withTransaction {
        val existingDrafts = dao.getDrafts()
        val draft = newDraft(
            name = DraftName.nextUntitled(existingDrafts.map { it.name }),
            displayOrder = (dao.getMaxDisplayOrder() ?: -1L) + 1L,
        )
        dao.insertDraft(draft)
        dao.upsertWorkspace(WorkspaceEntity(selectedDraftId = draft.id))
        draft.id
    }

    override suspend fun renameDraft(id: String, name: String) {
        val trimmedName = name.trim()
        if (trimmedName.isEmpty()) {
            throw DraftRepositoryException.InvalidName
        }
        val updatedRows = dao.updateName(
            id = id,
            name = trimmedName,
            updatedAt = clock.currentTimeMillis(),
        )
        if (updatedRows == 0) {
            throw DraftRepositoryException.DraftNotFound(id)
        }
    }

    override suspend fun selectDraft(id: String) {
        database.withTransaction {
            if (dao.getDraft(id) == null) {
                throw DraftRepositoryException.DraftNotFound(id)
            }
            dao.upsertWorkspace(WorkspaceEntity(selectedDraftId = id))
        }
    }

    override suspend fun saveContent(id: String, content: String) {
        val updatedRows = dao.updateContent(
            id = id,
            content = content,
            updatedAt = clock.currentTimeMillis(),
        )
        if (updatedRows == 0) {
            throw DraftRepositoryException.DraftNotFound(id)
        }
    }

    override suspend fun deleteDraft(id: String) {
        database.withTransaction {
            val drafts = dao.getDrafts()
            val targetIndex = drafts.indexOfFirst { it.id == id }
            if (targetIndex < 0) {
                throw DraftRepositoryException.DraftNotFound(id)
            }

            if (drafts.size == 1) {
                dao.deleteDraft(id)
                val replacement = newDraft(
                    name = "Untitled 1",
                    displayOrder = 0,
                )
                dao.insertDraft(replacement)
                dao.upsertWorkspace(WorkspaceEntity(selectedDraftId = replacement.id))
                return@withTransaction
            }

            val workspace = dao.getWorkspace()
            dao.deleteDraft(id)
            val remainingDrafts = drafts.filterNot { it.id == id }
            val currentSelectedId = workspace?.selectedDraftId
            val selectedDraftId = when {
                currentSelectedId != null && currentSelectedId != id &&
                    remainingDrafts.any { it.id == currentSelectedId } -> currentSelectedId
                targetIndex < drafts.lastIndex -> drafts[targetIndex + 1].id
                else -> drafts[targetIndex - 1].id
            }
            dao.upsertWorkspace(WorkspaceEntity(selectedDraftId = selectedDraftId))
        }
    }

    private fun newDraft(name: String, displayOrder: Long): DraftEntity {
        val now = clock.currentTimeMillis()
        return DraftEntity(
            id = idGenerator.create(),
            name = name,
            content = "",
            displayOrder = displayOrder,
            createdAt = now,
            updatedAt = now,
        )
    }
}

private fun DraftEntity.toDomain() = Draft(
    id = id,
    name = name,
    content = content,
    displayOrder = displayOrder,
    createdAt = createdAt,
    updatedAt = updatedAt,
)
