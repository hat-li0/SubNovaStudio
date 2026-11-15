from typing import List, Optional
from app.models.provider import ChatMessage

def _is_arabic_target(target_lang: Optional[str]) -> bool:
    t = (target_lang or "ar").strip().lower()
    return not t or any(k in t for k in ("ar", "arabic", "عرب"))


class PromptBuilder:
    """Builds dry, strict, programmatic chat messages for local and cloud LLM subtitle translation."""

    def build_prompt(
        self,
        source_lang: str,
        target_lang: str,
        current_subtitles: str,
        previous_context: str = "",
        next_context: str = "",
        characters_context: str = "",
        glossary_context: str = "",
        custom_instructions: str = "",
        story_notes: str = "",
        model_name: str = ""
    ) -> List[ChatMessage]:

        is_target_ar = _is_arabic_target(target_lang)
        is_allam = is_target_ar and ("allam" in (model_name or "").lower())
        if is_allam:
            system_content = f"""أنت مترجم شارات وأنمي محترف وخبير في الترجمة إلى اللغة العربية الفصحى البليغة المعبرة درامياً.
مهمتك: ترجمة أسطر الحوار التالية من {source_lang} إلى العربية الفصحى بسلاسة وبلاغة سينمائية عالية.

القواعد الصارمة:
1. التزم حصراً بصيغة المخرج: `[الرقم] النص المترجم` سطراً بسطر.
⚠️ تحذير إلزامي: اكتب رقم السطر الفعلي المعطى لك بدقة داخل القوسين مثل [51] أو [128]، وإياك تماماً أن تترك القوسين فارغين هكذا [ ] أو []!
2. أخرج الحوار المترجم فقط دون أي مقدمات، اعتذار، أو تعليقات توضيحية جانبية.
3. ترجم كل الكلام إلى حوار عربي فصيح وطبيعي. لا تترك أي عبارات أجنبية أو كلمات إنجليزية. عرب الألقاب (-سان، -تشان، -كون، سينباي).
4. استخدم علامات الترقيم العربية حصراً: علامة الاستفهام (؟)، الفاصلة العربية (،)، المنقوطة (؛).
5. النصوص المرسلة إليك نقية تماماً من وسوم ومؤثرات التنسيق؛ ترجم الحوارات واللوحات مباشرة دون القلق بشأن الأكواد، مع الحفاظ على فواصل الأسطر \\N فقط.
6. التزم بجنس الشخصيات وسياق الخطاب (أنتِ، فعلتِ، اذهبي بكسرة صريحة).
7. حافظ على رقم كل سطر داخل القوسين [الرقم] دون أي تغيير أو حذف.
8. ⚠️ قاعدة التوقيت وتزامن النطق بالمللي ثانية: ممنوع منعاً باتاً دمج سطرين في سطر واحد حتى لو كانا جملة واحدة متصلة! ترجم كل سطر في سطره المستقل مع رقمه المعطى له حصراً لمطابقة توقيت الشاشة تماماً.

مثال:
[51] - Where are you going?\\N- I am going home, Kaori-san.
[52] Wait, are you okay?

الخرج:
[51] - إلى أين أنتِ ذاهبة؟\\N- أنا عائد إلى المنزل يا كاوري-سان.
[52] انتظر، هل أنت بخير؟"""
        elif is_target_ar:
            system_content = f"""You are an elite, master anime and series subtitle translator.
Translate the following subtitle lines from {source_lang} into fluent, natural Modern Standard Arabic (فصحى بليغة معبرة درامياً).

CRITICAL RULES:
1. Output format must strictly be `[ID] Translated text` line by line.
2. Output ONLY the translated Arabic dialogue. NEVER add preambles, greetings, or prefixes (e.g. do NOT write "المترجم:" or "الترجمة:" or "Here is...").
3. NEVER add explanations, notes, or commentary in parentheses (e.g. do NOT write "(المخاطب فتاة)" or "(المتحدث غاضب)").
4. Translate all speech completely and exclusively into natural Arabic dialogue. NEVER output Chinese, Japanese (kanji/kana), or mixed foreign phrases. NEVER leave stray English/foreign words or fillers (e.g. "yeah", "hey", "wait", "oh", "huh", "okay" -> ترجمها أو احذفها حسب المعنى). Transliterate Japanese honorifics (-kun -> -كون, -san -> -سان, -chan -> -تشان, Senpai -> سينباي).
5. Use proper Arabic punctuation exclusively: Arabic question mark (؟), Arabic comma (،), Arabic semicolon (؛). Never use English (?, , ;). Punctuation attaches directly to words without spaces.
6. For multi-speaker lines with dialogue dashes (e.g. `- ...\\N- ...`), preserve `- ` on each speaker line. For single-speaker lines, do NOT add a leading dash.
7. All styling and effect tags have been safely isolated. Translate all speech and on-screen sign texts directly and naturally, preserving only multi-line breaks \\N.
8. Gender & Grammar: Strictly follow character genders. For female addressing use Kasrah (أنتِ، فعلتِ، قلتِ، اذهبي), NEVER improper Ya'a (أنتي، فعلتي).
9. Translate every line and keep the exact numeric [ID] unchanged.
10. CRITICAL TIMING & 1-TO-1 AUDIO SYNCHRONIZATION: NEVER merge two lines into one even if they form a single continuous sentence! Every single subtitle line must be translated on its own line with its exact [ID]. Subtitle display timing is anchored to each specific line; merging lines ruins audio-video synchronization.

Input format:
[1] - Where are you going?\\N- I am going home, Kaori-san.
[2] Wait, are you okay?

Output format:
[1] - إلى أين أنتِ ذاهبة؟\\N- أنا عائد إلى المنزل يا كاوري-سان.
[2] انتظر، هل أنت بخير؟"""
        else:
            eff_target = target_lang.strip() or "English"
            system_content = f"""You are an elite, master anime and series subtitle translator.
Translate the following subtitle lines from {source_lang} into fluent, natural {eff_target}.

CRITICAL RULES:
1. Output format must strictly be `[ID] Translated text` line by line.
2. Output ONLY the translated {eff_target} dialogue. NEVER add preambles, greetings, translator prefixes, or meta commentary.
3. NEVER add explanations or notes in parentheses (e.g. do NOT write "(speaker is female)").
4. Translate all speech completely and naturally into {eff_target}. NEVER leave untranslated source-language dialogue or mixed scripts unless referring to canonical proper names/honorifics.
5. Use standard {eff_target} punctuation cleanly attached to words.
6. For multi-speaker lines with dialogue dashes (e.g. `- ...\\N- ...`), preserve `- ` on each speaker line. For single-speaker lines, do NOT add a leading dash.
7. All styling and effect tags have been safely isolated. Translate all speech and on-screen sign texts directly and naturally, preserving only multi-line breaks \\N.
8. Follow character genders, pronouns, and personality/style notes accurately.
9. Translate every line and keep the exact numeric [ID] unchanged.
10. CRITICAL TIMING & 1-TO-1 AUDIO SYNCHRONIZATION: NEVER merge two lines into one even if they form a single continuous sentence! Every single subtitle line must be translated on its own line with its exact [ID].

Input format:
[1] - どこへ行くの？\\N- 家に帰るよ、香織さん。
[2] 待って、大丈夫？

Output format:
[1] - Where are you going?\\N- I'm going home, Kaori-san.
[2] Wait, are you okay?"""

        if custom_instructions:
            system_content += f"\n\nADDITIONAL INSTRUCTIONS:\n{custom_instructions}"
            
        user_parts = []
        
        # Reference & context blocks (isolated for reference only)
        context_blocks = []
        if is_allam:
            if story_notes:
                context_blocks.append(f"[ملاحظات القصة والمشهد]:\n{story_notes}")
            if characters_context:
                context_blocks.append(f"[الشخصيات وجنس الخطاب]:\n{characters_context}")
            if glossary_context:
                context_blocks.append(f"[معجم المصطلحات]:\n{glossary_context}")
            if previous_context:
                context_blocks.append(f"[الحوار السابق كمرجع]:\n{previous_context}")
            if next_context:
                context_blocks.append(f"[الحوار اللاحق كمرجع]:\n{next_context}")
                
            if context_blocks:
                user_parts.append("### مراجع سياقية للاطلاع فقط (ممنوع منعاً باتاً ترجمة هذا القسم):\n" + "\n\n".join(context_blocks))
                
            user_parts.append(f"الأسطر المطلوب ترجمتها الآن حصراً (ابدأ الترجمة من هنا وتوقف عند نهايتها):\n{current_subtitles}\n--- نهاية الأسطر المطلوب ترجمتها (توقف هنا ولا تترجم أي شيء إضافي) ---")
        else:
            if story_notes:
                context_blocks.append(f"[Story & Scene Notes]:\n{story_notes}")
            if characters_context:
                context_blocks.append(f"[Characters & Genders]:\n{characters_context}")
            if glossary_context:
                context_blocks.append(f"[Glossary & Terminology]:\n{glossary_context}")
            if previous_context:
                context_blocks.append(f"[Previous Dialogue for Reference]:\n{previous_context}")
                
            if context_blocks:
                user_parts.append("### REFERENCE ONLY (DO NOT TRANSLATE THIS SECTION):\n" + "\n\n".join(context_blocks))
                
            # Actual Subtitles to Translate
            user_parts.append(f"CURRENT SUBTITLES TO TRANSLATE:\n{current_subtitles}")
            
            if next_context:
                user_parts.append(f"### UPCOMING CONTEXT FOR REFERENCE:\n{next_context}")
            
        user_content = "\n\n".join(user_parts)
        
        return [
            ChatMessage(role="system", content=system_content),
            ChatMessage(role="user", content=user_content)
        ]

    def build_improvement_prompt(
        self,
        source_lang: str,
        target_lang: str,
        current_subtitles: str,
        characters_context: str = "",
        glossary_context: str = "",
        story_notes: str = "",
        custom_instructions: str = "",
        model_name: str = ""
    ) -> List[ChatMessage]:
        """
        Builds the Subtitle Improvement prompt with dry programmatic constraints.
        No conversational roleplay or modification reports.
        """
        is_target_ar = _is_arabic_target(target_lang)
        is_allam = is_target_ar and ("allam" in (model_name or "").lower())
        if is_allam:
            system_content = f"""أنت مدقق ومحرر لغوي محترف لترجمة الأنمي والمسلسلات باللغة العربية الفصحى.
مهمتك: صقل وتدقيق أسطر الترجمة التالية إلى لغة عربية فصحى راقية، بليغة، دقيقة درامياً وخالية تماماً من الركاكة والأخطاء.

القواعد الصارمة:
1. صيغة المخرج حصراً: `[الرقم] النص المصقول` سطراً بسطر مع كتابة رقم السطر كما هو داخل القوسين [51], [52].
⚠️ تحذير إلزامي: اكتب رقم السطر بدقة بين القوسين، وإياك تماماً أن تترك القوسين فارغين هكذا [ ] أو []!
2. أخرج النص المصقول فقط دون أي تقارير، شروحات، مقارنات، أو مقدمات.
3. التزم بعلامات الترقيم العربية (؟ ، ؛) وقواعد التأنيث الدقيقة (أنتِ، فعلتِ).
4. النصوص نقية من وسوم التنسيق؛ صقل التراكيب مباشرة وحافظ على فواصل الأسطر \\N فقط.
5. لا تغير أرقام الأسطر [الرقم] دون أي استثناء."""
        elif is_target_ar:
            system_content = f"""You are an elite, master Arabic subtitle editor and localization expert.
Refine and polish the following Arabic subtitle lines into immaculate, dramatic Modern Standard Arabic (فصحى راقية، بليغة، دقيقة درامياً وخالية تماماً من الركاكة والأخطاء).

CRITICAL RULES:
1. Output format must strictly be `[ID] Refined Arabic text` line by line.
2. Output ONLY the refined Arabic text. NEVER write reports, comparison summaries, or explanations of what was changed.
3. NEVER add prefixes (e.g. "المترجم:", "المصقول النهائي:", "التعديلات:") or notes in parentheses (e.g. "(المخاطب فتاة)").
4. Purify the Arabic dialogue: eliminate literal machine translation, fix clumsy phrasing into natural speech.
5. Standardize all punctuation to Arabic: Arabic question mark (؟), Arabic comma (،), Arabic semicolon (؛). No English punctuation (?, , ;) or spaces before punctuation.
6. Ensure grammatical perfection: strictly verify feminine addressing (أنتِ، فعلتِ، اذهبي) without writing improper Ya'a (أنتي، فعلتي).
7. For multi-speaker dialogue (`- ...\\N- ...`), ensure both lines have `- `. For single-speaker dialogue, do not add a leading dash.
8. All styling and effect tags have been safely isolated. Refine speech and on-screen texts naturally, preserving only multi-line breaks \\N.
9. Keep every numeric [ID] unchanged.

Input format:
[1] هل انتي بخير؟
[2] - نعم لا تقلقين\\N- حسنا

Output format:
[1] هل أنتِ بخير؟
[2] - أجل، لا تقلقي\\N- حسناً."""
        else:
            eff_target = (target_lang or "English").strip()
            system_content = f"""You are an elite, master {eff_target} subtitle editor and localization expert.
Refine and polish the following {eff_target} subtitle lines into immaculate, natural, dramatic {eff_target} dialogue.

CRITICAL RULES:
1. Output format must strictly be `[ID] Refined {eff_target} text` line by line.
2. Output ONLY the refined {eff_target} text. NEVER write reports, comparison summaries, or explanations of what was changed.
3. NEVER add prefixes or meta commentary in parentheses.
4. Polish awkward phrasing into crisp, idiomatic {eff_target} matching speaker tone and gender context.
5. Standardize punctuation cleanly for {eff_target}.
6. For multi-speaker dialogue (`- ...\\N- ...`), ensure both lines keep `- `. For single-speaker dialogue, do not add a leading dash.
7. All styling and effect tags have been safely isolated. Preserve multi-line breaks \\N.
8. Keep every numeric [ID] unchanged.

Input format:
[1] Are you feeling good right now?
[2] - Yes don't worry\\N- Okay then

Output format:
[1] Are you okay?
[2] - Yes, don't worry.\\N- All right."""

        if custom_instructions:
            system_content += f"\n\nADDITIONAL INSTRUCTIONS:\n{custom_instructions}"

        user_parts = []
        context_blocks = []
        if story_notes:
            context_blocks.append(f"[Story & Scene Notes]:\n{story_notes}")
        if characters_context:
            context_blocks.append(f"[Characters & Genders]:\n{characters_context}")
        if glossary_context:
            context_blocks.append(f"[Glossary]:\n{glossary_context}")

        if context_blocks:
            user_parts.append("### REFERENCE ONLY (DO NOT TRANSLATE THIS SECTION):\n" + "\n\n".join(context_blocks))

        user_parts.append(f"### SUBTITLES TO REFINE:\n{current_subtitles}")

        user_content = "\n\n".join(user_parts)

        return [
            ChatMessage(role="system", content=system_content),
            ChatMessage(role="user", content=user_content)
        ]

    def build_proofread_prompt(
        self,
        source_lang: str,
        target_lang: str,
        current_subtitles: str,
        glossary_context: str = "",
    ) -> List[ChatMessage]:
        """Backwards compatible proofread prompt delegating to build_improvement_prompt."""
        return self.build_improvement_prompt(
            source_lang=source_lang,
            target_lang=target_lang,
            current_subtitles=current_subtitles,
            glossary_context=glossary_context
        )
