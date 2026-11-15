import json
from app.models.subtitle import SubtitleDocument
from app.subtitle.writers.base import SubtitleWriter

class JSONWriter(SubtitleWriter):
    """Writer for JSON subtitle format."""
    
    def write_text(self, document: SubtitleDocument) -> str:
        events = []
        for event in document.events:
            text = event.translated_text if event.translated_text else event.original_text
            events.append({
                "start": event.start_time,
                "end": event.end_time,
                "text": text
            })
        return json.dumps(events, ensure_ascii=False, indent=2)
