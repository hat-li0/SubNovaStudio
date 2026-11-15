package com.subtitlepro.studio.engine.healer

import java.util.regex.Pattern

object SubtitleHealer {

    private val PREFIX_REGEX = Pattern.compile(
        """^(?:(?:Original|Current Arabic|Improved Arabic|Improved|Corrected|Arabic|Revision|Refined|Result|Translation|Translated|Translated text|Target|Draft|Translator|المنظر العربي المترجم|المنظر العربي|المترجم|المترجمة|المدقق|المراجع|تقرير التعديلات|تقرير التحسين|تقرير المراجعة|التعديلات|التصحيحات|التصحيح|النص العربي المصقول النهائي مباشرة|النص العربي المصقول النهائي|النص المصقول النهائي|المصقول النهائي مباشرة|المصقول النهائي|النص المصقول|السطر المصقول|الترجمة المحسنة|الترجمة المقترحة|الترجمة النهائية|الترجمة العربية|الترجمة|المسودة|النتيجة|المصححة|الصياغة الجديدة|الصياغة الفصيحة|الأصل|النص الأصلي|النص العربي|التحسين|التعديل|ترجمة|إليك الترجمة|الترجمة هي|نص الترجمة)[\s:\-–—]*)+""",
        Pattern.CASE_INSENSITIVE
    )

    fun protectAssTags(text: String): Pair<String, List<String>> {
        if (text.isBlank()) return Pair(text, emptyList())
        val assTags = mutableListOf<String>()

        // 1. Vector drawing blocks {\p1}...{\p0}
        var protected = text.replace(Regex("""\{\\p[1-9]}[^\\{]*\{\\p0}""")) { m ->
            assTags.add(m.value)
            "___ASS_DRAWING_${assTags.size - 1}___"
        }

        // 2. Override tags {\...}
        protected = protected.replace(Regex("""\{\\[^}]*}""")) { m ->
            assTags.add(m.value)
            "___ASS_TAG_${assTags.size - 1}___"
        }

        return Pair(protected, assTags)
    }

    fun restoreAssTags(text: String, tags: List<String>): String {
        if (text.isBlank() || tags.isEmpty()) return text
        var restored = text
        for (i in tags.indices) {
            val tag = tags[i]
            val tagToken = "___ASS_TAG_${i}___"
            val drawToken = "___ASS_DRAWING_${i}___"
            restored = when {
                restored.contains(tagToken) -> restored.replace(tagToken, tag)
                restored.contains(drawToken) -> restored.replace(drawToken, tag)
                else -> {
                    if (!tag.contains("""\p[1-9]""".toRegex())) {
                        tag + restored
                    } else restored
                }
            }
        }

        // Deduplicate adjacent identical tags: {\an8}{\an8} -> {\an8}
        restored = restored.replace(Regex("""(\{\\[^}]+})\1+"""), "$1")
        return restored
    }

    fun cleanInvisibleAndUnicodeArtifacts(text: String): String {
        if (text.isBlank()) return ""
        // Zero-width characters & directional marks
        var cleaned = text.replace(Regex("""[\u200b\u200c\u200d\u200e\u200f\ufeff\u202a-\u202e\u2066-\u2069]"""), "")
        // Non-breaking space
        cleaned = cleaned.replace('\u00a0', ' ')
        // Convert CRLF to ASS linebreaks \N
        cleaned = cleaned.replace("\r\n", "\\N").replace("\r", "\\N")
        return cleaned
    }

    fun cleanMarkdownAndHtml(text: String): String {
        if (text.isBlank()) return ""
        var cleaned = text
        cleaned = cleaned.replace(Regex("""<br\s*/?>""", RegexOption.IGNORE_CASE), "\\N")
        // Strip think tags
        cleaned = cleaned.replace(Regex("""<think>[\s\S]*?</think>""", RegexOption.IGNORE_CASE), "")
        cleaned = cleaned.replace(Regex("""<think>[\s\S]*$""", RegexOption.IGNORE_CASE), "")
        // Convert basic italics / bold
        cleaned = cleaned.replace(Regex("""<i>(.*?)</i>""", RegexOption.IGNORE_CASE), "{\\i1}$1{\\i0}")
        cleaned = cleaned.replace(Regex("""<b>(.*?)</b>""", RegexOption.IGNORE_CASE), "{\\b1}$1{\\b0}")
        // Strip other HTML
        cleaned = cleaned.replace(Regex("""<[^>]+>"""), "")
        // Strip code fences
        cleaned = cleaned.replace(Regex("""```[\s\S]*?```"""), "")
        cleaned = cleaned.replace("`", "")
        // Strip markdown bold/italic
        cleaned = cleaned.replace(Regex("""\*\*([^*]+)\*\*"""), "$1")
        cleaned = cleaned.replace(Regex("""\*([^*]+)\*"""), "$1")
        cleaned = cleaned.replace(Regex("""__([^_]+)__"""), "$1")
        return cleaned
    }

    fun cleanLlmPrefixes(text: String): String {
        if (text.isBlank()) return ""
        var cleaned = text.trim()
        // Strip pipes if prompt echo leaked
        if (cleaned.contains("|")) {
            val parts = cleaned.split("|")
            cleaned = parts.last().trim()
        }
        for (i in 0 until 3) {
            val prev = cleaned
            cleaned = PREFIX_REGEX.matcher(cleaned).replaceAll("").trim()
            cleaned = cleaned.replace(Regex("""^[\*:\s\-–—\.]+"""), "").trim()
            if (cleaned == prev) break
        }
        // Remove leading numbering [1] or 1.
        cleaned = cleaned.replace(Regex("""^\[?\d+]?[\s:\-–—\.]+"""), "").trim()
        return cleaned
    }

    fun cleanSdhAndSoundEffects(text: String): String {
        if (text.isBlank()) return ""
        var cleaned = text
        cleaned = cleaned.replace(Regex("""\([a-zA-Z\s,]{2,}\)"""), "")
        cleaned = cleaned.replace(Regex("""\[[a-zA-Z\s,]{2,}]"""), "")
        cleaned = cleaned.replace(Regex("""\{[a-zA-Z\s,]{2,}}"""), "")
        return cleaned.trim()
    }

    fun cleanStrayLatinLetters(text: String): String {
        if (text.isBlank()) return ""
        var cleaned = text
        // Stray English syllables right after linebreaks: \NI, \Na, \Nyeah, \Noh
        cleaned = cleaned.replace(Regex("""\\N\s*(?:I|a|yeah|oh|you|the|it|is|and)\b""", RegexOption.IGNORE_CASE), "\\N")
        // Stray single Latin letters at start or end of lines
        cleaned = cleaned.replace(Regex("""^\s*[a-zA-Z]\s+"""), "")
        cleaned = cleaned.replace(Regex("""\s+[a-zA-Z]\s*$"""), "")
        return cleaned.trim()
    }

    fun normalizeAssLinebreaks(text: String): String {
        if (text.isBlank()) return ""
        var cleaned = text.replace("\\n", "\\N")
        cleaned = cleaned.replace(Regex("""(?:\s*\\N\s*){2,}"""), "\\N")
        cleaned = cleaned.replace(Regex("""^\\N\s*"""), "")
        cleaned = cleaned.replace(Regex("""\s*\\N$"""), "")
        return cleaned.trim()
    }

    fun normalizeArabicPunctuation(text: String): String {
        if (text.isBlank()) return ""
        var cleaned = text
        // Only convert punctuation to Arabic standard when adjacent to Arabic text
        cleaned = cleaned.replace(Regex("""([ء-ي])\s*,\s*"""), "$1، ")
        cleaned = cleaned.replace(Regex("""\s*,\s*([ء-ي])"""), "، $1")

        cleaned = cleaned.replace(Regex("""([ء-ي])\s*\?"""), "$1؟")
        cleaned = cleaned.replace(Regex("""\?\s*([ء-ي])"""), "؟ $1")

        cleaned = cleaned.replace(Regex("""([ء-ي])\s*;\s*"""), "$1؛ ")
        cleaned = cleaned.replace(Regex("""\s*;\s*([ء-ي])"""), "؛ $1")

        // Interrobang normalization
        cleaned = cleaned.replace(Regex("""[\?؟]+!+|!+[\?؟]+"""), "؟!")

        // Deduplicate repeated punctuation
        cleaned = cleaned.replace(Regex("""،\s*،+"""), "،")
        cleaned = cleaned.replace(Regex("""؟\s*؟+"""), "؟")
        cleaned = cleaned.replace(Regex("""!{3,}"""), "!!")

        // Space normalization around punctuation: no space before
        cleaned = cleaned.replace(Regex("""\s+([،؟؛!])"""), "$1")
        return cleaned
    }

    fun purgeCorruptTags(text: String): String {
        if (text.isBlank()) return ""
        var res = text
        res = res.replace(Regex("""\{\\i[01]}\s*\{\\i[01]}"""), "")
        res = res.replace(Regex("""\{\\b[01]}\s*\{\\b[01]}"""), "")
        res = res.replace(Regex("""\{\\u[01]}\s*\{\\u[01]}"""), "")
        res = res.replace(Regex("""\{\s*\\?[01]?\s*}"""), "")
        res = res.replace(Regex("""^(\{\\i[01]})(\{\\an\d+})"""), "$2$1")
        return res
    }

    fun fixOrphanQuotes(text: String): String {
        if (text.isBlank()) return ""
        var cleaned = text
        // If single unpaired quotation mark exists at ends, strip it
        for (q in listOf("\"", "'", "“", "”", "«", "»")) {
            val count = cleaned.count { it.toString() == q }
            if (count % 2 != 0) {
                if (cleaned.startsWith(q)) cleaned = cleaned.removePrefix(q).trim()
                else if (cleaned.endsWith(q)) cleaned = cleaned.removeSuffix(q).trim()
            }
        }
        return cleaned
    }

    fun normalizeDialogueDashes(text: String): String {
        if (text.isBlank()) return ""
        var cleaned = text
        cleaned = cleaned.replace(Regex("""(?m)^[–—]\s*"""), "- ")
        cleaned = cleaned.replace(Regex("""\\N[–—]\s*"""), "\\N- ")
        return cleaned
    }

    fun heal(
        text: String,
        originalText: String = "",
        enableArabicPunct: Boolean = true,
        enableLatinClean: Boolean = true,
        enableQuoteFix: Boolean = true,
        protectTags: Boolean = true
    ): String {
        if (text.isBlank()) return text

        var (processed, tags) = if (protectTags) {
            protectAssTags(text)
        } else {
            Pair(text, emptyList())
        }

        val (_, origTags) = if (originalText.isNotBlank() && protectTags) {
            protectAssTags(originalText)
        } else {
            Pair("", emptyList())
        }

        processed = cleanInvisibleAndUnicodeArtifacts(processed)
        processed = cleanMarkdownAndHtml(processed)
        processed = cleanLlmPrefixes(processed)
        processed = cleanSdhAndSoundEffects(processed)

        if (enableLatinClean) {
            processed = cleanStrayLatinLetters(processed)
        }

        if (enableArabicPunct) {
            processed = normalizeArabicPunctuation(processed)
        }

        if (enableQuoteFix) {
            processed = fixOrphanQuotes(processed)
        }

        processed = normalizeDialogueDashes(processed)
        processed = normalizeAssLinebreaks(processed)

        // Restore protected ASS tags
        var healed = if (protectTags && tags.isNotEmpty()) {
            restoreAssTags(processed, tags)
        } else {
            processed
        }

        // Smart recovery of missing formatting tags from originalText
        if (origTags.isNotEmpty() && protectTags) {
            val origHasI1 = origTags.any { it.contains("\\i1") }
            val origHasI0 = origTags.any { it.contains("\\i0") }
            if (origHasI1 && !healed.contains("\\i1")) {
                healed = "{\\i1}$healed{\\i0}"
            } else if (origHasI0 && !healed.contains("\\i0")) {
                healed = "$healed{\\i0}"
            }

            // Restore missing positioning tags
            val posTags = origTags.filter { it.contains(Regex("""\\(an\d+|pos|move|fad|fade|org|clip)""")) }
            for (pt in posTags.reversed()) {
                if (!healed.contains(pt)) {
                    healed = pt + healed
                }
            }
        }

        healed = purgeCorruptTags(healed)
        return healed.trim()
    }
}
