package com.specdriven.notes

import androidx.compose.ui.graphics.luminance
import androidx.compose.ui.graphics.toPixelMap
import androidx.compose.ui.test.captureToImage
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.compose.ui.test.onNodeWithTag
import androidx.test.ext.junit.runners.AndroidJUnit4
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class MainActivityTest {
    @get:Rule
    val composeRule = createAndroidComposeRule<MainActivity>()

    @Test
    fun appShellLaunches() {
        composeRule.onNodeWithTag("notes-root").assertExists()
    }

    @Test
    fun themeIsDark() {
        val pixels = composeRule.onNodeWithTag("notes-root")
            .captureToImage()
            .toPixelMap()

        assertTrue(pixels[0, 0].luminance() < 0.5f)
    }
}
