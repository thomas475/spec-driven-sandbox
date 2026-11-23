package com.specdriven.notes.data.document

internal object TextDocumentName {
    fun importedDraftName(displayName: String?): String? {
        val trimmedName = displayName?.trim().orEmpty()
        val withoutSuffix = if (trimmedName.endsWith(TEXT_SUFFIX, ignoreCase = true)) {
            trimmedName.dropLast(TEXT_SUFFIX.length).trim()
        } else {
            trimmedName
        }
        return withoutSuffix.takeIf(String::isNotEmpty)
    }

    fun suggestedExportName(draftName: String): String {
        val trimmedName = draftName.trim().ifEmpty { DEFAULT_FILE_NAME }
        return if (trimmedName.endsWith(TEXT_SUFFIX, ignoreCase = true)) {
            trimmedName
        } else {
            "$trimmedName$TEXT_SUFFIX"
        }
    }

    private const val TEXT_SUFFIX = ".txt"
    private const val DEFAULT_FILE_NAME = "Untitled"
}
