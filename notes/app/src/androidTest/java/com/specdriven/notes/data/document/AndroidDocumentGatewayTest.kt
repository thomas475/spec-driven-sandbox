package com.specdriven.notes.data.document

import android.net.Uri
import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import java.nio.charset.StandardCharsets
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertThrows
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class AndroidDocumentGatewayTest {
    private val context = ApplicationProvider.getApplicationContext<android.content.Context>()
    private val gateway = AndroidDocumentGateway(context.contentResolver)

    @Before
    fun setUp() {
        context.contentResolver.delete(uri("written"), null, null)
    }

    @Test
    fun readsDisplayNameAndExactUtf8Content() = runBlocking {
        val content = "First\r\nΚαλημέρα 👋  "

        val document = gateway.readText(
            reference("read/text?name=%20%20Example.TXT%20%20&value=${Uri.encode(content)}"),
        )

        assertEquals("  Example.TXT  ", document.displayName)
        assertEquals("First\r\nΚαλημέρα 👋  ", document.content)
    }

    @Test
    fun writesExactUtf8BytesWithoutByteOrderMark() = runBlocking {
        val content = "First\nΚαλημέρα 👋"

        gateway.writeText(reference("write"), content)

        assertArrayEquals(
            content.toByteArray(StandardCharsets.UTF_8),
            requireNotNull(context.contentResolver.openInputStream(uri("written"))).use {
                it.readBytes()
            },
        )
    }

    @Test
    fun mapsOpenFailuresByTransferDirection() {
        assertThrows(DocumentReadFailedException::class.java) {
            runBlocking { gateway.readText(reference("failure")) }
        }
        assertThrows(DocumentWriteFailedException::class.java) {
            runBlocking { gateway.writeText(reference("failure"), "Text") }
        }
    }

    @Test
    fun mapsInterruptedWriteFailure() {
        assertThrows(DocumentWriteFailedException::class.java) {
            runBlocking {
                gateway.writeText(reference("write/interrupted"), "Text that cannot be written")
            }
        }
    }

    @Test
    fun preservesEncodingAndSizeFailures() {
        assertThrows(InvalidTextEncodingException::class.java) {
            runBlocking { gateway.readText(reference("read/malformed")) }
        }

        assertThrows(DocumentTooLargeException::class.java) {
            runBlocking { gateway.readText(reference("read/oversize")) }
        }
    }

    private fun reference(path: String): DocumentReference =
        DocumentReference.fromUriString(uri(path).toString())

    private fun uri(path: String): Uri =
        Uri.parse("content://com.specdriven.notes.test.documents/$path")
}
