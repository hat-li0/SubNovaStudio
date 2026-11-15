import re
from app.models.subtitle import SubtitleFormat, SubtitleDocument, SubtitleEvent, SubtitleStyle
from .base import SubtitleParser

class ASSParser(SubtitleParser):
    def parse_text(self, content: str) -> SubtitleDocument:
        doc = SubtitleDocument(format=SubtitleFormat.ASS)
        lines = content.splitlines()
        
        current_section = None
        format_order = []
        event_idx = 1
        
        for line in lines:
            line_str = line.strip()
            if not line_str:
                if current_section == "Script Info":
                    doc.raw_header_lines.append(line)
                continue
                
            if line_str.startswith('[') and line_str.endswith(']'):
                current_section = line_str[1:-1]
                if current_section.lower() == "script info":
                    doc.raw_header_lines.append(line)
                continue
                
            if current_section and current_section.lower() == "script info":
                if any(line_str.lower().startswith(k) for k in (
                    "last style storage:", "audio file:", "video file:", "video ar mode:",
                    "video aspect ratio:", "video zoom percent:", "scroll position:",
                    "active line:", "video position:"
                )):
                    continue
                doc.raw_header_lines.append(line)
                if ':' in line_str:
                    k, v = line_str.split(':', 1)
                    doc.script_info[k.strip()] = v.strip()
                    
            elif current_section and "styles" in current_section.lower():
                if line_str.startswith('Format:'):
                    pass
                elif line_str.startswith('Style:'):
                    style = SubtitleStyle(raw_line=line)
                    name_part = line_str.split(':', 1)[1]
                    parts = [p.strip() for p in name_part.split(',')]
                    if parts:
                        style.name = parts[0]
                    doc.styles.append(style)
                    
            elif current_section and "events" in current_section.lower():
                if line_str.startswith('Format:'):
                    format_str = line_str.split(':', 1)[1]
                    format_order = [f.strip().lower() for f in format_str.split(',')]
                elif line_str.startswith('Dialogue:') or line_str.startswith('Comment:'):
                    is_comment = line_str.startswith('Comment:')
                    data_str = line_str.split(':', 1)[1]
                    parts = data_str.split(',', len(format_order)-1)
                    
                    if len(parts) != len(format_order):
                        continue
                        
                    event_data = dict(zip(format_order, parts))
                    raw_text = event_data.get('text', '')
                    # Strip vector drawings {\p1}...{\p0} and any {...} tags/comments from clean_text while preserving raw_text
                    clean_text = re.sub(r'\{\\p[1-9]\}[^\\{]*\{\\p0\}', '', raw_text)
                    clean_text = re.sub(r'\{[^}]*\}', '', clean_text)
                    # Add spaces around \N and \n to prevent fusing with English words (e.g. \NI -> \N I)
                    clean_text = clean_text.replace('\\N', ' \\N ').replace('\\n', ' \\n ')
                    clean_text = re.sub(r'\s+', ' ', clean_text).strip()
                    
                    layer_s = event_data.get('layer', '0').strip()
                    ml_s = event_data.get('marginl', '0').strip()
                    mr_s = event_data.get('marginr', '0').strip()
                    mv_s = event_data.get('marginv', '0').strip()

                    event = SubtitleEvent(
                        id=event_idx,
                        layer=int(layer_s) if layer_s.isdigit() else 0,
                        start=event_data.get('start', '').strip(),
                        end=event_data.get('end', '').strip(),
                        style=event_data.get('style', 'Default').strip(),
                        speaker=event_data.get('name', '').strip(),
                        margin_l=int(ml_s) if ml_s.isdigit() else 0,
                        margin_r=int(mr_s) if mr_s.isdigit() else 0,
                        margin_v=int(mv_s) if mv_s.isdigit() else 0,
                        effect=event_data.get('effect', '').strip(),
                        original_text=raw_text,
                        text=clean_text,
                        is_comment=is_comment,
                        format_type=SubtitleFormat.ASS
                    )
                    doc.events.append(event)
                    event_idx += 1
                    
            elif current_section and current_section.lower() in ("fonts", "graphics"):
                if current_section not in doc.metadata:
                    doc.metadata[current_section] = []
                doc.metadata[current_section].append(line)
                
        return doc
