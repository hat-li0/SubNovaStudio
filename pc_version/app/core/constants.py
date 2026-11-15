from typing import List, Dict

SUPPORTED_FORMATS: List[str] = ['srt', 'ass', 'ssa', 'vtt', 'sbv', 'txt', 'json']
DEFAULT_BATCH_SIZE: int = 15
MAX_EVENTS_PER_BATCH: int = 30
MAX_INPUT_TOKENS: int = 6000
DEFAULT_TEMPERATURE: float = 0.2
DEFAULT_CONTEXT_PREV: int = 4
DEFAULT_CONTEXT_NEXT: int = 3
ID_MIN_DIGITS: int = 3
MAX_RETRIES: int = 4
MAX_CONCURRENCY: int = 3
CACHE_TTL_SECONDS: int = 86400 * 7

# API rate limits
ANILIST_RATE_LIMIT_PER_MIN: int = 90
JIKAN_RATE_LIMIT_PER_SEC: int = 3

# Language codes dict
LANGUAGE_CODES: Dict[str, str] = {
    'en': 'English',
    'ja': 'Japanese',
    'fr': 'French',
    'de': 'German',
    'es': 'Spanish',
    'ko': 'Korean',
    'zh': 'Chinese',
    'it': 'Italian',
    'ru': 'Russian',
    'pt': 'Portuguese',
    'tr': 'Turkish',
    'ar': 'Arabic',
    'auto': 'Auto Detect',
}

SOURCE_LANGUAGES: List[str] = [
    "✨ كشف تلقائي للغة (Auto Detect)",
    "English (الإنجليزية)",
    "Japanese (اليابانية)",
    "French (الفرنسية)",
    "German (الألمانية)",
    "Spanish (الإسبانية)",
    "Korean (الكورية)",
    "Chinese (الصينية)",
    "Italian (الإيطالية)",
    "Russian (الروسية)",
    "Portuguese (البرتغالية)",
    "Turkish (التركية)",
]

TARGET_LANGUAGES: List[str] = [
    "Arabic (العربية الفصحى)",
    "English (الإنجليزية)",
]

# Gender enum values
GENDERS: List[str] = ['Male', 'Female', 'Non-binary', 'Unknown']

# Character match thresholds
CHARACTER_MATCH_THRESHOLD_HIGH: float = 0.85
CHARACTER_MATCH_THRESHOLD_LOW: float = 0.60
