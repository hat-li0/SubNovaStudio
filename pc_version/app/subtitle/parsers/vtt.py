import re
from app.models.subtitle import SubtitleFormat, SubtitleDocument, SubtitleEvent
from app.subtitle.timecode import extract_timecode_token, parse_timecode_ms
from .base import SubtitleParser

_VTT_TIME_LINE_RE = re.compile(r'^\s*(\S+?)\s*-->\s*([^\s]+)(?:\s+(.*))?$')
_VTT_SKIP_HEADERS = ("WEBVTT", "STYLE", "REGION")


class VTTParser(SubtitleParser):
    def parse_text(self, content: str) -> SubtitleDocument:
        doc = SubtitleDocument(format=SubtitleFormat.VTT)
        normalized = (content or "").replace('\ufeff', '').replace('\r\n', '\n').replace('\r', '\n').strip()
        if not normalized:
            return doc

        blocks = re.split(r'\n[ \t]*\n+', normalized)
        idx = 1

        for block in blocks:
            lines = [ln.rstrip('\r') for ln in block.split('\n')]
            while lines and not lines[0].strip():
                lines.pop(0)
            while lines and not lines[-1].strip():
                lines.pop()
            if not lines:
                continue

            head = lines[0].strip()
            if head == "NOTE" or head.startswith(("NOTE ", "NOTE\t")):
                continue
            if any(head == h or head.startswith((f"{h} ", f"{h}\t", f"{h}-", f"{h}:")) for h in _VTT_SKIP_HEADERS):
                continue

            time_line_idx = -1
            for i, ln in enumerate(lines):
                if _VTT_TIME_LINE_RE.match(ln):
                    time_line_idx = i
                    break

            if time_line_idx < 0:
                continue

            m = _VTT_TIME_LINE_RE.match(lines[time_line_idx])
            if not m:
                continue
            start = extract_timecode_token(m.group(1))
            end = extract_timecode_token(m.group(2))
            if parse_timecode_ms(start) is None or parse_timecode_ms(end) is None:
                continue

            text_lines = lines[time_line_idx + 1:]
            text = '\n'.join(text_lines)
            clean_text = re.sub(r'<[^>]+>', '', text)
            doc.events.append(SubtitleEvent(
                id=idx,
                start=start,
                end=end,
                original_text=text,
                text=clean_text,
                format_type=SubtitleFormat.VTT
            ))
            idx += 1
        return doc
