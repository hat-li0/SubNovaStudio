import os
import tempfile
from app.subtitle import parse_subtitle, write_subtitle
from app.models.subtitle import SubtitleEvent, SubtitleFormat


def test_ass_rebuild_text_with_tags():
    event = SubtitleEvent(
        id=1,
        original_text=r"{\an8\pos(320,50)}Hello World!",
        text="Hello World!",
        format_type=SubtitleFormat.ASS
    )

    rebuilt = event.rebuild_text("مرحباً بالعالم!")
    assert r"{\an8\pos(320,50)}" in rebuilt
    assert "مرحباً بالعالم!" in rebuilt


def test_ass_roundtrip_translation():
    doc = parse_subtitle('tests/test_data/anime.ass')
    
    # Translate second event
    doc.events[1].translated_text = "إنه فوق 9000!"

    with tempfile.NamedTemporaryFile(suffix='.ass', delete=False) as tmp:
        tmp_path = tmp.name

    try:
        write_subtitle(doc, tmp_path)
        reparsed = parse_subtitle(tmp_path)
        assert len(reparsed.events) == len(doc.events)
        assert reparsed.events[1].speaker == 'Vegeta'
        assert "9000" in reparsed.events[1].original_text or "9000" in (reparsed.events[1].translated_text or "")
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
