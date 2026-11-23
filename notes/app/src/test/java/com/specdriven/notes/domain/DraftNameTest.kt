package com.specdriven.notes.domain

import org.junit.Assert.assertEquals
import org.junit.Test

class DraftNameTest {
    @Test
    fun emptyNamesStartAtOne() {
        assertEquals("Untitled 1", DraftName.nextUntitled(emptyList()))
    }

    @Test
    fun lowestAvailablePositiveNumberIsReused() {
        val names = listOf("Untitled 1", "Untitled 3", "Project")

        assertEquals("Untitled 2", DraftName.nextUntitled(names))
    }

    @Test
    fun duplicateAndNonCanonicalNamesDoNotBreakNaming() {
        val names = listOf("Untitled 1", "Untitled 1", "Untitled 01", "untitled 2")

        assertEquals("Untitled 2", DraftName.nextUntitled(names))
    }
}

