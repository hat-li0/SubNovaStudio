from typing import Optional, List
from pydantic import BaseModel, Field

class GlossaryEntry(BaseModel):
    id: Optional[int] = None
    anime_id: Optional[int] = None
    source_term: str
    target_term: str
    is_exact_match: bool = True
    is_case_sensitive: bool = False
    notes: str = ''
