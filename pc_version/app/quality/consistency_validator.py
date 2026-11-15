import re
from typing import List, Dict, Any
from app.models.anime import GlossaryEntry
from app.models.subtitle import SubtitleEvent

class ConsistencyValidator:
    """Validates consistency of glossary terms across events."""
    
    def validate_consistency(self, events: List[SubtitleEvent], glossary: List[GlossaryEntry]) -> List[Dict[str, Any]]:
        """
        Checks whether glossary terms are used consistently across events.
        Detects if a term is translated inconsistently.
        """
        warnings = []
        
        for entry in glossary:
            source_term = entry.source_term
            target_term = entry.target_term
            
            for event in events:
                original = event.original_text or ""
                translated = event.translated_text or ""
                
                if not original or not translated:
                    continue
                    
                # Check if source term is in original text
                source_found = False
                if entry.is_case_sensitive:
                    if entry.is_exact_match:
                        pattern = r'\b' + re.escape(source_term) + r'\b'
                        source_found = bool(re.search(pattern, original))
                    else:
                        source_found = source_term in original
                else:
                    original_lower = original.lower()
                    term_lower = source_term.lower()
                    if entry.is_exact_match:
                        pattern = r'\b' + re.escape(term_lower) + r'\b'
                        source_found = bool(re.search(pattern, original_lower))
                    else:
                        source_found = term_lower in original_lower
                        
                if source_found:
                    # Check if target term is in translated text
                    target_found = target_term in translated
                    if not target_found:
                        warnings.append({
                            "event_id": event.id,
                            "source_term": source_term,
                            "expected_target": target_term,
                            "actual_text": translated,
                            "message": f"Glossary term '{source_term}' was found in original text but expected translation '{target_term}' is missing."
                        })
                        
        return warnings
