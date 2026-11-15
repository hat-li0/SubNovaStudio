import os
from typing import Union
from app.models.subtitle import SubtitleDocument, SubtitleFormat
from .detector import detect_format
from .exceptions import ParseError
from .parsers.srt import SRTParser
from .parsers.ass import ASSParser
from .parsers.vtt import VTTParser
from .parsers.sbv import SBVParser
from .parsers.txt import TXTParser
from .parsers.json_sub import JSONParser

from .writers.srt import SRTWriter
from .writers.ass import ASSWriter
from .writers.vtt import VTTWriter
from .writers.sbv import SBVWriter
from .writers.txt import TXTWriter
from .writers.json_sub import JSONWriter
from .video_extractor import VideoSubtitleExtractor, SubtitleStreamInfo, VIDEO_EXTENSIONS

PARSER_MAP = {
    SubtitleFormat.SRT: SRTParser,
    SubtitleFormat.ASS: ASSParser,
    SubtitleFormat.SSA: ASSParser,
    SubtitleFormat.VTT: VTTParser,
    SubtitleFormat.SBV: SBVParser,
    SubtitleFormat.TXT: TXTParser,
    SubtitleFormat.JSON: JSONParser,
}

WRITER_MAP = {
    SubtitleFormat.SRT: SRTWriter,
    SubtitleFormat.ASS: ASSWriter,
    SubtitleFormat.SSA: ASSWriter,
    SubtitleFormat.VTT: VTTWriter,
    SubtitleFormat.SBV: SBVWriter,
    SubtitleFormat.TXT: TXTWriter,
    SubtitleFormat.JSON: JSONWriter,
}


def parse_subtitle(file_path: str, separate_effects: bool = False) -> SubtitleDocument:
    """Detects format and parses subtitle file into SubtitleDocument. If separate_effects is True, separates mixed effect-dialogue lines."""
    fmt = detect_format(file_path)
    
    # Handle string or enum
    if isinstance(fmt, str):
        try:
            fmt_enum = SubtitleFormat(fmt.lower())
        except ValueError:
            fmt_enum = SubtitleFormat.SRT
    else:
        fmt_enum = fmt

    parser_cls = PARSER_MAP.get(fmt_enum, SRTParser)
    parser = parser_cls()
    doc = parser.parse(file_path)
    if separate_effects:
        from app.subtitle.effect_separator import EffectSeparator
        doc = EffectSeparator.separate_document(doc)
    return doc


def write_subtitle(document: SubtitleDocument, file_path: str) -> None:
    """Writes SubtitleDocument to file using the appropriate writer based on destination extension or doc format."""
    from app.quality.healer import SubtitleHealer
    if hasattr(document, 'events') and document.events:
        meta = getattr(document, 'metadata', None) or {}
        target_lang = meta.get("target_lang", "ar")
        speakers = document.get_speakers() if hasattr(document, "get_speakers") else set()
        known_names = set(speakers) | set(meta.get("known_names") or ())
        heal_opts = {"target_lang": target_lang}
        for event in document.events:
            if event.translated_text:
                event.translated_text = SubtitleHealer.heal(
                    event.translated_text,
                    event.original_text,
                    options=heal_opts,
                    known_names=known_names,
                )

    # Ensure destination directory exists before writing
    dest_dir = os.path.dirname(os.path.abspath(file_path))
    if dest_dir:
        os.makedirs(dest_dir, exist_ok=True)

    try:
        fmt = detect_format(file_path)
    except Exception:
        fmt = getattr(document, 'format', SubtitleFormat.SRT)

    if isinstance(fmt, str):
        try:
            fmt_enum = SubtitleFormat(fmt.lower())
        except ValueError:
            fmt_enum = SubtitleFormat.SRT
    else:
        fmt_enum = fmt

    writer_cls = WRITER_MAP.get(fmt_enum, SRTWriter)
    writer = writer_cls()
    writer.write(document, file_path)
