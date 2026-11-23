package com.specdriven.notes.data.document

sealed class DocumentTransferException(
    message: String,
    cause: Throwable? = null,
) : Exception(message, cause)

class DocumentReadFailedException(cause: Throwable) :
    DocumentTransferException("Text document could not be read", cause)

class InvalidTextEncodingException(cause: Throwable) :
    DocumentTransferException("Text document is not valid UTF-8", cause)

class DocumentTooLargeException(
    val maximumBytes: Int,
) : DocumentTransferException("Text document exceeds $maximumBytes bytes")

class DocumentWriteFailedException(cause: Throwable) :
    DocumentTransferException("Text document could not be written", cause)
