from typing import List, Optional
from rapidfuzz import fuzz
from app.models.anime import CharacterProfile, CharacterMatch
from app.models.subtitle import SubtitleEvent

class CharacterResolver:
    """Resolves speaker names to Character Profiles."""
    
    def __init__(self, profiles: List[CharacterProfile]):
        self.profiles = profiles

    def resolve_speaker(self, speaker_name: str) -> Optional[CharacterMatch]:
        if not speaker_name or not self.profiles:
            return None
            
        best_match = None
        highest_score = 0.0
        
        name_lower = speaker_name.lower()

        for profile in self.profiles:
            # 1. Exact Match
            names = [
                profile.canonical_name, 
                profile.first_name, 
                profile.last_name, 
                profile.native_name
            ]
            for n in names:
                if n and speaker_name == n:
                    return CharacterMatch(profile=profile, score=100.0, match_type="exact", matched_against=n)
                    
            # 2. Case-insensitive Match
            for n in names:
                if n and name_lower == n.lower():
                    return CharacterMatch(profile=profile, score=95.0, match_type="case_insensitive", matched_against=n)
                    
            # 3. Alias Match
            for alias in profile.aliases:
                if name_lower == alias.lower():
                    return CharacterMatch(profile=profile, score=90.0, match_type="alias", matched_against=alias)
                    
            # 4. Rapidfuzz Match
            for n in names + profile.aliases:
                if not n:
                    continue
                ratio = max(
                    fuzz.ratio(name_lower, n.lower()),
                    fuzz.token_sort_ratio(name_lower, n.lower())
                )
                if ratio > highest_score:
                    highest_score = ratio
                    best_match = CharacterMatch(profile=profile, score=ratio, match_type="fuzzy", matched_against=n)
                    
        if best_match and best_match.score >= 80.0:
            return best_match
            
        return None

    def get_batch_characters(self, events: List[SubtitleEvent]) -> List[CharacterProfile]:
        """Find all unique speakers in batch events, resolve them, return used character profiles."""
        unique_speakers = {e.speaker.strip() for e in events if e.speaker and e.speaker.strip()}
        
        resolved_profiles = {}
        for spk in unique_speakers:
            match = self.resolve_speaker(spk)
            if match and match.profile:
                # Deduplicate by canonical_name or id
                key = match.profile.canonical_name or str(match.profile.id or id(match.profile))
                resolved_profiles[key] = match.profile
                
        return list(resolved_profiles.values())
