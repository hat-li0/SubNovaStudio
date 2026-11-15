class SubtitlerError(Exception):
    """Base exception for all GPTSubtitler errors."""
    pass

class ParseError(SubtitlerError):
    """Raised when parsing a subtitle file fails."""
    pass

class WriteError(SubtitlerError):
    """Raised when writing a subtitle file fails."""
    pass

class ProviderError(SubtitlerError):
    """Raised when an LLM provider returns an error."""
    pass

class ConnectionError(SubtitlerError):
    """Raised on network connection issues."""
    pass

class TranslationError(SubtitlerError):
    """Raised when translation fails."""
    pass

class ValidationError(SubtitlerError):
    """Raised on data validation issues."""
    pass

class CharacterResolutionError(SubtitlerError):
    """Raised when character resolution fails."""
    pass

class AnimeNotFoundError(SubtitlerError):
    """Raised when anime could not be found."""
    pass

class RateLimitError(SubtitlerError):
    """Raised when an API rate limit is exceeded."""
    pass

class CacheError(SubtitlerError):
    """Raised on cache related errors."""
    pass
