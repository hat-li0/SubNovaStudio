import re
from typing import Optional

# Matches either H+:MM:SS([.,]frac)? OR MM:SS[.,]frac (WebVTT without hours)
_STRICT_HMS_RE = re.compile(r"^(\d+):(\d{1,2}):(\d{1,2})(?:[.,](\d+))?$")
_STRICT_MS_RE = re.compile(r"^(\d{1,2}):(\d{1,2})[.,](\d+)$")

# Matches leading timecode prefix inside cue lines (may be followed by cue settings)
_TOKEN_HMS_RE = re.compile(r"^(\d+:\d{1,2}:\d{1,2}(?:[.,]\d+)?)")
_TOKEN_MS_RE = re.compile(r"^(\d{1,2}:\d{1,2}[.,]\d+)")


def parse_timecode_ms(time_str: str) -> Optional[int]:
    """
    Strictly parses subtitle timecodes into integer milliseconds.

    Supported formats:
    - ASS / SSA: H:MM:SS.cc (e.g. '0:01:23.45')
    - SRT:       HH:MM:SS,mmm (or .mmm, with 1 to N fractional digits)
    - WebVTT:    HH:MM:SS.mmm or MM:SS.mmm (without hours)
    - Whole seconds: HH:MM:SS

    Returns None if the string is invalid, negative, or has out-of-range
    minutes (>= 60) or seconds (>= 60).
    """
    if not time_str or not isinstance(time_str, str):
        return None
    s = time_str.strip()
    if not s or s.startswith("-"):
        return None

    m_hms = _STRICT_HMS_RE.match(s)
    if m_hms:
        h_s, m_s, sec_s, frac_s = m_hms.groups()
        h = int(h_s)
        m = int(m_s)
        sec = int(sec_s)
    else:
        m_ms = _STRICT_MS_RE.match(s)
        if not m_ms:
            return None
        m_s, sec_s, frac_s = m_ms.groups()
        h = 0
        m = int(m_s)
        sec = int(sec_s)

    if m >= 60 or sec >= 60:
        return None

    frac_ms = 0
    if frac_s:
        # Handle arbitrary precision fractional digits cleanly (1 to N digits)
        # using exact integer arithmetic with half-up millisecond rounding.
        denom = 10 ** len(frac_s)
        frac_ms = (int(frac_s) * 1000 + denom // 2) // denom

    return (h * 3600 + m * 60 + sec) * 1000 + frac_ms


def parse_timecode_ms_safe(time_str: str, default: int = 0) -> int:
    """Parses a timecode to milliseconds, returning `default` if invalid."""
    val = parse_timecode_ms(time_str)
    return val if val is not None else default


def is_valid_timecode(time_str: str) -> bool:
    """Returns True if `time_str` is a valid subtitle timecode."""
    return parse_timecode_ms(time_str) is not None


def extract_timecode_token(raw_token: str) -> str:
    """
    Extracts the leading timecode substring from a cue field that may have
    trailing SRT coordinates (X1:...) or WebVTT cue settings (align:start line:90%).
    """
    if not raw_token:
        return ""
    s = raw_token.strip().split()[0]
    m = _TOKEN_HMS_RE.match(s) or _TOKEN_MS_RE.match(s)
    return m.group(1) if m else s


def format_ass_time(ms: int) -> str:
    """Formats milliseconds to strict ASS timestamp: H:MM:SS.cc (rounded centiseconds)."""
    ms = max(0, int(ms))
    total_cs = (ms + 5) // 10
    cs = total_cs % 100
    total_sec = total_cs // 100
    h = total_sec // 3600
    m = (total_sec % 3600) // 60
    s = total_sec % 60
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def format_srt_time(ms: int) -> str:
    """Formats milliseconds to strict SRT timestamp: HH:MM:SS,mmm."""
    ms = max(0, int(ms))
    rem_ms = ms % 1000
    total_sec = ms // 1000
    h = total_sec // 3600
    m = (total_sec % 3600) // 60
    s = total_sec % 60
    return f"{h:02d}:{m:02d}:{s:02d},{rem_ms:03d}"


def format_vtt_time(ms: int) -> str:
    """Formats milliseconds to strict WebVTT timestamp: HH:MM:SS.mmm."""
    ms = max(0, int(ms))
    rem_ms = ms % 1000
    total_sec = ms // 1000
    h = total_sec // 3600
    m = (total_sec % 3600) // 60
    s = total_sec % 60
    return f"{h:02d}:{m:02d}:{s:02d}.{rem_ms:03d}"


def detect_timecode_style(template_str: str, fallback_fmt: Optional[str] = None) -> str:
    """Detects whether a template timecode is 'srt', 'vtt', or 'ass'."""
    t = (template_str or "").strip()
    fb = (fallback_fmt or "").strip().lower()
    if "," in t:
        return "srt"
    # SubtitleEvent initializes unpopulated times to '00:00:00.00'; defer to explicit container fallback format
    if t == "00:00:00.00" and fb in ("srt", "vtt", "ass"):
        return fb
    if "." in t:
        # VTT uses HH:MM:SS.mmm (3+ fractional digits) or MM:SS.mmm; ASS uses .cc (1-2 digits)
        if re.search(r"\.\d{3,}$", t) or _STRICT_MS_RE.match(t):
            return "vtt"
        return "ass"
    if fb in ("srt", "vtt", "ass"):
        return fb
    return "ass"


def format_timecode(
    ms: int,
    template_str: str = "",
    fmt: Optional[str] = None,
    force_fmt: bool = False,
) -> str:
    """
    Formats milliseconds while preserving the timecode precision/style of `template_str`
    when available, falling back to `fmt` ('srt', 'vtt', 'ass').
    Set `force_fmt=True` to unconditionally convert to `fmt`.
    """
    fmt_clean = (fmt or "").strip().lower()
    if force_fmt and fmt_clean in ("srt", "vtt", "ass"):
        target = fmt_clean
    else:
        target = detect_timecode_style(template_str, fallback_fmt=fmt_clean)

    if target == "srt":
        return format_srt_time(ms)
    elif target == "vtt":
        return format_vtt_time(ms)
    return format_ass_time(ms)


def normalize_timecode(
    time_str: str,
    template_str: str = "",
    fmt: Optional[str] = None,
    force_fmt: bool = False,
) -> Optional[str]:
    """
    Validates and normalizes a timecode string while preserving style from `template_str`
    (or `time_str` itself if `template_str` is empty), or returns None if invalid.
    """
    ms = parse_timecode_ms(time_str)
    if ms is None:
        return None
    has_real_template = bool(template_str and template_str != "00:00:00.00" and ("," in template_str or "." in template_str))
    if has_real_template:
        ref = template_str
    elif fmt:
        ref = ""
    else:
        ref = time_str
    return format_timecode(ms, template_str=ref, fmt=fmt, force_fmt=force_fmt)
