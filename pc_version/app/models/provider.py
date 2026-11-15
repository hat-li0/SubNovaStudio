from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class ProviderType(str, Enum):
    LM_STUDIO = "lm_studio"
    OLLAMA = "ollama"
    OPENAI = "openai"
    GEMINI = "gemini"
    OPENAI_COMPATIBLE = "openai_compatible"


class ModelInfo(BaseModel):
    id: str
    name: str = ""
    context_length: Optional[int] = None
    owned_by: str = ""


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatResponse(BaseModel):
    content: str
    model: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

    @property
    def input_tokens(self) -> int:
        return self.prompt_tokens

    @property
    def output_tokens(self) -> int:
        return self.completion_tokens


class ProviderConfig(BaseModel):
    provider_type: ProviderType = ProviderType.LM_STUDIO
    base_url: str = "http://localhost:1234/v1"
    api_key: Optional[str] = None
    timeout: int = 120
    max_retries: int = 3
