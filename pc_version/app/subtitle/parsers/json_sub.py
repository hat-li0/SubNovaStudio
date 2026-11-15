import json
from app.models.subtitle import SubtitleFormat, SubtitleDocument, SubtitleEvent
from .base import SubtitleParser

class JSONParser(SubtitleParser):
    def parse_text(self, content: str) -> SubtitleDocument:
        doc = SubtitleDocument(format=SubtitleFormat.JSON)
        data = json.loads(content)
        if isinstance(data, list):
            for idx, item in enumerate(data, 1):
                doc.events.append(SubtitleEvent(
                    id=idx,
                    start=item.get('start', ''),
                    end=item.get('end', ''),
                    original_text=item.get('text', ''),
                    text=item.get('text', ''),
                    format_type=SubtitleFormat.JSON
                ))
        return doc
