from app.models.subtitle import SubtitleDocument
from app.subtitle.writers.base import SubtitleWriter

class SBVWriter(SubtitleWriter):
    """Writer for YouTube SBV subtitle format."""
    
    def write_text(self, document: SubtitleDocument) -> str:
        lines = []
        for event in document.events:
            lines.append(f"{event.start_time},{event.end_time}")
            text = event.translated_text if event.translated_text else event.original_text
            lines.append(text)
            lines.append("")
        return "\n".join(lines)
