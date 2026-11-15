import os
import sys
import tempfile
import pytest
from unittest.mock import patch, MagicMock
from app.core.resources import resource_path, find_binary
from app.models.subtitle import SubtitleEvent, SubtitleFormat
from app.subtitle.video_extractor import VideoSubtitleExtractor
from app.translation.prompts import PromptBuilder
import main

def test_resource_path_and_find_binary():
    """Verify resource_path resolves paths and find_binary locates binaries."""
    # Test resource_path resolves existing icon
    resolved_icon = resource_path(os.path.join("app", "resources", "icons", "subnova_icon.ico"))
    assert os.path.isabs(resolved_icon)
    assert os.path.exists(resolved_icon)

    # Test find_binary for python executable on PATH or system
    py_bin = find_binary("python")
    assert py_bin is not None
    assert "python" in py_bin.lower()

    # VideoSubtitleExtractor should return non-empty binary strings
    assert VideoSubtitleExtractor.get_ffmpeg_bin() is not None
    assert VideoSubtitleExtractor.get_ffprobe_bin() is not None

def test_karaoke_tag_visual_effect_detection():
    """Verify karaoke tags are detected as visual effects to prevent translation mangling."""
    karaoke_event = SubtitleEvent(
        id=1,
        style="Default",
        original_text=r"{\k25}Hello {\k30}World",
        format_type=SubtitleFormat.ASS
    )
    assert karaoke_event.is_visual_effect() is True
    assert karaoke_event.is_translatable() is False

    dialogue_event = SubtitleEvent(
        id=2,
        style="Default",
        original_text=r"Hello World",
        format_type=SubtitleFormat.ASS
    )
    assert dialogue_event.is_visual_effect() is False
    assert dialogue_event.is_translatable() is True

def test_fatal_crash_logging():
    """Verify log_fatal_crash writes formatted crash dump to crash.log."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        fake_crash_log = os.path.join(tmp_dir, "crash.log")
        with patch.object(sys, "frozen", True, create=True), patch("sys.executable", os.path.join(tmp_dir, "app.exe")):
            try:
                raise ValueError("Simulated fatal test crash")
            except ValueError:
                exc_type, exc_val, tb = sys.exc_info()
                main.log_fatal_crash(exc_type, exc_val, tb, show_dialog=False)

        # Confirm crash.log exists and contains the trace
        assert os.path.exists(fake_crash_log)
        with open(fake_crash_log, "r", encoding="utf-8") as f:
            content = f.read()
        assert "FATAL APPLICATION CRASH" in content
        assert "Simulated fatal test crash" in content

def test_prompt_anti_language_leakage():
    """Verify prompt builder includes strict anti-language-leakage rules."""
    pb = PromptBuilder()
    messages = pb.build_prompt(
        source_lang="Japanese",
        target_lang="Arabic",
        current_subtitles="[1] Konnichiwa"
    )
    sys_prompt = messages[0].content
    assert "Chinese" in sys_prompt
    assert "Japanese (kanji/kana)" in sys_prompt
    assert "Arabic" in sys_prompt
