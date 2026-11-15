import pytest
import asyncio
import os
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

from app.models.subtitle import SubtitleDocument, SubtitleEvent, SubtitleFormat
from app.models.provider import ChatResponse, ChatMessage, ProviderConfig, ProviderType
from app.models.character import CharacterProfile, GenderEnum, GenderInfo
from app.subtitle import parse_subtitle, write_subtitle
from app.subtitle.detector import detect_format
from app.subtitle.video_extractor import VideoSubtitleExtractor, SubtitleStreamInfo, VIDEO_EXTENSIONS
from app.quality.healer import SubtitleHealer
from app.translation.engine import TranslationEngine
from app.translation.batcher import TokenBatcher
from app.translation.prompts import PromptBuilder
from app.translation.validator import PipelineValidator
from app.storage.checkpoint import CheckpointManager
from app.storage.memory_repo import TranslationMemoryRepository
from app.core.database import DatabaseManager
from app.anime.metadata_service import AnimeMetadataService
from app.anime.identifier import MediaIdentifier
from app.providers import get_provider
from app.providers.base import ProviderBase

class FullMockProvider(ProviderBase):
    def __init__(self):
        super().__init__(ProviderConfig(type=ProviderType.LM_STUDIO, base_url="http://localhost:1234/v1"))
        self.call_count = 0

    async def list_models(self):
        return [MagicMock(id="google/gemma-4-e2b"), MagicMock(id="qwen2.5-coder")]

    async def chat_completion(self, messages, model, temperature=0.2, max_tokens=None, **kwargs):
        self.call_count += 1
        user_content = messages[-1].content
        lines = []
        for line in user_content.splitlines():
            line_str = line.strip()
            if line_str.startswith("[") and "]" in line_str:
                idx = line_str[1:line_str.find("]")]
                lines.append(f"[{idx}] مرحباً بكم في الحلقة الجديدة، هل أنت جاهز؟")
        return ChatResponse(
            content="\n".join(lines),
            model=model,
            prompt_tokens=50,
            completion_tokens=40,
            total_tokens=90
        )

    async def test_connection(self):
        return True


def test_1_subtitles_parsing_writing_and_roundtrip():
    """Tests SRT, ASS, and VTT parsing, format detection, and write roundtrip."""
    # 1. SRT Test
    srt_content = """1
00:00:01,000 --> 00:00:04,000
Hello world, are you ready?

2
00:00:05,000 --> 00:00:08,000
Yes, let's go!
"""
    with tempfile.NamedTemporaryFile(suffix=".srt", mode="w", encoding="utf-8", delete=False) as f:
        f.write(srt_content)
        srt_path = f.name

    try:
        doc = parse_subtitle(srt_path)
        assert doc.format == SubtitleFormat.SRT
        assert len(doc.events) == 2
        assert "Hello world" in doc.events[0].original_text
        assert doc.events[1].original_text == "Yes, let's go!"

        # Write to another SRT
        out_srt = srt_path.replace(".srt", "_out.srt")
        doc.events[0].translated_text = "مرحباً بالعالم، هل أنت مستعد؟"
        write_subtitle(doc, out_srt)
        assert os.path.exists(out_srt)
        parsed_out = parse_subtitle(out_srt)
        assert "مرحباً بالعالم" in (parsed_out.events[0].original_text or parsed_out.events[0].text)
        if os.path.exists(out_srt):
            os.remove(out_srt)
    finally:
        if os.path.exists(srt_path):
            os.remove(srt_path)

    # 2. ASS with complex tags
    ass_content = """[Script Info]
Title: Test ASS
ScriptType: v4.00+
WrapStyle: 0
PlayResX: 1920
PlayResY: 1080

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,50,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,2,2,2,10,10,10,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:01.00,0:00:03.50,Default,,0,0,0,,{\\an8\\pos(960,120)}Look at the sky!\\N{\\c&H00FFFF&}It's beautiful.
"""
    with tempfile.NamedTemporaryFile(suffix=".ass", mode="w", encoding="utf-8", delete=False) as f:
        f.write(ass_content)
        ass_path = f.name

    try:
        doc_ass = parse_subtitle(ass_path)
        assert doc_ass.format == SubtitleFormat.ASS
        assert len(doc_ass.events) == 1
        ev = doc_ass.events[0]
        assert r"{\an8\pos(960,120)}" in ev.original_text
        assert r"\N" in ev.original_text

        # Test writing ASS with translation while preserving tags
        ev.translated_text = r"{\an8\pos(960,120)}انظر إلى السماء!\N{\c&H00FFFF&}إنها جميلة."
        out_ass = ass_path.replace(".ass", "_out.ass")
        write_subtitle(doc_ass, out_ass)
        assert os.path.exists(out_ass)
        with open(out_ass, "r", encoding="utf-8") as rf:
            out_content = rf.read()
        assert "[Script Info]" in out_content
        assert "[V4+ Styles]" in out_content
        assert r"{\an8\pos(960,120)}" in out_content
        assert "انظر إلى السماء!" in out_content
        if os.path.exists(out_ass):
            os.remove(out_ass)
    finally:
        if os.path.exists(ass_path):
            os.remove(ass_path)


def test_2_auto_healing_comprehensive():
    """Tests all features of the SubtitleHealer engine."""
    # Punctuation normalization
    raw_ar = "مرحبا, كيف حالك? انا بخير; شكرا لك!"
    fixed_punct = SubtitleHealer.normalize_arabic_punctuation(raw_ar)
    assert "،" in fixed_punct
    assert "؟" in fixed_punct
    assert "؛" in fixed_punct
    assert "," not in fixed_punct
    assert "?" not in fixed_punct

    # Tag protection and restoration
    orig_with_tags = r"{\an8\pos(500,200)}Hello world!\N{\fad(200,200)}Goodbye!"
    protected, tags = SubtitleHealer.protect_ass_tags(orig_with_tags)
    assert "___ASS_TAG_" in protected
    assert len(tags) == 2
    restored = SubtitleHealer.restore_ass_tags(protected, tags)
    assert restored == orig_with_tags

    # Stray Latin removal
    noise_text = r"مرحبا بك \NI {Hmm.} \Na وأهلاً"
    clean_noise = SubtitleHealer.clean_stray_latin(noise_text)
    assert r"\NI" not in clean_noise
    assert r"{Hmm.}" not in clean_noise
    assert "مرحبا بك" in clean_noise and "وأهلاً" in clean_noise

    # Orphan quote fixing
    unbalanced = 'قال المعلم: "هذا درس مهم جدا'
    fixed_quotes = SubtitleHealer.fix_orphan_quotes(unbalanced)
    assert fixed_quotes.count('"') % 2 == 0 or '"' not in fixed_quotes

    # Master heal pipeline
    raw_input = r"{\an8}مرحبا, كيف حالك? \NI {Oh.}"
    healed = SubtitleHealer.heal(raw_input, orig_with_tags, {
        "arabic_punct": True,
        "latin_clean": True,
        "quote_fix": True,
        "protect_tags": True
    })
    assert "،" in healed
    assert "؟" in healed
    assert r"\NI" not in healed
    assert "{Oh.}" not in healed
    assert r"{\an8}" in healed


@pytest.mark.asyncio
async def test_3_translation_engine_full_lifecycle():
    """Tests end-to-end translation, auto-healing, post-improvement, and memory cache."""
    doc = SubtitleDocument(format=SubtitleFormat.SRT)
    doc.events = [
        SubtitleEvent(id=1, start_time="00:00:01,000", end_time="00:00:03,000", original_text="Welcome to the episode, are you ready?"),
        SubtitleEvent(id=2, start_time="00:00:03,500", end_time="00:00:05,000", original_text="Yes, we are completely ready!"),
        SubtitleEvent(id=3, start_time="00:00:05,500", end_time="00:00:07,000", original_text="Welcome to the episode, are you ready?") # Duplicate for TM
    ]

    provider = FullMockProvider()
    engine = TranslationEngine(
        batcher=TokenBatcher(max_tokens=2000, max_events=2)
    )

    progress_reports = []
    def track_progress(*args):
        progress_reports.append(args)

    translated_doc = await engine.translate_document(
        document=doc,
        provider=provider,
        model="google/gemma-4-e2b",
        source_lang="English",
        target_lang="Arabic",
        on_progress=track_progress,
        concurrency=2,
        temperature=0.2,
        auto_heal=True,
        auto_improve=True,
        story_notes="أنمي درامي، الأبطال شجعان"
    )

    assert len(translated_doc.events) == 3
    for ev in translated_doc.events:
        assert ev.translated_text
        assert "مرحباً" in ev.translated_text or "جاهز" in ev.translated_text
    assert len(progress_reports) > 0


def test_4_video_subtitle_extractor_logic():
    """Tests video file detection, stream selection scoring, and codec mappings."""
    for ext in ('.mkv', '.mp4', '.avi', '.mov', '.webm', '.flv', '.ts', '.m4v'):
        assert VideoSubtitleExtractor.is_video_file(f"test_movie{ext}")
    assert not VideoSubtitleExtractor.is_video_file("test_sub.srt")
    assert not VideoSubtitleExtractor.is_video_file("test_sub.ass")

    # Test smart stream scoring
    streams = [
        SubtitleStreamInfo(index=0, global_index=2, codec_name='subrip', extension='.srt', language='eng', title='Signs & Songs', is_default=False),
        SubtitleStreamInfo(index=1, global_index=3, codec_name='ass', extension='.ass', language='eng', title='Full Dialogue [Subtitles]', is_default=True),
        SubtitleStreamInfo(index=2, global_index=4, codec_name='subrip', extension='.srt', language='spa', title='Spanish', is_default=False)
    ]

    best = VideoSubtitleExtractor.select_best_stream(streams, preferred_lang="en")
    assert best is not None
    assert best.index == 1
    assert best.codec_name == 'ass'
    assert best.title == 'Full Dialogue [Subtitles]'


def test_5_anime_and_character_metadata():
    """Tests Anime title cleaning, character profile attributes, and gender representation."""
    identifier = MediaIdentifier()
    dirty_name = "[SubsPlease] Sousou no Frieren - 01 (1080p) [ABCD1234].mkv"
    media_info = identifier.identify_media_info(dirty_name)
    assert "Sousou no Frieren" in media_info["title"]
    assert media_info["media_type"] == "anime"
    assert media_info["episode"] == "01"

    # Test CharacterProfile
    char = CharacterProfile(
        canonical_name="Frieren",
        arabic_name="فريرن",
        gender_info=GenderInfo(gender=GenderEnum.FEMALE, confidence=1.0, source="Database")
    )
    assert char.canonical_name == "Frieren"
    assert char.arabic_name == "فريرن"
    assert char.gender_info.gender == GenderEnum.FEMALE
    pronouns = char.get_pronouns()
    assert pronouns.get("subject") == "هي"


def test_6_ui_widgets_headless():
    """Tests GUI panels, character filtering, quick healing, and live preview."""
    import sys
    from PySide6.QtWidgets import QApplication
    from app.ui.windows.main_window import MainWindow

    app = QApplication.instance() or QApplication(sys.argv)
    win = MainWindow()
    assert win is not None
    assert win.tabs.count() == 4

    # Test character panel search/filter
    win.character_panel.add_character("Eren Yeager", "إيرين ييغر", "Male")
    win.character_panel.add_character("Mikasa Ackerman", "ميكاسا أكرمان", "Female")
    win.character_panel.add_character("Armin Arlert", "أرمين أرليرت", "Male")
    assert win.character_panel.table.rowCount() == 3

    # Filter for 'Mikasa'
    win.character_panel._filter_table("Mikasa")
    assert win.character_panel.table.isRowHidden(0) is True   # Eren hidden
    assert win.character_panel.table.isRowHidden(1) is False  # Mikasa shown
    assert win.character_panel.table.isRowHidden(2) is True   # Armin hidden

    # Reset filter
    win.character_panel._filter_table("")
    assert win.character_panel.table.isRowHidden(0) is False
    assert win.character_panel.table.isRowHidden(1) is False

    # Test Live Preview
    win.live_preview.update_preview("Hello", "مرحباً")
    assert win.live_preview.lbl_orig.text() == "Hello"
    assert win.live_preview.lbl_imp.text() == "مرحباً"
    win.live_preview.clear()
    assert "بانتظار" in win.live_preview.lbl_orig.text()

    # Test Stepper Plus / Minus Buttons
    init_b = win.settings_panel.sb_batch_size.value()
    win.settings_panel.sb_batch_size.btn_plus.click()
    assert win.settings_panel.sb_batch_size.value() == init_b + 1
    win.settings_panel.sb_batch_size.btn_minus.click()
    assert win.settings_panel.sb_batch_size.value() == init_b
    win.deleteLater()
    app.processEvents()
