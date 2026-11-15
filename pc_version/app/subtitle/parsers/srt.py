import re
from app.models.subtitle import SubtitleFormat, SubtitleDocument, SubtitleEvent
from app.subtitle.timecode import extract_timecode_token, parse_timecode_ms
from .base import SubtitleParser

_SRT_TIME_LINE_RE = re.compile(r'^\s*(\S+?)\s*-->\s*([^\s]+)(?:\s+(.*))?$')


class SRTParser(SubtitleParser):
    def parse_text(self, content: str) -> SubtitleDocument:
        doc = SubtitleDocument(format=SubtitleFormat.SRT)
        normalized = (content or "").replace('\ufeff', '').replace('\r\n', '\n').replace('\r', '\n').strip()
        if not normalized:
            return doc

        blocks = re.split(r'\n[ \t]*\n+', normalized)
        fallback_idx = 1

        for block in blocks:
            lines = [ln.rstrip('\r') for ln in block.split('\n')]
            # Trim leading/trailing empty lines inside a block
            while lines and not lines[0].strip():
                lines.pop(0)
            while lines and not lines[-1].strip():
                lines.pop()
            if not lines:
                continue

            time_line_idx = -1
            idx = fallback_idx
            if len(lines) >= 2 and lines[0].strip().isdigit() and _SRT_TIME_LINE_RE.match(lines[1]):
                idx = int(lines[0].strip())
                time_line_idx = 1
            elif _SRT_TIME_LINE_RE.match(lines[0]):
                time_line_idx = 0

            if time_line_idx < 0:
                continue

            m = _SRT_TIME_LINE_RE.match(lines[time_line_idx])
            if not m:
                continue
            start = extract_timecode_token(m.group(1))
            end = extract_timecode_token(m.group(2))
            if parse_timecode_ms(start) is None or parse_timecode_ms(end) is None:
                continue

            raw_text = '\n'.join(lines[time_line_idx + 1:])
            clean_text = re.sub(r'<[^>]+>', '', raw_text)

            event = SubtitleEvent(
                id=idx,
                start=start,
                end=end,
                original_text=raw_text,
                text=clean_text,
                format_type=SubtitleFormat.SRT
            )
            doc.events.append(event)
            fallback_idx = max(fallback_idx + 1, idx + 1)
        return doc
