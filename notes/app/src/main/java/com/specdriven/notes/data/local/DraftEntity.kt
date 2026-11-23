package com.specdriven.notes.data.local

import androidx.room.ColumnInfo
import androidx.room.Entity
import androidx.room.Index
import androidx.room.PrimaryKey

@Entity(
    tableName = "drafts",
    indices = [Index(value = ["display_order"], unique = true)],
)
data class DraftEntity(
    @PrimaryKey val id: String,
    val name: String,
    val content: String,
    @ColumnInfo(name = "display_order") val displayOrder: Long,
    @ColumnInfo(name = "created_at") val createdAt: Long,
    @ColumnInfo(name = "updated_at") val updatedAt: Long,
)

