import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from PySide6.QtWidgets import QApplication
from app.models.subtitle import SubtitleDocument, SubtitleEvent
from app.translation.engine import TranslationEngine
from app.translation.context import ContextBuilder
from app.ui.dialogs.untranslated_dialog import UntranslatedLinesDialog


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if not app:
        app = QApplication([])
    return app


def test_find_untranslated_events_detection():
    """Verify that find_untranslated_events accurately identifies all untranslated cases."""
    doc = SubtitleDocument()
    doc.events = [
        SubtitleEvent(id=1, text="Hello world", original_text="Hello world", translated_text="مرحباً بالعالم"),
        SubtitleEvent(id=2, text="How are you?", original_text="How are you?", translated_text=None),
        SubtitleEvent(id=3, text="I am fine.", original_text="I am fine.", translated_text="   "),
        SubtitleEvent(id=4, text="Wait here!", original_text="Wait here!", translated_text="Wait here!"),
        SubtitleEvent(id=5, text="...", original_text="...", translated_text="..."),
        SubtitleEvent(id=6, text="{\\p1}m 0 0 l 10 10{\\p0}", original_text="{\\p1}m 0 0 l 10 10{\\p0}", translated_text=None),
    ]

    untranslated = TranslationEngine.find_untranslated_events(doc, target_lang="Arabic", skip_effects=True)
    untrans_ids = [e.id for e in untranslated]

    # Event 1: Translated -> Excluded
    # Event 2: None -> Included
    # Event 3: Whitespace -> Included
    # Event 4: Unchanged English with no Arabic -> Included
    # Event 5: Punctuation dots -> Excluded
    # Event 6: Visual effect -> Excluded by skip_effects=True
    assert untrans_ids == [2, 3, 4]


def test_untranslated_lines_dialog_actions(qapp):
    """Test UntranslatedLinesDialog table population, search filter, and user action buttons."""
    events = [
        SubtitleEvent(id=10, start="00:01:00.00", end="00:01:02.00", speaker="Shinji", original_text="I must not run away."),
        SubtitleEvent(id=11, start="00:01:03.00", end="00:01:05.00", speaker="Misato", original_text="Get in the robot!"),
    ]

    dlg = UntranslatedLinesDialog(events=events, filename="Episode_01.ass", is_batch=True)
    assert dlg.table.rowCount() == 2
    assert dlg.table.item(0, 0).text() == "[010]"
    assert dlg.table.item(0, 3).text() == "Shinji"
    assert "I must not run away" in dlg.table.item(0, 4).text()
    assert dlg.chk_batch is not None

    # Test filtering
    dlg.search_input.setText("Misato")
    assert dlg.table.isRowHidden(0) is True
    assert dlg.table.isRowHidden(1) is False

    dlg.search_input.setText("")
    assert dlg.table.isRowHidden(0) is False
    assert dlg.table.isRowHidden(1) is False

    # Test Action Translate
    dlg._on_translate_clicked()
    assert dlg.selected_action == UntranslatedLinesDialog.ACTION_TRANSLATE

    # Test Action Save As-Is
    dlg._on_save_as_is_clicked()
    assert dlg.selected_action == UntranslatedLinesDialog.ACTION_SAVE_AS_IS

    # Test Batch toggle
    dlg.chk_batch.setChecked(True)
    assert dlg.should_apply_to_batch() is True


def test_context_builder_surrounding_dialogue_and_translations():
    """Verify ContextBuilder provides preceding/succeeding dialogue and already translated text."""
    cb = ContextBuilder(prev_count=2, next_count=2)
    events = [
        SubtitleEvent(id=1, original_text="Are you ready?", translated_text="هل أنتِ مستعدة؟"),
        SubtitleEvent(id=2, original_text="Almost.", translated_text="تقريباً."),
        SubtitleEvent(id=3, original_text="Don't be late.", translated_text=None),  # Target untranslated
        SubtitleEvent(id=4, original_text="I won't.", translated_text="لن أتأخر."),
    ]

    ctx = cb.build_context(events, [events[2]])

    # Previous context must include both lines and their existing Arabic translations!
    assert "Are you ready? -> هل أنتِ مستعدة؟" in ctx["prev_text"]
    assert "Almost. -> تقريباً." in ctx["prev_text"]

    # Current text is the untranslated line with its ID
    assert "[003] Don't be late." in ctx["current_text"]

    # Next context includes the upcoming dialogue and translation
    assert "I won't. -> لن أتأخر." in ctx["next_text"]


@pytest.mark.asyncio
async def test_translate_remaining_events_preserves_full_context():
    """Test that translate_remaining_events translates untranslated lines within full document context."""
    from app.providers.base import ProviderBase, ChatResponse, ProviderConfig

    doc = SubtitleDocument()
    doc.events = [
        SubtitleEvent(id=1, original_text="Scene starts here.", translated_text="يبدأ المشهد هنا."),
        SubtitleEvent(id=2, original_text="Where is the key?", translated_text=None),  # Untranslated
        SubtitleEvent(id=3, original_text="In my pocket.", translated_text="في جيبي."),
    ]

    engine = TranslationEngine()

    class TestMockProvider(ProviderBase):
        def __init__(self):
            super().__init__(ProviderConfig(provider_type="lm_studio", base_url="http://mock"))
            self.last_messages = []

        async def chat_completion(self, messages, model="mock", **kwargs):
            self.last_messages = messages
            # Check that prompt contains previous context!
            prompt_str = " ".join(m.content for m in messages)
            assert "Scene starts here." in prompt_str
            return ChatResponse(content="[001] أين المفتاح؟")

        async def test_connection(self):
            return True

        async def list_models(self):
            return []

    mock_provider = TestMockProvider()
    remaining = [doc.events[1]]
    count = await engine.translate_remaining_events(
        document=doc,
        remaining_events=remaining,
        provider=mock_provider,
        model="test-model",
        source_lang="English",
        target_lang="Arabic",
    )

    assert count == 1
    assert doc.events[1].translated_text == "أين المفتاح؟"
