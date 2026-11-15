from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, model_validator


class GenderEnum(str, Enum):
    MALE = "MALE"
    FEMALE = "FEMALE"
    NON_BINARY = "NON_BINARY"
    UNKNOWN = "UNKNOWN"
    CONFLICT = "CONFLICT"

    @classmethod
    def _missing_(cls, value):
        if isinstance(value, str):
            val_clean = value.strip().upper().replace("-", "_").replace(" ", "_")
            for member in cls:
                if member.name == val_clean or member.value == val_clean:
                    return member
        return cls.UNKNOWN


class GenderInfo(BaseModel):
    gender: GenderEnum = GenderEnum.UNKNOWN
    source: str = ""
    confidence: float = 0.0
    conflicts: List[Dict[str, Any]] = Field(default_factory=list)


class CharacterProfile(BaseModel):
    id: Optional[int] = None
    anime_id: Optional[int] = None
    canonical_name: str
    first_name: str = ""
    last_name: str = ""
    native_name: str = ""
    arabic_name: str = ""
    aliases: List[str] = Field(default_factory=list)
    gender_info: GenderInfo = Field(default_factory=GenderInfo)
    role: str = ""
    age: str = ""
    description: str = ""
    voice_actor: str = ""
    speech_style: str = ""
    translation_notes: str = ""
    is_user_override: bool = False

    @model_validator(mode='before')
    @classmethod
    def process_gender(cls, data: Any) -> Any:
        if isinstance(data, dict):
            g = data.pop("gender", None)
            conf = data.pop("gender_confidence", None)
            src = data.pop("gender_source", None)

            if "gender_info" in data and isinstance(data["gender_info"], dict):
                gi = dict(data["gender_info"])
                if g is not None:
                    gi["gender"] = g if isinstance(g, GenderEnum) else GenderEnum(str(g))
                if conf is not None:
                    gi["confidence"] = float(conf)
                if src is not None:
                    gi["source"] = str(src)
                data["gender_info"] = gi
            elif "gender_info" not in data and (g is not None or conf is not None or src is not None):
                if isinstance(g, str):
                    g = GenderEnum(g)
                elif g is None:
                    g = GenderEnum.UNKNOWN
                data["gender_info"] = {
                    "gender": g,
                    "source": src or "direct",
                    "confidence": float(conf) if conf is not None else 1.0,
                    "conflicts": []
                }
        return data

    @property
    def gender(self) -> GenderEnum:
        if self.gender_info:
            return self.gender_info.gender
        return GenderEnum.UNKNOWN

    @gender.setter
    def gender(self, val: Any) -> None:
        if not self.gender_info:
            self.gender_info = GenderInfo()
        if isinstance(val, str):
            val = GenderEnum(val)
        self.gender_info.gender = val

    @property
    def gender_source(self) -> str:
        if self.gender_info:
            return self.gender_info.source
        return ""

    @gender_source.setter
    def gender_source(self, val: str) -> None:
        if not self.gender_info:
            self.gender_info = GenderInfo()
        self.gender_info.source = str(val or "")

    @property
    def gender_confidence(self) -> float:
        if self.gender_info:
            return self.gender_info.confidence
        return 0.0

    @gender_confidence.setter
    def gender_confidence(self, val: float) -> None:
        if not self.gender_info:
            self.gender_info = GenderInfo()
        self.gender_info.confidence = float(val if val is not None else 0.0)

    def display_gender(self) -> str:
        """Returns Arabic gender string"""
        mapping = {
            GenderEnum.MALE: "ذكر",
            GenderEnum.FEMALE: "أنثى",
            GenderEnum.NON_BINARY: "غير ثنائي",
            GenderEnum.UNKNOWN: "غير معروف",
            GenderEnum.CONFLICT: "متعارض"
        }
        return mapping.get(self.gender_info.gender, "غير معروف")

    def get_pronouns(self) -> Dict[str, str]:
        """Returns dict with subject, object, possessive pronouns in Arabic"""
        if self.gender_info.gender == GenderEnum.MALE:
            return {"subject": "هو", "object": "ـه", "possessive": "ـه"}
        elif self.gender_info.gender == GenderEnum.FEMALE:
            return {"subject": "هي", "object": "ـها", "possessive": "ـها"}
        return {"subject": "هم", "object": "ـهم", "possessive": "ـهم"}

    def match_score(self, name: str) -> int:
        """Returns 0-100 match score against canonical_name and aliases"""
        name_lower = name.lower()
        canonical_lower = self.canonical_name.lower()
        if name_lower == canonical_lower:
            return 100
        for alias in self.aliases:
            if name_lower == alias.lower():
                return 100
        if name_lower in canonical_lower or canonical_lower in name_lower:
            return 80
        return 0


class CharacterMatch(BaseModel):
    character: Optional[CharacterProfile] = None
    profile: Optional[CharacterProfile] = None
    score: float = 0.0
    match_type: str = ""
    matched_against: str = ""

    @model_validator(mode="before")
    @classmethod
    def sync_character_and_profile(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "profile" in data and "character" not in data:
                data["character"] = data["profile"]
            elif "character" in data and "profile" not in data:
                data["profile"] = data["character"]
        return data

    @model_validator(mode="after")
    def ensure_both(self) -> "CharacterMatch":
        if self.profile and not self.character:
            self.character = self.profile
        elif self.character and not self.profile:
            self.profile = self.character
        return self

