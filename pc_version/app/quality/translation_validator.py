from typing import List, Dict, Any, Union
from app.models.subtitle import SubtitleEvent
from app.models.anime import CharacterProfile, GlossaryEntry
from app.quality.gender_validator import GenderValidator
from app.quality.consistency_validator import ConsistencyValidator
from app.quality.format_validator import FormatValidator
from app.character.resolver import CharacterResolver


class QualityValidator:
    """Orchestrator for all quality checks."""

    def __init__(self):
        self.gender_validator = GenderValidator()
        self.consistency_validator = ConsistencyValidator()
        self.format_validator = FormatValidator()

    def run_quality_checks(
        self,
        events: List[SubtitleEvent],
        characters_map: Union[Dict[str, CharacterProfile], List[CharacterProfile]],
        glossary: List[GlossaryEntry],
        target_lang: str = "ar",
    ) -> Dict[str, Any]:
        """
        Runs all quality validators and returns a structured report.
        Resolves speaker names dynamically via CharacterResolver (including first names, aliases, and fuzzy matching).
        """
        report = {
            "warnings_count": 0,
            "flagged_events": [],
            "recommendation": "Pass"
        }

        t_low = (target_lang or "ar").strip().lower()
        is_target_ar = not t_low or any(k in t_low for k in ("ar", "arabic", "عرب"))

        is_dict_map = isinstance(characters_map, dict)
        profiles_list = (
            list(characters_map.values())
            if is_dict_map
            else list(characters_map or [])
        )
        resolver = CharacterResolver(profiles_list) if profiles_list else None

        for event in events:
            event_warnings = []

            # Format validation
            original = event.original_text or ""
            translated = event.translated_text or ""
            format_warnings = self.format_validator.validate_ass_tags(original, translated)
            event_warnings.extend(format_warnings)

            # Gender validation via CharacterResolver (Arabic target only)
            if is_target_ar:
                speaker = (event.speaker or "").strip()
                profile = None
                if speaker:
                    if is_dict_map and speaker in characters_map:
                        profile = characters_map[speaker]
                    elif resolver:
                        match = resolver.resolve_speaker(speaker)
                        if match and match.profile:
                            profile = match.profile

                if profile:
                    gender_warnings = self.gender_validator.validate_gender(translated, profile)
                    event_warnings.extend(gender_warnings)

            if event_warnings:
                report["flagged_events"].append({
                    "event_id": event.id,
                    "warnings": event_warnings
                })
                report["warnings_count"] += len(event_warnings)

        # Consistency validation
        consistency_warnings = self.consistency_validator.validate_consistency(events, glossary)
        if consistency_warnings:
            report["warnings_count"] += len(consistency_warnings)
            for cw in consistency_warnings:
                eid = cw["event_id"]
                existing = next((e for e in report["flagged_events"] if e["event_id"] == eid), None)
                if existing:
                    existing["warnings"].append(cw["message"])
                else:
                    report["flagged_events"].append({
                        "event_id": eid,
                        "warnings": [cw["message"]]
                    })

        if report["warnings_count"] > 0:
            report["recommendation"] = "Review"

        return report
