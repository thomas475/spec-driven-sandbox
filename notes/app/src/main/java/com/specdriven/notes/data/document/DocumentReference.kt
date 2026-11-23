package com.specdriven.notes.data.document

class DocumentReference private constructor(
    internal val uriString: String,
) {
    override fun equals(other: Any?): Boolean =
        other is DocumentReference && uriString == other.uriString

    override fun hashCode(): Int = uriString.hashCode()

    override fun toString(): String = "DocumentReference(redacted)"

    companion object {
        fun fromUriString(uriString: String): DocumentReference {
            require(uriString.isNotBlank())
            return DocumentReference(uriString)
        }
    }
}
