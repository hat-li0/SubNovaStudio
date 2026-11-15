from typing import List, Optional
import re
from app.core.database import DatabaseManager
from app.models.anime import GlossaryEntry
from app.models.subtitle import SubtitleEvent

class GlossaryRepository:
    """Repository for Glossary data."""
    
    def __init__(self, db: DatabaseManager):
        self.db = db
        
    def add_entry(self, entry: GlossaryEntry) -> int:
        sql = """
            INSERT INTO glossary (anime_id, source_term, target_term, is_exact_match, is_case_sensitive, notes)
            VALUES (?, ?, ?, ?, ?, ?)
        """
        params = (
            entry.anime_id, entry.source_term, entry.target_term,
            int(entry.is_exact_match), int(entry.is_case_sensitive), entry.notes
        )
        cursor = self.db.execute(sql, params)
        return cursor.lastrowid

    def get_all_for_anime(self, anime_id: Optional[int]) -> List[GlossaryEntry]:
        if anime_id is None:
            sql = "SELECT * FROM glossary WHERE anime_id IS NULL ORDER BY id ASC"
            rows = self.db.fetch_all(sql)
        else:
            sql = "SELECT * FROM glossary WHERE anime_id = ? ORDER BY id ASC"
            rows = self.db.fetch_all(sql, (anime_id,))
        return [self._map_row(r) for r in rows]

    def replace_entries_for_anime(
        self,
        anime_id: Optional[int],
        entries: List[GlossaryEntry],
    ) -> List[GlossaryEntry]:
        """Atomically replaces all glossary entries for a given anime_id (or global when None)."""
        saved: List[GlossaryEntry] = []
        with self.db.get_connection() as conn:
            if anime_id is None:
                conn.execute("DELETE FROM glossary WHERE anime_id IS NULL")
            else:
                conn.execute("DELETE FROM glossary WHERE anime_id = ?", (anime_id,))

            for entry in entries:
                src = (getattr(entry, "source_term", "") or "").strip()
                tgt = (getattr(entry, "target_term", "") or "").strip()
                if not src or not tgt:
                    continue
                is_exact = bool(getattr(entry, "is_exact_match", True))
                is_case = bool(getattr(entry, "is_case_sensitive", False))
                notes = getattr(entry, "notes", "") or ""
                cur = conn.execute(
                    """
                    INSERT INTO glossary (anime_id, source_term, target_term, is_exact_match, is_case_sensitive, notes)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (anime_id, src, tgt, int(is_exact), int(is_case), notes),
                )
                saved.append(
                    GlossaryEntry(
                        id=cur.lastrowid,
                        anime_id=anime_id,
                        source_term=src,
                        target_term=tgt,
                        is_exact_match=is_exact,
                        is_case_sensitive=is_case,
                        notes=notes,
                    )
                )
        return saved

    def _map_row(self, row) -> GlossaryEntry:
        return GlossaryEntry(
            id=row["id"],
            anime_id=row["anime_id"],
            source_term=row["source_term"],
            target_term=row["target_term"],
            is_exact_match=bool(row["is_exact_match"]),
            is_case_sensitive=bool(row["is_case_sensitive"]),
            notes=row["notes"] or ""
        )

    def get_batch_glossary(self, anime_id: Optional[int], batch_events: List[SubtitleEvent]) -> List[GlossaryEntry]:
        """Extract only glossary terms that actually appear in the text of the batch events."""
        all_entries = self.get_all_for_anime(anime_id)
        if not all_entries:
            return []
            
        combined_text = " ".join(e.get_clean_text() for e in batch_events)
        combined_text_lower = combined_text.lower()
        
        matched_entries = []
        for entry in all_entries:
            term = entry.source_term
            if entry.is_case_sensitive:
                if entry.is_exact_match:
                    pattern = r'\b' + re.escape(term) + r'\b'
                    if re.search(pattern, combined_text):
                        matched_entries.append(entry)
                else:
                    if term in combined_text:
                        matched_entries.append(entry)
            else:
                term_lower = term.lower()
                if entry.is_exact_match:
                    pattern = r'\b' + re.escape(term_lower) + r'\b'
                    if re.search(pattern, combined_text_lower):
                        matched_entries.append(entry)
                else:
                    if term_lower in combined_text_lower:
                        matched_entries.append(entry)
                        
        return matched_entries
