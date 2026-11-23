package com.specdriven.notes.domain

object DraftName {
    private val untitledPattern = Regex("^Untitled ([1-9]\\d*)$")

    fun nextUntitled(existingNames: Collection<String>): String {
        val occupiedNumbers = existingNames.mapNotNull { name ->
            untitledPattern.matchEntire(name)?.groupValues?.get(1)?.toIntOrNull()
        }.toSet()
        val availableNumber = generateSequence(1) { it + 1 }
            .first { it !in occupiedNumbers }
        return "Untitled $availableNumber"
    }
}

