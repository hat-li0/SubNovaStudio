import re
from typing import List, Dict, Optional, Any
from dataclasses import dataclass

@dataclass
class DetectedLanguage:
    code: str
    name: str
    display_name: str
    confidence: float = 1.0

# Supported languages mapping
LANGUAGE_METADATA = {
    'en': {'name': 'English', 'display': 'English (الإنجليزية)'},
    'ja': {'name': 'Japanese', 'display': 'Japanese (اليابانية)'},
    'fr': {'name': 'French', 'display': 'French (الفرنسية)'},
    'de': {'name': 'German', 'display': 'German (الألمانية)'},
    'es': {'name': 'Spanish', 'display': 'Spanish (الإسبانية)'},
    'ko': {'name': 'Korean', 'display': 'Korean (الكورية)'},
    'zh': {'name': 'Chinese', 'display': 'Chinese (الصينية)'},
    'it': {'name': 'Italian', 'display': 'Italian (الإيطالية)'},
    'ru': {'name': 'Russian', 'display': 'Russian (الروسية)'},
    'pt': {'name': 'Portuguese', 'display': 'Portuguese (البرتغالية)'},
    'tr': {'name': 'Turkish', 'display': 'Turkish (التركية)'},
    'ar': {'name': 'Arabic', 'display': 'Arabic (العربية الفصحى)'},
}

# 3-letter ISO 639-2 codes mapped to 2-letter
ISO_639_2_TO_1 = {
    'eng': 'en', 'en': 'en',
    'jpn': 'ja', 'ja': 'ja',
    'fra': 'fr', 'fre': 'fr', 'fr': 'fr',
    'deu': 'de', 'ger': 'de', 'de': 'de',
    'spa': 'es', 'es': 'es',
    'kor': 'ko', 'ko': 'ko',
    'zho': 'zh', 'chi': 'zh', 'zh': 'zh',
    'ita': 'it', 'it': 'it',
    'rus': 'ru', 'ru': 'ru',
    'por': 'pt', 'pt': 'pt',
    'tur': 'tr', 'tr': 'tr',
    'ara': 'ar', 'ar': 'ar',
}

# Stopwords for Latin languages
LATIN_STOPWORDS: Dict[str, set] = {
    'en': {
        'the', 'and', 'you', 'that', 'was', 'for', 'are', 'with', 'his', 'they', 'at', 'be',
        'this', 'have', 'from', 'one', 'had', 'word', 'but', 'not', 'what', 'all', 'were',
        'we', 'when', 'your', 'can', 'said', 'there', 'use', 'each', 'which', 'she', 'do',
        'how', 'their', 'if', 'will', 'up', 'other', 'about', 'out', 'many', 'then', 'them',
        'these', 'so', 'some', 'her', 'would', 'make', 'like', 'him', 'into', 'time', 'has',
        'look', 'two', 'more', 'go', 'see', 'no', 'way', 'could', 'people', 'my', 'than',
        'first', 'been', 'call', 'who', 'its', 'now', 'find', 'long', 'down', 'day', 'did',
        'get', 'come', 'made', 'may', 'part', 'fight', 'freedom', 'just', 'know', 'think',
        'where', 'why', 'over', 'good', 'well', 'want', 'dont', 'cant', 'right', 'here'
    },
    'fr': {
        'de', 'la', 'le', 'et', 'les', 'des', 'en', 'un', 'une', 'du', 'dans', 'pour', 'avec',
        'qui', 'que', 'ce', 'est', 'pas', 'sont', 'sur', 'vous', 'nous', 'ils', 'elle', 'mais',
        'ou', 'donc', 'or', 'ni', 'car', 'comme', 'tout', 'faire', 'être', 'avoir', 'bien'
    },
    'es': {
        'de', 'la', 'que', 'el', 'en', 'y', 'los', 'del', 'se', 'las', 'por', 'un', 'para',
        'con', 'no', 'una', 'su', 'al', 'lo', 'como', 'más', 'pero', 'sus', 'le', 'ya', 'o',
        'fue', 'este', 'ha', 'sí', 'porque', 'esta', 'son', 'entre', 'está', 'cuando', 'muy'
    },
    'de': {
        'der', 'die', 'das', 'und', 'in', 'den', 'von', 'zu', 'mit', 'sich', 'des', 'auf',
        'für', 'ist', 'im', 'dem', 'nicht', 'ein', 'eine', 'als', 'auch', 'es', 'an', 'werden',
        'aus', 'er', 'hat', 'dass', 'sie', 'nach', 'wird', 'bei', 'einer', 'um', 'am', 'sind'
    },
    'it': {
        'di', 'il', 'la', 'che', 'in', 'per', 'un', 'del', 'della', 'non', 'si', 'da', 'con',
        'le', 'nel', 'una', 'dei', 'questo', 'sono', 'ma', 'come', 'anche', 'era', 'gli',
        'ha', 'più', 'delle', 'loro', 'alla', 'dello', 'tutto', 'quando', 'molto', 'senza'
    },
    'pt': {
        'de', 'que', 'do', 'da', 'em', 'um', 'para', 'com', 'não', 'uma', 'os', 'no', 'se',
        'na', 'por', 'mais', 'as', 'dos', 'como', 'mas', 'foi', 'ao', 'ele', 'das', 'tem',
        'à', 'seu', 'sua', 'ou', 'quando', 'muito', 'nos', 'já', 'está', 'eu', 'também'
    },
    'tr': {
        've', 'bir', 'bu', 'da', 'de', 'için', 'ile', 'çok', 'ama', 'gibi', 'kadar', 'sonra',
        'daha', 'var', 'yok', 'ben', 'sen', 'ne', 'mi', 'mu', 'mı', 'mü', 'bunu', 'olan',
        'bana', 'bize', 'zaman', 'diye', 'kendi', 'nasıl', 'neden', 'çünkü'
    }
}

class LanguageDetector:
    """
    Ultra-fast, zero-dependency, reliable language detector optimized for subtitles.
    Handles Non-Latin scripts (Japanese, Korean, Chinese, Cyrillic, Arabic) instantly via unicode blocks,
    and Latin scripts via frequency analysis and specific diacritical indicators.
    """

    @classmethod
    def clean_subtitle_text(cls, raw: str) -> str:
        """Strips ASS tags, html tags, braces, and linebreaks for pure text analysis."""
        if not raw:
            return ""
        # Strip ASS curly bracket tags {\an8}, {\pos(..)}, etc.
        text = re.sub(r"\{.*?\}", " ", raw)
        # Strip \N, \n, \h
        text = re.sub(r"\\[Nnh]", " ", text)
        # Strip HTML tags
        text = re.sub(r"<.*?>", " ", text)
        return text.strip()

    @classmethod
    def from_stream_code(cls, code: str) -> Optional[DetectedLanguage]:
        """Converts an ISO 639-2 or 639-1 language tag from ffprobe to DetectedLanguage."""
        if not code or code.lower() in ('und', 'unk', 'zxx'):
            return None
        clean_code = code.lower().strip()
        code_2 = ISO_639_2_TO_1.get(clean_code)
        if code_2 and code_2 in LANGUAGE_METADATA:
            meta = LANGUAGE_METADATA[code_2]
            return DetectedLanguage(code=code_2, name=meta['name'], display_name=meta['display'], confidence=0.95)
        return None

    @classmethod
    def detect_from_text(cls, text: str) -> DetectedLanguage:
        """
        Detects the primary language of the provided text string using script character ratio analysis
        before falling back to Latin word-frequency scoring.
        """
        cleaned = cls.clean_subtitle_text(text)
        if not cleaned:
            return DetectedLanguage(code='en', name='English', display_name='English (الإنجليزية)', confidence=0.5)

        ja_kana = len(re.findall(r"[\u3040-\u309F\u30A0-\u30FF]", cleaned))
        ko_chars = len(re.findall(r"[\uAC00-\uD7AF\u1100-\u11FF]", cleaned))
        cjk_chars = len(re.findall(r"[\u4E00-\u9FFF]", cleaned))
        ru_chars = len(re.findall(r"[\u0400-\u04FF]", cleaned))
        ar_chars = len(re.findall(r"[\u0600-\u06FF\u0750-\u077F]", cleaned))
        latin_chars = len(re.findall(r"[a-zA-Z\u00C0-\u017F]", cleaned))

        # Japanese combines Hiragana/Katakana + Kanji; only attribute CJK ideographs to Japanese when Kana is meaningful
        non_latin_cjk_pool = ja_kana + ko_chars + cjk_chars + ru_chars + ar_chars
        total_script = non_latin_cjk_pool + latin_chars
        if total_script == 0:
            return DetectedLanguage(code='en', name='English', display_name='English (الإنجليزية)', confidence=0.5)

        if ja_kana > 0 and (ja_kana >= latin_chars or (ja_kana / max(1, total_script)) >= 0.05):
            ja_score = ja_kana + cjk_chars
            zh_score = 0
        else:
            ja_score = ja_kana
            zh_score = cjk_chars

        script_counts = {
            'ja': ja_score,
            'ko': ko_chars,
            'zh': zh_score,
            'ru': ru_chars,
            'ar': ar_chars,
            'latin': latin_chars,
        }
        top_script = max(script_counts, key=lambda k: script_counts[k])
        top_count = script_counts[top_script]
        top_ratio = top_count / total_script

        if top_script != 'latin' and (top_count > latin_chars or top_ratio >= 0.45):
            meta = LANGUAGE_METADATA[top_script]
            base_conf = 0.99 if top_script in ('ja', 'ko') else (0.98 if top_script == 'ar' else 0.95)
            conf = round(min(base_conf, max(0.80, top_ratio + 0.15)), 2) if top_ratio < 0.85 else base_conf
            return DetectedLanguage(code=top_script, name=meta['name'], display_name=meta['display'], confidence=conf)

        # Latin Language Frequency Analysis
        words = re.findall(r"[a-zA-Z\u00C0-\u017F]+", cleaned.lower())
        if not words:
            return DetectedLanguage(code='en', name='English', display_name='English (الإنجليزية)', confidence=0.5)

        scores: Dict[str, float] = {k: 0.0 for k in LATIN_STOPWORDS}

        # Diacritics weighting (Explicit character matching without re.IGNORECASE to prevent Unicode case-folding collisions)
        if re.search(r"[äöüßÄÖÜ]", cleaned):
            scores['de'] += 5.0
        if re.search(r"[éèêëàâùûçœÉÈÊËÀÂÙÛÇŒ]", cleaned):
            scores['fr'] += 5.0
        if re.search(r"[ñ¿¡áíóúÑÁÍÓÚ]", cleaned):
            scores['es'] += 5.0
        if re.search(r"[ãõçêÃÕÇÊ]", cleaned):
            scores['pt'] += 5.0
        if re.search(r"[ğışöüçĞİŞÖÜÇ]", cleaned):
            scores['tr'] += 5.0

        for w in words:
            for lang, sw in LATIN_STOPWORDS.items():
                if w in sw:
                    scores[lang] += 1.0

        best_lang = max(scores, key=lambda k: scores[k])
        max_score = scores[best_lang]

        if max_score <= 1.0:
            # Fallback to English if word count is small or ambiguous
            return DetectedLanguage(code='en', name='English', display_name='English (الإنجليزية)', confidence=0.6)

        conf = min(0.99, max(0.65, max_score / (len(words) * 0.35 + 1.0)))
        meta = LANGUAGE_METADATA[best_lang]
        return DetectedLanguage(code=best_lang, name=meta['name'], display_name=meta['display'], confidence=conf)

    @classmethod
    def detect_from_events(cls, events: List[Any], sample_limit: int = 80) -> DetectedLanguage:
        """Samples up to sample_limit events from a subtitle document to determine the language."""
        if not events:
            return DetectedLanguage(code='en', name='English', display_name='English (الإنجليزية)', confidence=0.5)

        sample_lines = []
        for e in events[:sample_limit]:
            raw = getattr(e, "original_text", "") or getattr(e, "text", "") or str(e)
            cleaned = cls.clean_subtitle_text(raw)
            if cleaned:
                sample_lines.append(cleaned)

        full_sample = " ".join(sample_lines)
        return cls.detect_from_text(full_sample)

    @classmethod
    def resolve_source_language(
        cls,
        preferred_setting: str,
        events: Optional[List[Any]] = None,
        stream_code: Optional[str] = None
    ) -> DetectedLanguage:
        """
        Determines the effective source language:
        If user explicitly set a language (e.g. 'Japanese'), uses it.
        If user set 'Auto Detect' (or empty):
          1. Detects from actual subtitle events text (highest accuracy).
          2. Falls back to stream_code metadata if text is empty.
          3. Defaults to English.
        """
        clean_pref = preferred_setting.lower().strip() if preferred_setting else ""
        if "auto" not in clean_pref and clean_pref != "":
            # Check if matching known language
            for code, meta in LANGUAGE_METADATA.items():
                if meta['name'].lower() in clean_pref or code in clean_pref:
                    return DetectedLanguage(code=code, name=meta['name'], display_name=meta['display'], confidence=1.0)

        # Auto detection requested
        if events:
            detected = cls.detect_from_events(events)
            if detected and detected.confidence >= 0.6:
                return detected

        if stream_code:
            from_stream = cls.from_stream_code(stream_code)
            if from_stream:
                return from_stream

        # Default fallback
        return DetectedLanguage(code='en', name='English', display_name='English (الإنجليزية)', confidence=0.5)
