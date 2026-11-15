from typing import Optional, List, Any
from pydantic import BaseModel, Field, model_validator

# Canonical re-exports to eliminate duplication between models/anime.py and models/character.py
from app.models.character import GenderEnum, CharacterProfile, CharacterMatch
from app.models.glossary import GlossaryEntry

class MediaInfo(BaseModel):
    id: Optional[int] = None
    media_type: str = "anime"  # "anime", "tv", "movie"
    title: str = ""
    title_romaji: str = ""
    title_english: str = ""
    title_native: str = ""
    title_user: str = ""
    year: Optional[int] = None
    episodes: Optional[int] = None
    format: str = ""
    status: str = ""
    cover_image_url: str = ""
    source_name: str = ""
    source_id: str = ""
    overview: str = ""
    genres: List[str] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def sync_titles(cls, data: Any) -> Any:
        if isinstance(data, dict):
            t = data.get("title", "")
            tr = data.get("title_romaji", "")
            te = data.get("title_english", "")
            if not tr and t:
                data["title_romaji"] = t
            elif not t and tr:
                data["title"] = tr
            elif not t and te:
                data["title"] = te
        return data

    @property
    def display_title(self) -> str:
        return (
            self.title_user
            or self.title
            or self.title_romaji
            or self.title_english
            or self.title_native
            or "Unknown Title"
        )

# Backward compatibility alias
AnimeInfo = MediaInfo

