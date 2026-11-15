import hashlib
from typing import Optional
from app.core.database import DatabaseManager

class TranslationMemoryRepository:
    """Repository for Translation Memory data."""
    
    def __init__(self, db: DatabaseManager):
        self.db = db
        
    def _hash_text(self, text: str) -> str:
        return hashlib.sha256(text.encode('utf-8')).hexdigest()

    def save_translation(
        self, 
        source_text: str, 
        translated_text: str, 
        source_lang: str, 
        target_lang: str, 
        anime_id: Optional[int] = None, 
        character_id: Optional[int] = None, 
        provider: str = "", 
        model: str = "",
        speaker: str = "",
        speaker_gender: str = ""
    ) -> int:
        source_hash = self._hash_text(source_text)
        clean_speaker = (speaker or "").strip()
        clean_gender = (speaker_gender or "").strip().upper()
        
        sql = """
            INSERT INTO translation_memory (
                source_hash, source_text, translated_text, source_lang, 
                target_lang, anime_id, character_id, speaker, speaker_gender, provider, model
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            source_hash, source_text, translated_text, source_lang,
            target_lang, anime_id, character_id, clean_speaker, clean_gender, provider, model
        )
        
        try:
            cursor = self.db.execute(sql, params)
            return cursor.lastrowid
        except Exception:
            # Handle potential unique constraints or db locks in a real app
            return -1

    def lookup(
        self,
        source_text: str,
        source_lang: str,
        target_lang: str,
        speaker: str = "",
        speaker_gender: str = ""
    ) -> Optional[str]:
        """
        Look up a translation using SHA-256 hash of the source text.
        Short ambiguous phrases (< 4 words) are only returned if both speaker and gender match.
        """
        if not self.db or not source_text:
            return None

        source_hash = self._hash_text(source_text)
        word_count = len(source_text.strip().split())

        if word_count >= 4:
            sql = """
                SELECT translated_text FROM translation_memory 
                WHERE source_hash = ? AND source_lang = ? AND target_lang = ?
                ORDER BY id DESC, created_at DESC LIMIT 1
            """
            row = self.db.fetch_one(sql, (source_hash, source_lang, target_lang))
            return row["translated_text"] if row else None

        clean_speaker = (speaker or "").strip()
        clean_gender = (speaker_gender or "").strip().upper()
        if not clean_speaker:
            # Never blindly reuse ambiguous short phrases (< 4 words) without a matching speaker
            return None

        sql = """
            SELECT translated_text FROM translation_memory 
            WHERE source_hash = ? AND source_lang = ? AND target_lang = ?
              AND LOWER(TRIM(COALESCE(speaker, ''))) = LOWER(?)
              AND UPPER(TRIM(COALESCE(speaker_gender, ''))) = UPPER(?)
            ORDER BY id DESC, created_at DESC LIMIT 1
        """
        row = self.db.fetch_one(
            sql,
            (source_hash, source_lang, target_lang, clean_speaker, clean_gender or "UNKNOWN")
        )
        if row:
            return row["translated_text"]
        return None
