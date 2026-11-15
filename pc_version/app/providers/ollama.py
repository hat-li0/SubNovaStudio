import httpx
from typing import List, Optional
from app.models.provider import ModelInfo, ChatMessage, ChatResponse, ProviderConfig
from app.providers.base import ProviderBase
from app.core.exceptions import ProviderError, ConnectionError

class OllamaProvider(ProviderBase):
    """Ollama provider supporting native /api/tags and OpenAI compatibility."""
    
    def __init__(self, config: ProviderConfig):
        if not config.base_url:
            config.base_url = "http://localhost:11434"
        config.base_url = config.base_url.rstrip("/")
        super().__init__(config)
        
    async def list_models(self) -> List[ModelInfo]:
        url = f"{self.base_url}/api/tags"
        try:
            client = await self.get_client()
            response = await client.get(url)
            if response.status_code != 200:
                # Fallback to OpenAI compatible /v1/models
                url_v1 = f"{self.base_url}/v1/models"
                response = await client.get(url_v1)
            
            response.raise_for_status()
            data = response.json()
            models = []
            raw_list = data.get("models", []) or data.get("data", [])
            
            for item in raw_list:
                if isinstance(item, dict):
                    m_name = item.get("name") or item.get("id") or str(item)
                else:
                    m_name = str(item)
                models.append(ModelInfo(
                    id=m_name,
                    name=m_name
                ))
            return models
        except httpx.RequestError as e:
            raise ConnectionError(f"Failed to connect to Ollama at {url}: {e}")
        except Exception as e:
            raise ProviderError(f"Error listing Ollama models: {e}")

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
        url = f"{self.base_url}/api/chat"
        ollama_messages = [{"role": m.role, "content": m.content} for m in messages]
        
        options = {
            "temperature": temperature,
            "top_p": top_p if top_p is not None else 0.85,
            "repeat_penalty": repetition_penalty if repetition_penalty is not None else 1.0
        }
        if min_p is not None:
            options["min_p"] = min_p

        payload = {
            "model": model,
            "messages": ollama_messages,
            "stream": False,
            "options": options
        }
        if max_tokens:
            payload["options"]["num_predict"] = max_tokens
            
        try:
            client = await self.get_client()
            response = await client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
            
            content = data.get("message", {}).get("content", "")
            prompt_eval_count = data.get("prompt_eval_count", 0)
            eval_count = data.get("eval_count", 0)
            
            return ChatResponse(
                content=content,
                model=model,
                prompt_tokens=prompt_eval_count,
                completion_tokens=eval_count,
                total_tokens=prompt_eval_count + eval_count
            )
        except httpx.RequestError as e:
            raise ConnectionError(f"Failed to connect to Ollama: {e}")
        except Exception as e:
            raise ProviderError(f"Error in Ollama chat completion: {e}")

    async def test_connection(self) -> bool:
        try:
            await self.list_models()
            return True
        except Exception:
            return False
