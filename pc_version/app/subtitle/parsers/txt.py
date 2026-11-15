import re
from app.models.subtitle import SubtitleFormat, SubtitleDocument, SubtitleEvent
from .base import SubtitleParser

class TXTParser(SubtitleParser):
    def parse_text(self, content: str) -> SubtitleDocument:
        doc = SubtitleDocument(format=SubtitleFormat.TXT)
        lines = content.splitlines()
        for idx, line in enumerate(lines, 1):
            if line.strip():
                doc.events.append(SubtitleEvent(
                    id=idx, start='', end='', original_text=line, text=line, format_type=SubtitleFormat.TXT
                ))
        return doc
