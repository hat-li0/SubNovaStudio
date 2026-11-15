import pytest
from app.models.subtitle import SubtitleEvent
from app.translation.batcher import TokenBatcher
from app.translation.context import ContextBuilder
from app.translation.prompts import PromptBuilder
from app.translation.response_parser import ResponseParser
from app.translation.validator import TranslationValidator

def test_batcher():
    batcher = TokenBatcher(max_tokens=6000, max_events=2)
    events = [
        SubtitleEvent(id=1, text="Hello"),
        SubtitleEvent(id=2, text="World"),
        SubtitleEvent(id=3, text="Test")
    ]
    batches = batcher.create_batches(events)
    assert len(batches) == 2
    assert len(batches[0]) == 2
    assert len(batches[1]) == 1

def test_context_builder():
    cb = ContextBuilder(prev_count=1, next_count=1)
    events = [
        SubtitleEvent(id=1, text="Prev"),
        SubtitleEvent(id=2, text="Current"),
        SubtitleEvent(id=3, text="Next")
    ]
    ctx = cb.build_context(events, [events[1]])
    assert "Prev" in ctx["prev_text"]
    assert "Next" in ctx["next_text"]
    assert "[002] Current" in ctx["current_text"]

def test_prompt_builder():
    pb = PromptBuilder()
    msgs = pb.build_prompt("en", "ar", "[001] Hello")
    assert len(msgs) == 2
    assert msgs[0].role == "system"
    assert msgs[1].role == "user"
    assert "CURRENT SUBTITLES TO TRANSLATE:" in msgs[1].content

def test_response_parser():
    parser = ResponseParser()
    raw = "```\n[1] مرحبا\n[2] العالم\n```"
    res = parser.parse_response(raw, [1, 2])
    assert res[1] == "مرحبا"
    assert res[2] == "العالم"

def test_validator():
    validator = TranslationValidator()
    events = [SubtitleEvent(id=1, text="A"), SubtitleEvent(id=2, text="B")]
    translations = {1: "Trans A"}
    is_valid, issues = validator.validate_batch_output(translations, events)
    assert not is_valid
    assert "Missing translations for IDs: [2]" in issues[0]


@pytest.mark.asyncio
async def test_engine_skips_effects_and_preadopts_arabic():
    from app.models.subtitle import SubtitleDocument, SubtitleFormat
    from app.translation.engine import TranslationEngine
    from app.providers.base import ProviderBase
    from app.models.provider import ChatMessage, ChatResponse, ProviderConfig

    class MockProvider(ProviderBase):
        def __init__(self):
            super().__init__(ProviderConfig(provider_type="lm_studio", base_url="http://mock"))
            self.calls = []

        async def chat_completion(self, messages, model="mock", **kwargs):
            self.calls.append(messages)
            # Batch IDs are normalized to contiguous local IDs [001..N] to prevent ID slippage
            return ChatResponse(content="[001] إلى أين أنت ذاهب؟")

        async def test_connection(self):
            return True

        async def list_models(self):
            return []

    provider = MockProvider()
    engine = TranslationEngine()

    doc = SubtitleDocument(
        format=SubtitleFormat.ASS,
        events=[
            SubtitleEvent(id=1, style="Default", original_text=r"{\an8}SFX: BOOM"),
            SubtitleEvent(id=2, style="Default", original_text="Where are you going?"),
            SubtitleEvent(id=3, style="Default", original_text="مرحباً يا صديقي"),
        ]
    )

    result_doc = await engine.translate_document(
        document=doc,
        provider=provider,
        model="mock",
        source_lang="en",
        target_lang="ar",
        healing_options={"skip_visual_effects": True, "separate_inline_effects": True}
    )

    # 1. Effect line (id 1) was skipped from translation
    assert doc.events[0].is_visual_effect() is True
    assert doc.events[0].translated_text is None

    # 2. English line (id 2) was sent to provider and translated
    assert doc.events[1].translated_text == "إلى أين أنت ذاهب؟"

    # 3. Already-Arabic line (id 3) was pre-adopted without LLM query
    assert doc.events[2].translated_text == "مرحباً يا صديقي"

    # 4. Mock provider was only called for the English line (1 prompt call) using contiguous local ID [001]
    assert len(provider.calls) == 1
    prompt_text = provider.calls[0][1].content
    assert "[001] Where are you going?" in prompt_text
    assert "[003]" not in prompt_text
    assert "[002]" not in prompt_text


@pytest.mark.asyncio
async def test_engine_deduplicates_identical_lines_without_deleting_events():
    """Verify identical dialogue lines are translated once, propagated to duplicates, and none are deleted."""
    from app.models.subtitle import SubtitleDocument, SubtitleFormat
    from app.translation.engine import TranslationEngine
    from app.providers.base import ProviderBase
    from app.models.provider import ChatResponse, ProviderConfig

    class MockDedupProvider(ProviderBase):
        def __init__(self):
            super().__init__(ProviderConfig(provider_type="lm_studio", base_url="http://mock"))
            self.calls = []

        async def chat_completion(self, messages, model="mock", **kwargs):
            self.calls.append(messages)
            prompt = messages[1].content
            # Respond with contiguous local IDs [001], [002] present in the prompt
            lines = []
            if "[001]" in prompt:
                lines.append("[001] انتظرني هنا!")
            if "[002]" in prompt:
                lines.append("[002] أنا قادم.")
            return ChatResponse(content="\n".join(lines))

        async def test_connection(self):
            return True

        async def list_models(self):
            return []

    provider = MockDedupProvider()
    engine = TranslationEngine()

    # 5 events, but only 2 unique texts ("Wait for me here!" and "I am coming.")
    doc = SubtitleDocument(
        format=SubtitleFormat.ASS,
        events=[
            SubtitleEvent(id=1, style="Default", original_text="Wait for me here!"),
            SubtitleEvent(id=2, style="Default", original_text="Wait for me here!"),
            SubtitleEvent(id=3, style="Default", original_text="I am coming."),
            SubtitleEvent(id=4, style="Default", original_text="Wait for me here!"),
            SubtitleEvent(id=5, style="Default", original_text="Wait for me here!"),
        ]
    )

    result_doc = await engine.translate_document(
        document=doc,
        provider=provider,
        model="mock",
        source_lang="en",
        target_lang="ar",
        healing_options={"deduplicate_identical_lines": True}
    )

    # 1. Total events MUST remain exactly 5 (no lines deleted)
    assert len(result_doc.events) == 5

    # 2. Provider must ONLY be called for the 2 unique lines with contiguous local IDs ([001] and [002])
    assert len(provider.calls) == 1
    prompt_content = provider.calls[0][1].content
    assert "[001] Wait for me here!" in prompt_content
    assert "[002] I am coming." in prompt_content
    assert "[003]" not in prompt_content
    assert "[004]" not in prompt_content
    assert "[005]" not in prompt_content

    # 3. All 4 occurrences of "Wait for me here!" must receive the translation
    assert result_doc.events[0].translated_text == "انتظرني هنا!"
    assert result_doc.events[1].translated_text == "انتظرني هنا!"
    assert result_doc.events[3].translated_text == "انتظرني هنا!"
    assert result_doc.events[4].translated_text == "انتظرني هنا!"

    # 4. The other line must have its own translation
    assert result_doc.events[2].translated_text == "أنا قادم."


@pytest.mark.asyncio
async def test_engine_preserves_unique_tags_on_duplicated_lines():
    """Verify duplicates with different ASS tags receive the translation with their own tags restored."""
    from app.models.subtitle import SubtitleDocument, SubtitleFormat
    from app.translation.engine import TranslationEngine
    from app.providers.base import ProviderBase
    from app.models.provider import ChatResponse, ProviderConfig

    class MockTagDedupProvider(ProviderBase):
        def __init__(self):
            super().__init__(ProviderConfig(provider_type="lm_studio", base_url="http://mock"))
            self.calls = []

        async def chat_completion(self, messages, model="mock", **kwargs):
            self.calls.append(messages)
            return ChatResponse(content="[001] مرحباً بك!")

        async def test_connection(self):
            return True

        async def list_models(self):
            return []

    provider = MockTagDedupProvider()
    engine = TranslationEngine()

    doc = SubtitleDocument(
        format=SubtitleFormat.ASS,
        events=[
            SubtitleEvent(id=1, style="Default", speaker="Guide", original_text=r"{\an8}Welcome!"),
            SubtitleEvent(id=2, style="Default", speaker="Guide", original_text=r"{\i1}Welcome!{\i0}"),
            SubtitleEvent(id=3, style="Default", speaker="Guide", original_text=r"Welcome!"),
        ]
    )

    result_doc = await engine.translate_document(
        document=doc,
        provider=provider,
        model="mock",
        source_lang="en",
        target_lang="ar",
        healing_options={"deduplicate_identical_lines": True, "protect_tags": True}
    )

    # All events translated
    assert len(result_doc.events) == 3
    assert len(provider.calls) == 1

    # First event had {\an8}
    assert r"{\an8}" in result_doc.events[0].translated_text

    # Second event had {\i1}...{\i0} and should NOT leak {\an8}
    assert r"{\i1}" in result_doc.events[1].translated_text
    assert r"{\an8}" not in result_doc.events[1].translated_text

    # Third event had no tags
    assert r"{\an8}" not in result_doc.events[2].translated_text
    assert r"{\i1}" not in result_doc.events[2].translated_text
    assert "مرحباً بك!" in result_doc.events[2].translated_text
