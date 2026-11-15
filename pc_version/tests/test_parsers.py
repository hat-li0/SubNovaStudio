import os
from app.subtitle import parse_subtitle

def test_srt_parser():
    doc = parse_subtitle('tests/test_data/small.srt')
    assert len(doc.events) == 3
    assert doc.events[1].text == 'Second line\nWith two lines'
    assert doc.events[1].original_text == 'Second <i>line</i>\nWith two lines'

def test_ass_parser():
    doc = parse_subtitle('tests/test_data/anime.ass')
    assert len(doc.events) == 4
    assert doc.events[1].speaker == 'Vegeta'
    assert doc.events[1].text == "It's over 9000!"
    assert doc.events[2].is_comment == True
