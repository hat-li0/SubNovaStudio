import pytest
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch

from app.translation.response_parser import ResponseParser
from app.subtitle.video_extractor import VideoSubtitleExtractor, SubtitleStreamInfo
from app.translation.engine import TranslationEngine
from app.translation.batcher import TokenBatcher
from app.models.subtitle import SubtitleDocument, SubtitleEvent, SubtitleFormat
from app.ui.widgets.settings_panel import IntStepper, DoubleStepper
from app.ui.widgets.log_panel import LogPanel, FullLogDialog
from PySide6.QtWidgets import QApplication

@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if not app:
        app = QApplication([])
    return app

def test_response_parser_prompt_leak_cleanup():
    """Ensure ResponseParser eliminates echoes like Original:... | Current Arabic:... and label prefixes."""
    parser = ResponseParser()

    # 1. Pipe echo with Current Arabic
    raw_1 = "[001] Original: I didn't think you'd come. | Current Arabic: لم أكن أعتقد أنك ستأتي."
    parsed = parser.parse_response(raw_1, [1])
    assert parsed.get(1) == "لم أكن أعتقد أنك ستأتي."

    # 2. Pipe echo with Improved
    raw_2 = "[002] Original: What are you doing? | Improved: ماذا تفعل هنا؟"
    parsed = parser.parse_response(raw_2, [2])
    assert parsed.get(2) == "ماذا تفعل هنا؟"

    # 3. Direct label prefix (Improved: / الترجمة المحسنة:)
    raw_3 = """
    [003] Improved: أهلاً وسهلاً بك في المدينة.
    [004] الترجمة المحسنة: لا تقلق بشأن ذلك أبداً.
    [005] الصياغة الجديدة: نحن هنا لمساعدتك.
    [006] "لقد حان وقت المغادرة."
    [007] `سأفعل ما بوسعي.`
    """
    parsed = parser.parse_response(raw_3, [3, 4, 5, 6, 7])
    assert parsed.get(3) == "أهلاً وسهلاً بك في المدينة."
    assert parsed.get(4) == "لا تقلق بشأن ذلك أبداً."
    assert parsed.get(5) == "نحن هنا لمساعدتك."
    assert parsed.get(6) == "لقد حان وقت المغادرة."
    assert parsed.get(7) == "سأفعل ما بوسعي."

def test_video_extractor_prefer_ass(tmp_path):
    """Verify that extract_subtitle respects prefer_ass and generates .ass target path."""
    dummy_video = tmp_path / "sample_video.mkv"
    dummy_video.write_bytes(b"dummy video content")

    fake_stream = SubtitleStreamInfo(
        index=0,
        global_index=2,
        codec_name="subrip",
        extension=".srt",
        language="eng",
        title="English Dialogues"
    )

    with patch.object(VideoSubtitleExtractor, "probe_subtitle_streams", return_value=[fake_stream]):
        with patch("subprocess.run") as mock_run:
            def fake_run(cmd, *args, **kwargs):
                if "-c:s" in cmd and "copy" in cmd:
                    return MagicMock(returncode=1, stderr="ass muxer supports only codec ass")
                elif "-c:s" in cmd and "ass" in cmd:
                    out_p = cmd[-1]
                    Path(out_p).write_text("[Script Info]\nTitle: Converted ASS\n", encoding="utf-8")
                    return MagicMock(returncode=0, stderr="")
                return MagicMock(returncode=0, stderr="")

            mock_run.side_effect = fake_run

            ok, out_path, err = VideoSubtitleExtractor.extract_subtitle(
                str(dummy_video), stream_index=0, prefer_ass=True
            )

            assert ok is True
            assert out_path.endswith(".ass")
            assert mock_run.call_count >= 1
            assert Path(out_path).exists()
            # Verify that for SRT source converting to ASS, it called ffmpeg with -c:s ass
            args = mock_run.call_args[0][0]
            assert "-c:s" in args
            assert "ass" in args

def test_single_file_saving_in_main_window(qapp, tmp_path):
    """Verify that _save_file_auto saves only ONE file (.ara.ass) and never duplicates as _improved."""
    from app.ui.windows.main_window import MainWindow
    
    win = MainWindow()
    test_sub = tmp_path / "episode_01.ass"
    test_sub.write_text("[Script Info]\nTitle: Test\n[Events]\nDialogue: 0,0:00:01.00,0:00:02.00,Default,,0,0,0,,Hello", encoding="utf-8")
    
    # Load document
    win.current_file_path = str(test_sub)
    win.document = SubtitleDocument(
        format=SubtitleFormat.ASS,
        events=[
            SubtitleEvent(id="1", start_ms=1000, end_ms=2000, text="Hello", translated_text="مرحباً")
        ]
    )

    # Trigger auto-save
    win._save_file_auto()
    
    expected_ara = tmp_path / "episode_01.ara.ass"
    unwanted_improved = tmp_path / "episode_01_improved.ass"
    
    assert expected_ara.exists(), "The primary .ara.ass file must exist!"
    assert not unwanted_improved.exists(), "There must NOT be a separate _improved file!"

    # Now simulate calling _save_file_improved (which was redirected to single file save)
    win.document.events[0].translated_text = "أهلاً بك"
    win._save_file_improved(str(test_sub))

    assert expected_ara.exists()
    assert not unwanted_improved.exists(), "_save_file_improved should NOT create a separate _improved.ass!"
    
    # Content check
    saved_content = expected_ara.read_text(encoding="utf-8")
    assert "أهلاً بك" in saved_content
    
    win.close()
    win.deleteLater()
    qapp.processEvents()

def test_stepper_widgets(qapp):
    """Verify that IntStepper and DoubleStepper increment and decrement properly."""
    stepper = IntStepper(min_val=1, max_val=100, val=15)
    assert stepper.value() == 15
    
    stepper.btn_plus.click()
    assert stepper.value() == 16
    
    stepper.btn_minus.click()
    stepper.btn_minus.click()
    assert stepper.value() == 14

    d_stepper = DoubleStepper(min_val=0.0, max_val=2.0, val=0.3, step=0.05)
    assert abs(d_stepper.value() - 0.3) < 1e-4
    
    d_stepper.btn_plus.click()
    assert abs(d_stepper.value() - 0.35) < 1e-4
    
    d_stepper.btn_minus.click()
    assert abs(d_stepper.value() - 0.30) < 1e-4

def test_log_panel_expansion_and_dialog(qapp):
    """Verify log panel expand toggle and full log dialog functionality."""
    panel = LogPanel()
    
    toggled = []
    panel.expand_toggled.connect(lambda exp: toggled.append(exp))
    
    # Toggle expand
    panel.btn_expand.click()
    assert panel._is_expanded is True
    assert len(toggled) == 1 and toggled[0] is True
    assert "استعادة" in panel.btn_expand.text()
    
    # Toggle back
    panel.btn_expand.click()
    assert panel._is_expanded is False
    assert len(toggled) == 2 and toggled[1] is False
    assert "تكبير" in panel.btn_expand.text()
    
    # Add logs including error
    panel.append_log("INFO: Standard message")
    panel.append_log("🔴 [ERROR] Something went wrong!")
    
    # Open full dialog
    dialog = FullLogDialog(panel, full_text=panel.text_edit.toHtml())
    assert "Something went wrong!" in dialog.text_view.toPlainText()
    dialog.close()
    panel.close()

def test_video_full_automatic_pipeline(qapp, tmp_path):
    """Verify that importing a video automatically probes, extracts, loads, and sets busy state without dialogs."""
    from app.ui.windows.main_window import MainWindow
    from app.ui.bus import EventBus
    
    win = MainWindow()
    fake_video = tmp_path / "anime_ep01.mkv"
    fake_video.write_bytes(b"dummy mkv")

    streams = [
        SubtitleStreamInfo(index=0, global_index=2, codec_name="hdmv_pgs_subtitle", extension=".sup", language="eng", title="PGS Sign"),
        SubtitleStreamInfo(index=1, global_index=3, codec_name="ass", extension=".ass", language="eng", title="English Full Dialogue", is_default=True)
    ]

    out_ass = tmp_path / "anime_ep01.ass"
    out_ass.write_text("[Script Info]\nTitle: Test\n\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\nDialogue: 0,0:00:01.00,0:00:02.00,Default,,0,0,0,,Hello", encoding="utf-8")

    with patch.object(VideoSubtitleExtractor, "probe_subtitle_streams", return_value=streams):
        with patch.object(VideoSubtitleExtractor, "extract_subtitle", return_value=(True, str(out_ass), "")):
            # Call _on_file_selected with video file
            win._on_file_selected([str(fake_video)])

            # Verify that stream 1 (the text ASS dialogue track) was selected over the PGS stream
            assert win.selected_files == [str(out_ass)]
            assert win.document is not None
            assert len(win.document.events) == 1
            # Verify progress panel enters busy state automatically
            assert win.progress_panel.btn_cancel.isEnabled() is True
            assert win.progress_panel.btn_start.isEnabled() is False

    win.close()
    win.deleteLater()
    qapp.processEvents()


def test_language_detector_core():
    """Verify LanguageDetector correctly identifies Japanese, English, French, and handles ASS clean tags."""
    from app.core.language_detector import LanguageDetector
    
    # 1. Japanese text
    ja_text = "{\\an8}こんにちは、世界！\\Nこれはテストです。"
    res_ja = LanguageDetector.detect_from_text(ja_text)
    assert res_ja.code == "ja"
    assert res_ja.name == "Japanese"
    assert res_ja.confidence >= 0.9

    # 2. English text
    en_text = "The quick brown fox jumps over the lazy dog. You are doing great today."
    res_en = LanguageDetector.detect_from_text(en_text)
    assert res_en.code == "en"
    assert res_en.name == "English"

    # 3. French text
    fr_text = "Bonjour tout le monde, comment allez-vous aujourd'hui avec ce projet ?"
    res_fr = LanguageDetector.detect_from_text(fr_text)
    assert res_fr.code == "fr"
    assert res_fr.name == "French"

    # 4. Resolve source language: Auto Detect vs Manual Override
    res_auto = LanguageDetector.resolve_source_language("✨ كشف تلقائي للغة (Auto Detect)", events=[
        SubtitleEvent(id="1", start_ms=0, end_ms=1000, text="私たちがやらなければならない。")
    ])
    assert res_auto.code == "ja"

    res_manual = LanguageDetector.resolve_source_language("Spanish (الإسبانية)")
    assert res_manual.code == "es"


def test_video_subtitle_extraction_leaves_no_raw_file(qapp, tmp_path):
    """
    Verify that when extracting subtitles from a video:
    1. The raw subtitle is written to a temporary location, NOT the video folder.
    2. The video folder has no raw .ass file created.
    3. Auto-save writes ONLY the final .ara.ass file into the video folder.
    4. The temporary file is cleaned up.
    """
    from app.ui.windows.main_window import MainWindow
    from app.subtitle.video_extractor import VideoSubtitleExtractor, SubtitleStreamInfo

    win = MainWindow()
    
    # Create fake video file in a user directory
    user_video_dir = tmp_path / "user_movies"
    user_video_dir.mkdir()
    fake_video = user_video_dir / "Shingeki_No_Kyojin_S01E01.mkv"
    fake_video.write_bytes(b"dummy video data")

    streams = [
        SubtitleStreamInfo(index=0, global_index=2, codec_name="ass", extension=".ass", language="eng", title="Dialogue", is_default=True)
    ]

    # Create temporary extracted file to simulate ffmpeg
    def fake_extract(v_path, stream_index=0, output_path=None, prefer_ass=True):
        assert output_path is not None, "Output path must be explicitly provided (temp path)!"
        assert str(user_video_dir) not in output_path, "Extraction must NOT output into the video directory!"
        Path(output_path).write_text(
            "[Script Info]\nTitle: Test\n\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\nDialogue: 0,0:00:01.00,0:00:02.00,Default,,0,0,0,,Fight for freedom!",
            encoding="utf-8"
        )
        return True, output_path, ""

    with patch.object(VideoSubtitleExtractor, "probe_subtitle_streams", return_value=streams):
        with patch.object(VideoSubtitleExtractor, "extract_subtitle", side_effect=fake_extract):
            # Select video
            win._on_file_selected([str(fake_video)])

            # Check that raw .ass is NOT in user_video_dir
            raw_video_dir_ass = user_video_dir / "Shingeki_No_Kyojin_S01E01.ass"
            assert not raw_video_dir_ass.exists(), "The raw .ass file must NOT be created in the user's video folder!"

            # Check that language was auto-detected
            assert win.detected_source_lang == "English"
            assert "English" in win.settings_panel.lbl_detected_badge.text()

            # Check video_origin_map
            extracted_path = win.current_file_path
            assert extracted_path in win.video_origin_map
            assert win.video_origin_map[extracted_path] == str(fake_video)
            assert Path(extracted_path).exists()

            # Now simulate translation complete -> trigger auto-save
            win.document.events[0].translated_text = "قاتل من أجل الحرية!"
            win._save_file_auto()

            # Verify that ONLY the final Arabic file exists next to the video
            expected_ara_ass = user_video_dir / "Shingeki_No_Kyojin_S01E01.ara.ass"
            assert expected_ara_ass.exists(), "The final .ara.ass file MUST exist next to the video!"
            assert not raw_video_dir_ass.exists(), "The original extracted .ass must NEVER exist next to the video!"

            # Verify that the temp extracted file has been cleaned up
            assert not Path(extracted_path).exists(), "The temporary extracted file must be deleted after saving!"

            # Verify content of final Arabic subtitle
            saved_content = expected_ara_ass.read_text(encoding="utf-8")
            assert "قاتل من أجل الحرية!" in saved_content

            # Test that subsequent Master Subtitle Improvement does NOT fail with FileNotFoundError
            # when the raw extracted file has been cleaned up
            win._on_improvement_started()
            # Verify the current active path points to the saved .ara.ass file
            assert win.current_file_path == str(expected_ara_ass)
            assert str(expected_ara_ass) in win.selected_files

    win.close()
    win.deleteLater()
    qapp.processEvents()


@pytest.mark.asyncio
async def test_improvement_context_size_exceeded_binary_split():
    """Verify that when LM Studio returns 'Context size has been exceeded', engine triggers binary split immediately."""
    from app.translation.engine import TranslationEngine
    from app.translation.batcher import TokenBatcher
    from app.models.subtitle import SubtitleDocument, SubtitleEvent, SubtitleFormat
    from app.models.provider import ChatResponse

    doc = SubtitleDocument(
        format=SubtitleFormat.ASS,
        events=[
            SubtitleEvent(id="1", start_ms=0, end_ms=1000, text="First line", translated_text="السطر الأول"),
            SubtitleEvent(id="2", start_ms=1000, end_ms=2000, text="Second line", translated_text="السطر الثاني"),
        ]
    )

    batcher = TokenBatcher(max_tokens=2048, max_events=10)
    engine = TranslationEngine(batcher=batcher)

    mock_provider = MagicMock()
    mock_provider.provider_type = "lmstudio"
    call_count = 0

    async def fake_chat(messages, model, temperature=0.2, max_tokens=None, **kwargs):
        nonlocal call_count
        call_count += 1
        # First call with the combined batch of 2 lines fails with LM Studio context size error
        if call_count == 1:
            raise RuntimeError('HTTP 400 Error from LM Studio: {"error":"Context size has been exceeded."}')
        # Split calls with 1 line each succeed
        content = ""
        user_msg = messages[-1].content
        if "[1]" in user_msg:
            content += "[1] السطر الأول المحسن الفاخر\n"
        if "[2]" in user_msg:
            content += "[2] السطر الثاني المحسن الفاخر\n"
        return ChatResponse(content=content, input_tokens=50, output_tokens=30)

    mock_provider.chat_completion = AsyncMock(side_effect=fake_chat)

    await engine.improve_document(
        document=doc,
        provider=mock_provider,
        model="google/gemma-4-e2b",
        source_lang="English",
        target_lang="Arabic"
    )

    # Verify that binary split happened (1 failed call + 2 split calls = 3 calls total)
    assert call_count == 3
    assert doc.events[0].translated_text == "السطر الأول المحسن الفاخر"
    assert doc.events[1].translated_text == "السطر الثاني المحسن الفاخر"


def test_french_video_stream_and_text_auto_detection(qapp, tmp_path):
    """Verify that French stream [FRE] from video probe + French text detects French properly."""
    from app.ui.windows.main_window import MainWindow
    from app.subtitle.video_extractor import VideoSubtitleExtractor, SubtitleStreamInfo

    win = MainWindow()
    fake_video = tmp_path / "anime_subfrench.mkv"
    fake_video.write_bytes(b"dummy")

    streams = [
        SubtitleStreamInfo(index=0, global_index=2, codec_name="ass", extension=".ass", language="fre", title="French Dialogue", is_default=True)
    ]

    def fake_extract(v_path, stream_index=0, output_path=None, prefer_ass=True):
        Path(output_path).write_text(
            "[Script Info]\nTitle: Test\n\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\nDialogue: 0,0:00:01.00,0:00:02.00,Default,,0,0,0,,Bonjour tout le monde, comment allez-vous aujourd'hui ?",
            encoding="utf-8"
        )
        return True, output_path, ""

    with patch.object(VideoSubtitleExtractor, "probe_subtitle_streams", return_value=streams):
        with patch.object(VideoSubtitleExtractor, "extract_subtitle", side_effect=fake_extract):
            win._on_file_selected([str(fake_video)])
            
            assert win.detected_source_lang == "French"
            assert "French" in win.settings_panel.lbl_detected_badge.text()

    win.close()
    win.deleteLater()
    qapp.processEvents()


@pytest.mark.asyncio
async def test_fresh_session_no_cache_reuse(qapp, tmp_path):
    """
    Verify that when use_cache is False:
    1. Pre-existing event translations are completely purged.
    2. Checkpoints on disk are cleaned up and NOT loaded.
    3. Translation Memory lookups are bypassed.
    4. 100% of the lines are freshly dispatched to the AI provider.
    """
    from app.translation.engine import TranslationEngine
    from app.translation.batcher import TokenBatcher
    from app.models.subtitle import SubtitleDocument, SubtitleEvent, SubtitleFormat
    from app.storage.checkpoint import CheckpointManager
    from app.core.database import DatabaseManager
    from app.storage.memory_repo import TranslationMemoryRepository
    from app.models.provider import ChatResponse

    db = DatabaseManager()
    db.clear_cache()
    tm_repo = TranslationMemoryRepository(db)

    # Pre-populate TM with a translation
    tm_repo.save_translation("Hello", "ترجمة قديمة جداً من الذاكرة", "English", "Arabic")

    # Create dummy subtitle and checkpoint file
    sub_file = tmp_path / "test_session.ass"
    sub_file.write_text("[Script Info]\nTitle: Test\n", encoding="utf-8")
    
    # Save a checkpoint on disk
    ckpt_path = CheckpointManager.get_checkpoint_path(str(sub_file))
    CheckpointManager.save(str(sub_file), 2, {1: "ترجمة من نقطة التوقف القديمة"})
    assert Path(ckpt_path).exists()

    doc = SubtitleDocument(
        format=SubtitleFormat.ASS,
        file_path=str(sub_file),
        events=[
            SubtitleEvent(id=1, text="Hello", original_text="Hello", translated_text="ترجمة متبقية في الذاكرة"),
            SubtitleEvent(id=2, text="How are you?", original_text="How are you?", translated_text=None)
        ]
    )

    batcher = TokenBatcher(max_tokens=2048, max_events=10)
    engine = TranslationEngine(batcher=batcher, tm_repo=tm_repo)

    called_events = []
    async def fake_chat(messages, model, temperature=0.2, max_tokens=None, **kwargs):
        user_msg = messages[-1].content
        if "[001]" in user_msg or "[1]" in user_msg:
            called_events.append(1)
        if "[002]" in user_msg or "[2]" in user_msg:
            called_events.append(2)
        return ChatResponse(content="[001] مرحباً بك\n[002] كيف حالك اليوم؟", input_tokens=40, output_tokens=30)

    mock_provider = MagicMock()
    mock_provider.chat_completion = AsyncMock(side_effect=fake_chat)

    # Run translation with use_cache=False (default fresh mode)
    await engine.translate_document(
        document=doc,
        provider=mock_provider,
        model="gpt-4o",
        source_lang="English",
        target_lang="Arabic",
        source_file_path=str(sub_file),
        use_cache=False
    )

    # Verify both lines were freshly translated by AI and NOT pulled from TM or Checkpoint
    assert 1 in called_events
    assert 2 in called_events
    assert doc.events[0].translated_text == "مرحباً بك"
    assert doc.events[1].translated_text == "كيف حالك اليوم؟"
    assert "ترجمة قديمة" not in doc.events[0].translated_text
    assert "ترجمة متبقية" not in doc.events[0].translated_text
    assert not Path(ckpt_path).exists()


def test_ultra_strict_impurity_purification():
    r"""
    Tests SubtitleHealer against dirty subtitle text samples containing:
    - Markdown bold/italic/code syntax (**, *, _, `)
    - HTML tags (<i>, <b>, <br/>, <font>)
    - Verbose LLM explanatory prefixes & line numbers
    - SDH bracketed sound effects ([music], (sighs), {gasp}, [موسيقى])
    - Stray Latin words and fillers (\Nyeah, \Noh, \NI, stray Latin letters)
    - Punctuation errors (English commas/question marks, repeated punctuation)
    - Orphan quotes
    - Lonely dialogue dashes
    - Duplicate ASS tags
    """
    from app.quality.healer import SubtitleHealer

    # Sample 1: Markdown, HTML breaks, SDH sound effects, and English fillers
    dirty_1 = r"**1. الترجمة:** <i>مرحباً</i> بك يا صديقي! <br/> [music] (sighs) \Nyeah {gasp} هل أنت بخير? \NI"
    healed_1 = SubtitleHealer.heal(dirty_1)
    assert "**" not in healed_1
    assert "1. الترجمة:" not in healed_1
    assert "<i>" not in healed_1 and "</i>" not in healed_1
    assert "<br" not in healed_1
    assert "[music]" not in healed_1
    assert "(sighs)" not in healed_1
    assert "{gasp}" not in healed_1
    assert r"\Nyeah" not in healed_1
    assert r"\NI" not in healed_1
    assert "؟" in healed_1
    assert r"{\i1}مرحباً{\i0}" in healed_1
    assert "بك يا صديقي!" in healed_1

    # Sample 2: LLM pipe echo and leading labels
    dirty_2 = "[005] Original: I didn't want this. | Improved: لم أكن أريد هذا على الإطلاق."
    healed_2 = SubtitleHealer.heal(dirty_2)
    assert healed_2 == "لم أكن أريد هذا على الإطلاق."

    # Sample 3: Orphan quotes and duplicate punctuation
    dirty_3 = '"هذا نص غير مغلق،،، وجميل جداً؟؟!!'
    healed_3 = SubtitleHealer.heal(dirty_3)
    assert healed_3.count('"') == 0
    assert "،،" not in healed_3
    assert "؟؟" not in healed_3
    assert "؟!" in healed_3

    # Sample 4: Single speaker dialogue dash removal and ASS tag de-duplication
    dirty_4 = r"{\an8}{\an8}- مرحباً بك في منزلي\N"
    healed_4 = SubtitleHealer.heal(dirty_4)
    # Lonely leading dash removed because only 1 speaker
    assert healed_4.startswith(r"{\an8}مرحباً")
    assert not healed_4.endswith(r"\N")
    assert r"{\an8}{\an8}" not in healed_4

    # Sample 5: Multi-speaker dialogue dashes preserved correctly
    dirty_5 = r"-- أين أنت؟\N-- أنا في الغرفة."
    healed_5 = SubtitleHealer.heal(dirty_5)
    assert healed_5 == r"- أين أنت؟\N- أنا في الغرفة."


def test_rebuild_text_no_dangling_n_or_duplicate_tags():
    """Verify that SubtitleEvent.rebuild_text never duplicates tags or appends trailing \\N."""
    from app.models.subtitle import SubtitleEvent

    event = SubtitleEvent(
        id=1,
        original_text=r"{\an8\pos(100,200)}Hello world!",
        translated_text=""
    )

    # LLM translation that already includes {\an8\pos(100,200)} and has trailing \N
    llm_output = r"{\an8\pos(100,200)}مرحباً بالعالم!\N"
    rebuilt = event.rebuild_text(llm_output)

    # Must NOT have duplicate tags
    assert rebuilt.count(r"{\an8\pos(100,200)}") == 1
    # Must NOT have trailing \N
    assert not rebuilt.endswith(r"\N")
    assert rebuilt == r"{\an8\pos(100,200)}مرحباً بالعالم!"


def test_multiline_id_block_parsing():
    """Verify that ResponseParser captures multiline ID blocks and echoes."""
    parser = ResponseParser()

    # 1. Multiline ID with echo of original, current, and improved
    raw_multiline = """
    [1]
    النص الأصلي (French): Je t'aime trop, Takeru.
    الترجمة الحالية: Je t'aime trop, Takeru.
    الترجمة المحسنة: أحبك كثيراً يا تاكيرو.

    [2]
    نحن معاً مدى الحياة، أليس كذلك؟

    3.
    الترجمة: مرحباً يا هيداكا.
    """
    parsed = parser.parse_response(raw_multiline, [1, 2, 3])
    assert parsed.get(1) == "أحبك كثيراً يا تاكيرو."
    assert parsed.get(2) == "نحن معاً مدى الحياة، أليس كذلك؟"
    assert parsed.get(3) == "مرحباً يا هيداكا."


@pytest.mark.asyncio
async def test_improvement_targeted_recovery():
    """Verify that if only 1 line is missing in improvement, single-line targeted recovery fixes it without failing the batch."""
    from app.translation.engine import TranslationEngine
    from app.translation.batcher import TokenBatcher
    from app.models.subtitle import SubtitleDocument, SubtitleEvent, SubtitleFormat
    from app.models.provider import ChatResponse

    doc = SubtitleDocument(
        format=SubtitleFormat.ASS,
        events=[
            SubtitleEvent(id=1, text="Hello", original_text="Hello", translated_text="مرحبا"),
            SubtitleEvent(id=2, text="How are you?", original_text="How are you?", translated_text="كيف حالك؟"),
            SubtitleEvent(id=3, text="Good", original_text="Good", translated_text="جيد"),
        ]
    )

    batcher = TokenBatcher(max_tokens=2048, max_events=10)
    engine = TranslationEngine(batcher=batcher)

    call_count = 0
    async def fake_chat(messages, model, temperature=0.2, max_tokens=None, **kwargs):
        nonlocal call_count
        call_count += 1
        user_msg = messages[-1].content
        # First call omits ID 3
        if call_count == 1:
            return ChatResponse(content="[1] مرحباً بك يا صديقي\n[2] كيف أصبحت اليوم؟", input_tokens=40, output_tokens=30)
        # Targeted single line call for ID 3
        return ChatResponse(content="أنا بخير والحمد لله", input_tokens=20, output_tokens=15)

    mock_provider = MagicMock()
    mock_provider.chat_completion = AsyncMock(side_effect=fake_chat)

    await engine.improve_document(
        document=doc,
        provider=mock_provider,
        model="google/gemma-4-e2b",
        source_lang="English",
        target_lang="Arabic"
    )

    # 1 batch call + 1 targeted recovery call = 2 calls (NO binary split, NO endless retries!)
    assert call_count == 2
    assert doc.events[0].translated_text == "مرحباً بك يا صديقي"
    assert doc.events[1].translated_text == "كيف أصبحت اليوم؟"
    assert doc.events[2].translated_text == "أنا بخير والحمد لله"

def test_future_translation_pipeline_guarantees_extreme_cleanliness():
    """Verifies that any future file passed through write_subtitle is automatically and strictly purified."""
    from app.subtitle import write_subtitle, parse_subtitle

    doc = SubtitleDocument(format=SubtitleFormat.ASS)
    doc.events = [
        # Line 1: corrupt empty tags and missing line break
        SubtitleEvent(
            id=1,
            start="00:00:01.00",
            end="00:00:04.00",
            original_text=r"{\i1}Depuis ce jour,\NYoshioka n'a plus rien tenté.{\i0}",
            translated_text=r"{\i1}{\i0}منذ ذلك اليوم، لم يعد يوشيوكا يحاول شيئاً."
        ),
        # Line 2: fused Arabic prefix + Latin name
        SubtitleEvent(
            id=2,
            start="00:00:05.00",
            end="00:00:08.00",
            original_text=r"Super, je vais choisir\Nun maillot trop craquant pour Takeru !",
            translated_text=r"رائع، سأختار قميصاً لامعاً جداً لتakeru!"
        ),
        # Line 3: positioning tag with empty style tag
        SubtitleEvent(
            id=3,
            start="00:00:09.00",
            end="00:00:12.00",
            original_text=r"{\an8}{\i1}Deuxième jour.\NAujourd'hui, nous explorons l'île.{\i0}",
            translated_text=r"{\an8}{\i1}{\i0}اليوم الثاني. اليوم، سنستكشف داخل الجزيرة."
        )
    ]

    with tempfile.NamedTemporaryFile(suffix=".ass", delete=False, mode="w", encoding="utf-8") as tf:
        temp_path = tf.name

    try:
        write_subtitle(doc, temp_path)
        loaded = parse_subtitle(temp_path)

        # 1. Line 1: NO empty {\i1}{\i0}, wrapped in proper {\i1}...{\i0}, and has \N
        text_1 = loaded.events[0].original_text
        assert r"{\i1}{\i0}" not in text_1
        assert text_1.startswith(r"{\i1}")
        assert text_1.endswith(r"{\i0}")
        assert r"\N" in text_1

        # 2. Line 2: NO 'akeru', transliterated to 'لتاكيرو', and has \N
        text_2 = loaded.events[1].original_text
        assert "akeru" not in text_2
        assert "لتاكيرو" in text_2
        assert r"\N" in text_2

        # 3. Line 3: NO {\i1}{\i0}, {\an8} placed first, followed by {\i1}, and has \N
        text_3 = loaded.events[2].original_text
        assert r"{\i1}{\i0}" not in text_3
        assert text_3.startswith(r"{\an8}{\i1}")
        assert text_3.endswith(r"{\i0}")
        assert r"\N" in text_3
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)

def test_visual_effects_recognition_and_preservation():
    """
    Tests that visual effects (Karaoke FX, vector drawings, 3D typesetting, and signs)
    are recognized as non-translatable and preserved untouched in the subtitle file.
    """
    from app.subtitle import write_subtitle, parse_subtitle

    doc = SubtitleDocument(format=SubtitleFormat.ASS)
    doc.events = [
        # 1. Real dialogue line
        SubtitleEvent(id=1, style="Default", original_text="Are you my master?"),
        # 2. Romaji Karaoke FX line (Effect=fx)
        SubtitleEvent(
            id=2, style="ED2-Ro", effect="fx",
            original_text=r"{\an5\pos(640,400)\t(0,200,\alpha&HFF&)}sa-yo-na-ra"
        ),
        # 3. 3D rotated sign board
        SubtitleEvent(
            id=3, style="signs",
            original_text=r"{\fnCaviar Dreams\org(732,318)\fry-2.86\frx-0.68\pos(746,910)}Infirmary"
        ),
        # 4. Vector drawing
        SubtitleEvent(
            id=4, style="Default",
            original_text=r"{\p1}m 0 0 l 100 0 l 100 100 l 0 100{\p0}"
        ),
        # 5. Real dialogue with simple italics
        SubtitleEvent(id=5, style="Default", original_text=r"{\i1}I will always protect you.{\i0}")
    ]

    # Verify classification
    assert doc.events[0].is_translatable() is True
    assert doc.events[0].is_visual_effect() is False

    assert doc.events[1].is_visual_effect() is True
    assert doc.events[1].is_translatable() is False

    assert doc.events[2].is_visual_effect() is True
    assert doc.events[2].is_translatable() is False

    assert doc.events[3].is_visual_effect() is True
    assert doc.events[3].is_translatable() is False

    assert doc.events[4].is_translatable() is True
    assert doc.events[4].is_visual_effect() is False

    # get_translatable_events should only return dialogue (events 1 and 5)
    translatable = doc.get_translatable_events()
    assert len(translatable) == 2
    assert [e.id for e in translatable] == [1, 5]

    # Simulate translation of translatable events
    translatable[0].translated_text = "هل أنت سيدي؟"
    translatable[1].translated_text = "سأحميك دائماً."

    with tempfile.NamedTemporaryFile(suffix=".ass", delete=False, mode="w", encoding="utf-8") as tf:
        temp_path = tf.name

    try:
        write_subtitle(doc, temp_path)
        reparsed = parse_subtitle(temp_path)

        # All 5 events must exist in the saved file
        assert len(reparsed.events) == 5

        # Dialogue events were translated
        assert "هل أنت سيدي؟" in reparsed.events[0].original_text
        assert "سأحميك دائماً" in reparsed.events[4].original_text

        # Visual effects, 3D signs, and vector drawings are preserved 100% untouched
        assert reparsed.events[1].original_text == doc.events[1].original_text
        assert reparsed.events[2].original_text == doc.events[2].original_text
        assert reparsed.events[3].original_text == doc.events[3].original_text
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)






