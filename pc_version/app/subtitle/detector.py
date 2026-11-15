import os
from app.models.subtitle import SubtitleFormat
from .exceptions import ParseError

def detect_format(file_path: str) -> SubtitleFormat:
    ext = os.path.splitext(file_path)[1].lower()
    video_exts = ('.mkv', '.mp4', '.avi', '.mov', '.flv', '.wmv', '.webm', '.ts', '.m4v', '.ogv')
    if ext in video_exts:
        raise ParseError(f"الملف المحدد ({ext}) هو ملف فيديو حاوٍ وليس ملف ترجمة نصي مباشر. يرجى استخراج الترجمة المدمجة منه أولاً.")

    mapping = {
        '.srt': SubtitleFormat.SRT,
        '.ass': SubtitleFormat.ASS,
        '.ssa': SubtitleFormat.SSA,
        '.vtt': SubtitleFormat.VTT,
        '.sbv': SubtitleFormat.SBV,
        '.txt': SubtitleFormat.TXT,
        '.json': SubtitleFormat.JSON,
    }
    if ext in mapping:
        return mapping[ext]
    
    # Fallback to content-based detection
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read(1024).lstrip()
            if content.startswith('[Script Info]'):
                return SubtitleFormat.ASS
            elif 'WEBVTT' in content:
                return SubtitleFormat.VTT
            elif '{' in content and '}' in content:
                return SubtitleFormat.JSON
    except Exception:
        pass

    raise ParseError(f"Unrecognized subtitle format for file: {file_path}")
