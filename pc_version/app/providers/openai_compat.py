import httpx
from typing import List, Optional
from app.models.provider import ModelInfo, ChatMessage, ChatResponse, ProviderConfig
from app.providers.base import ProviderBase
from app.core.exceptions import ProviderError, ConnectionError

class OpenAICompatProvider(ProviderBase):
    """Generic OpenAI compatible provider."""
    
    def __init__(self, config: ProviderConfig):
        super().__init__(config)
        self.headers = {}
        if self.api_key:
            self.headers["Authorization"] = f"Bearer {self.api_key}"
            
    async def list_models(self) -> List[ModelInfo]:
        url = f"{self.base_url}/models"
        try:
            client = await self.get_client(self.headers)
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()
            models = []
            for item in data.get("data", []):
                models.append(ModelInfo(
                    id=item.get("id"),
                    name=item.get("id")
                ))
            return models
        except httpx.RequestError as e:
            raise ConnectionError(f"Failed to connect to OpenAI endpoint: {e}")
        except Exception as e:
            raise ProviderError(f"Error listing models: {e}")

    async def chat_completion(
        self, 
        messages: List[ChatMessage], 
        model: str, 
        temperature: float = 0.1, 
        max_tokens: Optional[int] = None,
        top_p: Optional[float] = 0.85,
        min_p: Optional[float] = 0.05,
        repetition_penalty: Optional[float] = 1.0
    ) -> ChatResponse:
        url = f"{self.base_url}/chat/completions"
        payload = {
            "model": model,
            "messages": [m.model_dump() for m in messages],
            "temperature": temperature if temperature is not None else 0.1,
            "stream": False
        }
        if top_p is not None:
            payload["top_p"] = top_p
        if min_p is not None:
            payload["min_p"] = min_p
        if repetition_penalty is not None:
            payload["repetition_penalty"] = repetition_penalty
        if max_tokens:
            payload["max_tokens"] = max_tokens
            
        try:
            client = await self.get_client(self.headers)
            response = await client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
            
            content = data["choices"][0]["message"]["content"]
            usage = data.get("usage", {})
            
            return ChatResponse(
                content=content,
                model=model,
                prompt_tokens=usage.get("prompt_tokens", 0),
                completion_tokens=usage.get("completion_tokens", 0),
                total_tokens=usage.get("total_tokens", 0)
            )
        except httpx.RequestError as e:
            raise ConnectionError(f"Failed to connect to OpenAI endpoint: {e}")
        except Exception as e:
            raise ProviderError(f"Error in chat completion: {e}")

    async def test_connection(self) -> bool:
        try:
            await self.list_models()
            return True
        except Exception:
            return False
