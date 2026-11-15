from typing import List, Optional, Dict
from app.core.database import DatabaseManager
from app.models.anime import MediaInfo, CharacterProfile, GenderEnum


class CharacterRepository:
    """Repository for Anime and Character persistence (characters, aliases, anime, anime_sources)."""

    def __init__(self, db: DatabaseManager):
        self.db = db

    def save_anime(self, media: MediaInfo) -> int:
        """Upserts a MediaInfo record into anime and anime_sources tables and returns anime_id."""
        if not media:
            return -1

        existing_id: Optional[int] = None
        if media.source_name and media.source_id:
            src_row = self.db.fetch_one(
                "SELECT anime_id FROM anime_sources WHERE source_name = ? AND source_id = ? LIMIT 1",
                (media.source_name, str(media.source_id)),
            )
            if src_row:
                existing_id = src_row["anime_id"]

        if existing_id is None:
            cand_title = (media.title_romaji or media.title or media.title_english or "").strip()
            if cand_title:
                t_row = self.db.fetch_one(
                    "SELECT id FROM anime WHERE LOWER(TRIM(COALESCE(title_romaji, ''))) = LOWER(?) OR LOWER(TRIM(COALESCE(title_english, ''))) = LOWER(?) LIMIT 1",
                    (cand_title, cand_title),
                )
                if t_row:
                    existing_id = t_row["id"]

        t_romaji = media.title_romaji or media.title or ""
        t_english = media.title_english or media.title or ""
        t_native = media.title_native or ""
        t_user = media.title_user or ""

        if existing_id is not None:
            self.db.execute(
                """
                UPDATE anime
                SET title_romaji = COALESCE(NULLIF(?, ''), title_romaji),
                    title_english = COALESCE(NULLIF(?, ''), title_english),
                    title_native = COALESCE(NULLIF(?, ''), title_native),
                    title_user = COALESCE(NULLIF(?, ''), title_user),
                    episodes = COALESCE(?, episodes),
                    format = COALESCE(NULLIF(?, ''), format),
                    status = COALESCE(NULLIF(?, ''), status),
                    cover_image_url = COALESCE(NULLIF(?, ''), cover_image_url),
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    t_romaji, t_english, t_native, t_user,
                    media.episodes, media.format or "", media.status or "",
                    media.cover_image_url or "", existing_id,
                ),
            )
            anime_id = existing_id
        else:
            cursor = self.db.execute(
                """
                INSERT INTO anime (
                    title_romaji, title_english, title_native, title_user,
                    episodes, format, status, cover_image_url
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    t_romaji, t_english, t_native, t_user,
                    media.episodes, media.format or "", media.status or "",
                    media.cover_image_url or "",
                ),
            )
            anime_id = cursor.lastrowid

        if media.source_name and media.source_id and anime_id:
            existing_src = self.db.fetch_one(
                "SELECT id FROM anime_sources WHERE anime_id = ? AND source_name = ? LIMIT 1",
                (anime_id, media.source_name),
            )
            if existing_src:
                self.db.execute(
                    "UPDATE anime_sources SET source_id = ? WHERE id = ?",
                    (str(media.source_id), existing_src["id"]),
                )
            else:
                self.db.execute(
                    "INSERT INTO anime_sources (anime_id, source_name, source_id, source_url) VALUES (?, ?, ?, ?)",
                    (anime_id, media.source_name, str(media.source_id), ""),
                )

        media.id = anime_id
        return anime_id

    def get_anime_by_source(self, source_name: str, source_id: str) -> Optional[MediaInfo]:
        row = self.db.fetch_one(
            """
            SELECT a.*, s.source_name, s.source_id
            FROM anime a
            JOIN anime_sources s ON a.id = s.anime_id
            WHERE s.source_name = ? AND s.source_id = ?
            LIMIT 1
            """,
            (source_name, str(source_id)),
        )
        if not row:
            return None
        return MediaInfo(
            id=row["id"],
            title=row["title_romaji"] or row["title_english"] or "",
            title_romaji=row["title_romaji"] or "",
            title_english=row["title_english"] or "",
            title_native=row["title_native"] or "",
            title_user=row["title_user"] or "",
            episodes=row["episodes"],
            format=row["format"] or "",
            status=row["status"] or "",
            cover_image_url=row["cover_image_url"] or "",
            source_name=row["source_name"] or "",
            source_id=row["source_id"] or "",
        )

    def get_anime_by_id(self, anime_id: int) -> Optional[MediaInfo]:
        row = self.db.fetch_one("SELECT * FROM anime WHERE id = ?", (anime_id,))
        if not row:
            return None
        src_row = self.db.fetch_one(
            "SELECT source_name, source_id FROM anime_sources WHERE anime_id = ? ORDER BY id DESC LIMIT 1",
            (anime_id,),
        )
        return MediaInfo(
            id=row["id"],
            title=row["title_romaji"] or row["title_english"] or "",
            title_romaji=row["title_romaji"] or "",
            title_english=row["title_english"] or "",
            title_native=row["title_native"] or "",
            title_user=row["title_user"] or "",
            episodes=row["episodes"],
            format=row["format"] or "",
            status=row["status"] or "",
            cover_image_url=row["cover_image_url"] or "",
            source_name=src_row["source_name"] if src_row else "",
            source_id=src_row["source_id"] if src_row else "",
        )

    def save_character(self, profile: CharacterProfile) -> int:
        sql = """
            INSERT INTO characters (
                anime_id, canonical_name, first_name, last_name, native_name, 
                arabic_name, gender, gender_source, gender_confidence, role, 
                age, description, voice_actor, speech_style, translation_notes, is_user_override
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            profile.anime_id, profile.canonical_name, profile.first_name, profile.last_name,
            profile.native_name, profile.arabic_name, profile.gender.value,
            profile.gender_source, profile.gender_confidence, profile.role,
            profile.age, profile.description, profile.voice_actor,
            profile.speech_style, profile.translation_notes, int(profile.is_user_override)
        )
        cursor = self.db.execute(sql, params)
        char_id = cursor.lastrowid
        profile.id = char_id
        for alias in (profile.aliases or []):
            if alias and alias.strip():
                self.add_alias(char_id, alias.strip())
        return char_id

    def save_characters_for_anime(self, anime_id: int, characters: List[CharacterProfile]) -> List[CharacterProfile]:
        """Upserts all characters and aliases for a given anime_id, preserving user overrides."""
        existing_rows = self.db.fetch_all("SELECT * FROM characters WHERE anime_id = ?", (anime_id,))
        existing_by_name: Dict[str, object] = {}
        for row in existing_rows:
            cname = (row["canonical_name"] or "").strip().lower()
            if cname:
                existing_by_name[cname] = row

        for profile in characters:
            profile.anime_id = anime_id
            cname_key = (profile.canonical_name or "").strip().lower()
            existing = existing_by_name.get(cname_key) if cname_key else None
            if existing:
                char_id = existing["id"]
                profile.id = char_id
                if not bool(existing["is_user_override"]):
                    self.db.execute(
                        """
                        UPDATE characters
                        SET first_name = COALESCE(NULLIF(?, ''), first_name),
                            last_name = COALESCE(NULLIF(?, ''), last_name),
                            native_name = COALESCE(NULLIF(?, ''), native_name),
                            arabic_name = COALESCE(NULLIF(?, ''), arabic_name),
                            gender = CASE WHEN ? != 'UNKNOWN' THEN ? ELSE gender END,
                            gender_source = CASE WHEN ? != 'UNKNOWN' THEN ? ELSE gender_source END,
                            gender_confidence = CASE WHEN ? > gender_confidence THEN ? ELSE gender_confidence END,
                            role = COALESCE(NULLIF(?, ''), role),
                            age = COALESCE(NULLIF(?, ''), age),
                            description = COALESCE(NULLIF(?, ''), description),
                            voice_actor = COALESCE(NULLIF(?, ''), voice_actor),
                            speech_style = COALESCE(NULLIF(?, ''), speech_style),
                            translation_notes = COALESCE(NULLIF(?, ''), translation_notes),
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                        """,
                        (
                            profile.first_name, profile.last_name, profile.native_name,
                            profile.arabic_name, profile.gender.value, profile.gender.value,
                            profile.gender.value, profile.gender_source,
                            profile.gender_confidence, profile.gender_confidence,
                            profile.role, profile.age, profile.description, profile.voice_actor,
                            profile.speech_style, profile.translation_notes, char_id,
                        ),
                    )
                for alias in (profile.aliases or []):
                    if alias and alias.strip():
                        self.add_alias(char_id, alias.strip())
            else:
                self.save_character(profile)

        return characters

    def get_character_by_id(self, id: int) -> Optional[CharacterProfile]:
        sql = "SELECT * FROM characters WHERE id = ?"
        row = self.db.fetch_one(sql, (id,))
        if not row:
            return None
        alias_rows = self.db.fetch_all(
            "SELECT alias FROM character_aliases WHERE character_id = ?",
            (id,),
        )
        aliases = [ar["alias"] for ar in alias_rows if ar["alias"]]
        return self._map_row(row, aliases=aliases)

    def get_characters_for_anime(self, anime_id: int) -> List[CharacterProfile]:
        sql = "SELECT * FROM characters WHERE anime_id = ?"
        rows = self.db.fetch_all(sql, (anime_id,))
        if not rows:
            return []
        alias_rows = self.db.fetch_all(
            """
            SELECT ca.character_id, ca.alias
            FROM character_aliases ca
            JOIN characters c ON c.id = ca.character_id
            WHERE c.anime_id = ?
            """,
            (anime_id,),
        )
        aliases_map: Dict[int, List[str]] = {}
        for ar in alias_rows:
            if ar["alias"]:
                aliases_map.setdefault(ar["character_id"], []).append(ar["alias"])
        return [self._map_row(r, aliases=aliases_map.get(r["id"], [])) for r in rows]

    def add_alias(self, character_id: int, alias: str) -> None:
        clean_alias = (alias or "").strip()
        if not clean_alias:
            return
        existing = self.db.fetch_one(
            "SELECT id FROM character_aliases WHERE character_id = ? AND LOWER(alias) = LOWER(?) LIMIT 1",
            (character_id, clean_alias),
        )
        if existing:
            return
        sql = "INSERT INTO character_aliases (character_id, alias, alias_type) VALUES (?, ?, ?)"
        self.db.execute(sql, (character_id, clean_alias, "alternative"))

    def set_user_override(self, character_id: int, arabic_name: str, gender: GenderEnum, notes: str) -> None:
        sql = """
            UPDATE characters 
            SET arabic_name = ?, gender = ?, translation_notes = ?, is_user_override = 1 
            WHERE id = ?
        """
        self.db.execute(sql, (arabic_name, gender.value, notes, character_id))

    def _map_row(self, row, aliases: Optional[List[str]] = None) -> CharacterProfile:
        row_keys = set(row.keys()) if hasattr(row, "keys") else set()
        return CharacterProfile(
            id=row["id"],
            anime_id=row["anime_id"],
            canonical_name=row["canonical_name"] or "",
            first_name=row["first_name"] or "",
            last_name=row["last_name"] or "",
            native_name=row["native_name"] or "",
            arabic_name=row["arabic_name"] or "",
            aliases=list(aliases or []),
            gender=GenderEnum(row["gender"]) if row["gender"] else GenderEnum.UNKNOWN,
            gender_source=row["gender_source"] or "",
            gender_confidence=row["gender_confidence"] or 0.0,
            role=row["role"] or "",
            age=row["age"] or "",
            description=row["description"] or "",
            voice_actor=row["voice_actor"] or "",
            speech_style=(row["speech_style"] or "") if "speech_style" in row_keys else "",
            translation_notes=(row["translation_notes"] or "") if "translation_notes" in row_keys else "",
            is_user_override=bool(row["is_user_override"])
        )
