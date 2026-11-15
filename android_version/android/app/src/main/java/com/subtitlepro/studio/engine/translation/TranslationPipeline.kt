package com.subtitlepro.studio.engine.translation

import com.subtitlepro.studio.data.model.AppConfig
import com.subtitlepro.studio.data.model.CharacterProfile
import com.subtitlepro.studio.data.model.GlossaryEntry
import com.subtitlepro.studio.data.model.SubtitleDocument
import com.subtitlepro.studio.data.model.SubtitleEvent
import com.subtitlepro.studio.engine.healer.SubtitleHealer
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.withContext

class TranslationPipeline(
    private val config: AppConfig,
    private val aiClient: AiClient
) {

    suspend fun execute(
        document: SubtitleDocument,
        characters: List<CharacterProfile> = emptyList(),
        glossary: List<GlossaryEntry> = emptyList(),
        onProgress: (percent: Float, processedLines: Int, totalLines: Int, message: String) -> Unit,
        onEventUpdated: (SubtitleEvent) -> Unit,
        onBatchCompleted: (batchIndex: Int, totalBatches: Int, processedLines: Int) -> Unit = { _, _, _ -> },
        onLog: (String) -> Unit
    ) = withContext(Dispatchers.IO) {
        val nonCommentEvents = document.events.filter { !it.isComment }
        val total = nonCommentEvents.size
        if (total == 0) {
            onLog("⚠️ لا توجد أسطر حوار للترجمة.")
            return@withContext
        }

        val batchSize = config.batchSize.coerceIn(5, 50)
        val batches = nonCommentEvents.chunked(batchSize)
        val totalBatches = batches.size

        onLog("🚀 بدء خط الإنتاج: إجمالي $total سطر حوار مقسمة إلى $totalBatches دفعة.")

        var processedCount = 0

        for ((bIdx, batch) in batches.withIndex()) {
            if (!coroutineContext.isActive) throw CancellationException("Translation was canceled")

            // Check if entire batch was already translated (e.g. resumed from checkpoint)
            val allAlreadyDone = batch.all { !it.translatedText.isNullOrBlank() }
            if (allAlreadyDone) {
                processedCount += batch.size
                val percent = (processedCount.toFloat() / total.toFloat()) * 100f
                onProgress(percent, processedCount, total, "تم استعادة الدفعة (${bIdx + 1}/$totalBatches) من نقطة الحفظ السابقة")
                onBatchCompleted(bIdx + 1, totalBatches, processedCount)
                continue
            }

            val batchIds = batch.map { it.id }
            val firstId = batch.first().id
            val lastId = batch.last().id

            onLog("⏳ معالجة الدفعة (${bIdx + 1}/$totalBatches) الأسطر [$firstId-$lastId]...")

            // 1. Build sliding context
            val prevLines = getPreviousContext(document.events, firstId, config.contextPrevLines)
            val nextLines = getNextContext(document.events, lastId, config.contextNextLines)

            // Stage 1: Translation
            val translatePrompt = PromptBuilder.buildTranslationPrompt(
                sourceLang = config.sourceLang,
                targetLang = config.targetLang,
                events = batch,
                previousContext = prevLines.joinToString("\n"),
                nextContext = nextLines.joinToString("\n"),
                characters = characters,
                glossary = glossary,
                storyNotes = config.storyNotes
            )

            var rawResponse = ""
            var attempt = 0
            while (attempt < 4) {
                try {
                    rawResponse = aiClient.sendChatCompletion(translatePrompt)
                    break
                } catch (e: Exception) {
                    if (e is CancellationException) throw e
                    attempt++
                    val isRateLimit = e.message?.contains("429", true) == true ||
                            e.message?.contains("quota", true) == true ||
                            e.message?.contains("resource_exhausted", true) == true ||
                            e.message?.contains("too many requests", true) == true

                    if (isRateLimit) {
                        val waitSec = when (attempt) {
                            1 -> 25L
                            2 -> 45L
                            else -> 60L
                        }
                        onLog("⏳ تم بلوغ حد الطلبات (429 Rate Limit) للمزود — جاري الانتظار $waitSec ثانية لإعادة الشحن التلقائي ومتابعة المعالجة بأمان...")
                        delay(waitSec * 1000L)
                    } else {
                        onLog("⚠️ محاولة غير ناجحة للدفعة ${bIdx + 1} ($attempt/4): ${e.message}")
                        if (attempt >= 4) throw e
                        delay(2000L * attempt)
                    }
                }
            }

            val parsedTranslations = ResponseParser.parse(rawResponse, batchIds)

            // Apply healing to translated events
            for (ev in batch) {
                val rawTrans = parsedTranslations[ev.id] ?: ""
                val healed = if (config.enableSmartHealing && rawTrans.isNotBlank()) {
                    SubtitleHealer.heal(
                        text = rawTrans,
                        originalText = ev.originalText,
                        enableArabicPunct = config.enableArabicPunct,
                        enableLatinClean = config.enableLatinClean,
                        enableQuoteFix = config.enableQuoteFix,
                        protectTags = config.protectTags
                    )
                } else {
                    rawTrans
                }

                if (healed.isNotBlank()) {
                    ev.translatedText = healed
                    onEventUpdated(ev)
                }
            }

            // Stage 2: Improvement (if enabled)
            if (config.autoImprove) {
                onLog("✨ بدء المرحلة الثانية (التحسين والتدقيق الفائق) للدفعة (${bIdx + 1}/$totalBatches)...")
                val improvePrompt = PromptBuilder.buildImprovementPrompt(
                    events = batch,
                    characters = characters,
                    glossary = glossary,
                    storyNotes = config.storyNotes
                )

                try {
                    val rawImproved = aiClient.sendChatCompletion(improvePrompt)
                    val parsedImproved = ResponseParser.parse(rawImproved, batchIds)
                    for (ev in batch) {
                        val imp = parsedImproved[ev.id]
                        if (!imp.isNullOrBlank()) {
                            val healedImp = SubtitleHealer.heal(
                                text = imp,
                                originalText = ev.originalText,
                                enableArabicPunct = config.enableArabicPunct,
                                enableLatinClean = config.enableLatinClean,
                                enableQuoteFix = config.enableQuoteFix,
                                protectTags = config.protectTags
                            )
                            ev.translatedText = healedImp
                            onEventUpdated(ev)
                        }
                    }
                } catch (e: Exception) {
                    if (e is CancellationException) throw e
                    onLog("⚠️ تعذر تطبيق مرحلة التحسين للدفعة ${bIdx + 1}: ${e.message} (تم اعتماد المرحلة الأولى)")
                }
            }

            processedCount += batch.size
            val percent = (processedCount.toFloat() / total.toFloat()) * 100f
            onProgress(percent, processedCount, total, "اكتملت الدفعة ${bIdx + 1} من $totalBatches")
            onBatchCompleted(bIdx + 1, totalBatches, processedCount)
        }

        onLog("🎉 اكتملت ترجمة وتدقيق كافة الأسطر بنجاح!")
    }

    private fun getPreviousContext(events: List<SubtitleEvent>, beforeId: Int, count: Int): List<String> {
        if (count <= 0) return emptyList()
        val index = events.indexOfFirst { it.id == beforeId }
        if (index <= 0) return emptyList()
        val start = (index - count).coerceAtLeast(0)
        return events.subList(start, index).mapNotNull {
            val speaker = if (it.speaker.isNotBlank()) "${it.speaker}: " else ""
            val txt = it.translatedText ?: it.text
            if (txt.isNotBlank()) "$speaker$txt" else null
        }
    }

    private fun getNextContext(events: List<SubtitleEvent>, afterId: Int, count: Int): List<String> {
        if (count <= 0) return emptyList()
        val index = events.indexOfFirst { it.id == afterId }
        if (index < 0 || index >= events.size - 1) return emptyList()
        val end = (index + 1 + count).coerceAtMost(events.size)
        return events.subList(index + 1, end).mapNotNull {
            val speaker = if (it.speaker.isNotBlank()) "${it.speaker}: " else ""
            if (it.text.isNotBlank()) "$speaker${it.text}" else null
        }
    }
}
