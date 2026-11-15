import pytest
import asyncio
from app.core.logging import EventBusLogHandler
from app.ui.bus import EventBus
from app.core.database import DatabaseManager
from app.models.subtitle import SubtitleDocument, SubtitleEvent, SubtitleFormat
from app.ui.dialogs.review_dialog import TranslationReviewDialog
import logging

def test_event_bus_log_handler():
    # Test that logging an error emits to the EventBus
    received = []
    def slot(msg):
        received.append(msg)
        
    bus = EventBus.instance()
    bus.log_message.connect(slot)
    
    test_logger = logging.getLogger("test_bus_logger")
    test_logger.setLevel(logging.DEBUG)
    handler = EventBusLogHandler()
    test_logger.addHandler(handler)
    
    test_logger.error("Test error message")
    test_logger.warning("Test warning message")
    
    # Clean up
    test_logger.removeHandler(handler)
    bus.log_message.disconnect(slot)
    
    assert any("Test error message" in m for m in received)
    assert any("Test warning message" in m for m in received)

def test_database_cache_operations():
    db = DatabaseManager(":memory:")
    
    # Test set and get
    db.set_cache("test_key", {"data": 123}, source="unit_test", ttl_seconds=3600)
    cached = db.get_cache("test_key")
    assert cached is not None
    assert cached["data"] == 123
    
    # Test non-existent key
    assert db.get_cache("unknown_key") is None
    
    # Test expired key
    db.set_cache("expired_key", {"data": 456}, source="unit_test", ttl_seconds=-10)
    assert db.get_cache("expired_key") is None

def test_review_dialog_document_integration(qtbot=None):
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    
    doc = SubtitleDocument(
        format=SubtitleFormat.ASS,
        events=[
            SubtitleEvent(id=1, text="Hello world", translated_text="مرحبا بالعالم"),
            SubtitleEvent(id=2, text="How are you", translated_text=""),
            SubtitleEvent(id=3, text="Test quote", translated_text='علامة "يتيمة'),
        ]
    )
    
    dlg = TranslationReviewDialog(document=doc)
    assert dlg.table.rowCount() == 3
    
    # Check that warnings were identified
    item_warn_row2 = dlg.table.item(1, 4)
    assert "Untranslated" in item_warn_row2.text()
    
    item_warn_row3 = dlg.table.item(2, 4)
    assert "Orphan quote" in item_warn_row3.text()
    
    # Edit row 2's translation and verify saving updates doc.events
    dlg.table.item(1, 3).setText("كيف حالك")
    dlg._on_save()
    
    ev2 = doc.get_event_by_id(2)
    assert ev2.translated_text == "كيف حالك"

@pytest.mark.asyncio
async def test_provider_client_pooling():
    from app.models.provider import ProviderConfig, ProviderType
    from app.providers.gemini import GeminiProvider
    
    cfg = ProviderConfig(type=ProviderType.OPENAI_COMPATIBLE, base_url="https://generativelanguage.googleapis.com", api_key="dummy")
    provider = GeminiProvider(cfg)
    
    client1 = await provider.get_client()
    client2 = await provider.get_client()
    assert client1 is client2
    
    await provider.close()

@pytest.mark.asyncio
async def test_gemini_fallback_on_429():
    import httpx
    import json
    from app.models.provider import ProviderConfig, ProviderType, ChatMessage
    from app.providers.gemini import GeminiProvider
    
    cfg = ProviderConfig(type=ProviderType.OPENAI_COMPATIBLE, base_url="https://test.api", api_key="dummy_key")
    provider = GeminiProvider(cfg)
    
    calls = []
    def handler(request):
        body = json.loads(request.content.decode("utf-8"))
        model = body.get("model")
        calls.append(model)
        if "pro" in model:
            return httpx.Response(429, text="Rate limit exceeded")
        return httpx.Response(200, json={
            "choices": [{"message": {"content": "Translated text"}}],
            "model": model,
            "usage": {"prompt_tokens": 10, "completion_tokens": 5}
        })
        
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider._client = client
    
    res = await provider.chat_completion([ChatMessage(role="user", content="Hi")], model="gemini-2.5-pro")
    assert res.content == "Translated text"
    assert "gemini-2.5-pro" in calls
    assert "gemini-2.5-flash" in calls
    await provider.close()
