package com.specdriven.notes.data.document

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class TextDocumentNameTest {
    @Test
    fun importedNameRemovesOneFinalSuffixAndTrimsWhitespace() {
        assertEquals("Notes", TextDocumentName.importedDraftName("  Notes.txt  "))
        assertEquals("Notes", TextDocumentName.importedDraftName("Notes.TXT"))
        assertEquals("Notes.txt", TextDocumentName.importedDraftName("Notes.txt.txt"))
        assertEquals("archive.md", TextDocumentName.importedDraftName("archive.md"))
    }

    @Test
    fun importedNameReturnsNullForMissingOrEmptyStem() {
        assertNull(TextDocumentName.importedDraftName(null))
        assertNull(TextDocumentName.importedDraftName(" \n "))
        assertNull(TextDocumentName.importedDraftName(" .txt "))
    }

    @Test
    fun exportNameAddsAtMostOneSuffixWithoutChangingDraftName() {
        assertEquals("Notes.txt", TextDocumentName.suggestedExportName("Notes"))
        assertEquals("Notes.txt", TextDocumentName.suggestedExportName("Notes.txt"))
        assertEquals("Notes.TXT", TextDocumentName.suggestedExportName("Notes.TXT"))
        assertEquals("Untitled.txt", TextDocumentName.suggestedExportName("  "))
    }
}
