import os
import tempfile
from app.subtitle import parse_subtitle, write_subtitle
from app.models.subtitle import SubtitleDocument, SubtitleEvent, SubtitleFormat


def test_srt_writer():
    doc = parse_subtitle('tests/test_data/small.srt')
    with tempfile.NamedTemporaryFile(suffix='.srt', delete=False) as tmp:
        tmp_path = tmp.name

    try:
        write_subtitle(doc, tmp_path)
        reparsed = parse_subtitle(tmp_path)
        assert len(reparsed.events) == len(doc.events)
        assert reparsed.events[0].start == doc.events[0].start
        assert reparsed.events[0].end == doc.events[0].end
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def test_ass_writer():
    doc = parse_subtitle('tests/test_data/anime.ass')
    with tempfile.NamedTemporaryFile(suffix='.ass', delete=False) as tmp:
        tmp_path = tmp.name

    try:
        write_subtitle(doc, tmp_path)
        reparsed = parse_subtitle(tmp_path)
        assert len(reparsed.events) == len(doc.events)
        assert reparsed.events[1].speaker == 'Vegeta'
        assert reparsed.events[2].is_comment is True
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
