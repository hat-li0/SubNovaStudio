import pytest
from app.models.subtitle import SubtitleEvent, SubtitleDocument, SubtitleFormat
from app.subtitle.effect_separator import EffectSeparator
from app.quality.healer import SubtitleHealer


def test_effect_separator_is_mixed_line():
    # 1. Mixed line with top sign (\an8) and bottom dialogue (\r\an2)
    ev1 = SubtitleEvent(id=1, original_text=r"{\an8\c&H00FFFF&}JAPANESE SIGN\N{\r\an2}Hello everyone!")
    assert EffectSeparator.is_mixed_line(ev1) is True

    # 2. Mixed line with dialogue first, then positioned explosion
    ev2 = SubtitleEvent(id=2, original_text=r"Hey, did you see that?\N{\pos(960,100)\c&H00FF00&}*EXPLOSION*")
    assert EffectSeparator.is_mixed_line(ev2) is True

    # 3. Mixed line with vector drawing ending in {\p0} followed by dialogue
    ev3 = SubtitleEvent(id=3, original_text=r"{\p1}m 0 0 l 10 10{\p0} Hello world")
    assert EffectSeparator.is_mixed_line(ev3) is True

    # 4. Mixed line with positioned sound effect and style reset {\r}
    ev4 = SubtitleEvent(id=4, original_text=r"{\pos(100,200)\c&H0000FF&}*Crash*{\r}What was that?")
    assert EffectSeparator.is_mixed_line(ev4) is True

    # 5. Normal two-speaker dialogue (NOT mixed)
    ev5 = SubtitleEvent(id=5, original_text=r"- Hello!\N- Hi there!")
    assert EffectSeparator.is_mixed_line(ev5) is False

    # 6. Normal multiline dialogue (NOT mixed)
    ev6 = SubtitleEvent(id=6, original_text=r"This is a long sentence\Nsplit across two lines.")
    assert EffectSeparator.is_mixed_line(ev6) is False

    # 7. Pure effect line (NOT mixed)
    ev7 = SubtitleEvent(id=7, original_text=r"{\an8\c&H00FFFF&}ONLY SIGN")
    assert EffectSeparator.is_mixed_line(ev7) is False


def test_effect_separator_separate_event():
    # Split mixed line into FX event and Dialogue event
    ev = SubtitleEvent(
        id=10,
        start="00:01:23.45",
        end="00:01:28.90",
        style="Default",
        original_text=r"{\an8\c&H00FFFF&}JAPANESE SIGN\N{\r\an2}Hello everyone!"
    )

    separated = EffectSeparator.separate_event(ev)
    assert len(separated) == 2

    # First event: The FX sign
    fx_ev = separated[0]
    assert fx_ev.is_visual_effect() is True
    assert fx_ev.is_translatable() is False
    assert r"{\an8\c&H00FFFF&}JAPANESE SIGN" in fx_ev.original_text
    assert fx_ev.start == "00:01:23.45"
    assert fx_ev.end == "00:01:28.90"

    # Second event: The spoken dialogue
    diag_ev = separated[1]
    assert diag_ev.is_visual_effect() is False
    assert diag_ev.is_translatable() is True
    assert "Hello everyone!" in diag_ev.text
    assert diag_ev.start == "00:01:23.45"
    assert diag_ev.end == "00:01:28.90"


def test_effect_separator_document_processing():
    doc = SubtitleDocument(
        format=SubtitleFormat.ASS,
        events=[
            SubtitleEvent(id=1, original_text="Normal dialogue 1"),
            SubtitleEvent(id=2, original_text=r"{\an8}TOP SIGN\N{\r}What are you doing?"),
            SubtitleEvent(id=3, original_text="Normal dialogue 2"),
        ]
    )

    separated_doc = EffectSeparator.separate_document(doc)
    assert len(separated_doc.events) == 4

    # Check sequential IDs
    assert [e.id for e in separated_doc.events] == [1, 2, 3, 4]

    # Event 1: Normal dialogue
    assert separated_doc.events[0].is_translatable() is True

    # Event 2: Isolated FX sign
    assert separated_doc.events[1].is_visual_effect() is True
    assert "TOP SIGN" in separated_doc.events[1].original_text

    # Event 3: Isolated Dialogue
    assert separated_doc.events[2].is_translatable() is True
    assert "What are you doing?" in separated_doc.events[2].text

    # Event 4: Normal dialogue 2
    assert separated_doc.events[3].is_translatable() is True


def test_subtitle_event_get_clean_text_isolates_drawings():
    ev = SubtitleEvent(
        id=1,
        original_text=r"{\p1}m 0 0 l 100 0 100 100 0 100{\p0} Button Text"
    )
    clean = ev.get_clean_text()
    # Coordinates must NEVER appear in the clean text
    assert "m 0 0" not in clean
    assert "100" not in clean
    assert clean == "Button Text"


def test_subtitle_healer_segmented_tags_restoration():
    orig = r"{\an8\c&H00FFFF&}JAPANESE SIGN\N{\r\an2}Hello everyone!"
    trans = r"عنوان اللوحة\Nمرحباً بالجميع!"

    healed = SubtitleHealer.heal(trans, orig)

    # Segment 1 must have \an8, Segment 2 must have \r\an2
    parts = healed.split(r"\N")
    assert len(parts) == 2
    assert r"{\an8" in parts[0]
    assert r"{\r\an2}" in parts[1] or r"{\r" in parts[1]


def test_subtitle_healer_drawing_preservation():
    drawing_line = r"{\p1}m 0 0 l 50 0 50 50 0 50{\p0}نص مترجم"
    healed = SubtitleHealer.heal(drawing_line, drawing_line)
    assert r"m 0 0 l 50 0 50 50 0 50" in healed
    assert r"{\p1}" in healed
    assert r"{\p0}" in healed


def test_subtitle_healer_sfx_spacing():
    # Sound effect bracket cues must be cleanly separated with spaces
    text = "[انفجار]مهلاً انتبه!"
    healed = SubtitleHealer.separate_sfx_and_audio_cues(text)
    assert healed == "[انفجار] مهلاً انتبه!"


def test_fansub_styles_dialogue_and_english_songs_filtering():
    """
    Verifies that English song styles (ED1-En, ED2-En, OP1-En) and dialogue styles
    (Default, Top, Alt) are 100% translatable and never dropped,
    while Romaji karaoke (ED2-Ro, OP1-Ro) and signs/fx are ignored.
    """
    # 1. ED2-En line with complex positioning, fade, and multiple \t tags
    ed2_en = SubtitleEvent(
        id=1,
        style="ED2-En",
        original_text=r"{\pos(960,1020)\fad(150,150)\t(0,200,\fscx105)\t(200,400,\fscx100)}Heap them all on the flame...\NEach of us is born alone"
    )
    assert ed2_en.is_style_translatable("ED2-En") is True
    assert ed2_en.is_style_blocked("ED2-En") is False
    assert ed2_en.is_visual_effect() is False
    assert ed2_en.is_translatable() is True

    # 2. ED2-Ro line with karaoke tags (Romaji)
    ed2_ro = SubtitleEvent(
        id=2,
        style="ED2-Ro",
        original_text=r"{\k12}ta{\k15}me{\k20}ra{\k18}i"
    )
    assert ed2_ro.is_style_translatable("ED2-Ro") is False
    assert ed2_ro.is_style_blocked("ED2-Ro") is True
    assert ed2_ro.is_visual_effect() is True
    assert ed2_ro.is_translatable() is False

    # 3. OP1-En line
    op1_en = SubtitleEvent(
        id=3,
        style="OP1-En",
        original_text=r"{\an8\clip(0,0,1920,1080)}Let your voice be heard"
    )
    assert op1_en.is_style_translatable("OP1-En") is True
    assert op1_en.is_visual_effect() is False
    assert op1_en.is_translatable() is True

    # 4. OP1-Ro line
    op1_ro = SubtitleEvent(
        id=4,
        style="OP1-Ro",
        original_text=r"koe wo kikasete"
    )
    assert op1_ro.is_style_blocked("OP1-Ro") is True
    assert op1_ro.is_visual_effect() is True
    assert op1_ro.is_translatable() is False

    # 5. Sign line
    sign_ev = SubtitleEvent(
        id=5,
        style="Sign",
        original_text=r"{\pos(500,200)}SCHOOL ENTRANCE"
    )
    assert sign_ev.is_style_blocked("Sign") is True
    assert sign_ev.is_visual_effect() is True
    assert sign_ev.is_translatable() is False

    # 6. Dialogue styles (Default, Top, Alt)
    for diag_style in ("Default", "Default-Italic", "Top", "Alt", "Main", "Dialogue"):
        d_ev = SubtitleEvent(id=6, style=diag_style, original_text="Hello world!")
        assert d_ev.is_style_translatable(diag_style) is True
        assert d_ev.is_visual_effect() is False
        assert d_ev.is_translatable() is True


def test_mixed_arabic_dialogue_with_english_effects():
    """
    Tests isolating English effects mixed with Arabic dialogue in the same line,
    ensuring the FX part is quarantined and only translatable dialogue remains.
    """
    # 1. Line with English SFX and Arabic dialogue with \N
    ev1 = SubtitleEvent(
        id=1,
        style="Default",
        original_text=r"{\an8\fs18}SFX: RUMBLE\N{\r\fs24}- ماذا كان ذلك الصوت؟"
    )
    assert EffectSeparator.is_mixed_line(ev1) is True
    sep1 = EffectSeparator.separate_event(ev1)
    assert len(sep1) == 2
    # FX Event:
    assert sep1[0].is_visual_effect() is True
    assert sep1[0].is_translatable() is False
    assert "SFX: RUMBLE" in sep1[0].original_text
    # Dialogue Event:
    assert sep1[1].is_visual_effect() is False
    assert sep1[1].is_translatable() is True
    assert "- ماذا كان ذلك الصوت؟" in sep1[1].text

    # 2. Inline effect without \N at start of Arabic dialogue
    ev2 = SubtitleEvent(
        id=2,
        style="Default",
        original_text=r"{\pos(100,200)}[SFX: EXPLOSION] هل الجميع بخير؟"
    )
    assert EffectSeparator.is_mixed_line(ev2) is True
    sep2 = EffectSeparator.separate_event(ev2)
    assert len(sep2) == 2
    assert sep2[0].is_visual_effect() is True
    assert "[SFX: EXPLOSION]" in sep2[0].original_text
    assert sep2[1].is_visual_effect() is False
    assert "هل الجميع بخير؟" in sep2[1].text

    # 3. Inline effect at end of dialogue
    ev3 = SubtitleEvent(
        id=3,
        style="Default",
        original_text=r"- انتبه يا صديقي! *CRASH*"
    )
    assert EffectSeparator.is_mixed_line(ev3) is True
    sep3 = EffectSeparator.separate_event(ev3)
    assert len(sep3) == 2
    assert sep3[0].is_translatable() is True
    assert "- انتبه يا صديقي!" in sep3[0].text
    assert sep3[1].is_visual_effect() is True
    assert "*CRASH*" in sep3[1].original_text


def test_pure_sfx_and_signs_with_default_style_detection():
    """
    Verifies that lines containing pure effects, signs, or onomatopoeia
    are accurately identified as visual effects even when style is 'Default'.
    """
    # 1. Pure SFX with Style Default
    sfx1 = SubtitleEvent(id=1, style="Default", original_text=r"{\pos(100,200)}SFX: BOOM")
    assert sfx1.is_visual_effect() is True
    assert sfx1.is_translatable() is False

    # 2. Asterisk sound cue with Style Default
    sfx2 = SubtitleEvent(id=2, style="Default", original_text="*gasp*")
    assert sfx2.is_visual_effect() is True
    assert sfx2.is_translatable() is False

    # 3. Episode title with Style Default
    sign1 = SubtitleEvent(id=3, style="Default", original_text=r"{\an8}EPISODE 01: AWAKENING")
    assert sign1.is_visual_effect() is True
    assert sign1.is_translatable() is False

    # 4. English Sign with Style Default
    sign2 = SubtitleEvent(id=4, style="Default", original_text=r"{\pos(200,300)}Sign: Police Station")
    assert sign2.is_visual_effect() is True
    assert sign2.is_translatable() is False

    # 5. Normal dialogue remains translatable
    diag = SubtitleEvent(id=5, style="Default", original_text="Where are you going?")
    assert diag.is_visual_effect() is False
    assert diag.is_translatable() is True


def test_document_skips_isolated_effects_and_preserves_count():
    """
    Tests document-level separation where effects are skipped from translation
    and preserved in the file.
    """
    doc = SubtitleDocument(
        format=SubtitleFormat.ASS,
        events=[
            SubtitleEvent(id=1, style="Default", original_text="Spoken dialogue 1"),
            SubtitleEvent(id=2, style="Default", original_text=r"{\an8}SFX: THUNDER\N- Did you hear that?"),
            SubtitleEvent(id=3, style="Default", original_text=r"{\pos(100,200)}*EXPLOSION*"),
            SubtitleEvent(id=4, style="Default", original_text="Spoken dialogue 2"),
        ]
    )
    doc = EffectSeparator.separate_document(doc)
    # Event 2 was split into 2 events, so total events = 5
    assert len(doc.events) == 5

    # Translatable events should ONLY be the 3 dialogue lines
    translatable = doc.get_translatable_events(skip_effects=True)
    assert len(translatable) == 3
    assert translatable[0].text == "Spoken dialogue 1"
    assert translatable[1].text == "- Did you hear that?"
    assert translatable[2].text == "Spoken dialogue 2"


def test_dialogue_with_subber_notes_in_effect_field_remains_translatable():
    """Verify lines with subber notes in the Effect field (e.g. 'new blur consistency') remain translatable."""
    ev = SubtitleEvent(
        id=1,
        layer=0,
        start="0:03:59.01",
        end="0:04:03.13",
        style="Default SY",
        effect="new blur consistency",
        original_text=r"{\blur1\c&H3D2C27&}Ah, the red fountains humans\Nmake are so pretty."
    )
    assert ev.is_visual_effect() is False
    assert ev.is_translatable() is True

    # But genuine Aegisub automation effects must still be flagged as visual effects
    ev_automation = SubtitleEvent(
        id=2,
        layer=0,
        start="0:01:00.00",
        end="0:01:05.00",
        style="Default",
        effect="template line",
        original_text="Some automated line"
    )
    assert ev_automation.is_visual_effect() is True
    assert ev_automation.is_translatable() is False


