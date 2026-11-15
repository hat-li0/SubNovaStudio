package com.subtitlepro.studio.data.parser

import com.subtitlepro.studio.data.model.SubtitleDocument
import com.subtitlepro.studio.data.model.SubtitleEvent
import com.subtitlepro.studio.data.model.SubtitleFormat

object VttParserWriter {

    fun parse(content: String): SubtitleDocument {
        val doc = SubtitleDocument(format = SubtitleFormat.VTT)
        val normalized = content.replace("\r\n", "\n").replace("\r", "\n")
        val blocks = normalized.split("\n\n")
        var eventId = 1

        for (rawBlock in blocks) {
            val lines = rawBlock.lines().map { it.trim() }.filter { it.isNotEmpty() }
            if (lines.isEmpty()) continue
            if (lines[0].startsWith("WEBVTT", ignoreCase = true)) continue

            var timeIndex = 0
            if (!lines[0].contains("-->") && lines.size > 1 && lines[1].contains("-->")) {
                timeIndex = 1
            }

            if (timeIndex >= lines.size) continue
            val timeLine = lines[timeIndex]
            if (!timeLine.contains("-->")) continue

            val timeParts = timeLine.split("-->")
            val start = timeParts[0].trim().substringBefore(" ")
            val end = timeParts[1].trim().substringBefore(" ")
            val textLines = lines.subList(timeIndex + 1, lines.size)
            val text = textLines.joinToString("\\N")

            val event = SubtitleEvent(
                id = eventId++,
                start = start,
                end = end,
                originalText = text,
                text = text,
                formatType = SubtitleFormat.VTT
            )
            doc.events.add(event)
        }

        return doc
    }

    fun write(doc: SubtitleDocument): String {
        val sb = StringBuilder()
        sb.append("WEBVTT\n\n")
        for (ev in doc.events) {
            if (ev.isComment) continue
            val start = formatVttTime(ev.start)
            val end = formatVttTime(ev.end)
            sb.append("$start --> $end\n")
            val text = (ev.translatedText ?: ev.originalText).replace("\\N", "\n").replace("\\n", "\n")
            sb.append(text).append("\n\n")
        }
        return sb.toString().trimEnd() + "\n"
    }

    private fun formatVttTime(time: String): String {
        var clean = time.trim().replace(",", ".")
        if (!clean.contains(".")) clean += ".000"
        val parts = clean.split(".")
        val ms = parts.getOrNull(1)?.padEnd(3, '0')?.take(3) ?: "000"
        var timePart = parts[0]
        val timeSegs = timePart.split(":")
        if (timeSegs.size == 2) {
            timePart = "00:$timePart"
        }
        return "$timePart.$ms"
    }
}
