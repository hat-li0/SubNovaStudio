package com.subtitlepro.studio.data.model

import java.util.regex.Pattern

enum class SubtitleFormat(val extension: String, val displayName: String) {
    ASS(".ass", "Advanced SubStation Alpha (.ass)"),
    SRT(".srt", "SubRip (.srt)"),
    SSA(".ssa", "SubStation Alpha (.ssa)"),
    VTT(".vtt", "WebVTT (.vtt)"),
    SBV(".sbv", "YouTube SBV (.sbv)"),
    TXT(".txt", "Plain Text (.txt)"),
    JSON(".json", "JSON Subtitle (.json)")
}

data class SubtitleStyle(
    var name: String = "Default",
    var fontname: String = "Arial",
    var fontsize: Double = 20.0,
    var primaryColor: String = "&H00FFFFFF",
    var secondaryColor: String = "&H00000000",
    var outlineColor: String = "&H00000000",
    var backColor: String = "&H00000000",
    var bold: Boolean = false,
    var italic: Boolean = false,
    var underline: Boolean = false,
    var strikeout: Boolean = false,
    var scaleX: Double = 100.0,
    var scaleY: Double = 100.0,
    var spacing: Double = 0.0,
    var angle: Double = 0.0,
    var borderStyle: Int = 1,
    var outline: Double = 2.0,
    var shadow: Double = 0.0,
    var alignment: Int = 2,
    var marginL: Int = 10,
    var marginR: Int = 10,
    var marginV: Int = 10,
    var encoding: Int = 1,
    var rawLine: String = ""
)

data class SubtitleEvent(
    val id: Int,
    var layer: Int = 0,
    var start: String = "00:00:00.00",
    var end: String = "00:00:00.00",
    var style: String = "Default",
    var speaker: String = "",
    var originalText: String = "",
    var text: String = "",
    var translatedText: String? = null,
    var marginL: Int = 0,
    var marginR: Int = 0,
    var marginV: Int = 0,
    var effect: String = "",
    var formatType: SubtitleFormat = SubtitleFormat.ASS,
    var isComment: Boolean = false
) {
    fun getCleanText(): String {
        val raw = if (originalText.isNotBlank()) originalText else text
        // 1. Strip vector drawings {\p1}...{\p0}
        var clean = raw.replace(Regex("""\{\\p[1-9]}[^\\{]*\{\\p0}"""), "")
        // 2. Strip remaining ASS tags
        clean = clean.replace(Regex("""\{[^}]*}"""), "")
        clean = clean.replace("\\n", "\\N")
        clean = clean.replace(Regex("""\s*\\N\s*"""), " \\N ")
        clean = clean.replace(Regex("""\s+"""), " ").trim()
        return clean
    }

    fun extractTags(): List<String> {
        if (originalText.isBlank()) return emptyList()
        val matcher = Pattern.compile("""(\{[^}]*\}|\\N|\\n)""").matcher(originalText)
        val list = mutableListOf<String>()
        while (matcher.find()) {
            list.add(matcher.group())
        }
        return list
    }
}

data class SubtitleDocument(
    val info: MutableMap<String, String> = mutableMapOf(),
    val styles: MutableList<SubtitleStyle> = mutableListOf(),
    val events: MutableList<SubtitleEvent> = mutableListOf(),
    var format: SubtitleFormat = SubtitleFormat.ASS,
    var filePath: String? = null,
    var fileName: String? = null
)

data class SubtitleStreamInfo(
    val index: Int,
    val codecName: String,
    val extension: String,
    val language: String = "und",
    val title: String = "",
    val frameCount: Int = 0
) {
    fun displayName(): String {
        val langStr = if (language.isNotBlank() && language != "und") language.uppercase() else "غير محدد"
        val titleStr = if (title.isNotBlank()) " «$title»" else ""
        val codecStr = codecName.uppercase()
        val linesStr = if (frameCount > 0) " ($frameCount سطر)" else ""
        return "مسار ${index + 1}: [$langStr] بصيغة ($codecStr)$titleStr$linesStr"
    }
}

data class CharacterProfile(
    val id: Int = 0,
    var canonicalName: String = "",
    var nativeName: String = "",
    var arabicName: String = "",
    var gender: String = "UNKNOWN", // MALE, FEMALE, UNKNOWN
    var role: String = "MAIN",
    var voiceActor: String = "",
    var isUserOverride: Boolean = false
)

data class GlossaryEntry(
    var sourceTerm: String = "",
    var targetTerm: String = "",
    var notes: String = ""
)

data class AnimeMetadata(
    var id: Int = 0,
    var titleRomaji: String = "",
    var titleEnglish: String = "",
    var titleNative: String = "",
    var episodes: Int = 0,
    var coverImageUrl: String = "",
    val characters: MutableList<CharacterProfile> = mutableListOf()
)

enum class ProviderType(val displayName: String) {
    GEMINI("Google Gemini (سحابي)"),
    OPENAI("OpenAI (سحابي)"),
    LMSTUDIO("LM Studio (محلي/شبكة)"),
    OLLAMA("Ollama (محلي/شبكة)"),
    CUSTOM("Custom OpenAI-Compatible (مخصص)")
}

data class AppConfig(
    var providerType: ProviderType = ProviderType.GEMINI,
    var geminiApiKey: String = "",
    var geminiModel: String = "gemini-2.5-flash",
    var openaiApiKey: String = "",
    var openaiModel: String = "gpt-4o-mini",
    var lmstudioUrl: String = "http://192.168.1.100:1234/v1",
    var lmstudioModel: String = "allam-7b-instruct-preview",
    var ollamaUrl: String = "http://192.168.1.100:11434",
    var ollamaModel: String = "llama3:latest",
    var customUrl: String = "https://api.openai.com/v1",
    var customApiKey: String = "",
    var customModel: String = "gpt-4o-mini",
    var temperature: Float = 0.05f,
    var topP: Float = 0.95f,
    var maxTokens: Int = 8192,
    var concurrency: Int = 1,
    var batchSize: Int = 25,
    var contextPrevLines: Int = 4,
    var contextNextLines: Int = 3,
    var sourceLang: String = "Auto Detect",
    var targetLang: String = "Arabic (العربية الفصحى)",
    var autoImprove: Boolean = false,
    var enableSmartHealing: Boolean = true,
    var enableArabicPunct: Boolean = true,
    var enableLatinClean: Boolean = true,
    var enableQuoteFix: Boolean = true,
    var protectTags: Boolean = true,
    var separateInlineEffects: Boolean = true,
    var storyNotes: String = ""
)

enum class TranslationStatus {
    IDLE,
    TRANSLATING,
    IMPROVING,
    PAUSED,
    COMPLETED,
    ERROR
}
