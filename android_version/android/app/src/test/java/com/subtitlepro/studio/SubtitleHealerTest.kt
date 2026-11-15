package com.subtitlepro.studio

import com.subtitlepro.studio.engine.healer.SubtitleHealer
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class SubtitleHealerTest {

    @Test
    fun testProtectAndRestoreAssTags() {
        val original = "{\\an8\\pos(192,20)}مرحبا بك{\\i1}يا بطل{\\i0}"
        val (protected, tags) = SubtitleHealer.protectAssTags(original)
        assertTrue(protected.contains("___ASS_TAG_"))
        assertEquals(3, tags.size)

        val restored = SubtitleHealer.restoreAssTags(protected, tags)
        assertEquals(original, restored)
    }

    @Test
    fun testArabicPunctuationNormalization() {
        val input = "هل أنت قادم, يا صديقي? نعم; بالتأكيد!!!"
        val healed = SubtitleHealer.normalizeArabicPunctuation(input)
        assertEquals("هل أنت قادم، يا صديقي؟ نعم؛ بالتأكيد!!", healed)
    }

    @Test
    fun testCleanLlmPrefixes() {
        val input = "المترجم: مرحبا بك يا صديقي"
        val cleaned = SubtitleHealer.cleanLlmPrefixes(input)
        assertEquals("مرحبا بك يا صديقي", cleaned)
    }

    @Test
    fun testCleanSdhAudioDescriptions() {
        val input = "(sigh) مرحبا بك يا صديقي [music]"
        val cleaned = SubtitleHealer.cleanSdhAndSoundEffects(input)
        assertEquals("مرحبا بك يا صديقي", cleaned)
    }

    @Test
    fun testFullHealPipeline() {
        val rawTranslation = "المترجم: {\\pos(120,450)\\an8}أهلاً بك, هل أنت بخير? (sigh) \\Nyeah"
        val originalText = "{\\pos(120,450)\\an8}Hello, are you okay?\\Nyeah"
        val result = SubtitleHealer.heal(rawTranslation, originalText)
        assertTrue(result.contains("{\\pos(120,450)\\an8}"))
        assertTrue(result.contains("،"))
        assertTrue(result.contains("؟"))
        assertTrue(!result.contains("المترجم:"))
        assertTrue(!result.contains("(sigh)"))
    }
}
