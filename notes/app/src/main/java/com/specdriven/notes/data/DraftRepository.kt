package com.specdriven.notes.data

import com.specdriven.notes.domain.Draft
import com.specdriven.notes.domain.Workspace
import kotlinx.coroutines.flow.Flow

interface DraftRepository {
    val drafts: Flow<List<Draft>>
    val workspace: Flow<Workspace>

    suspend fun initialize()
    suspend fun createDraft(): String
    suspend fun renameDraft(id: String, name: String)
    suspend fun selectDraft(id: String)
    suspend fun saveContent(id: String, content: String)
    suspend fun deleteDraft(id: String)
}

