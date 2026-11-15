import re
from app.models.subtitle import SubtitleDocument
from app.subtitle.timecode import parse_timecode_ms, format_ass_time
from app.subtitle.writers.base import SubtitleWriter
from app.quality.healer import SubtitleHealer


def _safe_ass_time(t_str: str) -> str:
    clean = (t_str or "").strip()
    if re.match(r'^\d+:\d{2}:\d{2}\.\d{2}$', clean):
        return clean
    ms = parse_timecode_ms(clean)
    if ms is not None:
        return format_ass_time(ms)
    return "0:00:00.00"


class ASSWriter(SubtitleWriter):
    """Writer for ASS subtitle format with perfect preservation."""
    
    def write_text(self, document: SubtitleDocument) -> str:
        lines = []
        
        # 1. Script Info
        if document.raw_header_lines:
            lines.extend(document.raw_header_lines)
            
        # 2. Styles
        if document.styles:
            lines.append("")
            lines.append("[V4+ Styles]")
            lines.append("Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding")
            for style in document.styles:
                lines.append(style.raw_line)
                
        # 3. Fonts
        if "Fonts" in document.metadata:
            lines.append("")
            lines.append("[Fonts]")
            lines.extend(document.metadata["Fonts"])
            
        # 4. Graphics
        if "Graphics" in document.metadata:
            lines.append("")
            lines.append("[Graphics]")
            lines.extend(document.metadata["Graphics"])
            
        # 5. Events
        lines.append("")
        lines.append("[Events]")
        lines.append("Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text")
        
        for event in document.events:
            event_type = "Comment" if event.is_comment else "Dialogue"
            if event.translated_text:
                text = event.rebuild_text(event.translated_text)
                if not event.is_comment:
                    text = SubtitleHealer.ensure_rtl_bidi(text)
            else:
                text = event.original_text
            # ASS Event Text cannot contain raw physical newlines
            safe_text = (text or "").replace("\r\n", "\\N").replace("\r", "\\N").replace("\n", "\\N")
            safe_start = _safe_ass_time(event.start_time)
            safe_end = _safe_ass_time(event.end_time)
            safe_style = (event.style or "Default").replace(",", ";").replace("\n", " ")
            safe_speaker = (event.speaker or "").replace(",", ";").replace("\n", " ")
            safe_effect = (event.effect or "").replace(",", ";").replace("\n", " ")
            line = f"{event_type}: {event.layer},{safe_start},{safe_end},{safe_style},{safe_speaker},{event.margin_l},{event.margin_r},{event.margin_v},{safe_effect},{safe_text}"
            lines.append(line)
            
        return "\n".join(lines) + "\n"
