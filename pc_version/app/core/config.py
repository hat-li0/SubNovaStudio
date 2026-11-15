import json
from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from app.core.resources import get_app_data_dir, _is_dir_writable

APP_DATA_DIR = get_app_data_dir()
CONFIG_FILE_PATH = APP_DATA_DIR / "config.json"
DEFAULT_DB_PATH = str(APP_DATA_DIR / "subtitler.db")

class AppSettings(BaseSettings):
    """Application settings using pydantic-settings."""
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')
    
    provider_type: str = Field(default="lmstudio")
    provider_url: str = Field(default="http://localhost:1234/v1")
    model_name: str = Field(default="")
    
    # Provider-specific settings for persistent UI state
    lmstudio_url: str = Field(default="http://localhost:1234/v1")
    lmstudio_model: str = Field(default="")
    
    ollama_url: str = Field(default="http://localhost:11434")
    ollama_model: str = Field(default="")
    
    gemini_api_key: str = Field(default="")
    gemini_model: str = Field(default="gemini-2.5-flash")
    
    openai_api_key: str = Field(default="")
    openai_model: str = Field(default="gpt-4o-mini")
    
    custom_url: str = Field(default="https://api.openai.com/v1")
    custom_api_key: str = Field(default="")
    custom_model: str = Field(default="")
    
    tmdb_api_key: str = Field(default="")
    
    temperature: float = Field(default=0.1)
    top_p: float = Field(default=0.85)
    min_p: float = Field(default=0.05)
    repetition_penalty: float = Field(default=1.0)
    max_tokens: int = Field(default=2048)
    max_context: int = Field(default=4096)
    concurrency: int = Field(default=1)
    
    batch_size: int = Field(default=15)
    max_events_per_batch: int = Field(default=30)
    context_prev_lines: int = Field(default=4)
    context_next_lines: int = Field(default=3)
    
    source_lang: str = Field(default="✨ كشف تلقائي للغة (Auto Detect)")
    target_lang: str = Field(default="Arabic (العربية الفصحى)")

    # Smart Auto-Healing & Quality Settings
    auto_improve: bool = Field(default=False)
    enable_smart_healing: bool = Field(default=True)
    enable_arabic_punct: bool = Field(default=True)
    enable_latin_clean: bool = Field(default=True)
    enable_quote_fix: bool = Field(default=True)
    protect_tags: bool = Field(default=True)
    skip_visual_effects: bool = Field(default=True)
    translate_signs: bool = Field(default=False)
    separate_inline_effects: bool = Field(default=True)
    deduplicate_identical_lines: bool = Field(default=True)
    play_sound_on_finish: bool = Field(default=True)
    story_notes: str = Field(default="")
    
    db_path: str = Field(default=DEFAULT_DB_PATH)
    log_level: str = Field(default="INFO")

    def save_to_file(self, path: Optional[str | Path] = None) -> None:
        """Save current settings to a JSON file."""
        target = Path(path) if path is not None else CONFIG_FILE_PATH
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "w", encoding="utf-8") as f:
            f.write(self.model_dump_json(indent=4))

    @classmethod
    def load_from_file(cls, path: Optional[str | Path] = None) -> "AppSettings":
        """Load settings from a JSON file with automatic path healing."""
        p = Path(path) if path is not None else CONFIG_FILE_PATH
        settings_obj = None
        if p.exists():
            try:
                with open(p, "r", encoding="utf-8") as f:
                    data = json.load(f)
                settings_obj = cls(**data)
            except Exception:
                pass
        if settings_obj is None:
            settings_obj = cls()

        # Path validation and auto-healing:
        # If the saved db_path points to an unwritable directory or invalid path,
        # heal it to the verified writable APP_DATA_DIR / "subtitler.db"
        current_db = Path(settings_obj.db_path)
        if not _is_dir_writable(current_db.parent):
            settings_obj.db_path = str(get_app_data_dir() / "subtitler.db")

        return settings_obj

_settings_instance = None

def get_settings() -> AppSettings:
    """Returns a singleton instance of AppSettings."""
    global _settings_instance
    if _settings_instance is None:
        _settings_instance = AppSettings.load_from_file()
    return _settings_instance
