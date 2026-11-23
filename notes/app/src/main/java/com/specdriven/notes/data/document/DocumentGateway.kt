package com.specdriven.notes.data.document

interface DocumentGateway {
    suspend fun readText(document: DocumentReference): ImportedTextDocument

    suspend fun writeText(document: DocumentReference, content: String)
}
