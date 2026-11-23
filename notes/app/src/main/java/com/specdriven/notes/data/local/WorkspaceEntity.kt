package com.specdriven.notes.data.local

import androidx.room.ColumnInfo
import androidx.room.Entity
import androidx.room.PrimaryKey

@Entity(tableName = "workspace")
data class WorkspaceEntity(
    @PrimaryKey val id: Int = SINGLETON_ID,
    @ColumnInfo(name = "selected_draft_id") val selectedDraftId: String,
) {
    companion object {
        const val SINGLETON_ID = 1
    }
}

