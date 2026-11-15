import re
from app.models.subtitle import SubtitleDocument
from app.subtitle.timecode import parse_timecode_ms, format_vtt_time
from app.subtitle.writers.base import SubtitleWriter


def _format_vtt_time(t_str: str) -> str:
    clean = (t_str or "").strip()
    if not clean:
        return "00:00:00.000"
    if re.match(r'^\d{2,}:\d{2}:\d{2}\.\d{3}$', clean):
        return clean
    ms = parse_timecode_ms(clean)
    if ms is not None:
        return format_vtt_time(ms)
    return "00:00:00.000"

def _ass_to_html_styles(text: str) -> str:
    """Converts ASS italic/bold tags (\\i1/\\i0, \\b1/\\b0) into balanced <i>/<b> WebVTT cues."""
    open_stack = []
    out = []
    pos = 0

    def _close_tag(tag_name: str):
        if tag_name not in open_stack:
            return
        reopen = []
        while open_stack:
            top = open_stack.pop()
            out.append(f"</{top}>")
            if top == tag_name:
                break
            reopen.append(top)
        for t in reversed(reopen):
            out.append(f"<{t}>")
            open_stack.append(t)

    def _open_tag(tag_name: str):
        if tag_name not in open_stack:
            out.append(f"<{tag_name}>")
            open_stack.append(tag_name)

    for m in re.finditer(r'\{\\([^}]*)\}', text):
        if m.start() > pos:
            out.append(text[pos:m.start()])
        body = "\\" + m.group(1)

        if re.search(r'\\r(?![a-zA-Z])', body):
            while open_stack:
                out.append(f"</{open_stack.pop()}>")

        i_matches = re.findall(r'\\i([01])(?![a-zA-Z0-9])', body)
        if i_matches:
            if i_matches[-1] == '1':
                _open_tag("i")
            else:
                _close_tag("i")

        b_matches = re.findall(r'\\b([01])(?![a-zA-Z0-9])', body)
        if b_matches:
            if b_matches[-1] == '1':
                _open_tag("b")
            else:
                _close_tag("b")

        pos = m.end()

    if pos < len(text):
        out.append(text[pos:])

    while open_stack:
        out.append(f"</{open_stack.pop()}>")

    result = "".join(out)
    return result.replace("<i></i>", "").replace("<b></b>", "")


def _clean_vtt_text(text: str) -> str:
    if not text:
        return ""
    cleaned = _ass_to_html_styles(text)
    cleaned = re.sub(r'\{\\[^}]*\}', '', cleaned)
    cleaned = cleaned.replace(r'\N', '\n').replace(r'\n', '\n')
    return cleaned.strip()

class VTTWriter(SubtitleWriter):
    """Writer for WebVTT subtitle format."""
    
    def write_text(self, document: SubtitleDocument) -> str:
        lines = ["WEBVTT", ""]
        for event in document.events:
            if getattr(event, "is_comment", False):
                continue
            start = _format_vtt_time(event.start_time)
            end = _format_vtt_time(event.end_time)
            lines.append(f"{start} --> {end}")
            text = event.translated_text if event.translated_text else event.original_text
            lines.append(_clean_vtt_text(text))
            lines.append("")
        return "\n".join(lines).strip() + "\n"
