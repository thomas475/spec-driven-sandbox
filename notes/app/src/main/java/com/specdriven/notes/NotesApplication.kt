package com.specdriven.notes

import android.app.Application
import androidx.room.Room
import com.specdriven.notes.data.DraftRepository
import com.specdriven.notes.data.RoomDraftRepository
import com.specdriven.notes.data.document.AndroidDocumentGateway
import com.specdriven.notes.data.document.DocumentGateway
import com.specdriven.notes.data.local.NotesDatabase

class NotesApplication : Application() {
    lateinit var repository: DraftRepository
        private set
    lateinit var documentGateway: DocumentGateway
        private set

    override fun onCreate() {
        super.onCreate()
        val database = Room.databaseBuilder(
            applicationContext,
            NotesDatabase::class.java,
            "notes.db",
        ).build()
        repository = RoomDraftRepository(database)
        documentGateway = AndroidDocumentGateway(contentResolver)
    }
}
