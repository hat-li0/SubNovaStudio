import httpx
import logging
from typing import List, Optional
from app.models.provider import ModelInfo, ChatMessage, ChatResponse, ProviderConfig
from app.providers.base import ProviderBase
from app.core.exceptions import ProviderError, ConnectionError

logger = logging.getLogger(__name__)

GEMINI_DEFAULT_MODELS = [
    "gemini-2.5-flash",
    "gemini-2.5-pro",
    "gemini-2.0-flash",
    "gemini-1.5-flash",
    "gemini-1.5-pro",
]

class GeminiProvider(ProviderBase):
    """Google Gemini provider with connection pooling and intelligent rate-limit fallback."""

    BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai"

    def __init__(self, config: ProviderConfig):
        if not config.base_url or "localhost" in config.base_url:
            config.base_url = self.BASE_URL
        config.base_url = config.base_url.rstrip("/")
        super().__init__(config)

        self.headers = {
            "Content-Type": "application/json",
        }
        if self.api_key:
            self.headers["Authorization"] = f"Bearer {self.api_key.strip()}"

    async def list_models(self) -> List[ModelInfo]:
        """Fetch available models from Gemini or return popular defaults."""
        if not self.api_key:
            return [ModelInfo(id=m, name=m) for m in GEMINI_DEFAULT_MODELS]

        url = f"{self.base_url}/models"
        try:
            client = await self.get_client()
            response = await client.get(url)
            if response.status_code == 200:
                data = response.json()
                models = []
                for item in data.get("data", []):
                    m_id = item.get("id", "")
                    if "gemini" in m_id.lower() or "models/gemini" in m_id.lower():
                        clean_id = m_id.replace("models/", "")
                        models.append(ModelInfo(id=clean_id, name=clean_id))
                if models:
                    return models
        except Exception as e:
            logger.warning(f"Could not fetch dynamic Gemini models: {e}. Falling back to default list.")

        return [ModelInfo(id=m, name=m) for m in GEMINI_DEFAULT_MODELS]

    async def chat_completion(
        self,
        messages: List[ChatMessage],
        model: str,
        temperature: float = 0.1,
        max_tokens: Optional[int] = None,
        top_p: Optional[float] = 0.85,
        min_p: Optional[float] = 0.05,
        repetition_penalty: Optional[float] = 1.0,
        _is_fallback: bool = False,
    ) -> ChatResponse:
        """Send chat completion to Google Gemini with connection reuse & auto-fallback."""
        if not self.api_key:
            raise ProviderError("Gemini API Key is missing. Please set your API key in the provider panel.")

        url = f"{self.base_url}/chat/completions"
        payload = {
            "model": model,
            "messages": [m.model_dump() for m in messages],
            "temperature": temperature if temperature is not None else 0.1,
            "stream": False
        }
        if top_p is not None:
            payload["top_p"] = top_p
        if max_tokens:
            payload["max_tokens"] = max_tokens

        try:
            client = await self.get_client()
            response = await client.post(url, json=payload)
            
            if response.status_code != 200:
                err_text = response.text
                if response.status_code == 400:
                    raise ProviderError(f"Gemini API 400 Bad Request: {err_text}")
                elif response.status_code in (401, 403):
                    raise ProviderError("Gemini API Key is invalid or unauthorized. Please verify your key.")
                elif response.status_code == 429:
                    # Intelligent Auto-Fallback: single-hop downgrade when heavy model hits rate limit
                    fallback_model = "gemini-2.5-flash"
                    if not _is_fallback and "pro" in model.lower() and model != fallback_model:
                        logger.warning(
                            f"⚠️ Rate limit / quota hit on '{model}'. Auto-falling back to '{fallback_model}'..."
                        )
                        return await self.chat_completion(
                            messages,
                            model=fallback_model,
                            temperature=temperature,
                            max_tokens=max_tokens,
                            top_p=top_p,
                            min_p=min_p,
                            repetition_penalty=repetition_penalty,
                            _is_fallback=True,
                        )
                    raise ProviderError("Gemini Rate Limit / Quota exceeded. Please wait or check your Gemini quota.")
                else:
                    raise ProviderError(f"Gemini HTTP {response.status_code} Error: {err_text}")

            data = response.json()
            choices = data.get("choices", [])
            if not choices:
                raise ProviderError(f"Gemini returned an empty choices array: {data}")

            content = choices[0].get("message", {}).get("content", "")
            usage = data.get("usage", {})

            return ChatResponse(
                content=content or "",
                model=model,
                prompt_tokens=usage.get("prompt_tokens", 0),
                completion_tokens=usage.get("completion_tokens", 0),
                total_tokens=usage.get("total_tokens", 0)
            )
        except httpx.RequestError as e:
            raise ConnectionError(f"Failed to connect to Google Gemini endpoint: {e}")
        except ProviderError:
            raise
        except Exception as e:
            raise ProviderError(f"Error in Gemini chat completion: {e}")

    async def test_connection(self) -> bool:
        """Validate API Key by sending a minimal test message."""
        if not self.api_key:
            return False
        try:
            test_msg = [ChatMessage(role="user", content="Ping")]
            model = self.config.model_name if hasattr(self.config, 'model_name') and self.config.model_name else "gemini-2.5-flash"
            resp = await self.chat_completion(test_msg, model=model, max_tokens=5)
            return bool(resp.content)
        except Exception as e:
            logger.error(f"Gemini connection test failed: {e}")
            return False
