import os
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import patch
import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QUndoStack
from PySide6.QtWidgets import QApplication

from app.models.subtitle import SubtitleDocument, SubtitleEvent, SubtitleFormat
from app.subtitle import parse_subtitle, write_subtitle
from app.subtitle.parsers.srt import SRTParser
from app.subtitle.parsers.vtt import VTTParser
from app.subtitle.parsers.ass import ASSParser
from app.subtitle.writers.srt import SRTWriter
from app.subtitle.writers.vtt import VTTWriter
from app.subtitle.writers.ass import ASSWriter
from app.subtitle.timecode import (
    parse_timecode_ms,
    format_timecode,
    format_ass_time,
    format_srt_time,
    format_vtt_time,
    normalize_timecode,
)
from app.subtitle.video_extractor import VideoSubtitleExtractor
from app.ui.commands import ShiftTimingsCommand
from app.ui.dialogs.timing_dialog import ShiftTimingsDialog
from app.ui.models.subtitle_table_model import SubtitleTableModel
from app.ui.widgets.inline_editor_widget import InlineSubtitleEditor
from app.ui.widgets.video_player_widget import SubNovaVideoPlayerWidget


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if not app:
        app = QApplication([])
    return app


def test_timecode_parsing_precision_and_validation():
    # Standard formats
    assert parse_timecode_ms("0:01:23.45") == 83450
    assert parse_timecode_ms("00:01:23,450") == 83450
    assert parse_timecode_ms("00:01:23.450") == 83450
    # VTT without hours
    assert parse_timecode_ms("01:23.450") == 83450
    # Whole seconds
    assert parse_timecode_ms("00:01:23") == 83000

    # Non-3-digit fractional seconds (>3 digits previously caused +minutes corruption!)
    assert parse_timecode_ms("0:00:01.5") == 1500
    assert parse_timecode_ms("0:00:01.2500") == 1250
    assert parse_timecode_ms("0:00:01.250000") == 1250
    # Rounding up across second boundary cleanly
    assert parse_timecode_ms("0:00:01.9999") == 2000

    # Strict rejection of invalid / out-of-range / negative inputs
    assert parse_timecode_ms("") is None
    assert parse_timecode_ms("abc") is None
    assert parse_timecode_ms("-0:00:01.00") is None
    assert parse_timecode_ms("0:00:-1.00") is None
    assert parse_timecode_ms("00:75:00.00") is None
    assert parse_timecode_ms("00:01:65,000") is None
    assert parse_timecode_ms("12:34") is None

    # Format style preservation (VTT .mmm preserved instead of degrading to .cc)
    assert format_timecode(83450, template_str="01:00.000") == "00:01:23.450"
    assert format_timecode(83450, template_str="00:01:00,000") == "00:01:23,450"
    assert format_timecode(83450, template_str="0:01:00.00") == "0:01:23.45"


def test_timing_dialog_direction_matches_timeline_math(qapp):
    dlg = ShiftTimingsDialog(None, has_selection=False, sample_start_time="0:00:10.00")
    try:
        dlg.spn_ms.setValue(500)
        # Default: delay display (+ms, appears later on screen)
        dlg.radio_delay.setChecked(True)
        assert dlg.get_offset_ms() == 500
        assert "0:00:10.50" in dlg.lbl_preview.text()
        assert "لاحقاً" in dlg.lbl_preview.text()

        # Advance display (-ms, appears earlier on screen)
        dlg.radio_advance.setChecked(True)
        assert dlg.get_offset_ms() == -500
        assert "0:00:09.50" in dlg.lbl_preview.text()
        assert "أبكر" in dlg.lbl_preview.text()

        # Shifting backward past 0 explains clamp
        dlg.spn_ms.setValue(15000)
        assert "0:00:00.00" in dlg.lbl_preview.text()
        assert "التثبيت" in dlg.lbl_preview.text()
    finally:
        dlg.deleteLater()
        qapp.processEvents()


def test_table_model_rejects_invalid_and_preserves_duration_on_clamp(qapp):
    model = SubtitleTableModel()
    ev_clamp = SubtitleEvent(
        id=1,
        start_time="0:00:00.20",
        end_time="0:00:01.20",
        original_text="Near start",
        format_type=SubtitleFormat.ASS,
    )
    ev_vtt = SubtitleEvent(
        id=2,
        start_time="01:00.250",
        end_time="01:02.750",
        original_text="VTT precision",
        format_type=SubtitleFormat.VTT,
    )
    model.set_events([ev_clamp, ev_vtt])

    # Invalid cell time edits must be rejected strictly
    assert model.setData(model.index(0, 1), "not-a-time", Qt.ItemDataRole.EditRole) is False
    assert model.setData(model.index(0, 2), "00:99:00.00", Qt.ItemDataRole.EditRole) is False
    assert ev_clamp.start_time == "0:00:00.20"
    assert ev_clamp.end_time == "0:00:01.20"

    # Non-standard fractional precision normalized cleanly
    assert model.setData(model.index(1, 1), "01:00.2500", Qt.ItemDataRole.EditRole) is True
    assert ev_vtt.start_time == "00:01:00.250"

    # Clamp at 0 via ShiftTimingsCommand preserves full 1.00s duration and restores exact snapshot on Undo
    undo_stack = QUndoStack()
    cmd = ShiftTimingsCommand(model, -500, [0, 1])
    undo_stack.push(cmd)

    # Row 0: 0.20..1.20 - 0.50s => 0.00..1.00 (NOT truncated to 0.70!)
    assert ev_clamp.start_time == "0:00:00.00"
    assert ev_clamp.end_time == "0:00:01.00"
    # Row 1: VTT millisecond precision kept (01:02.750 - 500ms => 00:01:02.250)
    assert ev_vtt.start_time == "00:00:59.750"
    assert ev_vtt.end_time == "00:01:02.250"

    # Undo must restore exact pre-clamp timestamps
    undo_stack.undo()
    assert ev_clamp.start_time == "0:00:00.20"
    assert ev_clamp.end_time == "0:00:01.20"
    assert ev_vtt.start_time == "00:01:00.250"


def test_proportional_and_cursor_aware_line_split(qapp):
    model = SubtitleTableModel()
    ev = SubtitleEvent(
        id=1,
        start_time="00:00:10,000",
        end_time="00:00:20,000",
        original_text="Ok.\nThis second sentence is very much longer than the first one by far.",
        format_type=SubtitleFormat.SRT,
    )
    model.set_events([ev])

    # Proportional split: short first half must get LESS than 5000ms (around ~2000ms, clamped >= 20%)
    assert model.split_line(0) is True
    assert model.rowCount() == 2
    s1_end = parse_timecode_ms(model.events[0].end_time)
    s2_start = parse_timecode_ms(model.events[1].start_time)
    assert s1_end == s2_start
    assert 12000 <= s1_end < 15000

    # Active video playback position overrides proportional split
    model2 = SubtitleTableModel()
    ev2 = SubtitleEvent(
        id=1,
        start_time="0:00:10.00",
        end_time="0:00:20.00",
        original_text=r"First part\NSecond part",
        format_type=SubtitleFormat.ASS,
    )
    model2.set_events([ev2])
    assert model2.split_line(0, split_at_ms=13400) is True
    assert model2.events[0].end_time == "0:00:13.40"
    assert model2.events[1].start_time == "0:00:13.40"


def test_inline_editor_rejects_invalid_timing_edits(qapp):
    editor = InlineSubtitleEditor()
    try:
        ev = SubtitleEvent(
            id=1,
            start_time="0:00:05.00",
            end_time="0:00:08.00",
            original_text="Test",
            translated_text="تجربة",
        )
        editor.load_event(0, ev, 1)

        emitted = []
        editor.line_updated.connect(lambda *args: emitted.append(args))

        # Invalid time string must block emission and mark red
        editor.edit_start.setText("bad-time")
        assert len(emitted) == 0
        assert "غير صالح" in editor.lbl_cps.text()
        assert "ef4444" in editor.edit_start.styleSheet()

        # Reversed order (end < start) must also block emission
        editor.edit_start.setText("0:00:12.00")
        assert len(emitted) == 0
        assert "النهاية قبل البداية" in editor.lbl_cps.text()

        # Valid range restores green CPS and emits
        editor.edit_end.setText("0:00:15.00")
        assert len(emitted) == 1
        assert emitted[0][1] == "0:00:12.00"
        assert emitted[0][2] == "0:00:15.00"
        assert editor.edit_start.styleSheet() == ""
    finally:
        editor.deleteLater()
        qapp.processEvents()


def test_video_player_half_open_intervals_and_overlap_filtering(qapp):
    player = SubNovaVideoPlayerWidget()
    try:
        events = [
            SubtitleEvent(id=1, start_time="0:00:01.00", end_time="0:00:03.00", original_text="Comment", is_comment=True),
            SubtitleEvent(id=2, start_time="0:00:01.00", end_time="0:00:03.00", original_text=r"{\p1}m 0 0 l 10 10{\p0}", format_type=SubtitleFormat.ASS),
            SubtitleEvent(id=3, start_time="bad", end_time="0:00:05.00", original_text="Invalid start"),
            SubtitleEvent(id=4, start_time="0:00:01.00", end_time="0:00:03.00", original_text="First", translated_text="الأول"),
            SubtitleEvent(id=5, start_time="0:00:02.00", end_time="0:00:04.00", original_text="Second", translated_text="الثاني"),
            SubtitleEvent(id=6, start_time="01:00.500", end_time="01:02.000", original_text="VTT", translated_text="صيغة ويب", format_type=SubtitleFormat.VTT),
        ]
        player.set_subtitles_for_overlay(events)
        # Comment, vector drawing, and invalid timestamp must be excluded
        assert len(player.subtitles) == 3

        # Half-open interval [s_ms, e_ms) & simultaneous lines
        assert player.get_active_subtitles_at(1000) == ["الأول"]
        assert player.get_active_subtitles_at(2500) == ["الأول", "الثاني"]
        assert player.get_active_subtitles_at(3000) == ["الثاني"]  # 3000 excluded from 1000..3000
        assert player.get_active_subtitles_at(4000) == []
        # VTT without hours parsed cleanly
        assert player.get_active_subtitles_at(61000) == ["صيغة ويب"]

        # Seeking with invalid string must not jump to 0
        with patch.object(player, "seek_to_ms") as mock_seek:
            player.seek_to_time_str("invalid-time")
            assert not mock_seek.called
            player.seek_to_time_str("01:00.500")
            mock_seek.assert_called_once_with(60500)
    finally:
        player.cleanup()
        player.deleteLater()
        qapp.processEvents()


def test_srt_vtt_ass_parsers_and_writers_edge_cases():
    # 1. SRT with whitespace-only blank lines, variable arrow spacing, display coordinates, 4-digit fraction
    srt_raw = (
        "\ufeff1\r\n"
        "00:00:01,2500  -->  00:00:03,500 X1:100 X2:500 Y1:50 Y2:100\r\n"
        "Hello coordinates\r\n"
        "   \r\n"
        "00:00:04,000-->00:00:06,9999\r\n"
        "Missing index & tight arrow\r\n"
    )
    srt_doc = SRTParser().parse_text(srt_raw)
    assert len(srt_doc.events) == 2
    assert srt_doc.events[0].start_time == "00:00:01,2500"
    assert srt_doc.events[0].end_time == "00:00:03,500"
    assert srt_doc.events[1].end_time == "00:00:06,9999"

    # SRTWriter normalizes .2500 and .9999 -> 00:00:07,000 cleanly
    written_srt = SRTWriter().write_text(srt_doc)
    assert "00:00:01,250 --> 00:00:03,500" in written_srt
    assert "00:00:04,000 --> 00:00:07,000" in written_srt

    # 2. VTT with header metadata, NOTE, STYLE, REGION, and omitted hours MM:SS.mmm
    vtt_raw = (
        "WEBVTT\nKind: captions\nLanguage: en\n\n"
        "STYLE\n::cue { color: yellow; }\n\n"
        "NOTE this is a multi-line comment\nwith extra info\n\n"
        "REGION\nid:top width:50%\n\n"
        "01:23.450 --> 01:25.670 align:start line:90%\n"
        "<v Alice>WebVTT cue <01:24.000>text\n"
    )
    vtt_doc = VTTParser().parse_text(vtt_raw)
    assert len(vtt_doc.events) == 1
    assert vtt_doc.events[0].start_time == "01:23.450"
    assert vtt_doc.events[0].end_time == "01:25.670"
    assert vtt_doc.events[0].text == "WebVTT cue text"

    written_vtt = VTTWriter().write_text(vtt_doc)
    assert "00:01:23.450 --> 00:01:25.670" in written_vtt

    # 3. ASSWriter safely converts SRT comma timestamps and multiline text
    cross_doc = SubtitleDocument(format=SubtitleFormat.SRT)
    cross_doc.events.append(
        SubtitleEvent(
            id=1,
            start_time="00:01:23,450",
            end_time="00:01:25,999",
            original_text="Line A\nLine B",
            translated_text="سطر 1\nسطر 2",
        )
    )
    written_ass = ASSWriter().write_text(cross_doc)
    assert "Dialogue: 0,0:01:23.45,0:01:26.00," in written_ass
    assert "سطر 1\\Nسطر 2" in written_ass
    reparsed_ass = ASSParser().parse_text(written_ass)
    assert len(reparsed_ass.events) == 1
    assert reparsed_ass.events[0].start_time == "0:01:23.45"


def test_video_extractor_handles_container_offset_and_negative_timestamps():
    ffmpeg = VideoSubtitleExtractor.get_ffmpeg_bin()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        ass_src = tmp / "source.ass"
        mkv_vid_delayed = tmp / "vid_delayed.mkv"
        mkv_normal_delay_cue = tmp / "normal.mkv"

        ass_src.write_text(
            "[Script Info]\n"
            "Title: Offset Test\n"
            "ScriptType: v4.00+\n\n"
            "[V4+ Styles]\n"
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
            "Style: Default,Arial,48,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,2,0,2,10,10,10,1\n\n"
            "[Events]\n"
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
            "Dialogue: 0,0:00:00.20,0:00:00.80,Default,,0,0,0,,Pre-zero line\n"
            "Dialogue: 0,0:00:01.00,0:00:03.00,Default,,0,0,0,,Crossing zero line\n",
            encoding="utf-8",
        )

        # Shift video stream +2.0s relative to subtitle => format.start_time=2.0, ffmpeg emits negative ASS times
        res = subprocess.run(
            [
                ffmpeg, "-y",
                "-itsoffset", "2.0", "-f", "lavfi", "-t", "3", "-i", "color=c=black:s=160x120",
                "-i", str(ass_src),
                "-c:v", "libx264", "-c:s", "copy",
                str(mkv_vid_delayed),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if res.returncode != 0:
            pytest.skip("ffmpeg video muxing unavailable")

        from app.ui.bus import EventBus
        emitted_delayed_logs = []
        EventBus.instance().log_message.connect(emitted_delayed_logs.append)
        try:
            out_ass = tmp / "extracted_fixed.ass"
            ok, path, err = VideoSubtitleExtractor.extract_subtitle(str(mkv_vid_delayed), stream_index=0, output_path=str(out_ass))
            assert ok is True
            doc = parse_subtitle(path)
            # Pre-zero line (-1.80..-1.20) must be dropped; crossing-zero (-1.00..1.00) must be clamped to 0:00:00.00..0:00:01.00
            assert len(doc.events) == 1
            assert doc.events[0].start_time == "0:00:00.00"
            assert doc.events[0].end_time == "0:00:01.00"
            assert "Crossing zero line" in doc.events[0].text
            assert any("إزاحة" in m for m in emitted_delayed_logs)
        finally:
            try:
                EventBus.instance().log_message.disconnect(emitted_delayed_logs.append)
            except Exception:
                pass

        # Normal file where first cue speaks at 0.85s must extract 0.85s untouched and not emit false sync warning
        ass_norm = tmp / "normal.ass"
        ass_norm.write_text(
            "[Script Info]\nScriptType: v4.00+\n\n[V4+ Styles]\n"
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
            "Style: Default,Arial,48,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,2,0,2,10,10,10,1\n\n"
            "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
            "Dialogue: 0,0:00:00.85,0:00:02.50,Default,,0,0,0,,Normal first line\n",
            encoding="utf-8",
        )
        res2 = subprocess.run(
            [ffmpeg, "-y", "-f", "lavfi", "-t", "3", "-i", "color=c=black:s=160x120", "-i", str(ass_norm), "-c:v", "libx264", "-c:s", "copy", str(mkv_normal_delay_cue)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        assert res2.returncode == 0
        emitted_logs = []
        EventBus.instance().log_message.connect(emitted_logs.append)
        try:
            out_norm = tmp / "norm_ext.ass"
            ok2, path2, _ = VideoSubtitleExtractor.extract_subtitle(str(mkv_normal_delay_cue), stream_index=0, output_path=str(out_norm))
            assert ok2 is True
            doc2 = parse_subtitle(path2)
            assert doc2.events[0].start_time == "0:00:00.85"
            assert not any("إزاحة" in m for m in emitted_logs)
        finally:
            try:
                EventBus.instance().log_message.disconnect(emitted_logs.append)
            except Exception:
                pass


def test_signed_ffmpeg_negative_timecode_parser():
    parse_neg = VideoSubtitleExtractor._parse_signed_timecode_ms
    assert parse_neg("0:00:-1.-80") == -1800
    assert parse_neg("0:00:0.-25") == -250
    assert parse_neg("0:00:-0.50") == -500
    assert parse_neg("-0:00:01.00") == -1000
    assert parse_neg("0:00:-1") == -1000
    assert parse_neg("0:01:02.50") == 62500

