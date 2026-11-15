import httpx
from abc import ABC, abstractmethod
from typing import List, Optional, Dict
from app.models.provider import ModelInfo, ChatMessage, ChatResponse, ProviderConfig

class ProviderBase(ABC):
    """Abstract base class for LLM providers with connection pooling."""
    
    def __init__(self, config: ProviderConfig):
        self.config = config
        self.base_url = config.base_url
        self.api_key = config.api_key
        self.timeout = config.timeout
        self.headers: Dict[str, str] = {}
        self._client: Optional[httpx.AsyncClient] = None

    async def get_client(self, custom_headers: Optional[Dict[str, str]] = None) -> httpx.AsyncClient:
        """Returns or creates a pooled AsyncClient session."""
        headers = dict(self.headers)
        if custom_headers:
            headers.update(custom_headers)
            
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=self.timeout,
                headers=headers,
                limits=httpx.Limits(max_keepalive_connections=20, max_connections=50)
            )
        return self._client

    async def close(self) -> None:
        """Close connection pool cleanly."""
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    @abstractmethod
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
        """Send a chat completion request to the provider."""
        pass
    
    @abstractmethod
    async def list_models(self) -> List[ModelInfo]:
        """List available models from the provider."""
        pass
    
    @abstractmethod
    async def test_connection(self) -> bool:
        """Test the connection to the provider."""
        pass
    
    async def is_available(self) -> bool:
        """Check if the provider is currently available."""
        try:
            return await self.test_connection()
        except Exception:
            return False
