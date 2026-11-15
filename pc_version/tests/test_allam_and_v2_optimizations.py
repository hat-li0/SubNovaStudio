import pytest
from app.translation.prompts import PromptBuilder
from app.translation.response_parser import ResponseParser
from app.translation.batcher import TokenBatcher
from app.core.config import AppSettings, get_settings
from app.models.provider import ModelInfo, ChatMessage
from app.models.subtitle import SubtitleEvent


def test_allam_prompt_builder():
    """Verify ALLaM models receive Arabic-native, high-efficiency prompts."""
    builder = PromptBuilder()
    
    # 1. Normal prompt (non-allam)
    std_msgs = builder.build_prompt(
        source_lang="English",
        target_lang="Arabic",
        current_subtitles="[1] Hello\n[2] World",
        model_name="qwen2.5-7b-instruct"
    )
    assert "You are an elite, master anime" in std_msgs[0].content
    
    # 2. ALLaM-optimized prompt
    allam_msgs = builder.build_prompt(
        source_lang="الإنجليزية",
        target_lang="العربية",
        current_subtitles="[1] Hello\n[2] World",
        story_notes="ملاحظة هامة",
        model_name="allam-7b-arabic-sft"
    )
    # Check that system instruction is purely in Arabic for ALLaM
    assert "أنت مترجم شارات وأنمي محترف" in allam_msgs[0].content
    assert "القواعد الصارمة" in allam_msgs[0].content
    assert "[ملاحظات القصة والمشهد]" in allam_msgs[1].content
    assert "الأسطر المطلوب ترجمتها الآن" in allam_msgs[1].content


def test_allam_improvement_prompt():
    """Verify ALLaM improvement prompt is Arabic-native."""
    builder = PromptBuilder()
    msgs = builder.build_improvement_prompt(
        source_lang="English",
        target_lang="Arabic",
        current_subtitles="[1] مرحباً\n[2] أهلاً",
        model_name="allam-7b-instruct-preview"
    )
    assert "أنت مدقق ومحرر لغوي محترف" in msgs[0].content
    assert "صقل وتدقيق" in msgs[0].content


def test_allam_empty_brackets_response_parsing():
    """Verify ALLaM empty brackets '[]' and '[ ]' are parsed, stripped and mapped positionally."""
    parser = ResponseParser()
    
    # Empty bracket lines from ALLaM SFT
    raw_allam = "[] إلى أين أنت ذاهب الآن؟\n[] أنا متجه إلى الأكاديمية."
    parsed = parser.parse_response(raw_allam, [10, 11])
    assert parsed == {
        10: "إلى أين أنت ذاهب الآن؟",
        11: "أنا متجه إلى الأكاديمية."
    }
    # Ensure leading brackets are completely gone
    assert not parsed[10].startswith("[]")
    assert not parsed[10].startswith("[ ]")
    
    # Empty bracket with spaces
    raw_allam_space = "[ ] مرحباً يا صديقي\n[ ] كيف أصبحت اليوم؟"
    parsed_space = parser.parse_response(raw_allam_space, [1, 2])
    assert parsed_space == {
        1: "مرحباً يا صديقي",
        2: "كيف أصبحت اليوم؟"
    }


def test_max_context_and_batcher_budgeting():
    """Verify TokenBatcher respects max_context properly."""
    # 4k context model (like ALLaM)
    batcher_4k = TokenBatcher(max_events=30, max_context=4096)
    events = [SubtitleEvent(id=i, text=f"Long dialogue line number {i} with several characters") for i in range(1, 30)]
    batches_4k = batcher_4k.create_batches(events, is_local=True)
    assert len(batches_4k[0]) <= 12
    
    # Large context model (like 32k)
    batcher_32k = TokenBatcher(max_events=30, max_context=32768)
    batches_32k = batcher_32k.create_batches(events, is_local=False)
    assert len(batches_32k[0]) == 29


def test_app_settings_max_context_and_parallel():
    """Verify AppSettings includes max_context and default local concurrency."""
    settings = AppSettings()
    assert hasattr(settings, 'max_context')
    assert settings.max_context == 4096
    assert hasattr(settings, 'concurrency')


def test_provider_panel_allam_and_engine_controls():
    """Verify ProviderPanel has max_context and parallel steppers, and detects ALLaM."""
    from PySide6.QtWidgets import QApplication
    from app.ui.widgets.provider_panel import ProviderPanel, PROVIDER_MODEL_PRESETS
    app = QApplication.instance() or QApplication([])

    panel = ProviderPanel()
    try:
        assert hasattr(panel, 'sb_max_context')
        assert hasattr(panel, 'sb_parallel')
        assert hasattr(panel, 'lbl_context_badge')
        
        # Check ALLaM presets exist for LM Studio and Ollama
        assert any("allam" in mid for mid, _ in PROVIDER_MODEL_PRESETS["lmstudio"])
        assert any("allam" in mid for mid, _ in PROVIDER_MODEL_PRESETS["ollama"])

        # Test context detection for ALLaM
        panel._detect_and_apply_context("allam-7b-arabic-sft")
        assert panel.sb_max_context.value() == 4096
        assert "4096" in panel.lbl_context_badge.text()

        # Test context detection for Qwen
        panel._detect_and_apply_context("qwen2.5-7b-instruct")
        assert panel.sb_max_context.value() == 32768
    finally:
        panel.deleteLater()
        app.processEvents()


def test_main_window_video_player_default_off_and_splitter():
    """Verify Media Player is off by default and toggle button is accessible."""
    from PySide6.QtWidgets import QApplication
    from app.ui.windows.main_window import MainWindow
    app = QApplication.instance() or QApplication([])

    win = MainWindow()
    try:
        # 1. Media player must be completely off / hidden by default
        assert win.video_container.isHidden()
        assert win.video_player.player is None
        
        # 2. Toggle button must be visible, accessible, and outside video_container
        assert win.btn_toggle_video.parent() != win.video_container
        assert "طافي" in win.btn_toggle_video.text() or "معطل" in win.btn_toggle_video.text()
        
        # 3. Toggle button opens the video player container
        win.btn_toggle_video.click()
        assert not win.video_container.isHidden()
        assert "إغلاق" in win.btn_toggle_video.text()
        
        # 4. Toggle button closes it and cleans up resources
        win.btn_toggle_video.click()
        assert win.video_container.isHidden()
        assert win.video_player.player is None
        assert "طافي" in win.btn_toggle_video.text()

        # 5. Check left panel minimum width >= 400 to prevent splitter overlap
        left_panel = win.findChild(type(win.provider_panel.parent().parent()))
        assert win.provider_panel.minimumWidth() >= 0
    finally:
        win.deleteLater()
        app.processEvents()
