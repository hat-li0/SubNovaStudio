package com.subtitlepro.studio.engine.translation

import com.subtitlepro.studio.engine.healer.SubtitleHealer
import java.util.regex.Pattern

object ResponseParser {

    private val ID_LINE_PATTERN = Pattern.compile("""^\[?(\d+)]?[\s:\-–—\.]+(.*)$""")

    fun parse(rawResponse: String, expectedIds: List<Int>): Map<Int, String> {
        val result = mutableMapOf<Int, String>()
        val lines = rawResponse.lines()

        for (rawLine in lines) {
            val line = rawLine.trim()
            if (line.isBlank() || line.startsWith("#") || line.startsWith("```")) continue

            val matcher = ID_LINE_PATTERN.matcher(line)
            if (matcher.find()) {
                val idStr = matcher.group(1) ?: continue
                val text = matcher.group(2) ?: ""
                val id = idStr.toIntOrNull()
                if (id != null && (expectedIds.isEmpty() || expectedIds.contains(id))) {
                    result[id] = SubtitleHealer.cleanLlmPrefixes(text)
                }
            }
        }

        // Fallback: If no IDs were detected but line counts match expectedIds
        if (result.isEmpty() && expectedIds.isNotEmpty()) {
            val cleanLines = lines.map { it.trim() }.filter { it.isNotBlank() && !it.startsWith("```") && !it.startsWith("#") }
            if (cleanLines.size == expectedIds.size) {
                for (i in expectedIds.indices) {
                    result[expectedIds[i]] = SubtitleHealer.cleanLlmPrefixes(cleanLines[i])
                }
            }
        }

        return result
    }
}
