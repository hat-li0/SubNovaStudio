package com.subtitlepro.studio.data.parser

import com.subtitlepro.studio.data.model.SubtitleDocument
import com.subtitlepro.studio.data.model.SubtitleFormat

object SubtitleManager {

    fun detectFormat(fileName: String, content: String): SubtitleFormat {
        val ext = fileName.substringAfterLast('.', "").lowercase()
        return when (ext) {
            "ass" -> SubtitleFormat.ASS
            "srt" -> SubtitleFormat.SRT
            "vtt" -> SubtitleFormat.VTT
            "ssa" -> SubtitleFormat.SSA
            "sbv" -> SubtitleFormat.SBV
            "json" -> SubtitleFormat.JSON
            "txt" -> SubtitleFormat.TXT
            else -> {
                val preview = content.take(1024).trimStart()
                if (preview.startsWith("[Script Info]")) {
                    SubtitleFormat.ASS
                } else if (preview.startsWith("WEBVTT")) {
                    SubtitleFormat.VTT
                } else if (preview.contains("-->")) {
                    SubtitleFormat.SRT
                } else {
                    SubtitleFormat.ASS
                }
            }
        }
    }

    fun parse(content: String, fileName: String): SubtitleDocument {
        val format = detectFormat(fileName, content)
        val doc = when (format) {
            SubtitleFormat.ASS, SubtitleFormat.SSA -> AssParserWriter.parse(content)
            SubtitleFormat.SRT -> SrtParserWriter.parse(content)
            SubtitleFormat.VTT -> VttParserWriter.parse(content)
            else -> SrtParserWriter.parse(content)
        }
        doc.format = format
        doc.fileName = fileName
        return doc
    }

    fun serialize(doc: SubtitleDocument, targetFormat: SubtitleFormat = doc.format): String {
        return when (targetFormat) {
            SubtitleFormat.ASS, SubtitleFormat.SSA -> AssParserWriter.write(doc)
            SubtitleFormat.SRT -> SrtParserWriter.write(doc)
            SubtitleFormat.VTT -> VttParserWriter.write(doc)
            SubtitleFormat.TXT -> {
                doc.events.joinToString("\n") { it.translatedText ?: it.originalText }
            }
            else -> AssParserWriter.write(doc)
        }
    }
}
