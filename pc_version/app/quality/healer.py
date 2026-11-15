import re
import unicodedata
from typing import Dict, Any, Optional, Tuple, List, Iterable, Set


class SubtitleHealer:
    r"""
    Smart Auto-Healing Post-Processing Engine for subtitle translations.
    Ultra-strict subtitle purification:
    1. Invisible & Unicode Artifacts stripping (zero-width characters, BOM, directional marks).
    2. Absolute ASS Tag Protection & Immunity.
    3. Markdown & HTML Artifacts Elimination (strip **, *, _, HTML tags, convert <br> to \N).
    4. LLM Labels, Prefixes, and ID Markers elimination ([1], 1., Improved:, الترجمة:, etc.).
    5. SDH Audio Descriptions & Foreign Sound Effects removal ((sigh), [music], {gasp}).
    6. Stray Latin Letters & English Fillers cleaning (\Nyeah, \Noh, \NI, stray words).
    7. ASS Line Break (\N) Normalization (no dangling, duplicate, or leading/trailing \N).
    8. Strict Arabic Punctuation Normalization & De-duplication.
    9. Orphan & Mismatched Quotation Marks elimination.
    10. Dialogue Dash Normalization.
    """

    _TECH_BRANDS_LOWER: Set[str] = {
        "wifi", "wi-fi", "youtube", "iphone", "ipad", "ipod", "imac", "macbook",
        "android", "ios", "windows", "macos", "linux", "google", "facebook",
        "twitter", "instagram", "tiktok", "discord", "netflix", "spotify",
        "bluetooth", "usb", "hdmi", "http", "https", "html", "css", "pdf",
        "mp3", "mp4", "mkv", "ass", "srt", "vtt", "github", "gmail",
        "chrome", "firefox", "playstation", "xbox", "nintendo", "steam",
        "apple", "samsung", "sony", "microsoft", "openai", "gemini",
    }

    @staticmethod
    def _is_arabic_target(target_lang: Optional[str]) -> bool:
        t = (target_lang or "ar").strip().lower()
        return not t or any(k in t for k in ("ar", "arabic", "عرب"))

    @staticmethod
    def protect_ass_tags(text: str) -> Tuple[str, List[str]]:
        r"""
        Extracts ASS override tags {\...} and replaces them with safe unique tokens.
        Preserves drawing tags {\p1}...{\p0} and override tags without corruption.
        """
        if not text:
            return text, []

        ass_tags: List[str] = []

        # 1. First protect complete vector drawing blocks {\p1}...{\p0} as atomic tokens
        def drawing_repl(m: re.Match) -> str:
            ass_tags.append(m.group(0))
            return f"___ASS_DRAWING_{len(ass_tags)-1}___"

        protected = re.sub(r'\{\\p[1-9]\}[^\\{]*\{\\p0\}', drawing_repl, text)

        # 2. Protect remaining ASS override tags {\...}
        def tag_repl(m: re.Match) -> str:
            ass_tags.append(m.group(0))
            return f"___ASS_TAG_{len(ass_tags)-1}___"

        protected = re.sub(r'\{\\[^}]*\}', tag_repl, protected)
        return protected, ass_tags

    @staticmethod
    def restore_ass_tags(text: str, ass_tags: List[str]) -> str:
        r"""
        Restores protected ASS tags and drawings and verifies none were dropped by the LLM.
        Prepends any dropped tags if missing, and de-duplicates identical adjacent tags.
        """
        if not text or not ass_tags:
            return text

        restored = text
        for i, tag in enumerate(ass_tags):
            tag_token = f"___ASS_TAG_{i}___"
            draw_token = f"___ASS_DRAWING_{i}___"
            if tag_token in restored:
                restored = restored.replace(tag_token, tag)
            elif draw_token in restored:
                restored = restored.replace(draw_token, tag)
            else:
                if not re.search(r'\\p[1-9]', tag):
                    restored = tag + restored

        # De-duplicate adjacent identical tags, e.g. {\an8}{\an8} -> {\an8}
        restored = re.sub(r'(\{\\[^}]+\})\1+', r'\1', restored)

        return restored

    @staticmethod
    def clean_invisible_and_unicode_artifacts(text: str) -> str:
        r"""Removes zero-width characters, BOM, LTR marks, and directional overrides while preserving RLM (\u200f)."""
        if not text:
            return ""
        # Strip zero-width spaces, joiners, LRM, BOM, and directional overrides (preserve \u200f RLM!)
        cleaned = re.sub(r'[\u200b\u200c\u200d\u200e\ufeff\u202a-\u202e\u2066-\u2069]', '', text)
        # Convert non-breaking space to regular space
        cleaned = cleaned.replace('\u00a0', ' ')
        # Standardize carriage returns to ASS linebreaks \N
        cleaned = cleaned.replace('\r\n', r'\N').replace('\r', r'\N')
        return cleaned

    @staticmethod
    def ensure_rtl_bidi(text: str) -> str:
        """
        Anchors Arabic RTL punctuation (!, ؟, ., -, leading dialogue dashes) using Unicode RLM (\\u200f)
        inside each \\N segment (after leading ASS tags and before closing ASS tags) so libass/VLC/MPV
        render Arabic punctuation on the correct visual side without reversing dashes or exclamation marks.
        """
        if not text:
            return text
        if not re.search(r'[\u0600-\u06FF]', text):
            return text

        segments = re.split(r'(\\N|\\n|\n)', text)
        out_segments: List[str] = []
        for idx, seg in enumerate(segments):
            if idx % 2 == 1:
                out_segments.append(seg)
                continue
            if not seg or not re.search(r'[\u0600-\u06FF]', seg):
                out_segments.append(seg)
                continue

            m_lead = re.match(r'^((?:\{[^{}]*\}\s*)*)(.*)$', seg)
            lead_tags = m_lead.group(1) if m_lead else ""
            rem = m_lead.group(2) if m_lead else seg

            m_trail = re.search(r'((?:\s*\{[^{}]*\})*)$', rem)
            trail_tags = m_trail.group(1) if m_trail else ""
            body = rem[:m_trail.start(1)] if m_trail else rem

            if body:
                needs_lead_rlm = (
                    not re.match(r'^[\u0621-\u064A\u0671-\u06D3\u200f]', body)
                    or bool(re.search(r'[A-Za-z]', body))
                )
                if needs_lead_rlm and not body.startswith('\u200f'):
                    body = '\u200f' + body

                needs_trail_rlm = bool(
                    re.search(r'[!\?؟\.\،\؛:\-"»\'\)\]]$', body)
                    or re.search(r'[A-Za-z]$', body)
                )
                if needs_trail_rlm and not body.endswith('\u200f'):
                    body = body + '\u200f'

            out_segments.append(f"{lead_tags}{body}{trail_tags}")

        return "".join(out_segments)

    @staticmethod
    def clean_markdown_and_html(text: str) -> str:
        r"""
        Eliminates markdown syntax, think blocks, and HTML tags that leak from LLM responses:
        - Converts <br>, <br/> to \N
        - Strips <think>...</think> and unclosed reasoning blocks
        - Strips HTML tags like <font...>, </font>, <span>, </span>, <div>, etc.
        - Converts <i>...</i> to {\i1}...{\i0} and <b>...</b> to {\b1}...{\b0}
        - Strips markdown formatting: **text**, *text*, __text__, `text`, ```code```, ### headings
        """
        if not text:
            return ""

        cleaned = text

        # Strip think blocks (DeepSeek / Reasoning models)
        cleaned = re.sub(r"<think>.*?</think>", "", cleaned, flags=re.DOTALL)
        if "<think>" in cleaned:
            cleaned = re.sub(r"<think>.*$", "", cleaned, flags=re.DOTALL)
        if "</think>" in cleaned:
            cleaned = cleaned.split("</think>")[-1]

        # Strip code fences and markdown headings
        cleaned = re.sub(r"```[a-zA-Z]*\n?", "", cleaned)
        cleaned = re.sub(r"^#{1,6}\s*", "", cleaned, flags=re.MULTILINE)

        # Convert <br> or <br/> to \N
        cleaned = re.sub(r'<br\s*/?>', r'\\N', cleaned, flags=re.IGNORECASE)

        # Convert simple italic/bold HTML tags to ASS tags
        cleaned = re.sub(r'<i>(.*?)</i>', r'{\\i1}\1{\\i0}', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'<b>(.*?)</b>', r'{\\b1}\1{\\b0}', cleaned, flags=re.IGNORECASE)

        # Strip remaining HTML tags
        cleaned = re.sub(r'</?(?:font|span|div|p|u|em|strong)[^>]*>', '', cleaned, flags=re.IGNORECASE)

        # Strip markdown bold / italic / code
        cleaned = re.sub(r'\*\*(.*?)\*\*', r'\1', cleaned)
        cleaned = re.sub(r'\*([^*\n]+)\*', r'\1', cleaned)
        cleaned = re.sub(r'__(.*?)__', r'\1', cleaned)
        cleaned = re.sub(r'`(.*?)`', r'\1', cleaned)

        return cleaned

    @staticmethod
    def clean_llm_labels_and_prefixes(text: str) -> str:
        r"""
        Removes line numbers, pipe echoes, and verbose LLM prefixes:
        [001], 1., 1:, Line 1:, الترجمة:, Improved:, الصياغة الجديدة:, etc.
        """
        if not text:
            return ""
        cleaned = text.strip()

        # Check for pipe echo format: e.g. "Original: ... | Improved: ..."
        if '|' in cleaned:
            parts = cleaned.split('|')
            if len(parts) == 2:
                left, right = parts[0].strip(), parts[1].strip()
                echo_triggers = ('original', 'نص أصلي', 'النص الأصلي', 'current arabic', 'الترجمة الحالية')
                target_triggers = ('improved', 'translation', 'الترجمة', 'المحسن', 'الصياغة')
                if any(trig in left.lower() for trig in echo_triggers) or any(trig in right.lower() for trig in target_triggers):
                    cleaned = right

        prefix_pattern = (
            r'^(?:النص الأصلي|الأصل الإنجليزي|الأصل|الترجمة الحالية|الترجمة المحسنة|'
            r'الترجمة المقترحة|الترجمة النهائية|الترجمة العربية|الترجمة|المعنى العربي|'
            r'المعنى|النص العربي|النص المحسن|النص|المحسن|النتيجة|الصياغة الجديدة|'
            r'الصياغة المعدلة|التدقيق اللغوي|التدقيق|التصحيح|التعديل|السطر \d+|'
            r'ترجمة|إليك الترجمة|الترجمة هي|نص الترجمة|'
            r'Line \d+|Improved|Translation|Translated|Translated text|Target|Draft|Correction|Corrected|Revision|'
            r'Revised|Output|Result|Arabic|Subtitle|Final)[\s\:\-–—]+\s*'
        )

        # Iteratively strip line numbers and labels (up to 3 passes for chained prefixes like "1. الترجمة: ...")
        for _ in range(3):
            prev = cleaned
            # 1. Strip line numbering: [001] or 1. or 1: or 1 -
            cleaned = re.sub(r'^[\[\(]?\d{1,4}[\]\)]?[\s\.\:\-–—]+\s*', '', cleaned)
            # 2. Strip "Line 1:" or "السطر 1:"
            cleaned = re.sub(r'^(?:Line|السطر)\s*\d+[\s\.\:\-–—]+\s*', '', cleaned, flags=re.IGNORECASE)
            # 3. Strip explanatory labels
            cleaned = re.sub(prefix_pattern, '', cleaned, flags=re.IGNORECASE)
            if cleaned == prev:
                break

        # Strip trailing translator notes e.g. (ملاحظة: ...) or - Note: ...
        cleaned = re.sub(r'\s*[-|–|—|:]\s*[\(\[]?(?:Note|ملاحظة|ملاحظه|Translation Note)[\s:]+.*$', '', cleaned, flags=re.IGNORECASE).strip()
        cleaned = re.sub(r'[\(\[]?(?:Note|ملاحظة|ملاحظه|Translation Note)[\s:]+.*[\]\)]?$', '', cleaned, flags=re.IGNORECASE).strip()
        cleaned = re.sub(r'[\s\-–—\:]+$', '', cleaned).strip()

        # Clean leading colon/bullet remnants (leave dashes to clean_dialogue_dashes)
        cleaned = re.sub(r'^[\*\:\s\.]+', '', cleaned).strip()

        # Strip wrapping quotes or backticks if entire text is enclosed
        if len(cleaned) >= 2:
            if (cleaned.startswith('"') and cleaned.endswith('"')) or \
               (cleaned.startswith('`') and cleaned.endswith('`')) or \
               (cleaned.startswith('«') and cleaned.endswith('»')) or \
               (cleaned.startswith('“') and cleaned.endswith('”')):
                cleaned = cleaned[1:-1].strip()

        return cleaned

    @staticmethod
    def clean_sdh_and_sound_effects(text: str) -> str:
        r"""Removes foreign and Arabic SDH sound descriptions like (sigh), [music], (gasp), {cough}, *sigh* while preserving legitimate parenthetical dialogue."""
        if not text:
            return ""
        cleaned = text
        # Remove non-ASS braces: {Hmm.}, {Sigh}, {cough} (excludes {\...} and ___ASS_TAG_...)
        cleaned = re.sub(r'\{(?!\\[A-Za-z]|___ASS_TAG_|___ASS_DRAWING_)[^{}]*\}', '', cleaned)
        sdh_keywords = (
            r'music|playing|song|singing|instrumental|humming|melody|tune|'
            r'sigh(?:s|ing)?|gasp(?:s|ing)?|pant(?:s|ing)?|groan(?:s|ing)?|'
            r'chuckle(?:s|ing)?|sob(?:s|bing)?|cough(?:s|ing)?|scream(?:s|ing)?|'
            r'snicker(?:s|ing)?|laugh(?:s|ing|ter)?|giggle(?:s|ing)?|applause|cheer(?:s|ing)?|'
            r'grunt(?:s|ing)?|whisper(?:s|ing)?|murmur(?:s|ing)?|scoff(?:s|ing)?|'
            r'yell(?:s|ing)?|shout(?:s|ing)?|cry(?:ing)?|cries|snor(?:e|es|ing)|'
            r'yawn(?:s|ing)?|clear(?:s|ing)?\s+throat|(?:heavy\s+)?breath(?:s|es|ing)|inhales?|exhales?|'
            r'footsteps|knock(?:s|ing)?|ring(?:s|ing)?|beep(?:s|ing)?|buzz(?:es|ing)?|click(?:s|ing)?|static|'
            r'thunder|rain|wind|silence|sfx|sound(?:\s+effects?)?|noise|audio|'
            r'explosion|gunshots?|indistinct|chatter|'
            r'door\s+(?:opens?|closes?|slams?)|phone\s+rings?(?:ing)?|bell\s+rings?(?:ing)?|'
            r'(?:ال)?(?:موسيقى|غناء|أغنية|ضحك|ضحكات|قهقهة|تنهد|تنهيدة|شهقة|شهق|'
            r'سعال|كحة|بكاء|صراخ|تصفيق|همس|طرق|رنين|خطوات|صمت|أنين|تثاؤب|'
            r'شخير|شهيق|زفير|ضجيج|صوت|أصوات|مؤثر\s+صوتي|مؤثرات\s+صوتية|انفجار|لغط|ثرثرة)'
        )
        # Remove SDH brackets like [music], [sighs], [laughter], [applause], [♪], [موسيقى], [ضحك]
        cleaned = re.sub(
            rf"\[(?:[^\[\]\n]{{0,40}}?(?:♪|♫|\b(?:{sdh_keywords})\b)[^\[\]\n]{{0,40}}?)\]",
            '',
            cleaned,
            flags=re.IGNORECASE,
        )
        # Remove SDH parentheses like (sigh), (gasp), (music playing), (chuckles), (موسيقى), (ضحك)
        cleaned = re.sub(
            rf"\((?:[^\(\)\n]{{0,40}}?(?:♪|♫|\b(?:{sdh_keywords})\b)[^\(\)\n]{{0,40}}?)\)",
            '',
            cleaned,
            flags=re.IGNORECASE,
        )
        # Remove SDH asterisks like *sigh*, *gasp*, *pant*, *groan*, *تنهد*, *شهقة*, *ضحك*
        cleaned = re.sub(r"\*(?:sigh|gasp|pant|groan|chuckle|sob|cough|screaming|snicker|laugh|laughter|applause|music|تنهد|شهقة|ضحك|بكاء|صراخ|موسيقى)[s]?\*", '', cleaned, flags=re.IGNORECASE)
        return cleaned

    @staticmethod
    def separate_sfx_and_audio_cues(text: str) -> str:
        r"""
        Ensures sound effect cues (e.g. [انفجار], (ضحك), *تنهد*) are cleanly separated
        from dialogue words with spaces so they never fuse with speech.
        """
        if not text:
            return ""
        separated = text
        separated = re.sub(r'(\[[^\]]+\])([ء-ي])', r'\1 \2', separated)
        separated = re.sub(r'([ء-ي])(\[[^\]]+\])', r'\1 \2', separated)
        separated = re.sub(r'(\([^\)]+\))([ء-ي])', r'\1 \2', separated)
        separated = re.sub(r'([ء-ي])(\([^\)]+\))', r'\1 \2', separated)
        separated = re.sub(r'(\*[^*\n]+\*)([ء-ي])', r'\1 \2', separated)
        separated = re.sub(r'([ء-ي])(\*[^*\n]+\*)', r'\1 \2', separated)
        return separated

    @staticmethod
    def transliterate_name_to_arabic(name: str, mid_word: bool = False) -> str:
        r"""Transliterates Latin/Japanese names into natural Arabic phonetic equivalents with accent normalization."""
        if not name:
            return ""

        # Normalize accented Latin / Romaji characters (e.g. Kôdan -> Kodan, Sōma -> Soma)
        clean_name = ''.join(c for c in unicodedata.normalize('NFKD', name) if not unicodedata.combining(c))

        mapping = [
            ('sh', 'ش'), ('ch', 'تش'), ('th', 'ث'), ('kh', 'خ'), ('ts', 'تس'),
            ('k', 'ك'), ('t', 'ت'), ('b', 'ب'), ('m', 'م'), ('n', 'ن'),
            ('r', 'ر'), ('y', 'ي'), ('w', 'و'), ('h', 'ه'), ('d', 'د'),
            ('s', 'س'), ('z', 'ز'), ('j', 'ج'), ('g', 'غ'), ('f', 'ف'),
            ('p', 'ب'), ('v', 'ف'), ('c', 'ك'), ('l', 'ل'),
            ('aa', 'ا'), ('ee', 'ي'), ('ii', 'ي'), ('oo', 'و'), ('uu', 'و'),
            ('ou', 'و'), ('ai', 'اي'), ('ei', 'اي'), ('oi', 'وي'),
            ('a', 'ا'), ('i', 'ي'), ('u', 'و'), ('e', 'ي'), ('o', 'و')
        ]
        words = clean_name.split()
        res_words = []
        for w in words:
            clean_w = w.lower()
            ar = ''
            i = 0
            while i < len(clean_w):
                matched = False
                for pat, rep in mapping:
                    if clean_w[i:].startswith(pat):
                        if not mid_word and i == 0 and pat in ('a', 'aa'):
                            rep = 'أ'
                        elif not mid_word and i == 0 and pat in ('e', 'i', 'ee', 'ii'):
                            rep = 'إي'
                        ar += rep
                        i += len(pat)
                        matched = True
                        break
                if not matched:
                    ar += clean_w[i]
                    i += 1
            ar = re.sub(r'ا{2,}', 'ا', ar)
            ar = re.sub(r'ي{2,}', 'ي', ar)
            ar = re.sub(r'و{2,}', 'و', ar)
            res_words.append(ar)
        return ' '.join(res_words)

    @staticmethod
    def fix_arabic_grammar_and_spelling(text: str) -> str:
        r"""
        Applies essential Modern Standard Arabic spelling and grammar normalizations:
        - Addressing feminine: أنتي -> أنتِ
        - Common spelling: إنشاء الله -> إن شاء الله, لاكن -> لكن, هاذا -> هذا, ذالك -> ذلك
        """
        if not text:
            return ""
        res = text
        # Correct feminine pronoun 'أنتي' to 'أنتِ'
        res = re.sub(r'\bأنتي\b', 'أنتِ', res)
        # Common typos
        res = re.sub(r'\bإنشاء\s+الله\b', 'إن شاء الله', res)
        res = re.sub(r'\bلاكن\b', 'لكن', res)
        res = re.sub(r'\bهاذا\b', 'هذا', res)
        res = re.sub(r'\bذالك\b', 'ذلك', res)
        return res

    @classmethod
    def clean_stray_latin_and_fillers(
        cls,
        text: str,
        known_names: Optional[Iterable[str]] = None,
    ) -> str:
        r"""
        Removes stray Latin letters, fillers, and transliterates untranslated foreign names in Arabic dialogue.
        Cleans: \Nyeah, \Noh, \NI, stray trailing/leading fillers, fused prefixes (لتakeru -> لتاكيرو).
        Preserves technical brand names (WiFi, YouTube, iPhone, etc.), uppercase acronyms (VIP, DNA),
        untranslated lowercase words (unless fused), and Latin-only lines/segments in bilingual subtitles.
        Transliterates Japanese honorifics (-kun -> -كون, -san -> -سان, etc.).
        """
        if not text:
            return ""

        known_names_lower: Set[str] = set()
        if known_names:
            for raw_name in known_names:
                n_str = str(raw_name or "").strip()
                if not n_str:
                    continue
                known_names_lower.add(n_str.lower())
                for tok in re.split(r"[\s\-_/]+", n_str):
                    if len(tok) >= 2:
                        known_names_lower.add(tok.lower())

        cleaned = text

        # Clean stray CJK/Asian and Cyrillic characters unconditionally
        cleaned = re.sub(r'[\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af\u0400-\u04ff]+', '', cleaned)

        fillers = (
            r'yeah|yes|no|oh|ah|uh|um|hmm|huh|wow|hey|wait|okay|ok|sorry|'
            r'please|thanks|bye|hi|hello|oops|ouch|ugh|sigh|sob|chuckle|gasp|'
            r'right|alright|look|listen'
        )

        # Clean stray single letters / fillers bordering \N and line edges when Arabic is present
        if re.search(r'[ء-ي]', cleaned):
            cleaned = re.sub(rf'^(?:{fillers}|[a-zA-Z]{{1,2}})[\s،,!\?؟\.\-–—:]+\s*([ء-ي])', r'\1', cleaned, flags=re.IGNORECASE)
            cleaned = re.sub(rf'([ء-ي])[\s،,!\?؟\.\-–—:]+(?:{fillers}|[a-zA-Z]{{1,2}})[\s،,!\?؟\.\-–—:]*$', r'\1', cleaned, flags=re.IGNORECASE)
            cleaned = re.sub(rf'\\N\s*(?:{fillers}|[a-zA-Z]{{1,2}})[\s،,!\?؟\.\-–—:]*(?:\s+|$)', r'\\N', cleaned, flags=re.IGNORECASE)
            cleaned = re.sub(rf'\\N\s*(?:{fillers}|[a-zA-Z]{{1,2}})[\s،,!\?؟\.\-–—:]*\s*([ء-ي])', r'\\N\1', cleaned, flags=re.IGNORECASE)
            cleaned = re.sub(rf'(?:^|\s+)[\s،,!\?؟\.\-–—:]*(?:{fillers}|[a-zA-Z]{{1,2}})\s*\\N', r'\\N', cleaned, flags=re.IGNORECASE)
            cleaned = re.sub(rf'([ء-ي])[\s،,!\?؟\.\-–—:]*(?:{fillers}|[a-zA-Z]{{1,2}})\s*\\N', r'\1\\N', cleaned, flags=re.IGNORECASE)

        def _fix_fused_prefix_latin(m: re.Match) -> str:
            ar_prefix = m.group(1)
            lat_word = m.group(2)
            return ar_prefix + cls.transliterate_name_to_arabic(lat_word, mid_word=True)

        # Process each \N segment independently so bilingual subtitles (English\NArabic) keep non-Arabic segments intact
        segments = re.split(r'(\\N)', cleaned)
        processed_segments: List[str] = []
        for idx, seg in enumerate(segments):
            if idx % 2 == 1:
                processed_segments.append(seg)
                continue
            if not seg or not re.search(r'[ء-ي]', seg):
                processed_segments.append(seg)
                continue

            # Transliterate Japanese honorifics attached with hyphen within Arabic segments
            seg = re.sub(r'[\-–—]+(?:kun|kûn)\b', '-كون', seg, flags=re.IGNORECASE)
            seg = re.sub(r'[\-–—]+(?:san|sân)\b', '-سان', seg, flags=re.IGNORECASE)
            seg = re.sub(r'[\-–—]+(?:chan|chân)\b', '-تشان', seg, flags=re.IGNORECASE)
            seg = re.sub(r'[\-–—]+(?:sama|sâma)\b', '-ساما', seg, flags=re.IGNORECASE)
            seg = re.sub(r'[\-–—]+(?:senpai|sempai)\b', '-سينباي', seg, flags=re.IGNORECASE)
            seg = re.sub(r'[\-–—]+(?:sensei)\b', '-سينسي', seg, flags=re.IGNORECASE)
            seg = re.sub(r'[\-–—]+(?:dono)\b', '-دونو', seg, flags=re.IGNORECASE)
            seg = re.sub(r'[\-–—]+(?:tan)\b', '-تان', seg, flags=re.IGNORECASE)

            # Fix fused Arabic prefix + Latin name/word (e.g. لتakeru -> لتاكيرو, بAdam -> بادام)
            seg = re.sub(r'([ء-ي]+)([a-zA-Z]+)', _fix_fused_prefix_latin, seg)
            seg = re.sub(rf'^\s*(?:{fillers}|[a-zA-Z]{{1,2}})[\s،,!\?؟\.\-–—:]+\s*([ء-ي])', r'\1', seg, flags=re.IGNORECASE)
            seg = re.sub(rf'([ء-ي\.\?!،])\s+(?:{fillers}|[a-zA-Z]{{1,2}})[؟!\.]*\s*$', r'\1', seg, flags=re.IGNORECASE)
            seg = re.sub(r'\s+[a-zA-Z]$', '', seg)

            # Restrict automatic transliteration to Title-Case character/vocative/honorific names only
            def _fix_standalone_name(m: re.Match) -> str:
                word = m.group(0)
                if word.lower() in ('n', 'h'):
                    return word
                if re.fullmatch(r'[A-Z]{2,5}s?', word):
                    return word
                if word.lower() in cls._TECH_BRANDS_LOWER:
                    return word
                if re.search(r'[a-z][A-Z]', word):
                    return word
                if not word[0].isupper():
                    return word

                before_ctx = seg[max(0, m.start() - 16):m.start()]
                after_ctx = seg[m.end():m.end() + 14]
                has_vocative = bool(re.search(r'(?:^|\s|[،,!؟\.\-"])(?:يا|أيها|أيتها)\s+$', before_ctx))
                has_honorific = bool(
                    re.match(
                        r'^[\-–—]+(?:كون|سان|تشان|ساما|سينباي|سينسي|دونو|تان|kun|kûn|san|sân|chan|chân|sama|sâma|senpai|sempai|sensei|dono|tan)(?!\w)',
                        after_ctx,
                        flags=re.IGNORECASE,
                    )
                )
                is_known_speaker = word.lower() in known_names_lower
                if has_vocative or has_honorific or is_known_speaker:
                    return cls.transliterate_name_to_arabic(word)
                return word

            seg = re.sub(r'(?<!\\)\b([A-Za-z\u00C0-\u024F]{2,})\b', _fix_standalone_name, seg)
            processed_segments.append(seg)

        cleaned = "".join(processed_segments)

        # Remove empty or corrupted tags: {}, {\}, { }
        cleaned = re.sub(r'\{\s*\\?\s*\}', '', cleaned)

        return cleaned

    @classmethod
    def clean_stray_latin(cls, text: str, known_names: Optional[Iterable[str]] = None) -> str:
        r"""Backwards-compatible wrapper calling SDH cleaner and stray Latin filler cleaner."""
        text = cls.clean_sdh_and_sound_effects(text)
        return cls.clean_stray_latin_and_fillers(text, known_names=known_names)

    @staticmethod
    def clean_ass_whitespace_and_newlines(text: str) -> str:
        r"""
        Cleans ASS linebreaks and whitespace:
        - Normalizes \n to \N
        - Removes leading/trailing \N (including before/after tags)
        - Collapses duplicate \N\N
        - Cleans spaces adjacent to \N (avoiding awkward rendering indents)
        - Removes trailing backslashes
        """
        if not text:
            return ""

        res = text.replace(r'\n', r'\N')
        # Remove spaces around \N
        res = re.sub(r'\s*\\N\s*', r'\\N', res)
        # Collapse multiple \N
        res = re.sub(r'(?:\\N)+', r'\\N', res)

        # Remove dangling \N at the start (even if preceded by tags)
        res = re.sub(r'^((\s*(?:___ASS_TAG_\d+___|\{\\[^}]*\}))*\s*)\\N\s*', r'\1', res)
        # Remove dangling \N at the end (even if followed by tags)
        res = re.sub(r'\s*\\N\s*((\s*(?:___ASS_TAG_\d+___|\{\\[^}]*\}))*\s*)$', r'\1', res)

        # Remove \N at absolute beginning or end
        res = re.sub(r'^(?:\\N)+', '', res)
        res = re.sub(r'(?:\\N)+$', '', res)
        # Remove trailing slashes
        res = re.sub(r'[\\/]+$', '', res)
        # Collapse double horizontal spaces
        res = re.sub(r'[ \t]+', ' ', res).strip()

        return res

    @staticmethod
    def normalize_arabic_punctuation(text: str) -> str:
        r"""
        Normalizes ASCII punctuation to Arabic standards when adjacent to Arabic text.
        Converts ',' -> '،', '?' -> '؟', ';' -> '؛'.
        Cleans excessive repeated punctuation while preserving '...' and '؟!'.
        """
        if not text:
            return text

        res = text
        # If line contains Arabic characters, normalize all ? to ؟ and , to ،
        if re.search(r'[ء-ي]', res):
            res = res.replace('?', '؟')
            # Comma: English ',' to Arabic '،' except inside numbers like 1,000
            res = re.sub(r'(?<!\d),(?!\d)', '،', res)
            # Semicolon: ';' to '؛'
            res = res.replace(';', '؛')

        # Fix combinations of ?! or !? or ؟! or !؟ to standard Arabic interrobang '؟!':
        res = re.sub(r'[؟]+!+|!+[؟]+', '؟!', res)

        # Fix repeated punctuation: '،،+' -> '،', '؟؟+' -> '؟', '!!+' -> '!'
        res = re.sub(r'[,،]\s*[,،]+', '،', res)
        res = re.sub(r'[?؟]\s*[?؟]+', '؟', res)
        res = re.sub(r'!{2,}', '!', res)
        res = re.sub(r'\.{4,}', '...', res)
        res = re.sub(r'(?<=[ء-ي])\s*\.\.(?!\.)', '...', res)

        # Remove leading punctuation marks (e.g. ,مرحباً or ؟أهلاً)
        res = re.sub(r'^[،؛؟\.\,\;\:\s]+', '', res)

        # Clean spaces before punctuation
        res = re.sub(r'\s+([،؛؟!\.])', r'\1', res)

        # Comma following quotes or brackets: e.g. "مرحباً", -> "مرحباً"،
        res = re.sub(r'([\"\'»”\]\)])\s*,\s*', r'\1، ', res)

        return res

    @staticmethod
    def fix_orphan_quotes(text: str) -> str:
        r"""
        Removes lonely unbalanced quotation marks from a line.
        Checks straight quotes, smart curly quotes, and guillemets.
        """
        if not text:
            return text

        res = text
        # Straight quotes
        if res.count('"') % 2 != 0:
            res = re.sub(r'"(?=[؟!\.\s]*$)', '', res)
            if res.count('"') % 2 != 0:
                res = re.sub(r'^\s*"', '', res)
            if res.count('"') % 2 != 0:
                res = res.replace('"', '')

        # Smart quotes
        for q in ['”', '“', '«', '»', '‘', '’']:
            if res.count(q) % 2 != 0:
                res = re.sub(re.escape(q) + r'(?=[؟!\.\s]*$)', '', res)
                if res.count(q) % 2 != 0:
                    res = re.sub(r'^\s*' + re.escape(q), '', res)
                if res.count(q) % 2 != 0:
                    res = res.replace(q, '')

        return res

    @classmethod
    def clean_dialogue_dashes(cls, text: str, original_text: str = "") -> str:
        r"""
        Normalizes dialogue hyphens:
        - Converts repetitive dashes (-- , — , – ) to standard subtitle dash '- '
        - Multi-speaker lines: If original had two speaker dashes (- Line 1\N- Line 2) and translation has \N,
          restores any missing dialogue dash.
        - Single-speaker lines: If line starts with '- ' without a second speaker, removes the dash.
        """
        if not text:
            return ""

        res = text
        # Normalize double dash or em-dash at start of lines or after \N to '- '
        res = re.sub(r'(^|\\N)\s*[—–-]{2,}\s*', r'\1- ', res)
        res = re.sub(r'[—–]', '-', res)

        # If original had dual dashes (- ... \N- ...) and translation has \N, restore missing dashes
        if original_text and r'\N' in original_text and r'\N' in res:
            orig_parts = original_text.split(r'\N')
            orig_dashes = [bool(re.search(r'^\s*\{\\[^}]*\}\s*-\s*|^\s*-\s*', p)) for p in orig_parts]
            if len(orig_dashes) >= 2 and all(orig_dashes):
                trans_parts = res.split(r'\N')
                new_trans_parts = []
                for tp in trans_parts:
                    has_dash = bool(re.search(r'^\s*(\{\\[^}]*\}|___ASS_TAG_\d+___)*\s*-\s*', tp))
                    if not has_dash:
                        # Prepend dash after any leading tags
                        tp = re.sub(r'^((\s*(?:___ASS_TAG_\d+___|\{\\[^}]*\}))*\s*)(.*)', r'\1- \3', tp)
                    new_trans_parts.append(tp)
                res = r'\N'.join(new_trans_parts)
                return res

        # If line starts with '- ' (or preceded by tags) and there is NO second speaker, strip leading dash
        if r'\N-' not in res and r'\N -' not in res:
            res = re.sub(r'^((\s*(?:___ASS_TAG_\d+___|\{\\[^}]*\}))*\s*)-\s*', r'\1', res)

        return res

    @staticmethod
    def purge_corrupt_tags(text: str) -> str:
        r"""
        Purges empty, conflicting, or meaningless tag sequences:
        - {\i1}{\i0}, {\i0}{\i1}, {\b1}{\b0}, {\b0}{\b1}, {\u1}{\u0}, {\u0}{\u1} (even with whitespace)
        - Redundant duplicate tags: {\i1}{\i1} -> {\i1}, {\i0}{\i0} -> {\i0}
        - Standalone closing tags at start of text: {\i0}, {\b0}
        - Standalone opening tags at end of text: {\i1}, {\b1}
        - Empty tag braces: {}, {\}, { }
        """
        if not text:
            return ""
        res = text
        # Remove empty tag pairs (including with whitespace between them)
        res = re.sub(r'\{\\i[01]\}\s*\{\\i[01]\}', '', res)
        res = re.sub(r'\{\\b[01]\}\s*\{\\b[01]\}', '', res)
        res = re.sub(r'\{\\u[01]\}\s*\{\\u[01]\}', '', res)
        res = re.sub(r'\{\s*\\?[01]?\s*\}', '', res)
        # Remove standalone closing tags at beginning of line (e.g. {\i0})
        res = re.sub(r'^(?:\{\\[ibu]0\}\s*)+', '', res)
        # Remove standalone opening tags at end of line (e.g. {\i1})
        res = re.sub(r'(?:\{\\[ibu]1\}\s*)+$', '', res)
        # Deduplicate identical adjacent tags and multi-tag sequences
        res = re.sub(r'(\{\\[^}]+\})\s*\1+', r'\1', res)
        res = re.sub(r'((?:\{\\[^}]+\}){2,})\s*\1+', r'\1', res)
        # Normalize tag order at beginning: positioning tags ({\an...}) should precede style tags ({\i...})
        res = re.sub(r'^(\{\\i[01]\})(\{\\an\d+\})', r'\2\1', res)
        return res

    @classmethod
    def balance_ass_linebreaks(cls, translated_text: str, original_text: str = "", max_cpl: int = 52) -> str:
        r"""
        Intelligently balances ASS linebreaks (\N):
        1. If the original line had \N and translation collapsed into 1 line, restores natural break.
        2. Smart Arabic CPL Wrapping: Even if the original was single-line, wraps long dialogue
           exceeding `max_cpl` (default 52 visible chars) across natural punctuation, conjunctions,
           or balanced midpoint whitespace so viewers can read comfortably on screen.
        """
        if not translated_text or r'\N' in translated_text:
            return translated_text

        orig_has_break = bool(original_text and r'\N' in original_text)
        trans_clean = re.sub(r'\{[^{}]*\}', '', translated_text).replace('\u200f', '').strip()

        if not orig_has_break:
            # Skip CPL wrapping for short lines or positioned graphic typeset signs
            if len(trans_clean) <= max_cpl:
                return translated_text
            if re.search(r'\\(?:pos|move|org|i?clip|p[1-9])\b', translated_text):
                return translated_text

            # Separate leading/trailing outer ASS override tags so \N stays inside visible dialogue
            m_lead = re.match(r'^((?:\{[^{}]*\}\s*)*)(.*)$', translated_text)
            lead_tags = m_lead.group(1) if m_lead else ""
            rem = m_lead.group(2) if m_lead else translated_text
            m_trail = re.search(r'((?:\s*\{[^{}]*\})*)$', rem)
            trail_tags = m_trail.group(1) if m_trail else ""
            body = rem[:m_trail.start(1)] if m_trail else rem
            if not body.strip() or ' ' not in body.strip():
                return translated_text

            body_len = len(body)
            target_mid = body_len // 2

            # Priority 1: Natural punctuation split inside middle window
            punct_matches = [
                m for m in re.finditer(r'([!؟\.\،؛:])\s+', body)
                if 0.22 * body_len <= m.end(1) <= 0.80 * body_len
            ]
            if punct_matches:
                best_m = min(
                    punct_matches,
                    key=lambda m: abs(m.end(1) - target_mid) * (0.65 if m.group(1) in ('!', '.', '؟') else 0.85),
                )
                split_body = body[:best_m.end(1)] + r'\N' + body[best_m.end(0):].lstrip()
                return f"{lead_tags}{split_body}{trail_tags}"

            # Priority 2: Arabic conjunction phrases / clause boundaries
            conj_matches = [
                m for m in re.finditer(r'\s+(?=(?:لكن|بينما|لأن|عندما|حيث|ثم|أو|بل|حتى|إلا|إذا)\b|و[ء-ي]{2,})', body)
                if 0.25 * body_len <= m.start() <= 0.78 * body_len
            ]
            if conj_matches:
                best_c = min(conj_matches, key=lambda m: abs(m.start() - target_mid))
                split_body = body[:best_c.start()] + r'\N' + body[best_c.end():].lstrip()
                return f"{lead_tags}{split_body}{trail_tags}"

            # Priority 3: Nearest whitespace around midpoint
            spaces = [m.start() for m in re.finditer(r'\s+', body) if 0.22 * body_len <= m.start() <= 0.78 * body_len]
            if spaces:
                best_sp = min(spaces, key=lambda s: abs(s - target_mid))
                split_body = body[:best_sp] + r'\N' + body[best_sp:].lstrip()
                return f"{lead_tags}{split_body}{trail_tags}"
            return translated_text

        orig_clean = re.sub(r'\{[^{}]*\}', '', original_text).strip()

        # If translation is short and has no dialogue dashes, keep single line
        if len(trans_clean) < 18 and not any(p in trans_clean for p in ['!', '؟', '?', '.', '،', '-']):
            return translated_text

        first_orig_split = orig_clean.find(r'\N')
        target_ratio = first_orig_split / len(orig_clean) if len(orig_clean) > 0 and first_orig_split > 0 else 0.5
        target_idx = int(target_ratio * len(translated_text))

        # 1. Dialogue dash: ' - ' -> '\N- '
        dash_match = re.search(r'([^\\])\s+-\s+', translated_text)
        if dash_match:
            pos = dash_match.start(0) + 1
            return translated_text[:pos] + r'\N- ' + translated_text[dash_match.end(0):]

        # 2. Natural punctuation (!, ؟, ., :, ،, ؛)
        punct_matches = list(re.finditer(r'([!؟\.\:،؛])\s+', translated_text))
        if punct_matches:
            best_m = None
            best_score = float('inf')
            for m in punct_matches:
                pos = m.end(1)
                dist = abs(pos - target_idx)
                if m.group(1) in ('!', '.', '؟'):
                    dist *= 0.65
                if dist < best_score:
                    best_score = dist
                    best_m = m
            if best_m:
                pos = best_m.end(1)
                return translated_text[:pos] + r'\N' + translated_text[best_m.end(0):]

        # 3. Space closest to target_idx within middle 50%
        spaces = [m.start() for m in re.finditer(r'\s+', translated_text) if 0.25 * len(translated_text) <= m.start() <= 0.75 * len(translated_text)]
        if spaces:
            best_space = min(spaces, key=lambda s: abs(s - target_idx))
            return translated_text[:best_space] + r'\N' + translated_text[best_space:].lstrip()

        return translated_text

    @classmethod
    def restore_segmented_tags(cls, healed: str, original_text: str) -> str:
        """
        Restores positioning and override tags per-segment when linebreaks (\\N) are present,
        preventing tags from a secondary segment (e.g. {\\r\\an2}) from overriding the first segment ({\\an8}).
        """
        if not original_text or r'\N' not in original_text or r'\N' not in healed:
            return healed

        orig_parts = original_text.split(r'\N')
        healed_parts = healed.split(r'\N')

        if len(orig_parts) != len(healed_parts):
            return healed

        new_healed_parts = []
        for o_part, h_part in zip(orig_parts, healed_parts):
            seg_tags = re.findall(r'\{\\[^}]*\}', o_part)
            pos_tags = [t for t in seg_tags if re.search(r'\\(an\d+|pos|move|fad|fade|org|clip|p[1-9]|c&|fn|fs|i[01]|b[01]|u[01])', t)]
            p_res = h_part
            for pt in reversed(pos_tags):
                if pt not in p_res:
                    p_res = pt + p_res
            new_healed_parts.append(p_res)

        return r'\N'.join(new_healed_parts)

    @classmethod
    def heal(
        cls,
        raw_translated: str,
        original_text: str = "",
        options: Optional[Dict[str, Any]] = None,
        known_names: Optional[Iterable[str]] = None,
    ) -> str:
        r"""
        Runs the complete multi-layer strict purification and healing pipeline:
        1. Invisible & Unicode Artifacts stripping.
        2. Markdown & HTML Artifacts Elimination.
        3. Absolute ASS Tag Protection & Immunity.
        4. LLM Labels & Prefixes elimination.
        5. SDH Audio Descriptions & Foreign Sound Effects removal.
        6. Stray Latin Letters & Fillers cleaning (Arabic target only; strips stray CJK/Cyrillic for all).
        7. Arabic Punctuation Normalization & Grammar (Arabic target only).
        8. ASS Line Break (\N) Normalization.
        9. Orphan Quotation Marks elimination.
        10. Dialogue Dash Normalization.
        11. Restoration of protected tags and original formatting tags.
        12. Smart positioning and style tags recovery.
        13. Intelligent subtitle line break (\N) balancing.
        14. Purging empty and corrupt tags.
        """
        if not raw_translated:
            return raw_translated

        opts: Dict[str, Any] = {
            "arabic_punct": True,
            "latin_clean": True,
            "quote_fix": True,
            "protect_tags": True,
            "sdh_clean": True,
            "prefix_clean": True,
            "dash_clean": True,
            "markdown_clean": True,
            "balance_linebreaks": True,
            "target_lang": "ar",
        }
        if options:
            opts.update(options)

        is_target_ar = cls._is_arabic_target(opts.get("target_lang", "ar"))

        # 1. Clean invisible unicode artifacts
        cleaned = cls.clean_invisible_and_unicode_artifacts(raw_translated)

        # 2. Clean Markdown & HTML artifacts (converts <br> to \N, <i> to {\i1}, etc.)
        if opts.get("markdown_clean", True):
            cleaned = cls.clean_markdown_and_html(cleaned)

        # 3. Protect ASS tags in translated text
        protected, tags = cls.protect_ass_tags(cleaned)
        _, orig_tags = cls.protect_ass_tags(original_text) if original_text else ("", [])

        # 4. Clean LLM label prefixes & line numbering
        if opts.get("prefix_clean", True):
            protected = cls.clean_llm_labels_and_prefixes(protected)

        # 5. Clean SDH audio descriptions & bracketed sound effects
        if opts.get("sdh_clean", True):
            protected = cls.clean_sdh_and_sound_effects(protected)

        # 6. Clean stray Latin letters/fillers for Arabic target, or only strip CJK/Cyrillic otherwise
        if opts.get("latin_clean", True):
            if is_target_ar:
                protected = cls.clean_stray_latin_and_fillers(protected, known_names=known_names)
            else:
                protected = re.sub(r'[\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af\u0400-\u04ff]+', '', protected)
                protected = re.sub(r'\{\s*\\?\s*\}', '', protected)

        # 7. Arabic punctuation & grammar rules apply strictly to Arabic targets
        if is_target_ar:
            if opts.get("arabic_punct", True):
                protected = cls.normalize_arabic_punctuation(protected)
            protected = cls.fix_arabic_grammar_and_spelling(protected)

        # 8. Clean ASS whitespace and linebreaks
        protected = cls.clean_ass_whitespace_and_newlines(protected)

        # 9. Fix orphan quotation marks
        if opts.get("quote_fix", True):
            protected = cls.fix_orphan_quotes(protected)

        # 10. Clean dialogue dashes (preserves/restores multi-speaker dashes, removes solitary single-line dash)
        if opts.get("dash_clean", True):
            protected = cls.clean_dialogue_dashes(protected, original_text=original_text)

        # 11. Restore protected ASS tags
        healed = cls.restore_ass_tags(protected, tags)

        # 11b. Pre-purge any corrupt or empty tag pairs before formatting restoration
        healed = cls.purge_corrupt_tags(healed)

        # 12. Smart restoration of original formatting tags & positioning
        if orig_tags and opts.get("protect_tags", True):
            # A. If original was wrapped in italics ({\i1}...{\i0}):
            orig_has_i1 = any(r'\i1' in t for t in orig_tags)
            orig_has_i0 = any(r'\i0' in t for t in orig_tags)
            if orig_has_i1 and r'\i1' not in healed:
                healed = f"{{\\i1}}{healed}{{\\i0}}"
            elif orig_has_i0 and r'\i0' not in healed:
                healed = f"{healed}{{\\i0}}"

            # B. If original had positioning tags ({\an8}, {\pos(...)}) that are missing:
            # If line has \N in both original and healed, segmented tag restoration (step 13b) will assign them.
            if r'\N' not in original_text or r'\N' not in healed:
                pos_tags = [t for t in orig_tags if re.search(r'\\(an\d+|pos|move|fad|fade|org|clip)', t)]
                for pt in reversed(pos_tags):
                    if pt not in healed:
                        healed = pt + healed

        # 13. Smart restoration of balanced linebreaks (\N) & CPL <= 52 wrapping
        if opts.get("balance_linebreaks", True):
            healed = cls.balance_ass_linebreaks(healed, original_text or "")

        # 13b. Segmented tag restoration (restores positioning per segment when \N is present)
        if original_text and opts.get("protect_tags", True) and r'\N' in original_text and r'\N' in healed:
            healed = cls.restore_segmented_tags(healed, original_text)

        # 13c. Sound effect & cue delimiter spacing
        if is_target_ar:
            healed = cls.separate_sfx_and_audio_cues(healed)

        # 14. Purge any corrupt or empty tag pairs (e.g. {\i1}{\i0}, {})
        healed = cls.purge_corrupt_tags(healed)

        # 15. Final whitespace normalization
        healed = cls.clean_ass_whitespace_and_newlines(healed)

        # 16. Optional Unicode RLM (\u200f) RTL BiDi anchoring (Arabic target only)
        if is_target_ar and opts.get("rtl_bidi", False):
            healed = cls.ensure_rtl_bidi(healed)

        return healed
