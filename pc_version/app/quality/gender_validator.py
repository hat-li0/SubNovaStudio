import re
from typing import List
from app.models.character import CharacterProfile, GenderEnum

class GenderValidator:
    """Validates gender consistency in Arabic translations."""
    
    def __init__(self):
        # Arabic patterns without \b since diacritics (Fatha/Kasra) break word boundaries
        self.masculine_patterns = [
            r'أنتَ', r'قلتَ', r'فعلتَ', r'ذهبتَ', r'عليك', r' له '
        ]
        self.feminine_patterns = [
            r'أنتِ', r'قلتِ', r'فعلتِ', r'ذهبتِ', r'عليكِ', r' لها '
        ]

    def validate_gender(self, translated_text: str, character: CharacterProfile) -> List[str]:
        """
        Analyzes Arabic text for potential pronoun/verb gender mismatches.
        Returns a list of warning messages for flagged suspicious candidates.
        """
        if not translated_text or not character:
            return []
            
        warnings = []
        gender = character.gender
        
        if gender == GenderEnum.FEMALE:
            for pattern in self.masculine_patterns:
                if re.search(pattern, translated_text):
                    warnings.append(
                        f"Female character '{character.canonical_name}' uses potential masculine form: {pattern}"
                    )
                    
        elif gender == GenderEnum.MALE:
            for pattern in self.feminine_patterns:
                if re.search(pattern, translated_text):
                    warnings.append(
                        f"Male character '{character.canonical_name}' uses potential feminine form: {pattern}"
                    )
                    
        return warnings
