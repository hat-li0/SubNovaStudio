import re
from app.models.subtitle import SubtitleFormat, SubtitleDocument, SubtitleEvent
from .base import SubtitleParser

class SBVParser(SubtitleParser):
    def parse_text(self, content: str) -> SubtitleDocument:
        doc = SubtitleDocument(format=SubtitleFormat.SBV)
        blocks = re.split(r'\n\n+', content.strip())
        idx = 1
        for block in blocks:
            lines = block.split('\n')
            if lines and ',' in lines[0]:
                times = lines[0].split(',')
                start, end = times[0].strip(), times[1].strip()
                text = '\n'.join(lines[1:])
                doc.events.append(SubtitleEvent(
                    id=idx, start=start, end=end, original_text=text, text=text, format_type=SubtitleFormat.SBV
                ))
                idx += 1
        return doc
