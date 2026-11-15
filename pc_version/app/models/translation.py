from typing import Optional, List
from pydantic import BaseModel, Field
from app.models.subtitle import SubtitleEvent
from app.models.character import CharacterProfile
from app.models.glossary import GlossaryEntry

class TranslationRequest(BaseModel):
    events: List[int] = Field(..., description="List of SubtitleEvent references (by id)")
    source_lang: str
    target_lang: str
    characters: List[CharacterProfile] = Field(default_factory=list)
    glossary_entries: List[GlossaryEntry] = Field(default_factory=list)
    context_prev: List[SubtitleEvent] = Field(default_factory=list)
    context_next: List[SubtitleEvent] = Field(default_factory=list)
    custom_instructions: str = ''
    temperature: float = 0.1
    top_p: float = 0.85
    min_p: float = 0.05
    repetition_penalty: float = 1.0
    model: str = ''

class TranslationResult(BaseModel):
    event_id: int
    original_text: str
    translated_text: str
    confidence: float = 1.0

class BatchResult(BaseModel):
    results: List[TranslationResult] = Field(default_factory=list)
    batch_index: int = 0
    total_batches: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    duration_seconds: float = 0.0
    retries: int = 0
    errors: List[str] = Field(default_factory=list)
    success: bool = True
