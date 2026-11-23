package com.specdriven.notes.data.document

import java.io.ByteArrayInputStream
import java.nio.charset.StandardCharsets
import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertThrows
import org.junit.Test

class TextDocumentCodecTest {
    @Test
    fun readsEmptyAsciiUnicodeLineEndingsAndTrailingWhitespaceExactly() {
        val values = listOf(
            "",
            "Plain text",
            "Καλημέρα 👋",
            "first\nsecond\n",
            "first\r\nsecond\r\n",
            "trailing spaces   \n\t",
        )

        values.forEach { value ->
            assertEquals(
                value,
                TextDocumentCodec.readUtf8(ByteArrayInputStream(value.toByteArray())),
            )
        }
    }

    @Test
    fun removesOnlyOneLeadingUtf8ByteOrderMark() {
        val byteOrderMark = byteArrayOf(0xEF.toByte(), 0xBB.toByte(), 0xBF.toByte())
        val input = byteOrderMark + byteOrderMark + "Text".toByteArray()

        assertEquals("\uFEFFText", TextDocumentCodec.readUtf8(ByteArrayInputStream(input)))
    }

    @Test
    fun acceptsExactLimitAndRejectsFirstByteBeyondIt() {
        val exactLimit = ByteArray(MAX_IMPORTED_TEXT_BYTES) { 'a'.code.toByte() }
        val overLimit = exactLimit + 'b'.code.toByte()

        assertEquals(
            MAX_IMPORTED_TEXT_BYTES,
            TextDocumentCodec.readUtf8(ByteArrayInputStream(exactLimit)).length,
        )
        assertThrows(DocumentTooLargeException::class.java) {
            TextDocumentCodec.readUtf8(ByteArrayInputStream(overLimit))
        }
    }

    @Test
    fun rejectsMalformedUtf8WithoutReplacementCharacters() {
        val malformed = byteArrayOf(0xC3.toByte(), 0x28)

        assertThrows(InvalidTextEncodingException::class.java) {
            TextDocumentCodec.readUtf8(ByteArrayInputStream(malformed))
        }
    }

    @Test
    fun encodesUtf8WithoutByteOrderMark() {
        val content = "First\nΚαλημέρα 👋"

        assertArrayEquals(
            content.toByteArray(StandardCharsets.UTF_8),
            TextDocumentCodec.encodeUtf8(content),
        )
    }
}
