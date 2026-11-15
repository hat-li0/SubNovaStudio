import pytest
from app.models.subtitle import SubtitleEvent, SubtitleDocument, SubtitleFormat
from app.subtitle.effect_separator import EffectSeparator, EffectPayloadIsolator
from app.quality.healer import SubtitleHealer


def test_has_translatable_text_classification():
    # 1. Pure drawings must NOT be translatable
    raw_drawing = r"{\p1}m 0 0 l 100 0 100 100 0 100{\p0}"
    assert EffectPayloadIsolator.has_translatable_text(raw_drawing) is False

    # 2. Pure sound effects in asterisks must NOT be translatable
    raw_gasp = "*gasp*"
    assert EffectPayloadIsolator.has_translatable_text(raw_gasp) is False

    # 3. Pure bracketed music or sound cues must NOT be translatable
    raw_music = "[Music Playing]"
    assert EffectPayloadIsolator.has_translatable_text(raw_music) is False
    raw_sfx = r"{\pos(100,200)}SFX: BOOM"
    assert EffectPayloadIsolator.has_translatable_text(raw_sfx) is False

    # 4. Styled signs with human text MUST be translatable
    raw_sign = r"{\an7\pos(320,150)\frz-5\fad(200,200)\fnCairo\fs45\bord3\shad1\c&HFFFFFF&\3c&H000000&}Tokyo Central Hospital"
    assert EffectPayloadIsolator.has_translatable_text(raw_sign) is True

    # 5. On-screen episode titles MUST be translatable
    raw_title = r"{\an8\c&H00FFFF&}EPISODE 01: AWAKENING"
    assert EffectPayloadIsolator.has_translatable_text(raw_title) is True

    # 6. Styled multi-line letters/notes MUST be translatable
    raw_letter = r"{\an7}Dear Kaori,\NPlease forgive me for leaving."
    assert EffectPayloadIsolator.has_translatable_text(raw_letter) is True

    # 7. Standard dialogue MUST be translatable
    raw_diag = r"Where are you going, Conan?"
    assert EffectPayloadIsolator.has_translatable_text(raw_diag) is True


def test_extract_clean_payload_zero_tags():
    # Verify that clean payload sent to LLM has ZERO tags or coordinate noise
    raw = r"{\an7\pos(320,150)\frz-5\fad(200,200)\fnCairo\fs45\bord3\shad1\c&HFFFFFF&\3c&H000000&}Tokyo Central Hospital"
    clean, skeleton = EffectPayloadIsolator.extract_clean_payload(raw)

    # Absolutely no ASS tags or brackets in clean payload!
    assert "{" not in clean
    assert "}" not in clean
    assert "\\" not in clean
    assert clean == "Tokyo Central Hospital"

    # Skeleton must hold original lead tags
    assert skeleton["segments"][0]["lead_tags"] == r"{\an7\pos(320,150)\frz-5\fad(200,200)\fnCairo\fs45\bord3\shad1\c&HFFFFFF&\3c&H000000&}"


def test_reconstruct_effect_text_exact_restoration():
    # Single styled sign
    raw = r"{\an7\pos(320,150)\frz-5\fad(200,200)\fnCairo\fs45\bord3\shad1\c&HFFFFFF&\3c&H000000&}Tokyo Central Hospital"
    clean, skeleton = EffectPayloadIsolator.extract_clean_payload(raw)
    translated = "مستشفى طوكيو المركزي"

    reconstructed = EffectPayloadIsolator.reconstruct_effect_text(translated, skeleton)
    expected = r"{\an7\pos(320,150)\frz-5\fad(200,200)\fnCairo\fs45\bord3\shad1\c&HFFFFFF&\3c&H000000&}مستشفى طوكيو المركزي"
    assert reconstructed == expected


def test_multiline_sign_distinct_tags_per_segment():
    # Multi-line sign with different tags on each line
    raw = r"{\an8\fs24\c&HFFFFFF&}Warning:\N{\c&HFF0000&}High Voltage Area"
    clean, skeleton = EffectPayloadIsolator.extract_clean_payload(raw)

    assert "{" not in clean
    assert "}" not in clean
    assert clean == r"Warning:\NHigh Voltage Area"

    translated = r"تحذير:\Nمنطقة ذات جهد عالٍ"
    reconstructed = EffectPayloadIsolator.reconstruct_effect_text(translated, skeleton)
    expected = r"{\an8\fs24\c&HFFFFFF&}تحذير:\N{\c&HFF0000&}منطقة ذات جهد عالٍ"
    assert reconstructed == expected


def test_subtitle_event_get_clean_text_and_rebuild():
    ev = SubtitleEvent(
        id=1,
        style="Sign",
        original_text=r"{\an8\pos(960,100)\c&H00FFFF&}POLICE DEPARTMENT"
    )

    # get_clean_text must return pure words without tags
    clean = ev.get_clean_text()
    assert clean == "POLICE DEPARTMENT"
    assert "{" not in clean

    # rebuild_text must re-inject the tags and heal
    rebuilt = ev.rebuild_text("قسم الشرطة")
    assert r"{\an8\pos(960,100)\c&H00FFFF&}" in rebuilt
    assert "قسم الشرطة" in rebuilt


def test_document_includes_translatable_signs_when_requested():
    doc = SubtitleDocument(
        format=SubtitleFormat.ASS,
        events=[
            SubtitleEvent(id=1, style="Default", original_text="Hello world"),
            SubtitleEvent(id=2, style="Sign", original_text=r"{\pos(100,200)}Tokyo Hospital"),
            SubtitleEvent(id=3, style="Default", original_text=r"{\p1}m 0 0 l 10 10{\p0}"),
            SubtitleEvent(id=4, style="Default", original_text="*gasp*"),
        ]
    )

    # Event 1 is dialogue (translatable)
    # Event 2 is a styled sign with text (translatable when include_signs=True)
    # Event 3 is pure vector drawing (never translatable)
    # Event 4 is pure gasp sound (never translatable)
    translatable = doc.get_translatable_events(skip_effects=True, include_signs=True)
    assert len(translatable) == 2
    assert translatable[0].id == 1
    assert translatable[1].id == 2


def test_table_model_fx_classification_preserves_text_lines():
    from app.ui.models.subtitle_table_model import SubtitleTableModel
    from PySide6.QtCore import Qt

    model = SubtitleTableModel()
    events = [
        SubtitleEvent(id=1, style="Default", original_text="Normal dialogue"),
        SubtitleEvent(id=2, style="Sign", original_text=r"{\pos(100,200)}Tokyo Hospital"),
        SubtitleEvent(id=3, style="Default", original_text=r"{\p1}m 0 0 l 10 10{\p0}"),
        SubtitleEvent(id=4, style="Default", original_text="*gasp*"),
    ]
    model.set_events(events)

    # Line 1 (dialogue): Pending
    assert model.data(model.index(0, 6), Qt.ItemDataRole.DisplayRole) == "Pending"
    # Line 2 (styled sign with text): Pending (NOT permanently locked to FX!)
    assert model.data(model.index(1, 6), Qt.ItemDataRole.DisplayRole) == "Pending"
    # Line 3 (vector drawing): مؤثرات (FX)
    assert model.data(model.index(2, 6), Qt.ItemDataRole.DisplayRole) == "مؤثرات (FX)"
    # Line 4 (pure gasp): مؤثرات (FX)
    assert model.data(model.index(3, 6), Qt.ItemDataRole.DisplayRole) == "مؤثرات (FX)"

    # When line 2 is translated, status becomes Done
    model.update_event(1, "مستشفى طوكيو", "Done")
    assert model.data(model.index(1, 6), Qt.ItemDataRole.DisplayRole) == "Done"
