package com.specdriven.notes.data.local

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import androidx.room.Upsert
import kotlinx.coroutines.flow.Flow

@Dao
interface DraftDao {
    @Query("SELECT * FROM drafts ORDER BY display_order ASC")
    fun observeDrafts(): Flow<List<DraftEntity>>

    @Query("SELECT * FROM workspace WHERE id = 1")
    fun observeWorkspace(): Flow<WorkspaceEntity?>

    @Query("SELECT * FROM drafts ORDER BY display_order ASC")
    suspend fun getDrafts(): List<DraftEntity>

    @Query("SELECT * FROM drafts WHERE id = :id")
    suspend fun getDraft(id: String): DraftEntity?

    @Query("SELECT * FROM workspace WHERE id = 1")
    suspend fun getWorkspace(): WorkspaceEntity?

    @Query("SELECT MAX(display_order) FROM drafts")
    suspend fun getMaxDisplayOrder(): Long?

    @Insert(onConflict = OnConflictStrategy.ABORT)
    suspend fun insertDraft(draft: DraftEntity)

    @Upsert
    suspend fun upsertWorkspace(workspace: WorkspaceEntity)

    @Query("UPDATE drafts SET name = :name, updated_at = :updatedAt WHERE id = :id")
    suspend fun updateName(id: String, name: String, updatedAt: Long): Int

    @Query("UPDATE drafts SET content = :content, updated_at = :updatedAt WHERE id = :id")
    suspend fun updateContent(id: String, content: String, updatedAt: Long): Int

    @Query("DELETE FROM drafts WHERE id = :id")
    suspend fun deleteDraft(id: String): Int
}

