package com.subtitlepro.studio.engine.translation

import com.subtitlepro.studio.data.model.CharacterProfile
import com.subtitlepro.studio.data.model.GlossaryEntry
import com.subtitlepro.studio.data.model.SubtitleEvent

data class ChatMessage(val role: String, val content: String)

object PromptBuilder {

    fun buildTranslationPrompt(
        sourceLang: String,
        targetLang: String,
        events: List<SubtitleEvent>,
        previousContext: String = "",
        nextContext: String = "",
        characters: List<CharacterProfile> = emptyList(),
        glossary: List<GlossaryEntry> = emptyList(),
        storyNotes: String = ""
    ): List<ChatMessage> {
        val systemPrompt = """
Translate the following subtitle lines from $sourceLang into natural Modern Standard Arabic (الفصحى).

CRITICAL RULES:
1. Output format must strictly be `[ID] Translated text` line by line.
2. Output ONLY the translated Arabic dialogue. Do NOT add prefixes like "المترجم:" or "الترجمة:" or "المنظر العربي:".
3. NEVER add explanations, translation notes, or text in parentheses (e.g. do NOT write "(المخاطب فتاة)" or "(المتحدث غاضب)").
4. Preserve all ASS tags (such as {\i1}, {\i0}, {\an8}, {\pos(...)}) and linebreaks \N in their exact positions.
5. Do NOT explain your translation or add any commentary.
6. Translate every line and keep the exact [ID] unchanged.

Input format:
[1] Where are you going?
[2] I am going home, Kaori.

Output format:
[1] إلى أين أنت ذاهب؟
[2] أنا عائد إلى المنزل يا كاوري.
        """.trimIndent()

        val userParts = mutableListOf<String>()

        val contextBlocks = mutableListOf<String>()
        if (storyNotes.isNotBlank()) {
            contextBlocks.add("[Story & Scene Notes]:\n$storyNotes")
        }
        if (characters.isNotEmpty()) {
            val charLines = characters.joinToString("\n") { c ->
                val ar = if (c.arabicName.isNotBlank()) " (${c.arabicName})" else ""
                "- ${c.canonicalName}$ar: Gender=${c.gender}, Role=${c.role}"
            }
            contextBlocks.add("[Characters & Genders]:\n$charLines")
        }
        if (glossary.isNotEmpty()) {
            val glossLines = glossary.joinToString("\n") { g ->
                val notes = if (g.notes.isNotBlank()) " (${g.notes})" else ""
                "- ${g.sourceTerm} -> ${g.targetTerm}$notes"
            }
            contextBlocks.add("[Glossary & Terminology]:\n$glossLines")
        }
        if (previousContext.isNotBlank()) {
            contextBlocks.add("[Previous Dialogue for Reference]:\n$previousContext")
        }

        if (contextBlocks.isNotEmpty()) {
            userParts.add("### REFERENCE ONLY (DO NOT TRANSLATE THIS SECTION):\n" + contextBlocks.joinToString("\n\n"))
        }

        val currentSubs = events.joinToString("\n") { ev ->
            "[${ev.id}] ${ev.getCleanText()}"
        }
        userParts.add("CURRENT SUBTITLES TO TRANSLATE:\n$currentSubs")

        if (nextContext.isNotBlank()) {
            userParts.add("### UPCOMING CONTEXT FOR REFERENCE:\n$nextContext")
        }

        return listOf(
            ChatMessage("system", systemPrompt),
            ChatMessage("user", userParts.joinToString("\n\n"))
        )
    }

    fun buildImprovementPrompt(
        events: List<SubtitleEvent>,
        characters: List<CharacterProfile> = emptyList(),
        glossary: List<GlossaryEntry> = emptyList(),
        storyNotes: String = ""
    ): List<ChatMessage> {
        val systemPrompt = """
Refine and polish the following Arabic subtitle lines into fluent, natural Modern Standard Arabic (الفصحى).

CRITICAL RULES:
1. Output format must strictly be `[ID] Refined Arabic text` line by line.
2. Output ONLY the refined Arabic text. Do NOT add prefixes like "المترجم:" or "المصقول النهائي:" or "التعديلات:".
3. NEVER write reports, comparison summaries, or explanations of what was edited.
4. NEVER add notes in parentheses (e.g. do NOT write "(المخاطب فتاة)" or "(تم التصحيح)").
5. Preserve all ASS tags (such as {\i1}, {\i0}, {\an8}, {\pos(...)}) and linebreaks \N in their exact positions.
6. Keep every numeric [ID] unchanged.

Input format:
[1] هل انت بخير؟
[2] نعم لا تقلقين

Output format:
[1] هل أنتِ بخير؟
[2] أجل، لا تقلقي.
        """.trimIndent()

        val userParts = mutableListOf<String>()

        val contextBlocks = mutableListOf<String>()
        if (storyNotes.isNotBlank()) {
            contextBlocks.add("[Story & Scene Notes]:\n$storyNotes")
        }
        if (characters.isNotEmpty()) {
            val charLines = characters.joinToString("\n") { c ->
                val ar = if (c.arabicName.isNotBlank()) " (${c.arabicName})" else ""
                "- ${c.canonicalName}$ar: Gender=${c.gender}"
            }
            contextBlocks.add("[Characters & Genders]:\n$charLines")
        }
        if (contextBlocks.isNotEmpty()) {
            userParts.add("### REFERENCE ONLY:\n" + contextBlocks.joinToString("\n\n"))
        }

        val currentSubs = events.joinToString("\n") { ev ->
            val arText = ev.translatedText ?: ev.originalText
            "[${ev.id}] $arText"
        }
        userParts.add("CURRENT SUBTITLES TO REFINE:\n$currentSubs")

        return listOf(
            ChatMessage("system", systemPrompt),
            ChatMessage("user", userParts.joinToString("\n\n"))
        )
    }
}
