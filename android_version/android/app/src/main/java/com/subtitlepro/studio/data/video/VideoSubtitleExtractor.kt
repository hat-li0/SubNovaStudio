package com.subtitlepro.studio.data.video

import android.content.Context
import android.media.MediaExtractor
import android.media.MediaFormat
import android.net.Uri
import com.subtitlepro.studio.data.model.SubtitleDocument
import com.subtitlepro.studio.data.model.SubtitleEvent
import com.subtitlepro.studio.data.model.SubtitleFormat
import com.subtitlepro.studio.data.model.SubtitleStreamInfo
import java.nio.ByteBuffer
import java.nio.charset.StandardCharsets

object VideoSubtitleExtractor {

    private val VIDEO_EXTENSIONS = setOf("mkv", "mp4", "avi", "mov", "flv", "wmv", "webm", "ts", "m4v")

    fun isVideoFile(fileName: String): Boolean {
        val ext = fileName.substringAfterLast('.', "").lowercase()
        return VIDEO_EXTENSIONS.contains(ext)
    }

    fun probeSubtitleTracks(context: Context, uri: Uri): List<SubtitleStreamInfo> {
        // 1. Try pure Kotlin MKV EBML parser first for rich Matroska files
        try {
            context.contentResolver.openInputStream(uri)?.use { stream ->
                val mkvTracks = MkvSubtitleExtractor.probeTracks(stream)
                if (mkvTracks.isNotEmpty()) {
                    return mkvTracks
                }
            }
        } catch (ignored: Throwable) {}

        // 2. Fallback to Android MediaExtractor
        val tracks = mutableListOf<SubtitleStreamInfo>()
        val extractor = MediaExtractor()
        try {
            extractor.setDataSource(context, uri, null)
            val count = extractor.trackCount
            var subIndex = 0

            for (i in 0 until count) {
                val format = extractor.getTrackFormat(i)
                val mime = format.getString(MediaFormat.KEY_MIME) ?: ""

                if (isSubtitleMime(mime)) {
                    val lang = if (format.containsKey(MediaFormat.KEY_LANGUAGE)) {
                        format.getString(MediaFormat.KEY_LANGUAGE) ?: "und"
                    } else "und"

                    val title = if (format.containsKey("title")) {
                        format.getString("title") ?: ""
                    } else ""

                    val codec = when {
                        mime.contains("ssa") || mime.contains("ass") -> "ass"
                        mime.contains("vtt") -> "webvtt"
                        else -> "srt"
                    }

                    val ext = when (codec) {
                        "ass" -> ".ass"
                        "webvtt" -> ".vtt"
                        else -> ".srt"
                    }

                    tracks.add(
                        SubtitleStreamInfo(
                            index = subIndex++,
                            codecName = codec,
                            extension = ext,
                            language = lang,
                            title = title,
                            frameCount = 0
                        )
                    )
                }
            }
        } catch (e: Exception) {
            e.printStackTrace()
        } finally {
            try {
                extractor.release()
            } catch (ignored: Exception) {}
        }
        return tracks
    }

    private fun isSubtitleMime(mime: String): Boolean {
        val lower = mime.lowercase()
        return lower.startsWith("text/") ||
                lower.contains("subrip") ||
                lower.contains("vtt") ||
                lower.contains("ass") ||
                lower.contains("ssa") ||
                lower.contains("subtitle") ||
                lower.contains("cea-608") ||
                lower.contains("tx3g")
    }

    private data class RawSubtitleSample(
        val startUs: Long,
        val text: String
    )

    fun extractSubtitleTrack(
        context: Context,
        uri: Uri,
        trackIndex: Int
    ): SubtitleDocument {
        // 1. Try pure Kotlin MKV EBML extractor (exact BlockDuration + original ASS styles)
        try {
            context.contentResolver.openInputStream(uri)?.use { stream ->
                val mkvDoc = MkvSubtitleExtractor.extractSubtitle(stream, trackIndex)
                if (mkvDoc != null && mkvDoc.events.isNotEmpty()) {
                    return mkvDoc
                }
            }
        } catch (ignored: Throwable) {}

        // 2. Fallback to MediaExtractor with dynamic, non-overlapping speech duration calculation
        val doc = SubtitleDocument(format = SubtitleFormat.SRT)
        val extractor = MediaExtractor()
        try {
            extractor.setDataSource(context, uri, null)
            val count = extractor.trackCount
            var currentSub = 0
            var targetTrack = -1

            for (i in 0 until count) {
                val format = extractor.getTrackFormat(i)
                val mime = format.getString(MediaFormat.KEY_MIME) ?: ""
                if (isSubtitleMime(mime)) {
                    if (currentSub == trackIndex) {
                        targetTrack = i
                        break
                    }
                    currentSub++
                }
            }

            if (targetTrack != -1) {
                extractor.selectTrack(targetTrack)
                val buffer = ByteBuffer.allocateDirect(128 * 1024)
                val rawSamples = mutableListOf<RawSubtitleSample>()

                while (true) {
                    buffer.clear()
                    val sampleSize = extractor.readSampleData(buffer, 0)
                    if (sampleSize < 0) break

                    val timeUs = extractor.sampleTime
                    val bytes = ByteArray(sampleSize)
                    buffer.get(bytes)
                    val text = String(bytes, StandardCharsets.UTF_8).trim()

                    if (text.isNotBlank()) {
                        rawSamples.add(RawSubtitleSample(timeUs, text))
                    }
                    extractor.advance()
                }

                // Dynamic, non-overlapping duration algorithm based on speech and reading speed
                var eventId = 1
                for (idx in rawSamples.indices) {
                    val curr = rawSamples[idx]
                    val textLen = curr.text.length
                    // Natural reading speed calculation (~15-20 CPS = 65ms per char, bounded between 1.5s and 7.0s)
                    val estDurationUs = (textLen * 65_000L).coerceIn(1_500_000L, 7_000_000L)
                    val nextStartUs = if (idx + 1 < rawSamples.size) rawSamples[idx + 1].startUs else (curr.startUs + estDurationUs)

                    val endUs = if (nextStartUs > curr.startUs) {
                        minOf(nextStartUs, curr.startUs + estDurationUs)
                    } else {
                        curr.startUs + estDurationUs
                    }

                    val startTime = formatUsToTime(curr.startUs)
                    val endTime = formatUsToTime(endUs)

                    doc.events.add(
                        SubtitleEvent(
                            id = eventId++,
                            start = startTime,
                            end = endTime,
                            originalText = curr.text,
                            text = curr.text,
                            formatType = SubtitleFormat.SRT
                        )
                    )
                }
            }
        } catch (e: Exception) {
            e.printStackTrace()
        } finally {
            try {
                extractor.release()
            } catch (ignored: Exception) {}
        }
        return doc
    }

    private fun formatUsToTime(us: Long): String {
        val totalMs = us / 1000
        val ms = (totalMs % 1000) / 10 // cs format for ASS
        val totalSec = totalMs / 1000
        val sec = totalSec % 60
        val totalMin = totalSec / 60
        val min = totalMin % 60
        val hr = totalMin / 60
        return String.format("%02d:%02d:%02d.%02d", hr, min, sec, ms)
    }
}
