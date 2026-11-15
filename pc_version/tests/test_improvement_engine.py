import pytest
import asyncio
from app.models.subtitle import SubtitleDocument, SubtitleEvent, SubtitleFormat
from app.models.provider import ChatResponse, ChatMessage, ProviderConfig, ProviderType
from app.providers.base import ProviderBase
from app.translation.engine import TranslationEngine
from app.quality.healer import SubtitleHealer

class MockProvider(ProviderBase):
    def __init__(self):
        super().__init__(ProviderConfig(type=ProviderType.LM_STUDIO, base_url="http://localhost:1234/v1"))

    async def list_models(self):
        return []

    async def chat_completion(self, messages, model, temperature=0.2, max_tokens=None, **kwargs):
        user_content = messages[-1].content
        lines = []
        for line in user_content.splitlines():
            if line.startswith("[") and "]" in line:
                idx = line[1:line.find("]")]
                lines.append(f"[{idx}] هذا نص محسن فائق الجودة خالي من الركاكة.")
        return ChatResponse(
            content="\n".join(lines),
            model=model,
            prompt_tokens=10,
            completion_tokens=20,
            total_tokens=30
        )

    async def test_connection(self):
        return True

@pytest.mark.asyncio
async def test_improve_document_flow():
    doc = SubtitleDocument(format=SubtitleFormat.SRT)
    doc.events = [
        SubtitleEvent(id=1, start_time="00:00:01,000", end_time="00:00:03,000", original_text="Wait, don't go!", translated_text="انتظر لا تذهب"),
        SubtitleEvent(id=2, start_time="00:00:03,500", end_time="00:00:05,000", original_text="I must go.", translated_text="يجب ان اذهب")
    ]
    
    provider = MockProvider()
    engine = TranslationEngine()
    
    improved_doc = await engine.improve_document(
        document=doc,
        provider=provider,
        model="mock-model",
        auto_heal=True
    )
    
    assert len(improved_doc.events) == 2
    assert "هذا نص محسن فائق الجودة" in improved_doc.events[0].translated_text
    assert "هذا نص محسن فائق الجودة" in improved_doc.events[1].translated_text

def test_quick_heal_document():
    doc = SubtitleDocument(format=SubtitleFormat.ASS)
    doc.events = [
        SubtitleEvent(id=1, start_time="0:00:01.00", end_time="0:00:03.00", original_text=r"{\an8}Hello", translated_text="مرحبا, كيف حالك? {Hmm.}"),
    ]
    engine = TranslationEngine()
    healed_count = engine.quick_heal_document(doc)
    assert healed_count == 1
    assert "،" in doc.events[0].translated_text
    assert "؟" in doc.events[0].translated_text
    assert "{Hmm.}" not in doc.events[0].translated_text
    assert r"{\an8}" in doc.events[0].translated_text
