import re
from typing import List

class FormatValidator:
    """Validates subtitle formatting and tags preservation."""
    
    def validate_ass_tags(self, original_text: str, rebuilt_text: str) -> List[str]:
        r"""
        Verifies that all ASS override tags and \N are preserved.
        """
        warnings = []
        if not original_text or not rebuilt_text:
            return warnings
            
        # Extract tags from original
        original_tags = re.findall(r"\{[^}]*\}", original_text)
        rebuilt_tags = re.findall(r"\{[^}]*\}", rebuilt_text)
        
        for tag in original_tags:
            if tag not in rebuilt_tags:
                warnings.append(f"Missing ASS tag in translation: {tag}")
                
        # Check \N line breaks
        orig_newlines = original_text.count(r"\N") + original_text.count(r"\n")
        rebuilt_newlines = rebuilt_text.count(r"\N") + rebuilt_text.count(r"\n")
        
        if orig_newlines > 0 and rebuilt_newlines == 0:
            warnings.append(f"Mismatched line breaks (\\N). Original has {orig_newlines}, translation has {rebuilt_newlines}.")
            
        return warnings
