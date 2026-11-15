from app.models.provider import ProviderConfig, ProviderType
from app.providers.base import ProviderBase
from app.providers.lmstudio import LMStudioProvider
from app.providers.ollama import OllamaProvider
from app.providers.openai_compat import OpenAICompatProvider
from app.providers.gemini import GeminiProvider
from app.providers.openai import OpenAIProvider

# Alias for consistent naming
OpenAICompatibleProvider = OpenAICompatProvider


def get_provider(config: ProviderConfig) -> ProviderBase:
    """Factory function to get a provider instance based on config."""
    ptype = config.provider_type
    if hasattr(ptype, "value"):
        ptype_val = ptype.value.lower()
    else:
        ptype_val = str(ptype).lower()

    if "gemini" in ptype_val:
        return GeminiProvider(config)
    elif ptype_val == "openai" or "providertype.openai" in ptype_val or ptype_val == "provider_type.openai":
        return OpenAIProvider(config)
    elif "lm" in ptype_val:
        return LMStudioProvider(config)
    elif "ollama" in ptype_val:
        return OllamaProvider(config)
    elif "openai" in ptype_val:
        return OpenAICompatProvider(config)
    else:
        return LMStudioProvider(config)
