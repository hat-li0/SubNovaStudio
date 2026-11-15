import re

def normalize_line_endings(text: str) -> str:
    return text.replace('\r\n', '\n').replace('\r', '\n')

def strip_bom(text: str) -> str:
    if text.startswith('\ufeff'):
        return text[1:]
    return text

def normalize_whitespace(text: str) -> str:
    return re.sub(r'[ \t]+', ' ', text).strip()
