from app.models.subtitle import SubtitleDocument
from app.subtitle.writers.base import SubtitleWriter

class TXTWriter(SubtitleWriter):
    """Writer for plain text subtitle format."""
    
    def write_text(self, document: SubtitleDocument) -> str:
        lines = []
        for event in document.events:
            text = event.translated_text if event.translated_text else event.original_text
            lines.append(text)
        return "\n".join(lines) + "\n"
