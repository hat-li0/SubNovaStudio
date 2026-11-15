import httpx
import logging
from typing import List, Optional
from app.models.provider import ModelInfo, ChatMessage, ChatResponse, ProviderConfig
from app.providers.base import ProviderBase
from app.core.exceptions import ProviderError, ConnectionError

logger = logging.getLogger(__name__)

OPENAI_DEFAULT_MODELS = [
    "gpt-4o",
    "gpt-4o-mini",
    "o3-mini",
    "gpt-4-turbo",
    "gpt-4",
    "o1-mini",
]

class OpenAIProvider(ProviderBase):
    """OpenAI (ChatGPT) provider with connection pooling and rate-limit auto-fallback."""

    BASE_URL = "https://api.openai.com/v1"

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
        """Fetch available models from OpenAI or return default models."""
        if not self.api_key:
            return [ModelInfo(id=m, name=m) for m in OPENAI_DEFAULT_MODELS]

        url = f"{self.base_url}/models"
        try:
            client = await self.get_client()
            response = await client.get(url)
            if response.status_code == 200:
                data = response.json()
                models = []
                for item in data.get("data", []):
                    m_id = item.get("id", "")
                    if m_id.startswith("gpt-") or m_id.startswith("o1") or m_id.startswith("o3"):
                        models.append(ModelInfo(id=m_id, name=m_id))
                if models:
                    models.sort(key=lambda x: x.id)
                    return models
        except Exception as e:
            logger.warning(f"Could not list OpenAI models: {e}. Using defaults.")

        return [ModelInfo(id=m, name=m) for m in OPENAI_DEFAULT_MODELS]

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
        """Send chat completion to OpenAI with connection pooling and auto-fallback."""
        if not self.api_key:
            raise ProviderError("OpenAI API Key is missing. Please set your API key in the provider panel.")

        url = f"{self.base_url}/chat/completions"
        payload = {
            "model": model,
            "messages": [m.model_dump() for m in messages],
            "stream": False
        }
        
        # Reasoning models do not accept custom temperature
        if not (model.startswith("o1") or model.startswith("o3")):
            payload["temperature"] = temperature
            if top_p is not None:
                payload["top_p"] = top_p
            payload["presence_penalty"] = 0.0
            payload["frequency_penalty"] = 0.0

        if max_tokens:
            if model.startswith("o1") or model.startswith("o3"):
                payload["max_completion_tokens"] = max_tokens
            else:
                payload["max_tokens"] = max_tokens

        try:
            client = await self.get_client()
            response = await client.post(url, json=payload)
            
            if response.status_code != 200:
                err_text = response.text
                if response.status_code in (401, 403):
                    raise ProviderError("OpenAI API Key is invalid or unauthorized. Please verify your key.")
                elif response.status_code == 429:
                    # Intelligent Auto-Fallback: single-hop downgrade to fast mini model
                    fallback_model = "gpt-4o-mini"
                    if not _is_fallback and model != fallback_model:
                        logger.warning(
                            f"⚠️ Rate limit on '{model}'. Auto-falling back to '{fallback_model}'..."
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
                    raise ProviderError("OpenAI Rate Limit or Quota exceeded. Please check your billing or rate limits.")
                else:
                    raise ProviderError(f"OpenAI HTTP {response.status_code} Error: {err_text}")

            data = response.json()
            choices = data.get("choices", [])
            if not choices:
                raise ProviderError(f"OpenAI returned empty choices: {data}")

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
            raise ConnectionError(f"Failed to connect to OpenAI endpoint: {e}")
        except ProviderError:
            raise
        except Exception as e:
            raise ProviderError(f"Error in OpenAI chat completion: {e}")

    async def test_connection(self) -> bool:
        """Validate connection and API key."""
        if not self.api_key:
            return False
        try:
            test_msg = [ChatMessage(role="user", content="Ping")]
            resp = await self.chat_completion(test_msg, model="gpt-4o-mini", max_tokens=5)
            return bool(resp.content)
        except Exception as e:
            logger.error(f"OpenAI connection test failed: {e}")
            return False
