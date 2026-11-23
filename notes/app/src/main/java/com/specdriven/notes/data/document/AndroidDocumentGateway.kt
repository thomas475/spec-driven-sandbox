package com.specdriven.notes.data.document

import android.content.ContentResolver
import android.net.Uri
import android.provider.OpenableColumns
import java.io.IOException
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineDispatcher
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

class AndroidDocumentGateway(
    private val contentResolver: ContentResolver,
    private val ioDispatcher: CoroutineDispatcher = Dispatchers.IO,
) : DocumentGateway {
    override suspend fun readText(document: DocumentReference): ImportedTextDocument =
        withContext(ioDispatcher) {
            val uri = Uri.parse(document.uriString)
            try {
                val content = contentResolver.openInputStream(uri)?.use(TextDocumentCodec::readUtf8)
                    ?: throw IOException("Content resolver returned no input stream")
                ImportedTextDocument(
                    displayName = queryDisplayName(uri),
                    content = content,
                )
            } catch (exception: CancellationException) {
                throw exception
            } catch (exception: InvalidTextEncodingException) {
                throw exception
            } catch (exception: DocumentTooLargeException) {
                throw exception
            } catch (exception: Exception) {
                throw DocumentReadFailedException(exception)
            }
        }

    override suspend fun writeText(document: DocumentReference, content: String) {
        withContext(ioDispatcher) {
            val uri = Uri.parse(document.uriString)
            try {
                val outputStream = contentResolver.openOutputStream(uri, WRITE_TRUNCATE_MODE)
                    ?: throw IOException("Content resolver returned no output stream")
                outputStream.use { stream ->
                    stream.write(TextDocumentCodec.encodeUtf8(content))
                    stream.flush()
                }
            } catch (exception: CancellationException) {
                throw exception
            } catch (exception: Exception) {
                throw DocumentWriteFailedException(exception)
            }
        }
    }

    private fun queryDisplayName(uri: Uri): String? = try {
        contentResolver.query(
            uri,
            arrayOf(OpenableColumns.DISPLAY_NAME),
            null,
            null,
            null,
        )?.use { cursor ->
            val nameColumn = cursor.getColumnIndex(OpenableColumns.DISPLAY_NAME)
            if (nameColumn >= 0 && cursor.moveToFirst() && !cursor.isNull(nameColumn)) {
                cursor.getString(nameColumn)
            } else {
                null
            }
        }
    } catch (_: Exception) {
        null
    }

    private companion object {
        const val WRITE_TRUNCATE_MODE = "wt"
    }
}
