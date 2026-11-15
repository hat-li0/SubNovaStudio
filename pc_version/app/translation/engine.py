import logging
import asyncio
import re
from typing import Callable, List, Optional, Dict, Tuple, Any, Set
from app.models.subtitle import SubtitleDocument, SubtitleEvent
from app.models.character import CharacterProfile
from app.models.glossary import GlossaryEntry
from app.providers.base import ProviderBase
from app.translation.batcher import TokenBatcher
from app.translation.context import ContextBuilder
from app.translation.prompts import PromptBuilder
from app.translation.response_parser import ResponseParser
from app.translation.validator import PipelineValidator
from app.translation.retry import RetryStrategy
from app.character.resolver import CharacterResolver
from app.storage.checkpoint import CheckpointManager
from app.storage.memory_repo import TranslationMemoryRepository
from app.quality.translation_validator import QualityValidator
from app.quality.healer import SubtitleHealer
from app.core.exceptions import TranslationError
from app.models.provider import ChatMessage

logger = logging.getLogger(__name__)

def remove_orphaned_quotes(text: str) -> str:
    """Removes single unclosed quotation marks from a line."""
    return SubtitleHealer.fix_orphan_quotes(text)

def _is_arabic_target(target_lang: Optional[str]) -> bool:
    t = (target_lang or "ar").strip().lower()
    return not t or any(k in t for k in ("ar", "arabic", "عرب"))


def _build_known_names(document: Optional[SubtitleDocument], characters: Optional[List]) -> Set[str]:
    names: Set[str] = set()
    if document and hasattr(document, "get_speakers"):
        for spk in document.get_speakers():
            if spk:
                names.add(spk.strip())
    for c in (characters or []):
        for attr in ("canonical_name", "first_name", "last_name"):
            val = getattr(c, attr, "")
            if val:
                names.add(str(val).strip())
        for alias in (getattr(c, "aliases", None) or []):
            if alias:
                names.add(str(alias).strip())
    return names


def _merge_healing_options(healing_options: Optional[Dict[str, Any]], target_lang: str) -> Dict[str, Any]:
    opts: Dict[str, Any] = dict(healing_options or {})
    opts["target_lang"] = target_lang
    return opts


def format_character_context(characters: List, target_lang: str = "ar") -> str:
    """Formats character list into token-efficient, clear context for LLM prompt (including style, notes, aliases)."""
    if not characters:
        return ""
    is_target_ar = _is_arabic_target(target_lang)
    lines = []
    for c in characters:
        name = getattr(c, "canonical_name", "") or str(c)
        ar_name = ""
        if is_target_ar:
            raw_ar = getattr(c, "arabic_name", "") or ""
            if not raw_ar and name:
                raw_ar = SubtitleHealer.transliterate_name_to_arabic(name)
            ar_name = f" ({raw_ar})" if raw_ar else ""

        gender_val = "Unknown"
        if hasattr(c, "gender"):
            gender_val = c.gender.value if hasattr(c.gender, "value") else str(c.gender)
        elif hasattr(c, "gender_info"):
            gender_val = c.gender_info.gender.value if hasattr(c.gender_info.gender, "value") else str(c.gender_info.gender)

        extras = []
        if getattr(c, "role", None):
            extras.append(f"Role: {c.role}")
        if is_target_ar and hasattr(c, "get_pronouns"):
            p = c.get_pronouns()
            if p:
                extras.append(f"Pronouns: {p.get('subject', '')}/{p.get('object', '')}")
        aliases = [a for a in (getattr(c, "aliases", None) or []) if a and a != name][:4]
        if aliases:
            extras.append(f"Aliases: {', '.join(aliases)}")
        speech_style = (getattr(c, "speech_style", "") or "").strip()
        if speech_style:
            extras.append(f"Style: {speech_style}")
        translation_notes = (getattr(c, "translation_notes", "") or "").strip()
        if translation_notes:
            extras.append(f"Notes: {translation_notes}")

        extra_str = (", " + ", ".join(extras)) if extras else ""
        lines.append(f"- {name}{ar_name}: Gender={gender_val}{extra_str}")
    return "\n".join(lines)

def format_glossary_context(glossary: List) -> str:
    """Formats glossary list into concise context for LLM prompt."""
    if not glossary:
        return ""
    lines = []
    for g in glossary:
        src = getattr(g, "source_term", "")
        tgt = getattr(g, "target_term", "")
        notes = getattr(g, "notes", "")
        notes_str = f" ({notes})" if notes else ""
        lines.append(f"- {src} -> {tgt}{notes_str}")
    return "\n".join(lines)


class TranslationEngine:
    """
    Main orchestrator for translating, improving, and auto-healing subtitles.
    Supports 2-stage localization pipeline, real-time live preview, and checkpointing.
    """
    
    def __init__(
        self,
        batcher: Optional[TokenBatcher] = None,
        context_builder: Optional[ContextBuilder] = None,
        prompt_builder: Optional[PromptBuilder] = None,
        parser: Optional[ResponseParser] = None,
        validator: Optional[PipelineValidator] = None,
        retry_strategy: Optional[RetryStrategy] = None,
        tm_repo: Optional[TranslationMemoryRepository] = None
    ):
        self.batcher = batcher or TokenBatcher()
        self.context_builder = context_builder or ContextBuilder()
        self.prompt_builder = prompt_builder or PromptBuilder()
        self.parser = parser or ResponseParser()
        self.validator = validator or PipelineValidator()
        self.retry = retry_strategy or RetryStrategy()
        self.tm_repo = tm_repo
        self.quality_validator = QualityValidator()

    async def _handle_backoff(self, attempt: int, err_msg: str):
        """Intelligent backoff with countdown for 429 / Rate Limit / Quota Exhaustion."""
        from app.ui.bus import EventBus
        err_lower = err_msg.lower()
        is_rate_limit = any(k in err_lower for k in ("429", "rate limit", "ratelimit", "quota", "resource_exhausted", "too many requests", "tpm", "rpm"))
        if is_rate_limit:
            delays = [25, 45, 60]
            delay = delays[min(max(0, attempt - 1), len(delays) - 1)]
            EventBus.instance().log_message.emit(
                f"⏳ تنبيه: تم بلوغ حد الطلبات (Rate Limit / Quota 429) للمزود. انتظر إعادة الشحن التلقائي: جاري الانتظار {delay} ثانية..."
            )
            while delay > 0:
                if asyncio.current_task() and asyncio.current_task().cancelled():
                    raise asyncio.CancelledError()
                step = min(5, delay)
                await asyncio.sleep(step)
                delay -= step
                if delay > 0 and delay % 10 == 0:
                    EventBus.instance().log_message.emit(f"⏳ متبقي {delay} ثانية قبل إعادة محاولة الطلب تلقائياً...")
        else:
            await asyncio.sleep(2 * attempt)

    def quick_heal_document(
        self,
        document: SubtitleDocument,
        healing_options: Optional[Dict[str, Any]] = None,
        characters: Optional[List] = None,
        target_lang: Optional[str] = None,
    ) -> int:
        """
        Performs instant zero-token programmatic Auto-Healing on all events:
        cleans punctuation, removes stray Latin, restores tags, fixes quotes.
        """
        eff_target = target_lang or (getattr(document, "metadata", None) or {}).get("target_lang", "ar")
        eff_opts = _merge_healing_options(healing_options, eff_target)
        known_names = _build_known_names(document, characters)
        count = 0
        for ev in document.events:
            target_text = ev.translated_text or ev.original_text
            if target_text:
                healed = SubtitleHealer.heal(target_text, ev.original_text, eff_opts, known_names=known_names)
                if ev.translated_text:
                    if ev.translated_text != healed:
                        ev.translated_text = healed
                        count += 1
                else:
                    if ev.original_text != healed:
                        ev.original_text = healed
                        count += 1
        return count

    def _is_local_provider(self, provider: Any) -> bool:
        """Determines if the provider is a local model engine (LM Studio, Ollama)."""
        if not provider:
            return False
        cls_name = provider.__class__.__name__.lower()
        if "lmstudio" in cls_name or "ollama" in cls_name:
            return True
        cfg = getattr(provider, "config", None)
        if cfg:
            ptype = str(getattr(cfg, "provider_type", "")).lower()
            if any(k in ptype for k in ("lmstudio", "ollama", "lm_studio")):
                return True
        return False

    @staticmethod
    def _compute_single_line_max_tokens(
        messages: List[ChatMessage],
        max_context: int = 4096,
        hard_cap: int = 512,
    ) -> int:
        """Computes a safe completion token budget fitting within `max_context`."""
        approx_prompt_tokens = sum(TokenBatcher.estimate_tokens_static(m.content) for m in messages)
        effective_ctx = max_context if (max_context and max_context > 512) else 4096
        headroom = effective_ctx - approx_prompt_tokens - 100
        if headroom > 128:
            return min(hard_cap, headroom)
        return max(128, min(hard_cap, effective_ctx // 4))

    _DYNAMIC_GLOSSARY_STOPWORDS: Set[str] = {
        "the", "and", "but", "for", "with", "what", "why", "when", "where", "who", "whom",
        "which", "how", "wait", "well", "yes", "yeah", "no", "oh", "ah", "hey", "hi",
        "hello", "good", "great", "okay", "ok", "sorry", "please", "thank", "thanks",
        "really", "just", "only", "even", "here", "there", "this", "that", "these",
        "those", "now", "then", "today", "tomorrow", "yesterday", "never", "always",
        "everyone", "everybody", "someone", "somebody", "anyone", "anybody", "nothing",
        "everything", "something", "right", "look", "listen", "stop", "come", "let",
        "god", "sir", "miss", "mrs", "mr", "ms", "dr", "lord", "lady", "dont", "cant",
        "wont", "are", "is", "was", "were", "have", "has", "had", "you", "they", "she",
    }

    @staticmethod
    def _normalize_ar_match(text: str) -> str:
        t = re.sub(r"[\u064B-\u065F\u0670]", "", text or "")
        t = t.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا").replace("ٱ", "ا")
        t = t.replace("ى", "ي").replace("ة", "ه")
        return t.strip()

    @classmethod
    def _extract_dynamic_glossary_pairs(
        cls,
        orig_clean: str,
        trans_clean: str,
        known_terms_lower: Set[str],
    ) -> Dict[str, str]:
        """Extracts consistent proper nouns / named entities and their Arabic forms from translated lines."""
        discovered: Dict[str, str] = {}
        if not orig_clean or not trans_clean:
            return discovered
        if not re.search(r"[\u0600-\u06FF]", trans_clean):
            return discovered

        from rapidfuzz import fuzz

        candidates: List[str] = []
        # 1. Multi-word Title Case entities (e.g. "Holy Sword", "Seiya Ryuuguuin")
        for m in re.finditer(r"\b([A-Z][a-z]{1,20}(?:\s+[A-Z][a-z]{1,20})+)\b", orig_clean):
            phrase = m.group(1).strip()
            first_tok = phrase.split()[0].lower()
            if first_tok not in cls._DYNAMIC_GLOSSARY_STOPWORDS:
                candidates.append(phrase)

        # 2. Mid-sentence capitalized single proper nouns (e.g. "... save Ristarte!")
        for m in re.finditer(r"(?<=[a-z,;:]\s)\b([A-Z][a-z]{2,20})\b", orig_clean):
            word = m.group(1).strip()
            if word.lower() not in cls._DYNAMIC_GLOSSARY_STOPWORDS:
                candidates.append(word)

        if not candidates:
            return discovered

        clean_ar_line = re.sub(r"\{[^{}]*\}", " ", trans_clean).replace(r"\N", " ")
        ar_tokens = re.findall(r"[\u0621-\u064A]+", clean_ar_line)
        if not ar_tokens:
            return discovered

        discovered_lower: Set[str] = set()
        for cand in candidates:
            cand_lower = cand.lower()
            if cand_lower in known_terms_lower or cand_lower in discovered_lower:
                continue

            ref_ar = SubtitleHealer.transliterate_name_to_arabic(cand)
            norm_ref = cls._normalize_ar_match(ref_ar)
            if len(norm_ref) < 3:
                continue

            cand_words_count = len(cand.split())
            best_score = 0.0
            best_ar = ""

            window_sizes = (cand_words_count,) if cand_words_count <= 2 else (2, 1)
            for wsize in window_sizes:
                if len(ar_tokens) < wsize:
                    continue
                for idx in range(len(ar_tokens) - wsize + 1):
                    raw_win = " ".join(ar_tokens[idx : idx + wsize])
                    stem = raw_win
                    # Strip common Arabic attached conjunctions/prepositions on first word if prefix
                    if len(ar_tokens[idx]) >= 4 and ar_tokens[idx][0] in ("و", "ف", "ل", "ب", "ك"):
                        alt_stem = ar_tokens[idx][1:]
                        alt_win = " ".join([alt_stem] + ar_tokens[idx + 1 : idx + wsize])
                    else:
                        alt_win = ""

                    for candidate_str in (stem, alt_win):
                        if not candidate_str:
                            continue
                        norm_win = cls._normalize_ar_match(candidate_str)
                        score = fuzz.ratio(norm_ref, norm_win)
                        if score > best_score:
                            best_score = score
                            best_ar = candidate_str

            if best_score >= 65.0 and best_ar:
                discovered[cand] = best_ar
                discovered_lower.add(cand_lower)

        return discovered

    @staticmethod
    def _resolve_event_speaker_meta(
        event: SubtitleEvent,
        resolver: Optional[CharacterResolver],
    ) -> Tuple[str, str]:
        """Returns normalized speaker identifier and resolved gender string for an event."""
        raw_spk = (event.speaker or "").strip()
        if not raw_spk:
            return "", "UNKNOWN"
        gender_val = "UNKNOWN"
        if resolver:
            match = resolver.resolve_speaker(raw_spk)
            if match and match.profile:
                g = match.profile.gender
                gender_val = g.value if hasattr(g, "value") else str(g)
        return raw_spk, str(gender_val or "UNKNOWN").upper()

    @staticmethod
    def _make_dedup_key(clean_t: str, speaker: str, gender: str) -> Optional[Tuple]:
        """
        Builds a safe deduplication key preventing cross-gender corruption:
        - Lines with >= 4 words can be deduplicated by text alone.
        - Lines with < 4 words ONLY deduplicate when speaker is explicitly known and matches (name + gender).
        """
        norm = (clean_t or "").strip()
        if not norm:
            return None
        if len(norm.split()) >= 4:
            return ("LONG", norm)
        clean_spk = (speaker or "").strip().lower()
        if not clean_spk:
            return None
        return ("SHORT", norm, clean_spk, (gender or "UNKNOWN").upper())

    async def translate_document(
        self,
        document: SubtitleDocument,
        provider: ProviderBase,
        model: str,
        source_lang: str = "en",
        target_lang: str = "ar",
        characters: Optional[List] = None,
        glossary: Optional[List] = None,
        story_notes: str = "",
        on_progress: Optional[Callable] = None,
        on_batch_status: Optional[Callable[[List[int], str], None]] = None,
        concurrency: int = 1,
        temperature: float = 0.1,
        max_tokens: Optional[int] = None,
        max_context: int = 4096,
        source_file_path: Optional[str] = None,
        auto_heal: bool = True,
        healing_options: Optional[Dict[str, bool]] = None,
        auto_improve: bool = False,
        use_cache: bool = False,
        force_fresh: bool = False,
        top_p: float = 0.85,
        min_p: float = 0.05,
        repetition_penalty: float = 1.0
    ) -> SubtitleDocument:
        """
        Execute the Complete Translation & Healing Pipeline:
        1. Force fresh reset (if requested)
        2. Checkpoint Resume check (if use_cache is enabled)
        3. In-memory / TM Deduplication (if use_cache is enabled)
        4. Targeted Character Resolution per batch
        5. Batch Processing with Targeted Single Line Recovery and Binary Split
        6. Smart Auto-Healing Post-Processing Pass
        7. Optional Automatic Post-Translation Linguistic Improvement Pass
        8. Atomic Checkpointing
        9. Quality Validation Pass
        """
        from app.ui.bus import EventBus
        
        separate_effects = True
        if healing_options and "separate_inline_effects" in healing_options:
            separate_effects = healing_options["separate_inline_effects"]
        if separate_effects:
            document.separate_mixed_effects()

        skip_effects = True
        if healing_options and "skip_visual_effects" in healing_options:
            skip_effects = healing_options["skip_visual_effects"]

        translate_signs = not skip_effects
        if healing_options and "translate_signs" in healing_options:
            translate_signs = bool(healing_options["translate_signs"])

        known_names = _build_known_names(document, characters)
        eff_healing_opts = _merge_healing_options(healing_options, target_lang)
        document.metadata["target_lang"] = target_lang
        document.metadata["known_names"] = sorted(known_names)

        translatable_events = document.get_translatable_events(skip_effects=skip_effects, include_signs=translate_signs)
        if not translatable_events:
            return document

        fx_count = len(document.events) - len(translatable_events)
        if fx_count > 0:
            EventBus.instance().log_message.emit(
                f"🛡️ تم رصد {fx_count} سطر مؤثرات ورسومات غير نصية: تم حمايتها وحفظها دون استهلاك أي توكن."
            )
            line_desc = "نصوص وحوارات ولوحات" if translate_signs else "حوارات"
            EventBus.instance().log_message.emit(
                f"💬 جاري ترجمة {len(translatable_events)} سطر {line_desc} نقية عبر عازل المؤثرات الذكي..."
            )
            
        total_lines = len(translatable_events)
        
        # Reset any pre-existing translation if starting fresh or if caching is disabled
        if force_fresh or not use_cache:
            for event in translatable_events:
                event.translated_text = None

        # Pre-adopt lines that are already purely in the target language (Arabic)
        is_target_ar = _is_arabic_target(target_lang)
        if is_target_ar:
            already_ar_count = 0
            for event in translatable_events:
                if not event.translated_text:
                    clean_t = event.get_clean_text().strip()
                    has_ar = bool(re.search(r"[\u0600-\u06FF]", clean_t))
                    has_foreign = bool(re.search(r"[A-Za-z\u3040-\u30ff\u4e00-\u9faf\uac00-\ud7af]", clean_t))
                    if has_ar and not has_foreign:
                        event.translated_text = clean_t
                        already_ar_count += 1
            if already_ar_count > 0:
                EventBus.instance().log_message.emit(
                    f"⚡ تم رصد {already_ar_count} سطر حوار بالعربية مسبقاً: تم اعتمادها فوراً دون استهلاك توكن أو انتظار."
                )

        file_path_for_ckpt = source_file_path or document.file_path
        
        # 1. Resume from checkpoint if available and caching is enabled
        if use_cache and file_path_for_ckpt:
            saved_checkpoint = CheckpointManager.load(file_path_for_ckpt)
            if saved_checkpoint:
                resumed_count = 0
                for event in translatable_events:
                    if event.id in saved_checkpoint and saved_checkpoint[event.id]:
                        event.translated_text = saved_checkpoint[event.id]
                        resumed_count += 1
                if resumed_count > 0:
                    EventBus.instance().log_message.emit(
                        f"🔄 Resumed {resumed_count}/{total_lines} lines from previous checkpoint."
                    )
                    if on_batch_status:
                        on_batch_status(list(saved_checkpoint.keys()), "Done")
        elif not use_cache and file_path_for_ckpt:
            # When not using cache, clear any stale checkpoint on disk
            CheckpointManager.cleanup(file_path_for_ckpt)

        # Character Resolver (built early so dedup and TM lookup respect speaker gender)
        resolver = CharacterResolver(characters) if characters else None

        # Deduplication settings
        dedup_enabled = True
        if healing_options and "deduplicate_identical_lines" in healing_options:
            dedup_enabled = healing_options["deduplicate_identical_lines"]

        # 2. In-document Deduplication & TM lookup (with speaker/gender + >=4-word guard)
        text_map: Dict[Tuple, str] = {}
        for e in translatable_events:
            if e.translated_text:
                clean_k = e.get_clean_text().strip()
                raw_spk, spk_gender = self._resolve_event_speaker_meta(e, resolver)
                dedup_k = self._make_dedup_key(clean_k, raw_spk, spk_gender)
                if dedup_k and dedup_k not in text_map:
                    text_map[dedup_k] = e.translated_text

        # TM Lookup for untranslated events (only when use_cache is explicitly enabled)
        if use_cache and self.tm_repo:
            tm_hit_count = 0
            for e in translatable_events:
                if not e.translated_text:
                    clean_t = e.get_clean_text().strip()
                    raw_spk, spk_gender = self._resolve_event_speaker_meta(e, resolver)
                    dedup_k = self._make_dedup_key(clean_t, raw_spk, spk_gender)
                    if dedup_k and dedup_k in text_map:
                        raw_clean = re.sub(r"\{[^}]*\}", "", text_map[dedup_k]).strip()
                        e.translated_text = SubtitleHealer.heal(raw_clean, e.original_text, eff_healing_opts, known_names=known_names) if auto_heal else remove_orphaned_quotes(raw_clean)
                        tm_hit_count += 1
                    else:
                        cached_trans = self.tm_repo.lookup(
                            clean_t, source_lang, target_lang,
                            speaker=raw_spk, speaker_gender=spk_gender,
                        )
                        if cached_trans:
                            raw_clean = re.sub(r"\{[^}]*\}", "", cached_trans).strip()
                            e.translated_text = SubtitleHealer.heal(raw_clean, e.original_text, eff_healing_opts, known_names=known_names) if auto_heal else remove_orphaned_quotes(raw_clean)
                            if dedup_k:
                                text_map[dedup_k] = cached_trans
                            tm_hit_count += 1
            if tm_hit_count > 0:
                EventBus.instance().log_message.emit(f"⚡ Reused {tm_hit_count} lines from Translation Memory / Duplicates.")

        # Pass 1: Propagate already-known translations (from pre-adopted Arabic or checkpoint) to eligible duplicates
        if dedup_enabled:
            early_dup_adopted = 0
            early_done_ids = []
            for e in translatable_events:
                if not e.translated_text:
                    clean_t = e.get_clean_text().strip()
                    raw_spk, spk_gender = self._resolve_event_speaker_meta(e, resolver)
                    dedup_k = self._make_dedup_key(clean_t, raw_spk, spk_gender)
                    if dedup_k and dedup_k in text_map:
                        raw_clean = re.sub(r"\{[^}]*\}", "", text_map[dedup_k]).strip()
                        e.translated_text = SubtitleHealer.heal(raw_clean, e.original_text, eff_healing_opts, known_names=known_names) if auto_heal else remove_orphaned_quotes(raw_clean)
                        early_dup_adopted += 1
                        early_done_ids.append(e.id)
            if early_dup_adopted > 0:
                EventBus.instance().log_message.emit(
                    f"⚡ تم تكرار واعتماد ترجمة {early_dup_adopted} سطر متطابق مع أسطر مترجمة مسبقاً تلقائياً."
                )
                if early_done_ids and on_batch_status:
                    on_batch_status(early_done_ids, "Done")

        # Pass 2: Group untranslated events to only translate unique (or speaker-distinct) lines
        untranslated_events = [e for e in translatable_events if not e.translated_text]
        primary_events: List[SubtitleEvent] = []
        duplicates_map: Dict[int, List[SubtitleEvent]] = {}
        text_to_primary: Dict[Tuple, SubtitleEvent] = {}

        if dedup_enabled:
            for event in untranslated_events:
                clean_t = event.get_clean_text().strip()
                raw_spk, spk_gender = self._resolve_event_speaker_meta(event, resolver)
                dedup_k = self._make_dedup_key(clean_t, raw_spk, spk_gender)
                if not dedup_k:
                    primary_events.append(event)
                    continue

                if dedup_k in text_to_primary:
                    prim = text_to_primary[dedup_k]
                    duplicates_map.setdefault(prim.id, []).append(event)
                else:
                    text_to_primary[dedup_k] = event
                    primary_events.append(event)

            dup_saved_count = len(untranslated_events) - len(primary_events)
            if dup_saved_count > 0:
                EventBus.instance().log_message.emit(
                    f"⚡ تم رصد {dup_saved_count} سطر حوار مكرر: سيتم ترجمة السطر الأول فقط وتمرير الترجمة تلقائياً للمكررات لحماية الموديل وتوفير التوكنز والوقت."
                )
                EventBus.instance().log_message.emit(
                    f"💬 جاري ترجمة {len(primary_events)} سطر حوار درامي فريد (توفير {dup_saved_count} سطر من التكرار)..."
                )
            events_to_translate = primary_events
        else:
            events_to_translate = untranslated_events
        
        if hasattr(self.batcher, 'max_context'):
            self.batcher.max_context = max_context
        is_local = self._is_local_provider(provider)
        batches = self.batcher.create_batches(events_to_translate, is_local=is_local)
        total_batches = len(batches)
        
        char_ctx_global = format_character_context(characters, target_lang=target_lang) if characters else ""
        glossary_ctx = format_glossary_context(glossary) if glossary else ""
        known_glossary_lower: Set[str] = {
            (getattr(g, "source_term", "") or "").strip().lower()
            for g in (glossary or [])
            if getattr(g, "source_term", "")
        } | {
            (getattr(c, "canonical_name", "") or "").strip().lower()
            for c in (characters or [])
            if getattr(c, "canonical_name", "")
        }
        running_glossary: Dict[str, str] = {}

        eff_concurrency = max(1, concurrency)
        semaphore = asyncio.Semaphore(eff_concurrency)
        progress_lock = asyncio.Lock()
        
        completed = 0
        completed_lines = total_lines - len(untranslated_events)
        total_tokens = 0

        async def process_with_sema(idx, batch):
            nonlocal completed, completed_lines, total_tokens
            
            # Cancellation check
            if asyncio.current_task() and asyncio.current_task().cancelled():
                raise asyncio.CancelledError()

            async with semaphore:
                async with progress_lock:
                    if running_glossary:
                        dyn_lines = "\n".join(f"- {k} -> {v} (Auto-Glossary)" for k, v in running_glossary.items())
                        eff_glossary_ctx = f"{glossary_ctx}\n{dyn_lines}".strip() if glossary_ctx else dyn_lines
                    else:
                        eff_glossary_ctx = glossary_ctx

                batch_tokens = await self._process_batch(
                    batch, translatable_events, provider, model, 
                    source_lang, target_lang, char_ctx_global, eff_glossary_ctx,
                    temperature, max_tokens, characters, glossary,
                    resolver=resolver, on_batch_status=on_batch_status,
                    story_notes=story_notes, auto_heal=auto_heal, healing_options=eff_healing_opts,
                    top_p=top_p, min_p=min_p, repetition_penalty=repetition_penalty,
                    max_context=max_context, known_names=known_names,
                )
                
                async with progress_lock:
                    completed += 1
                    completed_lines += len(batch)
                    total_tokens += (batch_tokens or 0)
                    
                    # Update text_map, Dynamic Running Glossary, and save to TM
                    newly_done_ids = []
                    for ev in batch:
                        if ev.translated_text:
                            clean_t = ev.get_clean_text().strip()
                            raw_spk, spk_gender = self._resolve_event_speaker_meta(ev, resolver)
                            dedup_k = self._make_dedup_key(clean_t, raw_spk, spk_gender)
                            if dedup_k:
                                text_map[dedup_k] = ev.translated_text
                            raw_clean_trans = re.sub(r"\{[^}]*\}", "", ev.translated_text).strip()

                            # Discover recurring proper nouns/entities for subsequent batches (Dynamic Running Glossary)
                            if len(running_glossary) < 25 and is_target_ar:
                                new_terms = self._extract_dynamic_glossary_pairs(
                                    clean_t,
                                    raw_clean_trans,
                                    known_glossary_lower | set(k.lower() for k in running_glossary),
                                )
                                for src_t, ar_t in new_terms.items():
                                    if len(running_glossary) >= 25:
                                        break
                                    running_glossary[src_t] = ar_t

                            if self.tm_repo:
                                try:
                                    self.tm_repo.save_translation(
                                        clean_t, ev.translated_text, source_lang, target_lang,
                                        provider=provider.__class__.__name__, model=model,
                                        speaker=raw_spk, speaker_gender=spk_gender,
                                    )
                                except Exception:
                                    pass

                            # Immediate propagation to all duplicates of this primary line
                            dup_events = duplicates_map.get(ev.id, [])
                            if dup_events:
                                for dup in dup_events:
                                    if not dup.translated_text:
                                        if auto_heal:
                                            dup.translated_text = SubtitleHealer.heal(
                                                raw_clean_trans, dup.original_text, eff_healing_opts, known_names=known_names
                                            )
                                        else:
                                            dup.translated_text = remove_orphaned_quotes(raw_clean_trans)
                                        completed_lines += 1
                                        newly_done_ids.append(dup.id)

                    if newly_done_ids and on_batch_status:
                        on_batch_status(newly_done_ids, "Done")

                    cur_completed = completed
                    cur_lines = completed_lines
                    cur_tokens = total_tokens

                    # Atomic checkpoint save (only when caching is enabled)
                    if use_cache and file_path_for_ckpt:
                        all_completed_map = {e.id: e.translated_text for e in translatable_events if e.translated_text}
                        CheckpointManager.save(file_path_for_ckpt, total_lines, all_completed_map, last_batch_index=idx)

                if on_progress:
                    try:
                        on_progress(cur_completed, total_batches, cur_lines, total_lines, cur_tokens)
                    except TypeError:
                        on_progress(cur_completed, total_batches)

        if batches:
            tasks = [process_with_sema(idx, batch) for idx, batch in enumerate(batches)]
            await asyncio.gather(*tasks)

        # Fail-safe: Populate any duplicates that were skipped or not yet filled
        for e in translatable_events:
            if not e.translated_text:
                clean_t = e.get_clean_text().strip()
                raw_spk, spk_gender = self._resolve_event_speaker_meta(e, resolver)
                dedup_k = self._make_dedup_key(clean_t, raw_spk, spk_gender)
                if dedup_k and dedup_k in text_map:
                    raw_clean = re.sub(r"\{[^}]*\}", "", text_map[dedup_k]).strip()
                    if auto_heal:
                        e.translated_text = SubtitleHealer.heal(raw_clean, e.original_text, eff_healing_opts, known_names=known_names)
                    else:
                        e.translated_text = remove_orphaned_quotes(raw_clean)

        # Cleanup checkpoint file upon successful translation
        if file_path_for_ckpt:
            CheckpointManager.cleanup(file_path_for_ckpt)

        # Optional Automatic Post-Translation Linguistic Improvement Pass
        if auto_improve:
            EventBus.instance().log_message.emit("✨ بدء مرحلة التدقيق اللغوي والتحسين الدرامي الفائق تلقائياً...")
            
            def improve_progress_adapter(*args):
                if on_progress:
                    if len(args) >= 5:
                        c_b, t_b, c_l, t_l, tok = args[:5]
                        try:
                            on_progress(c_b, t_b, c_l, t_l, tok, "improving")
                        except TypeError:
                            on_progress(c_b, t_b, c_l, t_l, tok)
                    else:
                        on_progress(*args)

            await self.improve_document(
                document=document,
                provider=provider,
                model=model,
                source_lang=source_lang,
                target_lang=target_lang,
                characters=characters,
                glossary=glossary,
                story_notes=story_notes,
                on_progress=improve_progress_adapter,
                on_batch_status=on_batch_status,
                concurrency=concurrency,
                temperature=temperature,
                max_tokens=max_tokens,
                auto_heal=auto_heal,
                healing_options=healing_options,
                top_p=top_p,
                min_p=min_p,
                repetition_penalty=repetition_penalty,
                max_context=max_context
            )

        # Deterministic CPS gap-safe lead-out extension for comfortable Arabic reading speed
        cps_opt_enabled = auto_heal and (not healing_options or healing_options.get("optimize_cps", True))
        if cps_opt_enabled:
            try:
                from app.subtitle.timing_sync import SubtitleTimingOptimizer
                extended = SubtitleTimingOptimizer.optimize_arabic_cps(document)
                if extended > 0:
                    EventBus.instance().log_message.emit(
                        f"⏱️ تم توسيع نهاية العرض لـ {extended} سطر سريع تلقائياً ضمن الفجوات الآمنة لتحسين القراءة العربية."
                    )
            except Exception as te:
                logger.debug(f"Timing CPS optimizer skipped: {te}")

        # 8. Quality Validation Pass
        try:
            chars_map = {c.canonical_name: c for c in characters} if characters else {}
            qa_report = self.quality_validator.run_quality_checks(
                translatable_events, chars_map, glossary or [], target_lang=target_lang
            )
            warn_count = qa_report.get("warnings_count", 0)
            if warn_count > 0:
                EventBus.instance().log_message.emit(
                    f"⚠️ Quality Check: {warn_count} potential issues detected across subtitles. Review in Tools ➔ Review Dialog."
                )
            else:
                EventBus.instance().log_message.emit("✅ QA Check: All lines passed quality and formatting checks.")
        except Exception as qe:
            logger.debug(f"Quality validation check error: {qe}")
            
        return document

    @staticmethod
    def find_untranslated_events(
        document: SubtitleDocument,
        target_lang: str = "ar",
        skip_effects: bool = True,
        include_signs: bool = False,
    ) -> List[SubtitleEvent]:
        """
        Identifies translatable events in document that lack a valid, non-empty target translation.
        """
        if not document or not document.events:
            return []

        translatable = document.get_translatable_events(skip_effects=skip_effects, include_signs=include_signs)
        untranslated: List[SubtitleEvent] = []
        is_target_ar = _is_arabic_target(target_lang)

        for ev in translatable:
            clean_orig = ev.get_clean_text().strip()
            if not clean_orig:
                continue

            # Case 1: translated_text is None or purely whitespace
            if not ev.translated_text or not ev.translated_text.strip():
                untranslated.append(ev)
                continue

            clean_trans = re.sub(r"\{[^}]*\}", "", ev.translated_text).strip()
            if not clean_trans:
                untranslated.append(ev)
                continue

            # Case 2: Target is Arabic, but translation contains ZERO Arabic letters
            # and contains leftover foreign words from original text
            if is_target_ar:
                has_ar = bool(re.search(r"[\u0600-\u06FF]", clean_trans))
                if not has_ar:
                    orig_words = [w for w in re.findall(r"[A-Za-z\u3040-\u30ff\u4e00-\u9faf\uac00-\ud7af]+", clean_orig) if len(w) > 1]
                    if orig_words:
                        untranslated.append(ev)
            else:
                has_latin = bool(re.search(r"[A-Za-z]", clean_trans))
                has_cjk_orig = bool(re.search(r"[\u3040-\u30ff\u4e00-\u9faf\uac00-\ud7af]", clean_orig))
                if has_cjk_orig and not has_latin:
                    untranslated.append(ev)

        return untranslated

    async def translate_remaining_events(
        self,
        document: SubtitleDocument,
        remaining_events: List[SubtitleEvent],
        provider: ProviderBase,
        model: str,
        source_lang: str = "en",
        target_lang: str = "ar",
        characters: Optional[List] = None,
        glossary: Optional[List] = None,
        story_notes: str = "",
        on_progress: Optional[Callable] = None,
        on_batch_status: Optional[Callable[[List[int], str], None]] = None,
        concurrency: int = 1,
        temperature: float = 0.1,
        max_tokens: Optional[int] = None,
        max_context: int = 4096,
        auto_heal: bool = True,
        healing_options: Optional[Dict[str, bool]] = None,
        top_p: float = 0.85,
        min_p: float = 0.05,
        repetition_penalty: float = 1.0,
    ) -> int:
        """
        Targeted translation of specific untranslated events using full document context.
        Each batch is anchored against `document.events` so previous and next scene dialogue,
        character context, and existing translations are completely preserved.
        """
        from app.ui.bus import EventBus

        if not remaining_events or not document or not document.events:
            return 0

        # Ensure only events that belong to document are processed
        doc_events_set = {e.id: e for e in document.events}
        target_events = [doc_events_set[e.id] for e in remaining_events if e.id in doc_events_set]
        if not target_events:
            return 0

        known_names = _build_known_names(document, characters)
        eff_healing_opts = _merge_healing_options(healing_options, target_lang)
        resolver = CharacterResolver(characters) if characters else None

        char_ctx_global = format_character_context(characters, target_lang=target_lang) if characters else ""
        glossary_ctx = format_glossary_context(glossary) if glossary else ""

        is_local = self._is_local_provider(provider)
        batches = self.batcher.create_batches(target_events, is_local=is_local)
        total_batches = len(batches)
        total_target_lines = len(target_events)

        EventBus.instance().log_message.emit(
            f"🔄 جاري معالجة {total_target_lines} سطر غير مترجم في {total_batches} دفعة بسياق الحوار والمشهد الأصلي..."
        )

        semaphore = asyncio.Semaphore(max(1, concurrency))
        progress_lock = asyncio.Lock()
        completed_batches = 0
        translated_lines_count = 0

        async def process_remaining_batch(idx, batch):
            nonlocal completed_batches, translated_lines_count

            if asyncio.current_task() and asyncio.current_task().cancelled():
                raise asyncio.CancelledError()

            async with semaphore:
                batch_tokens = await self._process_batch(
                    batch=batch,
                    all_events=document.events, # Crucial: Pass full document events for rich scene context!
                    provider=provider,
                    model=model,
                    source_lang=source_lang,
                    target_lang=target_lang,
                    char_ctx=char_ctx_global,
                    glossary_ctx=glossary_ctx,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    characters=characters,
                    glossary=glossary,
                    resolver=resolver,
                    on_batch_status=on_batch_status,
                    story_notes=story_notes,
                    auto_heal=auto_heal,
                    healing_options=eff_healing_opts,
                    top_p=top_p,
                    min_p=min_p,
                    repetition_penalty=repetition_penalty,
                    max_context=max_context,
                    known_names=known_names,
                )

                async with progress_lock:
                    completed_batches += 1
                    for ev in batch:
                        if ev.translated_text:
                            translated_lines_count += 1
                            raw_spk, spk_gender = self._resolve_event_speaker_meta(ev, resolver)
                            clean_t = ev.get_clean_text().strip()
                            if self.tm_repo:
                                try:
                                    self.tm_repo.save_translation(
                                        clean_t, ev.translated_text, source_lang, target_lang,
                                        provider=provider.__class__.__name__, model=model,
                                        speaker=raw_spk, speaker_gender=spk_gender,
                                    )
                                except Exception:
                                    pass

                    cur_b = completed_batches
                    cur_lines = translated_lines_count

                if on_progress:
                    try:
                        on_progress(cur_b, total_batches, cur_lines, total_target_lines, batch_tokens or 0)
                    except Exception:
                        pass

        tasks = [process_remaining_batch(idx, b) for idx, b in enumerate(batches)]
        await asyncio.gather(*tasks)

        EventBus.instance().log_message.emit(
            f"✅ تم بنجاح استكمال ترجمة {translated_lines_count}/{total_target_lines} سطر مع الحفاظ الكامل على سياق المشهد."
        )
        return translated_lines_count

    async def _translate_single_line(
        self,
        event: SubtitleEvent,
        provider: ProviderBase,
        model: str,
        source_lang: str,
        target_lang: str,
        char_ctx: str,
        glossary_ctx: str,
        temperature: float,
        story_notes: str = "",
        auto_heal: bool = True,
        healing_options: Optional[Dict[str, Any]] = None,
        top_p: float = 0.85,
        min_p: float = 0.05,
        repetition_penalty: float = 1.0,
        max_context: int = 4096,
        known_names: Optional[Set[str]] = None,
        **kwargs
    ) -> Tuple[str, int]:
        """Translates a single missing line for targeted recovery without restarting the full batch."""
        is_target_ar = _is_arabic_target(target_lang)
        eff_opts = _merge_healing_options(healing_options, target_lang)
        if is_target_ar:
            system_content = (
                f"Translate the following single subtitle line from {source_lang} into natural, eloquent Modern Standard Arabic (الفصحى).\n"
                "CRITICAL RULES:\n"
                "1. Output ONLY the translated Arabic dialogue. No greetings, notes, prefixes, or markdown quotes.\n"
                "2. Do NOT add prefixes like 'المترجم:' or 'الترجمة:' or notes in parentheses.\n"
                "3. Preserve all ASS tags like {\\...} and \\N in their exact positions.\n"
                "4. Translate completely. No stray English words/fillers. Use Arabic punctuation exclusively (؟،؛).\n"
                "5. Do NOT explain your translation or add any commentary."
            )
        else:
            eff_target = (target_lang or "English").strip()
            system_content = (
                f"Translate the following single subtitle line from {source_lang} into fluent, natural {eff_target}.\n"
                "CRITICAL RULES:\n"
                f"1. Output ONLY the translated {eff_target} dialogue. No greetings, notes, prefixes, or markdown quotes.\n"
                "2. Preserve all ASS tags like {\\...} and \\N in their exact positions.\n"
                f"3. Translate completely and naturally into {eff_target} using standard {eff_target} punctuation.\n"
                "4. Do NOT explain your translation or add any commentary."
            )
        if story_notes:
            system_content += f"\n\nSTORY NOTES:\n{story_notes}"
        if char_ctx:
            system_content += f"\n\nCHARACTERS:\n{char_ctx}"
        if glossary_ctx:
            system_content += f"\n\nGLOSSARY:\n{glossary_ctx}"

        messages = [
            ChatMessage(role="system", content=system_content),
            ChatMessage(role="user", content=f"Translate this line:\n{event.get_clean_text()}")
        ]
        dyn_max_tokens = self._compute_single_line_max_tokens(messages, max_context=max_context, hard_cap=512)
        try:
            resp = await provider.chat_completion(
                messages, model, temperature=temperature, max_tokens=dyn_max_tokens,
                top_p=top_p, min_p=min_p, repetition_penalty=repetition_penalty
            )
            toks = (getattr(resp, "input_tokens", 0) + getattr(resp, "output_tokens", 0))
            raw_text = ResponseParser.clean_text_item(resp.content)
            if auto_heal and raw_text:
                final_text = event.rebuild_text(
                    raw_text, target_lang=target_lang, known_names=known_names, options=eff_opts
                )
            else:
                from app.subtitle.effect_separator import EffectPayloadIsolator
                _, skeleton = EffectPayloadIsolator.extract_clean_payload(event.original_text)
                reconstructed = EffectPayloadIsolator.reconstruct_effect_text(raw_text, skeleton)
                final_text = remove_orphaned_quotes(reconstructed)
            return final_text, toks
        except Exception as e:
            logger.warning(f"Single line recovery failed for ID {event.id}: {e}")
            return "", 0

    async def _improve_single_line(
        self,
        event: SubtitleEvent,
        provider: ProviderBase,
        model: str,
        source_lang: str,
        target_lang: str,
        char_ctx: str,
        glossary_ctx: str,
        story_notes: str,
        temperature: float,
        auto_heal: bool = True,
        healing_options: Optional[Dict[str, Any]] = None,
        top_p: float = 0.85,
        min_p: float = 0.05,
        repetition_penalty: float = 1.0,
        max_context: int = 4096,
        known_names: Optional[Set[str]] = None,
        **kwargs
    ) -> Tuple[str, int]:
        """Refines a single missing line for targeted recovery without restarting the full improvement batch."""
        draft = event.translated_text or event.original_text
        is_target_ar = _is_arabic_target(target_lang)
        eff_opts = _merge_healing_options(healing_options, target_lang)
        if is_target_ar:
            system_content = (
                f"Refine and polish this Arabic subtitle line into natural, dramatic Modern Standard Arabic (الفصحى).\n"
                "CRITICAL RULES:\n"
                "1. Output ONLY the refined Arabic dialogue. No greetings, reports, notes, or prefixes.\n"
                "2. Do NOT add prefixes like 'المترجم:' or 'المصقول النهائي:' or notes in parentheses.\n"
                "3. Preserve all ASS tags like {\\...} and \\N in their exact positions.\n"
                "4. Standardize punctuation to Arabic (؟،؛) and fix any grammatical errors.\n"
                "5. Do NOT explain changes or write commentary."
            )
            label_target = "Arabic"
        else:
            eff_target = (target_lang or "English").strip()
            system_content = (
                f"Refine and polish this {eff_target} subtitle line into natural, dramatic {eff_target}.\n"
                "CRITICAL RULES:\n"
                f"1. Output ONLY the refined {eff_target} dialogue. No greetings, reports, notes, or prefixes.\n"
                "2. Preserve all ASS tags like {\\...} and \\N in their exact positions.\n"
                f"3. Polish phrasing and punctuation cleanly in {eff_target}.\n"
                "4. Do NOT explain changes or write commentary."
            )
            label_target = eff_target
        if story_notes:
            system_content += f"\n\nSTORY NOTES:\n{story_notes}"
        if char_ctx:
            system_content += f"\n\nCHARACTERS:\n{char_ctx}"

        user_content = (
            f"Original ({source_lang}): {event.get_clean_text()}\n"
            f"Draft Translation: {draft}\n\n"
            f"Refined {label_target} subtitle:"
        )
        messages = [
            ChatMessage(role="system", content=system_content),
            ChatMessage(role="user", content=user_content)
        ]
        dyn_max_tokens = self._compute_single_line_max_tokens(messages, max_context=max_context, hard_cap=512)
        try:
            resp = await provider.chat_completion(
                messages, model, temperature=temperature, max_tokens=dyn_max_tokens,
                top_p=top_p, min_p=min_p, repetition_penalty=repetition_penalty
            )
            toks = (getattr(resp, "input_tokens", 0) + getattr(resp, "output_tokens", 0))
            raw_text = ResponseParser.clean_text_item(resp.content)
            if auto_heal and raw_text:
                final_text = event.rebuild_text(
                    raw_text, target_lang=target_lang, known_names=known_names, options=eff_opts
                )
            else:
                from app.subtitle.effect_separator import EffectPayloadIsolator
                _, skeleton = EffectPayloadIsolator.extract_clean_payload(event.original_text)
                reconstructed = EffectPayloadIsolator.reconstruct_effect_text(raw_text, skeleton)
                final_text = remove_orphaned_quotes(reconstructed)
            return final_text, toks
        except Exception as e:
            logger.warning(f"Single line improvement recovery failed for ID {event.id}: {e}")
            return "", 0

    async def _process_batch(
        self,
        batch: List[SubtitleEvent],
        all_events: List[SubtitleEvent],
        provider: ProviderBase,
        model: str,
        source_lang: str,
        target_lang: str,
        char_ctx: str,
        glossary_ctx: str,
        temperature: float,
        max_tokens: Optional[int],
        characters: Optional[List] = None,
        glossary: Optional[List] = None,
        resolver: Optional[CharacterResolver] = None,
        on_batch_status: Optional[Callable[[List[int], str], None]] = None,
        story_notes: str = "",
        auto_heal: bool = True,
        healing_options: Optional[Dict[str, Any]] = None,
        top_p: float = 0.85,
        min_p: float = 0.05,
        repetition_penalty: float = 1.0,
        max_context: int = 4096,
        known_names: Optional[Set[str]] = None,
    ) -> int:
        """Process a single batch with Targeted Recovery and Binary Split fallback."""
        from app.ui.bus import EventBus

        is_target_ar = _is_arabic_target(target_lang)
        eff_opts = _merge_healing_options(healing_options, target_lang)
        eff_known = known_names if known_names is not None else _build_known_names(None, characters)

        expected_ids = [e.id for e in batch]
        local_ids = list(range(1, len(batch) + 1))
        real_to_local = {e.id: idx for idx, e in enumerate(batch, 1)}
        local_to_real = {idx: e.id for idx, e in enumerate(batch, 1)}
        if on_batch_status:
            on_batch_status(expected_ids, "Translating")

        # Resolve targeted characters for this specific batch
        if resolver and characters:
            batch_chars = resolver.get_batch_characters(batch)
            if not batch_chars:
                batch_chars = characters[:8]
            batch_char_ctx = format_character_context(batch_chars, target_lang=target_lang)
        else:
            batch_char_ctx = char_ctx

        attempt = 1
        missing_ids = None
        best_translations: Dict[int, str] = {}
        total_tokens_consumed = 0

        while self.retry.should_retry(attempt):
            if asyncio.current_task() and asyncio.current_task().cancelled():
                raise asyncio.CancelledError()

            try:
                # 1. Build context with contiguous local batch IDs [001..N] to prevent ID slippage
                ctx = self.context_builder.build_context(all_events, batch, id_map=real_to_local)
                is_allam = "allam" in (model or "").lower()
                local_missing_ids = [real_to_local[m] for m in missing_ids if m in real_to_local] if missing_ids else None
                custom_inst = self.retry.get_instructions_for_attempt(attempt, local_missing_ids, is_allam=is_allam)
                
                # 2. Build prompt
                messages = self.prompt_builder.build_prompt(
                    source_lang=source_lang,
                    target_lang=target_lang,
                    current_subtitles=ctx["current_text"],
                    previous_context=ctx["prev_text"],
                    next_context=ctx["next_text"],
                    characters_context=batch_char_ctx,
                    glossary_context=glossary_ctx,
                    custom_instructions=custom_inst,
                    story_notes=story_notes,
                    model_name=model
                )
                
                # 3. Call LLM with dynamic max tokens tailored to context headroom
                estimated_output = max(256, len(batch) * 60 + 200)
                approx_prompt_tokens = sum(TokenBatcher.estimate_tokens_static(m.content) for m in messages)
                effective_ctx = max_context if (max_context and max_context > 512) else 4096
                headroom = effective_ctx - approx_prompt_tokens - 100
                dynamic_max_tokens = min(
                    max_tokens or 4096,
                    estimated_output,
                    headroom if headroom > 256 else (max_tokens or 2048)
                )
                response = await provider.chat_completion(
                    messages, 
                    model, 
                    temperature=temperature, 
                    max_tokens=dynamic_max_tokens,
                    top_p=top_p,
                    min_p=min_p,
                    repetition_penalty=repetition_penalty
                )
                total_tokens_consumed += (getattr(response, "input_tokens", 0) + getattr(response, "output_tokens", 0))
                
                # 4. Parse with local IDs and remap back to real event IDs
                raw_translations = self.parser.parse_response(response.content, local_ids)
                translations = {
                    local_to_real[lid]: txt
                    for lid, txt in raw_translations.items()
                    if lid in local_to_real
                }
                best_translations.update(translations)
                
                # 5. Targeted Single Line Recovery if only a couple of lines are missing
                missing_in_current = [eid for eid in expected_ids if not best_translations.get(eid)]
                recovery_limit = max(3, min(6, len(batch) // 3))
                if 0 < len(missing_in_current) <= recovery_limit and len(best_translations) > 0:
                    EventBus.instance().log_message.emit(
                        f"🎯 Recovering missing line(s) {missing_in_current} individually..."
                    )
                    for mid in missing_in_current:
                        m_event = next((e for e in batch if e.id == mid), None)
                        if m_event:
                            rec_text, rec_toks = await self._translate_single_line(
                                m_event, provider, model, source_lang, target_lang,
                                batch_char_ctx, glossary_ctx, temperature,
                                story_notes=story_notes, auto_heal=auto_heal, healing_options=eff_opts,
                                top_p=top_p, min_p=min_p, repetition_penalty=repetition_penalty,
                                max_context=max_context, known_names=eff_known,
                            )
                            total_tokens_consumed += rec_toks
                            if rec_text:
                                best_translations[mid] = rec_text

                # 6. Validate (Structure, Gender, Terminology)
                is_valid, issues = self.validator.validate_batch_output(
                    best_translations, batch, characters, glossary, target_lang=target_lang
                )
                
                if is_valid:
                    last_orig, last_imp = "", ""
                    for event in batch:
                        text = best_translations.get(event.id, "")
                        if auto_heal:
                            final_text = SubtitleHealer.heal(
                                text, event.original_text, eff_opts, known_names=eff_known
                            )
                        else:
                            final_text = remove_orphaned_quotes(text)
                        event.translated_text = final_text
                        last_orig = event.original_text
                        last_imp = final_text
                        
                    if last_orig and last_imp:
                        EventBus.instance().live_preview_updated.emit(last_orig, last_imp)

                    if on_batch_status:
                        on_batch_status(expected_ids, "Done")
                    return total_tokens_consumed
                else:
                    EventBus.instance().log_message.emit(f"Batch validation failed on attempt {attempt}: {issues}")
                    
                    missing_ids = []
                    for issue in issues:
                        if "Missing translations for IDs:" in issue:
                            match = re.search(r"\[(.*?)\]", issue)
                            if match:
                                ids_str = match.group(1).split(",")
                                missing_ids.extend([int(id_str.strip()) for id_str in ids_str if id_str.strip().isdigit()])

            except asyncio.CancelledError:
                raise
            except Exception as e:
                err_str = str(e).lower()
                EventBus.instance().log_message.emit(f"Error processing batch on attempt {attempt}: {e}")
                if len(batch) > 1 and any(k in err_str for k in ("context size", "context length", "exceeded", "too large")):
                    EventBus.instance().log_message.emit("⚡ Context size limit hit in translation: Triggering immediate binary split...")
                    break
                await self._handle_backoff(attempt, str(e))
                
            attempt += 1

        # Binary Split fallback if batch size > 1 and max attempts reached
        if len(batch) > 1:
            EventBus.instance().log_message.emit(
                f"🔀 Splitting batch [{expected_ids[0]}-{expected_ids[-1]}] into two smaller halves..."
            )
            mid = len(batch) // 2
            half1 = batch[:mid]
            half2 = batch[mid:]
            
            t1 = await self._process_batch(
                half1, all_events, provider, model, source_lang, target_lang,
                char_ctx, glossary_ctx, temperature, max_tokens, characters, glossary,
                resolver, on_batch_status, story_notes=story_notes, auto_heal=auto_heal, healing_options=eff_opts,
                top_p=top_p, min_p=min_p, repetition_penalty=repetition_penalty,
                max_context=max_context, known_names=eff_known,
            )
            t2 = await self._process_batch(
                half2, all_events, provider, model, source_lang, target_lang,
                char_ctx, glossary_ctx, temperature, max_tokens, characters, glossary,
                resolver, on_batch_status, story_notes=story_notes, auto_heal=auto_heal, healing_options=eff_opts,
                top_p=top_p, min_p=min_p, repetition_penalty=repetition_penalty,
                max_context=max_context, known_names=eff_known,
            )
            return total_tokens_consumed + t1 + t2

        # Final single line fallback
        EventBus.instance().log_message.emit(
            f"Warning: Batch max attempts reached for ID {expected_ids[0]}. Saving partial translation."
        )
        t_low = (target_lang or "ar").strip().lower()
        is_en_target = not is_target_ar and any(k in t_low for k in ("en", "english", "انجل", "إنجل"))
        last_orig, last_imp = "", ""
        for event in batch:
            text = best_translations.get(event.id, "")
            is_corrupt = False
            if text:
                has_cjk = bool(re.search(r'[\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af\u0400-\u04ff]', text))
                if is_target_ar:
                    has_ar = bool(re.search(r'[\u0600-\u06FF]', text))
                    if not has_ar or has_cjk:
                        is_corrupt = True
                elif is_en_target:
                    has_latin = bool(re.search(r'[A-Za-z]', text))
                    if not has_latin or has_cjk:
                        is_corrupt = True

            if not text or is_corrupt:
                rec_text, rec_toks = await self._translate_single_line(
                    event, provider, model, source_lang, target_lang,
                    batch_char_ctx, glossary_ctx, temperature,
                    story_notes=story_notes, auto_heal=auto_heal, healing_options=eff_opts,
                    top_p=top_p, min_p=min_p, repetition_penalty=repetition_penalty,
                    max_context=max_context, known_names=eff_known,
                )
                text = rec_text or event.original_text
                total_tokens_consumed += rec_toks
            if auto_heal:
                final_text = SubtitleHealer.heal(text, event.original_text, eff_opts, known_names=eff_known)
            else:
                final_text = remove_orphaned_quotes(text)
            event.translated_text = final_text
            last_orig = event.original_text
            last_imp = final_text

        if last_orig and last_imp:
            EventBus.instance().live_preview_updated.emit(last_orig, last_imp)

        if on_batch_status:
            on_batch_status(expected_ids, "Done" if all(best_translations.get(e.id) for e in batch) else "Error")
        return total_tokens_consumed

    async def improve_document(
        self,
        document: SubtitleDocument,
        provider: ProviderBase,
        model: str,
        source_lang: str = "en",
        target_lang: str = "ar",
        characters: Optional[List] = None,
        glossary: Optional[List] = None,
        story_notes: str = "",
        on_progress: Optional[Callable] = None,
        on_batch_status: Optional[Callable[[List[int], str], None]] = None,
        concurrency: int = 1,
        temperature: float = 0.1,
        max_tokens: Optional[int] = None,
        auto_heal: bool = True,
        healing_options: Optional[Dict[str, bool]] = None,
        top_p: float = 0.85,
        min_p: float = 0.05,
        repetition_penalty: float = 1.0,
        max_context: int = 4096
    ) -> SubtitleDocument:
        """
        Execute Master Subtitle Improvement & Linguistic Refinement Pass:
        Refines existing Arabic translations with dramatic nuance, flawless grammar,
        Aegisub tag immunity, and Smart Auto-Healing de-noising.
        """
        from app.ui.bus import EventBus
        
        # Events that have either translated text or original text to improve
        skip_effects = True
        if healing_options and "skip_visual_effects" in healing_options:
            skip_effects = healing_options["skip_visual_effects"]

        dedup_enabled = True
        if healing_options and "deduplicate_identical_lines" in healing_options:
            dedup_enabled = healing_options["deduplicate_identical_lines"]

        translate_signs = not skip_effects
        if healing_options and "translate_signs" in healing_options:
            translate_signs = bool(healing_options["translate_signs"])

        known_names = _build_known_names(document, characters)
        eff_healing_opts = _merge_healing_options(healing_options, target_lang)
        document.metadata["target_lang"] = target_lang
        document.metadata["known_names"] = sorted(known_names)

        events_to_improve = [
            e for e in document.get_translatable_events(skip_effects=skip_effects, include_signs=translate_signs)
            if (e.translated_text or e.original_text)
        ]
        if not events_to_improve:
            EventBus.instance().log_message.emit("No dialogue lines found to improve.")
            return document

        imp_resolver = CharacterResolver(characters) if characters else None
        primary_improve_events: List[SubtitleEvent] = []
        improve_duplicates_map: Dict[int, List[SubtitleEvent]] = {}
        improve_text_to_primary: Dict[Tuple, SubtitleEvent] = {}

        if dedup_enabled:
            for e in events_to_improve:
                key_text = (e.translated_text or e.get_clean_text()).strip()
                orig_clean_words = (e.get_clean_text() or e.translated_text or "").strip()
                raw_spk, spk_gender = self._resolve_event_speaker_meta(e, imp_resolver)
                # Use original word count or translated word count for <4-word guard
                word_src = orig_clean_words if orig_clean_words else key_text
                is_long = len(word_src.split()) >= 4 or len(key_text.split()) >= 4
                if not key_text:
                    primary_improve_events.append(e)
                    continue
                if is_long:
                    dedup_k: Optional[Tuple] = ("LONG", key_text)
                elif raw_spk:
                    dedup_k = ("SHORT", key_text, raw_spk.lower(), spk_gender)
                else:
                    dedup_k = None

                if not dedup_k:
                    primary_improve_events.append(e)
                    continue
                if dedup_k in improve_text_to_primary:
                    prim = improve_text_to_primary[dedup_k]
                    improve_duplicates_map.setdefault(prim.id, []).append(e)
                else:
                    improve_text_to_primary[dedup_k] = e
                    primary_improve_events.append(e)

            dup_improve_count = len(events_to_improve) - len(primary_improve_events)
            if dup_improve_count > 0:
                EventBus.instance().log_message.emit(
                    f"⚡ تم رصد {dup_improve_count} سطر تدقيق مكرر: سيتم تدقيق السطر الأول فقط وتمرير التحسين للمكررات."
                )
            events_to_batch = primary_improve_events
        else:
            events_to_batch = events_to_improve
            
        if hasattr(self.batcher, 'max_context'):
            self.batcher.max_context = max_context
        is_local = self._is_local_provider(provider)
        batches = self.batcher.create_batches(events_to_batch, for_improvement=True, is_local=is_local)
        total_batches = len(batches)
        total_lines = len(events_to_improve)
        
        char_ctx = format_character_context(characters, target_lang=target_lang) if characters else ""
        glossary_ctx = format_glossary_context(glossary) if glossary else ""
        
        eff_concurrency = max(1, concurrency)
        semaphore = asyncio.Semaphore(eff_concurrency)
        progress_lock = asyncio.Lock()
        
        completed = 0
        completed_lines = 0
        total_tokens = 0

        async def process_with_sema(idx, batch):
            nonlocal completed, completed_lines, total_tokens
            
            if asyncio.current_task() and asyncio.current_task().cancelled():
                raise asyncio.CancelledError()

            async with semaphore:
                batch_tokens = await self._process_improvement_batch(
                    batch, provider, model, 
                    source_lang, target_lang,
                    char_ctx, glossary_ctx, story_notes,
                    temperature, max_tokens,
                    on_batch_status=on_batch_status,
                    auto_heal=auto_heal, healing_options=eff_healing_opts,
                    top_p=top_p, min_p=min_p, repetition_penalty=repetition_penalty,
                    max_context=max_context, known_names=known_names,
                )
                async with progress_lock:
                    completed += 1
                    completed_lines += len(batch)
                    total_tokens += (batch_tokens or 0)
                    
                    newly_done_ids = []
                    for ev in batch:
                        if ev.translated_text:
                            raw_clean = re.sub(r"\{[^}]*\}", "", ev.translated_text).strip()
                            dup_events = improve_duplicates_map.get(ev.id, [])
                            if dup_events:
                                for dup in dup_events:
                                    if auto_heal:
                                        dup.translated_text = SubtitleHealer.heal(
                                            raw_clean, dup.original_text, eff_healing_opts, known_names=known_names
                                        )
                                    else:
                                        dup.translated_text = remove_orphaned_quotes(raw_clean)
                                    completed_lines += 1
                                    newly_done_ids.append(dup.id)

                    if newly_done_ids and on_batch_status:
                        on_batch_status(newly_done_ids, "Done")

                    cur_completed = completed
                    cur_lines = completed_lines
                    cur_tokens = total_tokens
                if on_progress:
                    try:
                        on_progress(cur_completed, total_batches, cur_lines, total_lines, cur_tokens)
                    except TypeError:
                        on_progress(cur_completed, total_batches)

        tasks = [process_with_sema(idx, batch) for idx, batch in enumerate(batches)]
        await asyncio.gather(*tasks)

        # Fail-safe propagation for improve_document
        if dedup_enabled and improve_duplicates_map:
            for prim_id, dups in improve_duplicates_map.items():
                prim_ev = next((e for e in events_to_batch if e.id == prim_id), None)
                if prim_ev and prim_ev.translated_text:
                    raw_clean = re.sub(r"\{[^}]*\}", "", prim_ev.translated_text).strip()
                    for dup in dups:
                        if not dup.translated_text or dup.translated_text != prim_ev.translated_text:
                            if auto_heal:
                                dup.translated_text = SubtitleHealer.heal(
                                    raw_clean, dup.original_text, eff_healing_opts, known_names=known_names
                                )
                            else:
                                dup.translated_text = remove_orphaned_quotes(raw_clean)
        
        EventBus.instance().log_message.emit(f"✅ Master Subtitle Improvement Pass complete! ({total_lines} lines refined).")
        return document

    async def _process_improvement_batch(
        self,
        batch: List[SubtitleEvent],
        provider: ProviderBase,
        model: str,
        source_lang: str,
        target_lang: str,
        char_ctx: str,
        glossary_ctx: str,
        story_notes: str,
        temperature: float,
        max_tokens: Optional[int],
        on_batch_status: Optional[Callable[[List[int], str], None]] = None,
        auto_heal: bool = True,
        healing_options: Optional[Dict[str, Any]] = None,
        top_p: float = 0.85,
        min_p: float = 0.05,
        repetition_penalty: float = 1.0,
        max_context: int = 4096,
        known_names: Optional[Set[str]] = None,
    ) -> int:
        from app.ui.bus import EventBus

        is_target_ar = _is_arabic_target(target_lang)
        eff_opts = _merge_healing_options(healing_options, target_lang)

        expected_ids = [e.id for e in batch]
        if len(batch) > 1:
            local_ids = list(range(1, len(batch) + 1))
            real_to_local = {e.id: idx for idx, e in enumerate(batch, 1)}
            local_to_real = {idx: e.id for idx, e in enumerate(batch, 1)}
        else:
            local_ids = [batch[0].id]
            real_to_local = {batch[0].id: batch[0].id}
            local_to_real = {batch[0].id: batch[0].id}
        if on_batch_status:
            on_batch_status(expected_ids, "Improving")

        attempt = 1
        missing_ids = None
        best_translations: Dict[int, str] = {}
        total_tokens_consumed = 0
        
        # Pass clean lines with contiguous local IDs to prevent ID slippage across gaps
        current_text = "\n".join(
            f"[{real_to_local[e.id]}] {e.translated_text if e.translated_text else e.get_clean_text()}"
            for e in batch
        )
        
        estimated_output = max(256, len(batch) * 60 + 200)
        approx_prompt_tokens = TokenBatcher.estimate_tokens_static(current_text) + 450
        effective_ctx = max_context if (max_context and max_context > 512) else 4096
        headroom = effective_ctx - approx_prompt_tokens - 100
        dynamic_max_tokens = min(
            max_tokens or 4096,
            estimated_output,
            headroom if headroom > 256 else (max_tokens or 2048)
        )
        
        while self.retry.should_retry(attempt):
            if asyncio.current_task() and asyncio.current_task().cancelled():
                raise asyncio.CancelledError()

            try:
                is_allam = "allam" in (model or "").lower()
                local_missing_ids = [real_to_local[m] for m in missing_ids if m in real_to_local] if missing_ids else None
                custom_inst = self.retry.get_instructions_for_attempt(attempt, local_missing_ids, is_allam=is_allam)
                messages = self.prompt_builder.build_improvement_prompt(
                    source_lang=source_lang,
                    target_lang=target_lang,
                    current_subtitles=current_text,
                    characters_context=char_ctx,
                    glossary_context=glossary_ctx,
                    story_notes=story_notes,
                    custom_instructions=custom_inst,
                    model_name=model
                )
                
                response = await provider.chat_completion(
                    messages, model, temperature=temperature, max_tokens=dynamic_max_tokens,
                    top_p=top_p, min_p=min_p, repetition_penalty=repetition_penalty
                )
                total_tokens_consumed += (getattr(response, "input_tokens", 0) + getattr(response, "output_tokens", 0))
                
                raw_translations = self.parser.parse_response(response.content, local_ids)
                translations = {
                    local_to_real[lid]: txt
                    for lid, txt in raw_translations.items()
                    if lid in local_to_real
                }
                best_translations.update(translations)
                
                # Targeted Single Line Recovery for improvement if only a couple of lines are missing
                missing_in_current = [eid for eid in expected_ids if not best_translations.get(eid)]
                recovery_limit = max(3, min(6, len(batch) // 3))
                if 0 < len(missing_in_current) <= recovery_limit and len(best_translations) > 0:
                    EventBus.instance().log_message.emit(
                        f"🎯 Recovering missing improved line(s) {missing_in_current} individually..."
                    )
                    for mid in missing_in_current:
                        m_event = next((e for e in batch if e.id == mid), None)
                        if m_event:
                            rec_text, rec_toks = await self._improve_single_line(
                                m_event, provider, model, source_lang, target_lang,
                                char_ctx, glossary_ctx, story_notes, temperature,
                                auto_heal=auto_heal, healing_options=eff_opts,
                                top_p=top_p, min_p=min_p, repetition_penalty=repetition_penalty,
                                max_context=max_context, known_names=known_names,
                            )
                            total_tokens_consumed += rec_toks
                            if rec_text:
                                best_translations[mid] = rec_text

                # Check structure
                is_valid, issues = self.validator.validate_batch_output(
                    best_translations, batch, None, None, target_lang=target_lang
                )
                
                if is_valid:
                    last_orig, last_imp = "", ""
                    for event in batch:
                        text = best_translations.get(event.id, event.translated_text or event.original_text)
                        if auto_heal:
                            final_text = event.rebuild_text(
                                text, target_lang=target_lang, known_names=known_names, options=eff_opts
                            )
                        else:
                            from app.subtitle.effect_separator import EffectPayloadIsolator
                            _, skeleton = EffectPayloadIsolator.extract_clean_payload(event.original_text)
                            reconstructed = EffectPayloadIsolator.reconstruct_effect_text(text, skeleton)
                            final_text = remove_orphaned_quotes(reconstructed)
                        event.translated_text = final_text
                        last_orig = event.original_text
                        last_imp = final_text

                    if last_orig and last_imp:
                        EventBus.instance().live_preview_updated.emit(last_orig, last_imp)

                    if on_batch_status:
                        on_batch_status(expected_ids, "Done")
                    return total_tokens_consumed
                else:
                    EventBus.instance().log_message.emit(f"Improvement validation failed attempt {attempt}: {issues}")
                    missing_ids = []
                    for issue in issues:
                        if "Missing translations for IDs:" in issue:
                            match = re.search(r"\[(.*?)\]", issue)
                            if match:
                                ids_str = match.group(1).split(",")
                                missing_ids.extend([int(i.strip()) for i in ids_str if i.strip().isdigit()])
                                
            except asyncio.CancelledError:
                raise
            except Exception as e:
                err_str = str(e).lower()
                EventBus.instance().log_message.emit(f"Improvement error on attempt {attempt}: {e}")
                if len(batch) > 1 and any(k in err_str for k in ("context size", "context length", "exceeded", "too large")):
                    EventBus.instance().log_message.emit("⚡ Context size limit hit in improvement: Triggering immediate binary split...")
                    break
                await self._handle_backoff(attempt, str(e))
            
            attempt += 1
            
        # Binary Split fallback if batch size > 1
        if len(batch) > 1:
            EventBus.instance().log_message.emit(
                f"🔀 Splitting improvement batch [{expected_ids[0]}-{expected_ids[-1]}] ({len(batch)} lines) into smaller halves..."
            )
            mid = len(batch) // 2
            half1 = batch[:mid]
            half2 = batch[mid:]
            t1 = await self._process_improvement_batch(
                half1, provider, model, source_lang, target_lang,
                char_ctx, glossary_ctx, story_notes, temperature, max_tokens,
                on_batch_status=on_batch_status, auto_heal=auto_heal, healing_options=eff_opts,
                top_p=top_p, min_p=min_p, repetition_penalty=repetition_penalty,
                max_context=max_context, known_names=known_names,
            )
            t2 = await self._process_improvement_batch(
                half2, provider, model, source_lang, target_lang,
                char_ctx, glossary_ctx, story_notes, temperature, max_tokens,
                on_batch_status=on_batch_status, auto_heal=auto_heal, healing_options=eff_opts,
                top_p=top_p, min_p=min_p, repetition_penalty=repetition_penalty,
                max_context=max_context, known_names=known_names,
            )
            return total_tokens_consumed + t1 + t2

        EventBus.instance().log_message.emit("Warning: Improvement batch max attempts reached. Applying fallback healing.")
        t_low = (target_lang or "ar").strip().lower()
        is_en_target = not is_target_ar and any(k in t_low for k in ("en", "english", "انجل", "إنجل"))
        last_orig, last_imp = "", ""
        for event in batch:
            text = best_translations.get(event.id) or event.translated_text
            is_corrupt = False
            if text:
                has_cjk = bool(re.search(r'[\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af\u0400-\u04ff]', text))
                if is_target_ar:
                    has_ar = bool(re.search(r'[\u0600-\u06FF]', text))
                    if not has_ar or has_cjk:
                        is_corrupt = True
                elif is_en_target:
                    has_latin = bool(re.search(r'[A-Za-z]', text))
                    if not has_latin or has_cjk:
                        is_corrupt = True

            # If text is still missing or has corrupt/untranslated script, translate it freshly
            if not text or is_corrupt:
                rec_text, rec_toks = await self._translate_single_line(
                    event, provider, model, source_lang, target_lang,
                    char_ctx, glossary_ctx, temperature,
                    story_notes=story_notes, auto_heal=auto_heal, healing_options=eff_opts,
                    top_p=top_p, min_p=min_p, repetition_penalty=repetition_penalty,
                    max_context=max_context, known_names=known_names,
                )
                text = rec_text or event.original_text
                total_tokens_consumed += rec_toks

            if auto_heal:
                final_text = SubtitleHealer.heal(text, event.original_text, eff_opts, known_names=known_names)
            else:
                final_text = remove_orphaned_quotes(text)
            event.translated_text = final_text
            last_orig = event.original_text
            last_imp = final_text

        if last_orig and last_imp:
            EventBus.instance().live_preview_updated.emit(last_orig, last_imp)

        if on_batch_status:
            on_batch_status(expected_ids, "Done")
        return total_tokens_consumed

    async def proofread_document(
        self,
        document: SubtitleDocument,
        provider: ProviderBase,
        model: str,
        source_lang: str = "en",
        target_lang: str = "ar",
        glossary: Optional[List] = None,
        characters: Optional[List] = None,
        story_notes: str = "",
        on_progress: Optional[Callable] = None,
        on_batch_status: Optional[Callable[[List[int], str], None]] = None,
        concurrency: int = 1,
        temperature: float = 0.1,
        max_tokens: Optional[int] = None,
        max_context: int = 4096
    ) -> SubtitleDocument:
        """Backwards compatible proofread method delegating to improve_document."""
        return await self.improve_document(
            document=document,
            provider=provider,
            model=model,
            source_lang=source_lang,
            target_lang=target_lang,
            characters=characters,
            glossary=glossary,
            story_notes=story_notes,
            on_progress=on_progress,
            on_batch_status=on_batch_status,
            concurrency=concurrency,
            temperature=temperature,
            max_tokens=max_tokens,
            max_context=max_context
        )
