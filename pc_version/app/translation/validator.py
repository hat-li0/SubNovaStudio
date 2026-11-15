import re
from typing import Dict, List, Optional, Tuple
from app.models.subtitle import SubtitleEvent
from app.character.resolver import CharacterResolver
from app.core.logging import get_logger

logger = get_logger(__name__)


def _is_arabic_target(target_lang: Optional[str]) -> bool:
    t = (target_lang or "ar").strip().lower()
    return not t or any(k in t for k in ("ar", "arabic", "عرب"))


class GenderValidator:
    def validate(
        self,
        parsed_translations: Dict[int, str],
        expected_events: List[SubtitleEvent],
        characters: List,
        target_lang: str = "ar",
    ) -> List[str]:
        issues = []
        if not characters or not _is_arabic_target(target_lang):
            return issues

        resolver = CharacterResolver(characters)
        for event in expected_events:
            text = parsed_translations.get(event.id, "")
            if not text or not event.speaker:
                continue

            speaker = event.speaker.strip()
            match = resolver.resolve_speaker(speaker)
            if match and match.profile:
                profile = match.profile
                gender_info = getattr(profile, "gender_info", None)
                gender = str(getattr(gender_info, "gender", "") or getattr(profile, "gender", "")).upper()

                if "MALE" in gender and "FEMALE" not in gender:
                    # Match Arabic feminine 2nd-person Kasra suffixes without \b after nonspacing diacritic \u0650
                    if re.search(
                        r"(?:^|[\s\"\'\(\[«\-])(?:أنتِ|[\u0621-\u064A]{2,}(?:تِ|كِ))(?=$|\s|[!؟\.\،\؛:\"\'\)\]»])",
                        text,
                    ):
                        issues.append(
                            f"Gender Warning (ID {event.id}): Speaker {speaker} is MALE but text contains feminine 2nd-person form."
                        )
        return issues

class TerminologyValidator:
    def validate(self, parsed_translations: Dict[int, str], expected_events: List[SubtitleEvent], glossary: List) -> List[str]:
        issues = []
        if not glossary:
            return issues
            
        for event in expected_events:
            text = parsed_translations.get(event.id, "")
            orig = event.get_clean_text()
            if not text or not orig:
                continue
                
            for term in glossary:
                source = getattr(term, "source_term", "")
                target = getattr(term, "target_term", "")
                if source and target and source.lower() in orig.lower():
                    if target not in text:
                        issues.append(f"Terminology Warning (ID {event.id}): Expected '{target}' for '{source}' in translation.")
        return issues

class PipelineValidator:
    """Validates the output of a translation batch."""
    
    def __init__(self):
        self.gender_val = GenderValidator()
        self.term_val = TerminologyValidator()
    
    def validate_batch_output(
        self,
        parsed_translations: Dict[int, str],
        expected_events: List[SubtitleEvent],
        characters: List = None,
        glossary: List = None,
        target_lang: str = "ar",
    ) -> Tuple[bool, List[str]]:
        """
        Validate parsed translations against expected events.
        Returns (is_valid, list_of_blocking_issues)
        """
        issues = []
        is_target_ar = _is_arabic_target(target_lang)
        t_low = (target_lang or "ar").strip().lower()
        is_cjk_target = any(k in t_low for k in ("ja", "jp", "japanese", "zh", "chinese", "ko", "korean"))

        expected_ids = {e.id for e in expected_events}
        parsed_ids = set(parsed_translations.keys())
        
        # 1. Output Structure Validation
        missing_ids = expected_ids - parsed_ids
        if missing_ids:
            issues.append(f"Missing translations for IDs: {sorted(missing_ids)}")
            
        extra_ids = parsed_ids - expected_ids
        if extra_ids:
            issues.append(f"Extra unexpected translations for IDs: {sorted(extra_ids)}")
            
        for event_id in expected_ids.intersection(parsed_ids):
            text = parsed_translations[event_id]
            if not text or not text.strip():
                issues.append(f"Empty translation for ID: {event_id}")
            elif "```" in text or text.startswith("Here is"):
                issues.append(f"Suspicious markdown or conversational residue for ID: {event_id}")
            elif not is_cjk_target and re.search(r"[\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af]", text):
                issues.append(f"Hallucination (ID {event_id}): Text contains Chinese/Asian characters: '{text[:30]}'")
            elif is_target_ar and not re.search(r"[\u0600-\u06FF]", text) and len(text.strip()) > 3:
                issues.append(f"Untranslated or Non-Arabic Output (ID {event_id}): '{text[:30]}'")
            elif not is_target_ar and ("en" in t_low or "english" in t_low):
                if re.search(r"[\u0600-\u06FF]", text):
                    issues.append(f"Untranslated or Non-Target Output (ID {event_id}): '{text[:30]}'")
                elif len(text.strip()) > 3 and not re.search(r"[A-Za-z]", text):
                    issues.append(f"Untranslated or Non-Target Output (ID {event_id}): '{text[:30]}'")
                
        # 2. Gender Validation
        if characters:
            issues.extend(self.gender_val.validate(parsed_translations, expected_events, characters, target_lang=target_lang))
            
        # 3. Terminology Validation
        if glossary:
            issues.extend(self.term_val.validate(parsed_translations, expected_events, glossary))
                
        blocking_issues = [
            i for i in issues 
            if any(k in i for k in ("Missing", "Empty", "Suspicious", "Hallucination", "Untranslated", "Non-Arabic", "Non-Target"))
        ]
        is_valid = len(blocking_issues) == 0
        
        warnings = [i for i in issues if i not in blocking_issues]
        if warnings:
            for w in warnings:
                logger.warning(w)
                
        return is_valid, blocking_issues

# Alias for testing/backward compatibility
TranslationValidator = PipelineValidator
