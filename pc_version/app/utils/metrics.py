import re

def timestamp_to_seconds(ts: str) -> float:
    """Converts subtitle timestamp (00:01:02.500 or 0:00:01.00) to seconds."""
    if not ts or not ts.strip():
        return 0.0

    clean_ts = ts.strip().replace(",", ".")
    parts = clean_ts.split(":")
    try:
        if len(parts) == 3:
            h, m, s = float(parts[0]), float(parts[1]), float(parts[2])
            return h * 3600.0 + m * 60.0 + s
        elif len(parts) == 2:
            m, s = float(parts[0]), float(parts[1])
            return m * 60.0 + s
    except Exception:
        pass
    return 0.0

def calculate_cps(text: str, start_ts: str, end_ts: str) -> float:
    """Calculates Characters Per Second (CPS) for subtitle reading speed."""
    if not text or not start_ts or not end_ts:
        return 0.0

    start_sec = timestamp_to_seconds(start_ts)
    end_sec = timestamp_to_seconds(end_ts)
    duration = end_sec - start_sec

    if duration <= 0.2:
        return 0.0

    clean_text = re.sub(r"\{[^}]*\}", "", text)
    clean_len = len(clean_text.strip().replace("\n", " ").replace("\\N", " "))
    return clean_len / duration

def format_line_length(text: str, max_chars: int = 42) -> str:
    """Wraps text so no individual line exceeds max_chars, breaking cleanly at spaces."""
    if not text or len(text) <= max_chars or "\n" in text or "\\N" in text:
        return text

    words = text.split()
    lines = []
    current_line = []
    current_len = 0

    for word in words:
        space_needed = 1 if current_line else 0
        if current_len + len(word) + space_needed <= max_chars:
            current_line.append(word)
            current_len += len(word) + space_needed
        else:
            if current_line:
                lines.append(" ".join(current_line))
            current_line = [word]
            current_len = len(word)

    if current_line:
        lines.append(" ".join(current_line))

    return "\\N".join(lines)
