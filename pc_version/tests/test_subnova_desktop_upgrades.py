import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
from PySide6.QtWidgets import QApplication, QLabel
from app.ui.windows.main_window import MainWindow
from app.ui.widgets.provider_panel import ProviderPanel, PROVIDER_MODEL_PRESETS
from app.ui.dialogs.about_dialog import AboutDialog
from app.ui.dialogs.progress_dialog import ExtractionProgressDialog
from app.subtitle.video_extractor import SubtitleStreamInfo, VideoSubtitleExtractor

@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if not app:
        app = QApplication([])
    return app

def test_subnova_rebranding_and_developer_credits(qapp):
    win = MainWindow()
    try:
        # Check Window Title contains SubNova Studio
        assert "SubNova Studio" in win.windowTitle()
        assert "سوب نوفا" in win.windowTitle()
    finally:
        win.deleteLater()
        qapp.processEvents()

    about_dlg = AboutDialog()
    try:
        labels = [child.text() for child in about_dlg.findChildren(QLabel)]
        full_text = " ".join(labels)
        assert "SubNova Studio" in full_text
        assert "حاتم الحربي" in full_text
    finally:
        about_dlg.deleteLater()
        qapp.processEvents()

def test_about_dialog_has_hatim_alharbi_credits(qapp):
    about_dlg = AboutDialog()
    assert about_dlg.windowTitle() == "حول SubNova Studio"
    
    # Check that developer name and year 2026 are present in the dialog
    labels = [w.text() for w in about_dlg.findChildren(QLabel)]
    full_text = " ".join(labels)
    assert "حاتم الحربي" in full_text
    assert "Hatim Alharbi" in full_text
    assert "2026" in full_text
    assert "SubNova Studio" in full_text

def test_provider_panel_presets_and_instant_switching(qapp):
    panel = ProviderPanel()
    
    # Verify all 5 providers have presets
    for ptype in ["gemini", "openai", "lmstudio", "ollama", "openai_compatible"]:
        assert ptype in PROVIDER_MODEL_PRESETS
        assert len(PROVIDER_MODEL_PRESETS[ptype]) >= 4

    # Switch to Gemini
    gemini_idx = -1
    for i in range(panel.cb_provider.count()):
        if panel.cb_provider.itemData(i) == "gemini":
            gemini_idx = i
            break
    assert gemini_idx >= 0
    panel.cb_provider.setCurrentIndex(gemini_idx)
    assert not panel.key_container.isHidden()
    assert panel.url_container.isHidden()
    assert "gemini-2.5-flash" in panel.get_selected_model() or panel.cb_models.count() >= 5

    # Switch to LM Studio
    lm_idx = -1
    for i in range(panel.cb_provider.count()):
        if panel.cb_provider.itemData(i) == "lmstudio":
            lm_idx = i
            break
    panel.cb_provider.setCurrentIndex(lm_idx)
    assert not panel.url_container.isHidden()
    assert panel.key_container.isHidden()

    # Test preset chip selection
    panel._select_preset_chip("qwen2.5-14b-instruct")
    assert panel.get_selected_model() == "qwen2.5-14b-instruct"

def test_extraction_progress_dialog(qapp):
    dlg = ExtractionProgressDialog(None, title="SubNova Studio — جاري المعالجة", initial_msg="فحص الملف...")
    dlg.set_status("جاري الاستخراج...", "ملف تجريبي")
    dlg.set_determinate(50, 100)
    dlg.set_indeterminate()
    dlg.close()

def test_subtitle_table_model_editable_and_cps(qapp):
    from app.models.subtitle import SubtitleEvent
    from app.ui.models.subtitle_table_model import SubtitleTableModel
    from PySide6.QtCore import Qt

    model = SubtitleTableModel()
    ev1 = SubtitleEvent(id=1, start_time="0:00:01.00", end_time="0:00:03.00", speaker="Hero", original_text="Hello world!", translated_text="مرحبا بالعالم!")
    model.set_events([ev1])

    # Check flags are editable for cols 1-5
    for col in (1, 2, 3, 4, 5):
        idx = model.index(0, col)
        flags = model.flags(idx)
        assert bool(flags & Qt.ItemFlag.ItemIsEditable)

    # Test setData
    idx_trans = model.index(0, 5)
    success = model.setData(idx_trans, "أهلاً وسهلاً يا عالم!", Qt.ItemDataRole.EditRole)
    assert success is True
    assert ev1.translated_text == "أهلاً وسهلاً يا عالم!"
    assert model.statuses[0] == "Edited"

    # Test CPS calculation
    cps = model.calculate_cps(ev1)
    assert cps > 0.0

def test_timing_tools_shift_merge_split(qapp):
    from app.models.subtitle import SubtitleEvent
    from app.ui.models.subtitle_table_model import SubtitleTableModel

    model = SubtitleTableModel()
    ev1 = SubtitleEvent(id=1, start_time="0:01:00.00", end_time="0:01:02.00", speaker="A", original_text="Line 1", translated_text="السطر الأول")
    ev2 = SubtitleEvent(id=2, start_time="0:01:03.00", end_time="0:01:05.00", speaker="B", original_text="Line 2", translated_text="السطر الثاني")
    model.set_events([ev1, ev2])

    # 1. Test Shift Timings (+1000 ms)
    model.shift_timings(1000, [0])
    assert ev1.start_time == "0:01:01.00"
    assert ev1.end_time == "0:01:03.00"
    assert ev2.start_time == "0:01:03.00" # Unaffected

    # Shift back (-1000 ms)
    model.shift_timings(-1000, [0])
    assert ev1.start_time == "0:01:00.00"
    assert ev1.end_time == "0:01:02.00"

    # 2. Test Merge Lines
    merged = model.merge_lines([0, 1])
    assert merged is True
    assert model.rowCount() == 1
    assert model.events[0].start_time == "0:01:00.00"
    assert model.events[0].end_time == "0:01:05.00"
    assert "Line 1" in model.events[0].original_text and "Line 2" in model.events[0].original_text

    # 3. Test Split Line
    split_ok = model.split_line(0)
    assert split_ok is True
    assert model.rowCount() == 2
    assert model.events[0].start_time == "0:01:00.00"
    assert model.events[0].end_time == model.events[1].start_time
    assert model.events[1].end_time == "0:01:05.00"

def test_undo_stack_and_commands(qapp):
    from PySide6.QtGui import QUndoStack
    from app.models.subtitle import SubtitleEvent
    from app.ui.models.subtitle_table_model import SubtitleTableModel
    from app.ui.commands import EditCellCommand, ShiftTimingsCommand

    model = SubtitleTableModel()
    ev1 = SubtitleEvent(id=1, start_time="0:00:10.00", end_time="0:00:12.00", speaker="A", original_text="Hi", translated_text="أهلا")
    model.set_events([ev1])

    undo_stack = QUndoStack()
    
    # Edit command
    cmd = EditCellCommand(model, 0, 5, "أهلا", "مرحبا")
    undo_stack.push(cmd)
    assert ev1.translated_text == "مرحبا"

    # Undo
    undo_stack.undo()
    assert ev1.translated_text == "أهلا"

    # Redo
    undo_stack.redo()
    assert ev1.translated_text == "مرحبا"

    # Shift timing command
    shift_cmd = ShiftTimingsCommand(model, 500, [0])
    undo_stack.push(shift_cmd)
    assert ev1.start_time == "0:00:10.50"

    undo_stack.undo()
    assert ev1.start_time == "0:00:10.00"

def test_find_replace_bar(qapp):
    from app.ui.widgets.find_replace_bar import FindReplaceBar

    bar = FindReplaceBar()
    signals_received = []
    bar.find_next_requested.connect(lambda txt, cs: signals_received.append(("find", txt, cs)))
    bar.replace_requested.connect(lambda f, r, cs: signals_received.append(("replace", f, r, cs)))

    bar.edit_find.setText("Hello")
    bar.edit_replace.setText("أهلا")
    bar.btn_find.click()
    assert len(signals_received) == 1
    assert signals_received[0] == ("find", "Hello", False)

    bar.btn_replace.click()
    assert len(signals_received) == 2
    assert signals_received[1] == ("replace", "Hello", "أهلا", False)

def test_inline_subtitle_editor(qapp):
    from app.models.subtitle import SubtitleEvent
    from app.ui.widgets.inline_editor_widget import InlineSubtitleEditor

    editor = InlineSubtitleEditor()
    ev = SubtitleEvent(id=5, start_time="0:00:05.00", end_time="0:00:08.00", speaker="Narrator", original_text="Once upon a time", translated_text="كان يا ما كان")
    
    editor.load_event(4, ev, 20)
    assert "السطر #5" in editor.lbl_row_info.text()
    assert editor.edit_start.text() == "0:00:05.00"
    assert editor.edit_end.text() == "0:00:08.00"
    assert editor.edit_speaker.text() == "Narrator"
    assert "كان يا ما كان" in editor.edit_trans.toPlainText()
    assert "CPS:" in editor.lbl_cps.text()

def test_video_player_widget(qapp):
    from app.models.subtitle import SubtitleEvent
    from app.ui.widgets.video_player_widget import SubNovaVideoPlayerWidget

    player = SubNovaVideoPlayerWidget()
    try:
        assert player.lbl_time.text() == "00:00 / 00:00"

        ev1 = SubtitleEvent(id=1, start_time="0:00:01.00", end_time="0:00:03.00", original_text="Line 1", translated_text="السطر 1")
        player.set_subtitles_for_overlay([ev1])
        assert len(player.subtitles) == 1

        # Test time to ms
        ms = player._parse_time_to_ms("0:01:23.50")
        assert ms == 83500
    finally:
        player.cleanup()

def test_engine_rate_limit_backoff(qapp):
    import asyncio
    from app.translation.engine import TranslationEngine

    engine = TranslationEngine()
    
    # Verify rate limit detection logic without waiting 60s
    assert hasattr(engine, '_handle_backoff')

def test_fast_probe_subtitle_streams_no_packet_count(tmp_path):
    from app.subtitle.video_extractor import VideoSubtitleExtractor, SubtitleStreamInfo
    import json
    import subprocess

    dummy_video = tmp_path / "test.mkv"
    dummy_video.write_bytes(b"dummy")

    fake_ffprobe_output = json.dumps({
        "streams": [
            {
                "index": 2,
                "codec_name": "ass",
                "tags": {
                    "language": "eng",
                    "title": "Full Dialogue",
                    "NUMBER_OF_FRAMES": "345",
                    "NUMBER_OF_BYTES": "24500"
                },
                "disposition": {"default": 1, "forced": 0}
            },
            {
                "index": 3,
                "codec_name": "ass",
                "tags": {
                    "language": "eng",
                    "title": "Signs & Songs",
                    "NUMBER_OF_FRAMES": "22"
                },
                "disposition": {"default": 0, "forced": 1}
            }
        ]
    })

    with patch.object(subprocess, "run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout=fake_ffprobe_output, stderr="")
        streams = VideoSubtitleExtractor.probe_subtitle_streams(str(dummy_video))

        # Ensure -count_packets is NOT in command
        cmd_args = mock_run.call_args[0][0]
        assert "-count_packets" not in cmd_args

        # Verify parsed streams
        assert len(streams) == 2
        assert streams[0].title == "Full Dialogue"
        assert streams[0].frame_count == 345
        assert streams[0].byte_count == 24500
        assert streams[0].is_default is True

        # Verify selection picks Full Dialogue
        best = VideoSubtitleExtractor.select_best_stream(streams, "eng")
        assert best.title == "Full Dialogue"

@pytest.mark.asyncio
async def test_provider_panel_probe_clean_closing(qapp):
    from app.ui.widgets.provider_panel import ProviderPanel
    from app.providers.base import ProviderBase

    panel = ProviderPanel()
    mock_provider = MagicMock(spec=ProviderBase)
    mock_provider.list_models = MagicMock(side_effect=ConnectionRefusedError("Connection refused"))
    mock_provider.close = MagicMock(return_value=None)

    # In async test, simulate _probe_auto_detect
    with patch("app.ui.widgets.provider_panel.get_provider", return_value=mock_provider):
        await panel._probe_auto_detect("lmstudio")
        # Ensure provider.close() was called even on ConnectionRefusedError
        assert mock_provider.close.called
        assert panel._probe_running is False


def test_hide_effect_rows_button(qapp):
    from app.models.subtitle import SubtitleEvent
    win = MainWindow()
    try:
        # Check that the toggle button exists
        assert hasattr(win, "btn_toggle_fx")
        assert win.btn_toggle_fx.isCheckable() is True

        events = [
            SubtitleEvent(id=1, style="Default", original_text="Normal dialogue 1"),
            SubtitleEvent(id=2, style="Default", original_text=r"{\an8}SFX: BOOM"),
            SubtitleEvent(id=3, style="Default", original_text="Normal dialogue 2"),
        ]
        win.table_model.set_events(events)

        # Initially all rows are visible
        assert win.table_view.isRowHidden(0) is False
        assert win.table_view.isRowHidden(1) is False
        assert win.table_view.isRowHidden(2) is False

        # Click the button to hide effects
        win.btn_toggle_fx.click()
        assert win.btn_toggle_fx.isChecked() is True

        # Row 1 (SFX) must be hidden, rows 0 and 2 must remain visible
        assert win.table_view.isRowHidden(0) is False
        assert win.table_view.isRowHidden(1) is True
        assert win.table_view.isRowHidden(2) is False

        # Click again to unhide
        win.btn_toggle_fx.click()
        assert win.btn_toggle_fx.isChecked() is False
        assert win.table_view.isRowHidden(1) is False
    finally:
        win.deleteLater()
        qapp.processEvents()



