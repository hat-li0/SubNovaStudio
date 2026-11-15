import pytest
from app.models.provider import ProviderConfig, ProviderType, ChatMessage
from app.providers import get_provider, LMStudioProvider, OllamaProvider, OpenAICompatibleProvider


def test_provider_factory():
    cfg_lm = ProviderConfig(provider_type=ProviderType.LM_STUDIO, base_url="http://localhost:1234/v1")
    p_lm = get_provider(cfg_lm)
    assert isinstance(p_lm, LMStudioProvider)

    cfg_ol = ProviderConfig(provider_type=ProviderType.OLLAMA, base_url="http://localhost:11434")
    p_ol = get_provider(cfg_ol)
    assert isinstance(p_ol, OllamaProvider)

    cfg_oa = ProviderConfig(provider_type=ProviderType.OPENAI_COMPATIBLE, base_url="http://api.example.com/v1")
    p_oa = get_provider(cfg_oa)
    assert isinstance(p_oa, OpenAICompatibleProvider)


@pytest.mark.asyncio
async def test_provider_is_available_offline():
    cfg = ProviderConfig(provider_type=ProviderType.LM_STUDIO, base_url="http://invalid-localhost-9999/v1", timeout=1)
    provider = get_provider(cfg)
    is_avail = await provider.is_available()
    assert is_avail is False
