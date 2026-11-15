import asyncio
import sqlite3
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtWidgets import QApplication

from app.core.database import DatabaseManager
from app.models.provider import ChatResponse, ProviderConfig, ProviderType
from app.models.subtitle import SubtitleDocument, SubtitleEvent, SubtitleFormat
from app.providers.base import ProviderBase
from app.quality.healer import SubtitleHealer
from app.subtitle import parse_subtitle, write_subtitle
from app.subtitle.timecode import detect_timecode_style, normalize_timecode
from app.subtitle.timing_sync import SubtitleTimingOptimizer
from app.subtitle.video_extractor import SubtitleStreamInfo, VideoSubtitleExtractor
from app.subtitle.writers.srt import SRTWriter
from app.subtitle.writers.vtt import VTTWriter
from app.translation.batcher import TokenBatcher
from app.translation.engine import TranslationEngine
from app.translation.response_parser import ResponseParser
from app.ui.widgets.provider_panel import ProviderPanel
from app.ui.windows.main_window import MainWindow


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if not app:
        app = QApplication([])
    return app


def test_response_parser_slippage_and_missing_first_id_guard():
    parser = ResponseParser()

    # Case A: Gapped expected IDs [10, 12, 14, 18] renumbered sequentially by LLM as [10, 11, 12, 13]
    expected_gapped = [10, 12, 14, 18]
    raw_renumbered = "[10] سطر أول\n[11] سطر ثان\n[12] سطر ثالث\n[13] سطر رابع"
    parsed_a = parser.parse_response(raw_renumbered, expected_gapped)
    assert parsed_a == {
        10: "سطر أول",
        12: "سطر ثان",
        14: "سطر ثالث",
        18: "سطر رابع",
    }

    # Case B: LLM genuinely skipped ID 10 out of [10, 11, 12, 13] and returned [11, 12, 13]
    # Must NOT shift [11, 12, 13] onto [10, 11, 12]! ID 10 must remain missing for recovery.
    expected_seq = [10, 11, 12, 13]
    raw_missing_first = "[11] جملة حادية عشرة\n[12] جملة ثانية عشرة\n[13] جملة ثالثة عشرة"
    parsed_b = parser.parse_response(raw_missing_first, expected_seq)
    assert 10 not in parsed_b
    assert parsed_b == {
        11: "جملة حادية عشرة",
        12: "جملة ثانية عشرة",
        13: "جملة ثالثة عشرة",
    }

    # Case C: Leading timestamp line before pat_dot matching
    raw_with_timestamp = "12:05:00 Intro Scene\n[1] أهلاً بكم\n[2] لننطلق"
    parsed_c = parser.parse_response(raw_with_timestamp, [1, 2])
    assert parsed_c == {1: "أهلاً بكم", 2: "لننطلق"}


class _RecordingLocalMockProvider(ProviderBase):
    """Simulates a local LLM returning sequential 1..N IDs and records prompts/kwargs."""

    def __init__(self):
        super().__init__(ProviderConfig(provider_type=ProviderType.LM_STUDIO, base_url="http://localhost:1234/v1"))
        self.calls = []

    async def list_models(self):
        return []

    async def chat_completion(self, messages, model, temperature=0.1, max_tokens=None, **kwargs):
        user_msg = messages[-1].content
        self.calls.append({"user": user_msg, "max_tokens": max_tokens, "messages": messages})
        if "Translate this line:" in user_msg:
            return ChatResponse(content="سطر منفرد مترجم", model=model, input_tokens=20, output_tokens=10)
        if "Refined Arabic subtitle:" in user_msg:
            return ChatResponse(content="سطر محسن منفرد", model=model, input_tokens=20, output_tokens=10)

        word_map = {"Line Alpha": "ترجمة ألفا", "Line Beta": "ترجمة بيتا", "Line Gamma": "ترجمة جاما"}
        out_lines = []
        import re
        for m in re.finditer(r"\[(\d+)\]\s*(.+)", user_msg):
            idx = int(m.group(1))
            body = m.group(2).strip()
            if "SUBTITLES TO REFINE" in user_msg or "Draft" in user_msg:
                out_lines.append(f"[{idx}] محسن رقم {idx}")
            else:
                ar_body = word_map.get(body, f"ترجمة {idx}")
                out_lines.append(f"[{idx:03d}] {ar_body}")
        return ChatResponse(content="\n".join(out_lines), model=model, input_tokens=50, output_tokens=40)

    async def is_available(self):
        return True

    async def test_connection(self):
        return True


@pytest.mark.asyncio
async def test_engine_gapped_batch_ids_zero_slippage_and_single_line_budget():
    doc = SubtitleDocument(
        format=SubtitleFormat.ASS,
        events=[
            SubtitleEvent(id=1, start_time="0:00:01.00", end_time="0:00:03.00", speaker="Narrator", original_text="Line Alpha", text="Line Alpha"),
            SubtitleEvent(id=2, start_time="0:00:03.20", end_time="0:00:04.00", style="Signs", original_text=r"{\pos(100,100)\fad(100,100)}", text=""),
            SubtitleEvent(id=3, start_time="0:00:04.20", end_time="0:00:06.00", speaker="Narrator", original_text="Line Alpha", text="Line Alpha"),
            SubtitleEvent(id=4, start_time="0:00:06.20", end_time="0:00:08.50", original_text="Line Beta", text="Line Beta"),
            SubtitleEvent(id=5, start_time="0:00:08.60", end_time="0:00:09.00", original_text=r"{\p1}m 0 0 l 10 10{\p0}", text=""),
            SubtitleEvent(id=6, start_time="0:00:09.20", end_time="0:00:12.00", original_text="Line Gamma", text="Line Gamma"),
        ],
    )

    provider = _RecordingLocalMockProvider()
    engine = TranslationEngine(batcher=TokenBatcher(max_tokens=4000, max_events=20))

    await engine.translate_document(
        doc, provider, model="allam-7b-arabic-sft",
        source_lang="English", target_lang="Arabic",
        max_context=4096, auto_heal=False, auto_improve=False
    )

    # First batch call had primary_events [1, 4, 6] renumbered cleanly as [001], [002], [003]
    batch_prompt = provider.calls[0]["user"]
    assert "[001]" in batch_prompt
    assert "[002]" in batch_prompt
    assert "[003]" in batch_prompt
    assert "[004]" not in batch_prompt
    assert "[006]" not in batch_prompt

    # Exact alignment check (no slippage across gapped events)
    assert "ألفا" in doc.events[0].translated_text
    assert doc.events[1].translated_text is None  # visual effect untouched
    assert "ألفا" in doc.events[2].translated_text  # deduplicated duplicate
    assert "بيتا" in doc.events[3].translated_text
    assert doc.events[4].translated_text is None  # drawing untouched
    assert "جاما" in doc.events[5].translated_text

    # Improvement pass on same gapped doc also renumbers cleanly
    provider.calls.clear()
    await engine.improve_document(
        doc, provider, model="allam-7b-arabic-sft",
        source_lang="English", target_lang="Arabic",
        max_context=4096, auto_heal=False
    )
    imp_prompt = provider.calls[0]["user"]
    assert "[1]" in imp_prompt and "[2]" in imp_prompt and "[3]" in imp_prompt
    assert "[4]" not in imp_prompt and "[6]" not in imp_prompt
    assert "محسن رقم 1" in doc.events[0].translated_text
    assert "محسن رقم 1" in doc.events[2].translated_text  # deduplicated duplicate
    assert "محسن رقم 2" in doc.events[3].translated_text
    assert "محسن رقم 3" in doc.events[5].translated_text

    # Single-line max_tokens budget honors max_context
    provider.calls.clear()
    txt, _ = await engine._translate_single_line(
        doc.events[0], provider, "allam-7b-arabic-sft",
        "English", "Arabic", "", "", 0.1, max_context=1024
    )
    assert txt == "سطر منفرد مترجم"
    assert 64 <= provider.calls[0]["max_tokens"] <= 512

    provider.calls.clear()
    imp_txt, _ = await engine._improve_single_line(
        doc.events[0], provider, "allam-7b-arabic-sft",
        "English", "Arabic", "", "", "", 0.1, max_context=1024
    )
    assert imp_txt == "سطر محسن منفرد"
    assert 64 <= provider.calls[0]["max_tokens"] <= 512


def test_timecode_style_fallback_from_explicit_format():
    assert detect_timecode_style("00:00:00.00", "srt") == "srt"
    assert detect_timecode_style("00:00:00.00", "vtt") == "vtt"
    assert detect_timecode_style("00:00:00.00", "ass") == "ass"
    assert normalize_timecode("0:00:05.50", "00:00:00.00", fmt="srt") == "00:00:05,500"
    assert normalize_timecode("0:00:05.50", "00:00:00.00", fmt="vtt") == "00:00:05.500"
    assert normalize_timecode("00:00:05,500", "00:00:00.00", fmt="ass") == "0:00:05.50"


def test_timing_optimizer_cps_and_audio_offset():
    doc = SubtitleDocument(
        format=SubtitleFormat.ASS,
        events=[
            # Too short (1000ms) for 48 Arabic chars -> needs ~2700ms; capped safely by gap + max_extend
            SubtitleEvent(
                id=1, start_time="0:00:01.00", end_time="0:00:02.00",
                original_text="Long sentence here.",
                translated_text="هذه جملة عربية طويلة نسبياً تحتاج إلى وقت قراءة أطول.",
            ),
            # Followed closely (gap 150ms) by event 2 -> can only extend up to 3.40 - 0.08 = 3.32
            SubtitleEvent(
                id=2, start_time="0:00:03.40", end_time="0:00:04.20",
                original_text="Very quick line that needs more reading room too.",
                translated_text="سطر سريع جداً ويحتاج إلى تمديد طفيف جداً ضمن الفجوة.",
            ),
            SubtitleEvent(
                id=3, start_time="0:00:04.35", end_time="0:00:05.50",
                original_text="Third line.",
                translated_text="السطر الثالث.",
            ),
            # Visual effect should not be touched even if duration is short
            SubtitleEvent(
                id=4, start_time="0:00:06.00", end_time="0:00:06.20",
                original_text=r"{\pos(200,300)}", text="",
            ),
        ],
    )

    extended = SubtitleTimingOptimizer.optimize_arabic_cps(doc, max_cps=18.0, min_gap_ms=80, max_extend_ms=1200)
    assert extended == 2
    assert doc.events[0].start_time == "0:00:01.00"  # start never shifted
    assert doc.events[0].end_time == "0:00:03.20"    # extended +1200ms within 1400ms gap
    assert doc.events[1].end_time == "0:00:04.27"    # clamped to 4.35 - 0.08 = 4.27 (80ms safe gap)
    assert doc.events[3].end_time == "0:00:06.20"    # FX event skipped

    # Audio speech onset detection via mocked ffmpeg silencedetect stderr
    fake_proc = MagicMock(
        returncode=0,
        stderr="[silencedetect @ 0x1] silence_start: 0.000\n[silencedetect @ 0x1] silence_end: 2.350 | silence_duration: 2.350\n",
    )
    with patch("subprocess.run", return_value=fake_proc):
        offset_ms = SubtitleTimingOptimizer.detect_audio_speech_offset_ms("dummy.mkv", doc.events)
    assert offset_ms == 1350  # 2350ms audio onset - 1000ms first subtitle cue


def test_video_extractor_preserves_native_resolution(tmp_path):
    dummy_video = tmp_path / "hd720.mkv"
    dummy_video.write_bytes(b"video")

    # 1. Converted text subtitle (subrip -> ASS) MUST adopt the video resolution (1280x720)
    out_conv = tmp_path / "extracted_converted.ass"
    converted_ass_payload = (
        "[Script Info]\nScriptType: v4.00+\nPlayResX: 384\nPlayResY: 288\n\n"
        "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
        "Dialogue: 0,0:00:01.00,0:00:03.00,Default,,0,0,0,,Hello\n"
    )

    def _mock_conv_subproc(cmd, *args, **kwargs):
        cmd_joined = " ".join(str(x) for x in cmd)
        if "ffprobe" in str(cmd[0]).lower() and "width,height" in cmd_joined:
            return MagicMock(returncode=0, stdout='{"streams": [{"width": 1280, "height": 720}]}', stderr="")
        if "ffprobe" in str(cmd[0]).lower():
            return MagicMock(returncode=0, stdout='{"format": {"start_time": "0.000000"}, "streams": []}', stderr="")
        if "ffmpeg" in str(cmd[0]).lower():
            out_conv.write_text(converted_ass_payload, encoding="utf-8")
            return MagicMock(returncode=0, stdout="", stderr="")
        return MagicMock(returncode=0, stdout="", stderr="")

    srt_streams = [
        SubtitleStreamInfo(index=0, global_index=1, codec_name="subrip", extension=".srt", language="eng")
    ]
    with patch.object(VideoSubtitleExtractor, "probe_subtitle_streams", return_value=srt_streams), \
         patch.object(VideoSubtitleExtractor, "get_ffmpeg_bin", return_value="ffmpeg"), \
         patch.object(VideoSubtitleExtractor, "get_ffprobe_bin", return_value="ffprobe"), \
         patch.object(subprocess, "run", side_effect=_mock_conv_subproc):
        ok, res_path, err = VideoSubtitleExtractor.extract_subtitle(str(dummy_video), 0, str(out_conv), prefer_ass=True)

    assert ok is True, err
    conv_content = Path(res_path).read_text(encoding="utf-8-sig")
    assert "PlayResX: 1280" in conv_content
    assert "PlayResY: 720" in conv_content

    # 2. Lossless native ASS/SSA stream MUST preserve original PlayResX/Y and Style: Default untouched
    out_native = tmp_path / "extracted_native.ass"
    native_ass_payload = (
        "[Script Info]\nScriptType: v4.00+\nPlayResX: 1920\nPlayResY: 1080\nWrapStyle: 2\n\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
        "Style: Default,Noto Sans,64,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,2,0,2,10,10,10,1\n\n"
        "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
        "Dialogue: 0,0:00:01.00,0:00:03.00,Default,,0,0,0,,Hello\n"
    )

    def _mock_native_subproc(cmd, *args, **kwargs):
        cmd_joined = " ".join(str(x) for x in cmd)
        if "ffprobe" in str(cmd[0]).lower() and "width,height" in cmd_joined:
            return MagicMock(returncode=0, stdout='{"streams": [{"width": 1280, "height": 720}]}', stderr="")
        if "ffprobe" in str(cmd[0]).lower():
            return MagicMock(returncode=0, stdout='{"format": {"start_time": "0.000000"}, "streams": []}', stderr="")
        if "ffmpeg" in str(cmd[0]).lower():
            out_native.write_text(native_ass_payload, encoding="utf-8")
            return MagicMock(returncode=0, stdout="", stderr="")
        return MagicMock(returncode=0, stdout="", stderr="")

    ass_streams = [
        SubtitleStreamInfo(index=0, global_index=1, codec_name="ass", extension=".ass", language="eng")
    ]
    with patch.object(VideoSubtitleExtractor, "probe_subtitle_streams", return_value=ass_streams), \
         patch.object(VideoSubtitleExtractor, "get_ffmpeg_bin", return_value="ffmpeg"), \
         patch.object(VideoSubtitleExtractor, "get_ffprobe_bin", return_value="ffprobe"), \
         patch.object(subprocess, "run", side_effect=_mock_native_subproc):
        ok2, res_path2, err2 = VideoSubtitleExtractor.extract_subtitle(str(dummy_video), 0, str(out_native), prefer_ass=True)

    assert ok2 is True, err2
    native_content = Path(res_path2).read_text(encoding="utf-8-sig")
    assert "PlayResX: 1920" in native_content
    assert "PlayResY: 1080" in native_content
    assert "WrapStyle: 2" in native_content
    assert "Style: Default,Noto Sans,64," in native_content


def test_database_manager_recovers_corrupt_sqlite_file(tmp_path):
    db_file = tmp_path / "corrupt_test.db"

    # Populate a valid DB first, then corrupt it on disk
    db = DatabaseManager(str(db_file))
    db.execute(
        "INSERT INTO settings (key, value) VALUES (?, ?)",
        ("theme", "dark"),
    )
    db.close()

    # Overwrite header bytes with garbage so SQLite rejects it as malformed/not a database
    raw = bytearray(db_file.read_bytes())
    raw[:64] = b"\x00CORRUPTED_BTREE_HEADER_DATA_" + b"\xff" * (64 - 29)
    db_file.write_bytes(bytes(raw))

    # Re-opening DatabaseManager must automatically quarantine corrupt file and initialize clean DB
    recovered_db = DatabaseManager(str(db_file))
    try:
        rows = recovered_db.fetch_all("PRAGMA integrity_check")
        assert [r[0] for r in rows] == ["ok"]
        recovered_db.execute("INSERT INTO settings (key, value) VALUES (?, ?)", ("healthy", "yes"))
        row = recovered_db.fetch_one("SELECT value FROM settings WHERE key = ?", ("healthy",))
        assert row["value"] == "yes"
        backups = list(tmp_path.glob("corrupt_test.db.corrupt.*.bak"))
        assert len(backups) >= 1
    finally:
        recovered_db.close()


@pytest.mark.asyncio
async def test_provider_panel_pause_and_modal_guards(qapp):
    panel = ProviderPanel()
    panel.auto_detect_timer.stop()

    spawned = []

    async def fake_probe(ptype):
        spawned.append(ptype)

    panel._probe_auto_detect = fake_probe

    # Blocked while paused
    panel.pause_auto_detect()
    panel._auto_detect_tick()
    await asyncio.sleep(0.02)
    assert spawned == []

    # Blocked while modal dialog is active even when unpaused
    panel.resume_auto_detect()
    with patch("app.ui.widgets.provider_panel.QApplication.activeModalWidget", return_value=object()):
        panel._auto_detect_tick()
        await asyncio.sleep(0.02)
    assert spawned == []

    # Allowed when unpaused and no modal active
    with patch("app.ui.widgets.provider_panel.QApplication.activeModalWidget", return_value=None):
        panel._auto_detect_tick()
        await asyncio.sleep(0.02)
    assert spawned == ["lmstudio"]

    panel.stop_background_tasks()
    assert panel.auto_detect_timer.isActive() is False
    assert panel._stopped is True


def test_mainwindow_close_stops_background_tasks(qapp):
    win = MainWindow()
    with patch.object(win.provider_panel, "stop_background_tasks", wraps=win.provider_panel.stop_background_tasks) as spy_stop:
        win.close()
        assert spy_stop.called
    win.deleteLater()
    qapp.processEvents()


def test_healer_sdh_parentheticals_acronyms_and_phonetic_prefix():
    # Legitimate Arabic parentheticals must survive while SDH audio cues are removed
    assert SubtitleHealer.clean_sdh_and_sound_effects("سآتي لاحقاً (إن سمح الوقت) بالتأكيد.") == "سآتي لاحقاً (إن سمح الوقت) بالتأكيد."
    cleaned_sdh = SubtitleHealer.clean_sdh_and_sound_effects("[music] أهلاً بك (sighs) صديقي (موسيقى هادئة)!")
    assert "[music]" not in cleaned_sdh
    assert "(sighs)" not in cleaned_sdh
    assert "(موسيقى هادئة)" not in cleaned_sdh
    assert "أهلاً بك" in cleaned_sdh and "صديقي" in cleaned_sdh

    # Uppercase acronyms must survive in Arabic sentences while names transliterate
    acronyms_line = SubtitleHealer.clean_stray_latin_and_fillers("عضوية VIP مع فحص DNA وعميل FBI")
    assert "VIP" in acronyms_line
    assert "DNA" in acronyms_line
    assert "FBI" in acronyms_line

    # Phonetic fused prefix with mid_word=True (vs standalone initial vowel glottal stop)
    assert SubtitleHealer.transliterate_name_to_arabic("Adam") == "أدام"
    assert SubtitleHealer.transliterate_name_to_arabic("Adam", mid_word=True) == "ادام"
    assert "لتاكيرو" in SubtitleHealer.clean_stray_latin_and_fillers("هذا القميص لتakeru فقط")
    assert "بادام" in SubtitleHealer.clean_stray_latin_and_fillers("التقيت بAdam هناك")


def test_srt_vtt_style_conversion_and_ass_comment_roundtrip(tmp_path):
    doc = SubtitleDocument(
        format=SubtitleFormat.ASS,
        events=[
            SubtitleEvent(
                id=1, start_time="0:00:01.00", end_time="0:00:04.00",
                original_text=r"{\i1}مرحباً بكم\N{\b1}عنوان عريض{\b0}{\i0}",
                translated_text=r"{\i1}مرحباً بكم\N{\b1}عنوان عريض{\b0}{\i0}",
            ),
            SubtitleEvent(
                id=2, start_time="0:00:05.00", end_time="0:00:07.00",
                original_text=r"{\blur3}مؤثر ناعم",
                translated_text=r"{\blur3}مؤثر ناعم",
            ),
        ],
    )

    srt_out = SRTWriter().write_text(doc)
    vtt_out = VTTWriter().write_text(doc)
    for out in (srt_out, vtt_out):
        assert "<i>مرحباً بكم\n<b>عنوان عريض</b></i>" in out
        assert "مؤثر ناعم" in out
        assert "<b>مؤثر" not in out

    # ASS inline {comment} preserved in original_text & roundtrip, hidden in get_clean_text()
    ass_path = tmp_path / "comment_roundtrip.ass"
    ass_path.write_text(
        "[Script Info]\nScriptType: v4.00+\n\n"
        "[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
        "Style: Default,Arial,20,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,2,0,2,10,10,10,1\n\n"
        "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
        "Dialogue: 0,0:00:01.00,0:00:03.00,Default,,0,0,0,,{TS note}Hello {inline note}World\n",
        encoding="utf-8",
    )
    parsed = parse_subtitle(str(ass_path))
    assert "{TS note}" in parsed.events[0].original_text
    assert "{inline note}" in parsed.events[0].original_text
    assert parsed.events[0].get_clean_text() == "Hello World"

    out_ass = tmp_path / "comment_roundtrip_out.ass"
    write_subtitle(parsed, str(out_ass))
    reparsed = parse_subtitle(str(out_ass))
    assert "{TS note}" in reparsed.events[0].original_text
    assert "{inline note}" in reparsed.events[0].original_text
