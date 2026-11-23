package com.specdriven.notes.data.document

import java.io.ByteArrayOutputStream
import java.io.InputStream
import java.nio.ByteBuffer
import java.nio.charset.CodingErrorAction
import java.nio.charset.StandardCharsets

const val MAX_IMPORTED_TEXT_BYTES = 1_048_576

internal object TextDocumentCodec {
    private val utf8ByteOrderMark = byteArrayOf(0xEF.toByte(), 0xBB.toByte(), 0xBF.toByte())

    fun readUtf8(
        inputStream: InputStream,
        maximumBytes: Int = MAX_IMPORTED_TEXT_BYTES,
    ): String {
        val bytes = readBounded(inputStream, maximumBytes)
        val contentOffset = if (bytes.startsWith(utf8ByteOrderMark)) {
            utf8ByteOrderMark.size
        } else {
            0
        }
        return try {
            StandardCharsets.UTF_8
                .newDecoder()
                .onMalformedInput(CodingErrorAction.REPORT)
                .onUnmappableCharacter(CodingErrorAction.REPORT)
                .decode(ByteBuffer.wrap(bytes, contentOffset, bytes.size - contentOffset))
                .toString()
        } catch (exception: Exception) {
            throw InvalidTextEncodingException(exception)
        }
    }

    fun encodeUtf8(content: String): ByteArray = content.toByteArray(StandardCharsets.UTF_8)

    private fun readBounded(inputStream: InputStream, maximumBytes: Int): ByteArray {
        require(maximumBytes >= 0)
        val output = ByteArrayOutputStream(minOf(maximumBytes, DEFAULT_BUFFER_SIZE))
        val buffer = ByteArray(DEFAULT_BUFFER_SIZE)
        var totalBytes = 0
        while (true) {
            val bytesRead = inputStream.read(buffer)
            if (bytesRead < 0) {
                return output.toByteArray()
            }
            if (bytesRead == 0) {
                val nextByte = inputStream.read()
                if (nextByte < 0) {
                    return output.toByteArray()
                }
                totalBytes += 1
                if (totalBytes > maximumBytes) {
                    throw DocumentTooLargeException(maximumBytes)
                }
                output.write(nextByte)
                continue
            }
            totalBytes += bytesRead
            if (totalBytes > maximumBytes) {
                throw DocumentTooLargeException(maximumBytes)
            }
            output.write(buffer, 0, bytesRead)
        }
    }

    private fun ByteArray.startsWith(prefix: ByteArray): Boolean =
        size >= prefix.size && prefix.indices.all { index -> this[index] == prefix[index] }
}
