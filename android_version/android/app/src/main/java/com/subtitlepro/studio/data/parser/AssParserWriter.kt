package com.subtitlepro.studio.data.parser

import com.subtitlepro.studio.data.model.SubtitleDocument
import com.subtitlepro.studio.data.model.SubtitleEvent
import com.subtitlepro.studio.data.model.SubtitleFormat
import com.subtitlepro.studio.data.model.SubtitleStyle

object AssParserWriter {

    fun parse(content: String): SubtitleDocument {
        val doc = SubtitleDocument(format = SubtitleFormat.ASS)
        val lines = content.lines()
        var currentSection = ""
        var eventFormatCols = listOf("Layer", "Start", "End", "Style", "Name", "MarginL", "MarginR", "MarginV", "Effect", "Text")
        var eventId = 1

        for (rawLine in lines) {
            val line = rawLine.trim()
            if (line.startsWith("[") && line.endsWith("]")) {
                currentSection = line.substring(1, line.length - 1).trim()
                continue
            }

            if (line.isBlank() || line.startsWith(";")) {
                continue
            }

            when (currentSection.lowercase()) {
                "script info" -> {
                    val parts = line.split(":", limit = 2)
                    if (parts.size == 2) {
                        doc.info[parts[0].trim()] = parts[1].trim()
                    }
                }
                "v4+ styles", "v4 styles" -> {
                    if (line.startsWith("Format:", ignoreCase = true)) {
                        // format header
                    } else if (line.startsWith("Style:", ignoreCase = true)) {
                        val styleData = line.substring(6).trim()
                        val cols = styleData.split(",")
                        val style = SubtitleStyle(
                            name = cols.getOrNull(0)?.trim() ?: "Default",
                            fontname = cols.getOrNull(1)?.trim() ?: "Arial",
                            fontsize = cols.getOrNull(2)?.trim()?.toDoubleOrNull() ?: 20.0,
                            primaryColor = cols.getOrNull(3)?.trim() ?: "&H00FFFFFF",
                            rawLine = line
                        )
                        doc.styles.add(style)
                    }
                }
                "events" -> {
                    if (line.startsWith("Format:", ignoreCase = true)) {
                        val formatStr = line.substring(7).trim()
                        eventFormatCols = formatStr.split(",").map { it.trim() }
                    } else if (line.startsWith("Dialogue:", ignoreCase = true) || line.startsWith("Comment:", ignoreCase = true)) {
                        val isComment = line.startsWith("Comment:", ignoreCase = true)
                        val colonIndex = line.indexOf(":")
                        if (colonIndex != -1) {
                            val dataStr = line.substring(colonIndex + 1).trim()
                            val parts = splitCsvWithLimit(dataStr, eventFormatCols.size)

                            val colMap = mutableMapOf<String, String>()
                            for (i in eventFormatCols.indices) {
                                if (i < parts.size) {
                                    colMap[eventFormatCols[i].lowercase()] = parts[i].trim()
                                }
                            }

                            val text = colMap["text"] ?: ""
                            val event = SubtitleEvent(
                                id = eventId++,
                                layer = colMap["layer"]?.toIntOrNull() ?: 0,
                                start = colMap["start"] ?: "00:00:00.00",
                                end = colMap["end"] ?: "00:00:00.00",
                                style = colMap["style"] ?: "Default",
                                speaker = colMap["name"] ?: "",
                                marginL = colMap["marginl"]?.toIntOrNull() ?: 0,
                                marginR = colMap["marginr"]?.toIntOrNull() ?: 0,
                                marginV = colMap["marginv"]?.toIntOrNull() ?: 0,
                                effect = colMap["effect"] ?: "",
                                originalText = text,
                                text = text,
                                formatType = SubtitleFormat.ASS,
                                isComment = isComment
                            )
                            doc.events.add(event)
                        }
                    }
                }
            }
        }

        return doc
    }

    private fun splitCsvWithLimit(line: String, limit: Int): List<String> {
        val result = mutableListOf<String>()
        var current = StringBuilder()
        var commasFound = 0
        val targetCommas = limit - 1

        for (ch in line) {
            if (ch == ',' && commasFound < targetCommas) {
                result.add(current.toString())
                current = StringBuilder()
                commasFound++
            } else {
                current.append(ch)
            }
        }
        result.add(current.toString())
        return result
    }

    fun write(doc: SubtitleDocument): String {
        val sb = StringBuilder()
        sb.append("[Script Info]\n")
        sb.append("; Script generated by Subtitle Pro Studio Android\n")
        sb.append("ScriptType: v4.00+\n")
        sb.append("WrapStyle: 0\n")
        sb.append("ScaledBorderAndShadow: yes\n")
        for ((k, v) in doc.info) {
            if (!k.equals("ScriptType", ignoreCase = true) && !k.equals("WrapStyle", ignoreCase = true) && !k.equals("ScaledBorderAndShadow", ignoreCase = true)) {
                sb.append("$k: $v\n")
            }
        }
        sb.append("\n")

        sb.append("[V4+ Styles]\n")
        sb.append("Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n")
        if (doc.styles.isEmpty()) {
            sb.append("Style: Default,Arial,20,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,2,2,2,10,10,10,1\n")
        } else {
            for (st in doc.styles) {
                if (st.rawLine.isNotBlank()) {
                    sb.append(st.rawLine).append("\n")
                } else {
                    sb.append("Style: ${st.name},${st.fontname},${st.fontsize},${st.primaryColor},${st.secondaryColor},${st.outlineColor},${st.backColor},${if (st.bold) -1 else 0},${if (st.italic) -1 else 0},${if (st.underline) -1 else 0},${if (st.strikeout) -1 else 0},${st.scaleX},${st.scaleY},${st.spacing},${st.angle},${st.borderStyle},${st.outline},${st.shadow},${st.alignment},${st.marginL},${st.marginR},${st.marginV},${st.encoding}\n")
                }
            }
        }
        sb.append("\n")

        sb.append("[Events]\n")
        sb.append("Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n")
        for (ev in doc.events) {
            val prefix = if (ev.isComment) "Comment:" else "Dialogue:"
            val finalText = ev.translatedText ?: ev.originalText
            sb.append("$prefix ${ev.layer},${ev.start},${ev.end},${ev.style},${ev.speaker},${ev.marginL},${ev.marginR},${ev.marginV},${ev.effect},$finalText\n")
        }

        return sb.toString()
    }
}
