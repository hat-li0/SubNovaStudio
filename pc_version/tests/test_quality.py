import pytest
from app.quality.gender_validator import GenderValidator
from app.quality.consistency_validator import ConsistencyValidator
from app.quality.format_validator import FormatValidator
from app.quality.translation_validator import QualityValidator
from app.models.subtitle import SubtitleEvent
from app.models.character import CharacterProfile, GenderEnum
from app.models.glossary import GlossaryEntry


def test_gender_validator():
    validator = GenderValidator()
    
    # Test female using masculine
    female = CharacterProfile(canonical_name="Frieren", gender=GenderEnum.FEMALE)
    warnings = validator.validate_gender("أنتَ شجاع", female)
    assert len(warnings) == 1
    assert "أنتَ" in warnings[0]
    
    # Test female using correct feminine
    warnings = validator.validate_gender("أنتِ شجاعة", female)
    assert len(warnings) == 0


def test_consistency_validator():
    validator = ConsistencyValidator()
    glossary = [
        GlossaryEntry(source_term="Commander", target_term="القائد")
    ]
    
    event1 = SubtitleEvent(id=1, original_text="Yes, Commander", translated_text="نعم أيها القائد")
    event2 = SubtitleEvent(id=2, original_text="Hello Commander", translated_text="مرحبا أيها الزعيم")  # Missing target
    
    warnings = validator.validate_consistency([event1, event2], glossary)
    assert len(warnings) == 1
    assert warnings[0]["event_id"] == 2
    assert warnings[0]["expected_target"] == "القائد"


def test_format_validator():
    validator = FormatValidator()
    
    orig = r"Hello {\b1}World{\b0}\Ntest"
    valid_trans = r"مرحبا {\b1}عالم{\b0}\Nاختبار"
    invalid_trans = "مرحبا عالم اختبار"
    
    assert len(validator.validate_ass_tags(orig, valid_trans)) == 0
    
    warnings = validator.validate_ass_tags(orig, invalid_trans)
    assert len(warnings) >= 2  # missing {\b1}, {\b0}, and mismatched \N


def test_quality_validator():
    validator = QualityValidator()
    
    events = [
        SubtitleEvent(id=1, speaker="Frieren", original_text="I am Commander", translated_text="أنا القائد أنتَ")
    ]
    chars = {
        "Frieren": CharacterProfile(canonical_name="Frieren", gender=GenderEnum.FEMALE)
    }
    glossary = [
        GlossaryEntry(source_term="Commander", target_term="القائد")
    ]
    
    report = validator.run_quality_checks(events, chars, glossary)
    assert report["warnings_count"] == 1
    assert report["recommendation"] == "Review"
    assert "أنتَ" in report["flagged_events"][0]["warnings"][0]
