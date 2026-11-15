from typing import Set
from app.models.subtitle import SubtitleDocument

class SpeakerExtractor:
    """Extracts speakers from subtitles."""
    
    def extract_speakers(self, document: SubtitleDocument) -> Set[str]:
        """Extract unique non-empty Name fields from events."""
        speakers = set()
        for event in document.events:
            speaker = event.speaker.strip()
            if speaker:
                speakers.add(speaker)
        return speakers
