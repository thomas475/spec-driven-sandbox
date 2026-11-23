package com.specdriven.notes.domain

data class Draft(
    val id: String,
    val name: String,
    val content: String,
    val displayOrder: Long,
    val createdAt: Long,
    val updatedAt: Long,
)

