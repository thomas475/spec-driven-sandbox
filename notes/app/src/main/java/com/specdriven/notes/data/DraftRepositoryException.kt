package com.specdriven.notes.data

sealed class DraftRepositoryException(message: String) : Exception(message) {
    data object InvalidName : DraftRepositoryException("Draft name must not be blank")

    data class DraftNotFound(val draftId: String) :
        DraftRepositoryException("Draft not found: $draftId")
}

