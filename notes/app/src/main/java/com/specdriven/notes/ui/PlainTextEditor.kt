package com.specdriven.notes.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.input.TextFieldValue
import androidx.compose.ui.unit.dp

@Composable
fun PlainTextEditor(
    draftId: String?,
    value: TextFieldValue,
    onValueChange: (String, TextFieldValue) -> Unit,
    modifier: Modifier = Modifier,
) {
    val colors = MaterialTheme.colorScheme
    BasicTextField(
        value = value,
        onValueChange = { changedValue ->
            draftId?.let { onValueChange(it, changedValue) }
        },
        modifier = modifier
            .fillMaxSize()
            .imePadding()
            .background(colors.background)
            .padding(16.dp)
            .semantics { contentDescription = "Draft editor" }
            .testTag("editor"),
        enabled = draftId != null,
        textStyle = TextStyle(
            color = colors.onBackground,
            fontFamily = FontFamily.Monospace,
            fontSize = MaterialTheme.typography.bodyLarge.fontSize,
            lineHeight = MaterialTheme.typography.bodyLarge.lineHeight,
        ),
        cursorBrush = SolidColor(colors.primary),
        singleLine = false,
        maxLines = Int.MAX_VALUE,
    )
}
