package com.specdriven.notes.data.local

import androidx.room.Database
import androidx.room.RoomDatabase

@Database(
    entities = [DraftEntity::class, WorkspaceEntity::class],
    version = 1,
    exportSchema = true,
)
abstract class NotesDatabase : RoomDatabase() {
    abstract fun draftDao(): DraftDao
}

