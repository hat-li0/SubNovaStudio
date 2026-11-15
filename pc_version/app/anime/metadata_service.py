import logging
import asyncio
from typing import Tuple, List, Optional
import httpx
from app.anime.identifier import MediaIdentifier, AnimeIdentifier
from app.anime.sources.base import create_shared_http_client
from app.anime.sources.anilist import AniListSource
from app.anime.sources.jikan import JikanSource
from app.anime.sources.kitsu import KitsuSource
from app.anime.sources.tvmaze import TVMazeSource
from app.anime.sources.cinemeta import CinemetaSource
from app.anime.sources.tmdb import TMDBSource
from app.character.database import CharacterRepository
from app.models.anime import MediaInfo, AnimeInfo, CharacterProfile
from app.core.database import DatabaseManager
from app.core.config import get_settings

logger = logging.getLogger(__name__)


class MediaMetadataService:
    """Service orchestrating anime, movie, and TV show metadata retrieval across all sources."""

    def __init__(self, db: DatabaseManager):
        self.db = db
        self.identifier = MediaIdentifier()
        self._shared_client: Optional[httpx.AsyncClient] = None
        self._client_loop_id: Optional[int] = None
        self.char_repo = CharacterRepository(db)

        self.anilist = AniListSource()
        self.jikan = JikanSource()
        self.kitsu = KitsuSource()
        self.tvmaze = TVMazeSource()
        self.cinemeta = CinemetaSource()

        settings = get_settings()
        tmdb_key = getattr(settings, "tmdb_api_key", "")
        self.tmdb = TMDBSource(api_key=tmdb_key)

    def _sources(self):
        return (self.anilist, self.jikan, self.kitsu, self.tvmaze, self.cinemeta, self.tmdb)

    def _ensure_shared_client(self) -> httpx.AsyncClient:
        """Creates or reuses a single persistent HTTP/2-capable client across all metadata sources."""
        try:
            cur_loop_id = id(asyncio.get_running_loop())
        except RuntimeError:
            cur_loop_id = None

        if (
            self._shared_client is None
            or getattr(self._shared_client, "is_closed", False)
            or self._client_loop_id != cur_loop_id
        ):
            self._shared_client = create_shared_http_client()
            self._client_loop_id = cur_loop_id
            for src in self._sources():
                src.set_shared_client(self._shared_client)
        return self._shared_client

    async def aclose(self) -> None:
        """Closes the shared HTTP connection pool cleanly."""
        if self._shared_client is not None:
            try:
                if not getattr(self._shared_client, "is_closed", False):
                    await self._shared_client.aclose()
            except Exception:
                pass
            self._shared_client = None
            self._client_loop_id = None
            for src in self._sources():
                src.set_shared_client(None)

    def persist_media_and_characters(
        self,
        media: Optional[MediaInfo],
        characters: List[CharacterProfile],
    ) -> Tuple[Optional[MediaInfo], List[CharacterProfile]]:
        """Persists resolved media & characters into relational SQLite tables (anime, anime_sources, characters, character_aliases)."""
        if not media or not self.db:
            return media, characters
        try:
            anime_id = self.char_repo.save_anime(media)
            if anime_id and anime_id > 0 and characters:
                self.char_repo.save_characters_for_anime(anime_id, characters)
        except Exception as ex:
            logger.debug(f"Could not persist media/characters to DB tables: {ex}")
        return media, characters

    async def resolve_media_and_characters(
        self, file_path: str, user_title: Optional[str] = None
    ) -> Tuple[Optional[MediaInfo], List[CharacterProfile]]:
        """Identify media title and type from filename and resolve characters."""
        self._ensure_shared_client()

        info = self.identifier.identify_media_info(file_path)
        search_title = user_title.strip() if user_title else info["title"]
        media_type = info["media_type"]

        if not search_title:
            return None, []

        # Check database cache first
        cache_key = f"media_meta_{search_title.lower().strip()}"
        try:
            cached = self.db.get_cache(cache_key)
            if cached and isinstance(cached, dict):
                media_data = cached.get("anime") or cached.get("media")
                chars_data = cached.get("characters", [])
                cached_media = MediaInfo(**media_data) if media_data else None
                cached_chars = [CharacterProfile(**c) for c in chars_data]
                if cached_media and cached_chars:
                    if cached_media.id is None:
                        self.persist_media_and_characters(cached_media, cached_chars)
                    else:
                        try:
                            db_chars = self.char_repo.get_characters_for_anime(cached_media.id)
                            if db_chars:
                                cached_chars = db_chars
                        except Exception:
                            pass
                    logger.info(f"Loaded media metadata from local DB cache for: {search_title}")
                    return cached_media, cached_chars
        except Exception as ex:
            logger.debug(f"Cache lookup failed: {ex}")

        # Determine source priority based on media type
        sources_to_try = []
        if media_type == "tv":
            sources_to_try = [self.tvmaze]
            if self.tmdb.api_key:
                sources_to_try.append(self.tmdb)
            sources_to_try.extend([self.cinemeta, self.anilist, self.jikan])
        elif media_type == "movie":
            if self.tmdb.api_key:
                sources_to_try.append(self.tmdb)
            sources_to_try.extend([self.cinemeta, self.tvmaze, self.anilist])
        elif media_type == "anime":
            sources_to_try = [self.anilist, self.jikan, self.kitsu, self.tvmaze, self.cinemeta]
        else:  # unknown
            sources_to_try = [self.anilist, self.tvmaze, self.cinemeta]
            if self.tmdb.api_key:
                sources_to_try.append(self.tmdb)
            sources_to_try.extend([self.jikan, self.kitsu])

        media: Optional[MediaInfo] = None
        characters: List[CharacterProfile] = []

        for source in sources_to_try:
            try:
                results = await source.search_anime(search_title)
                if results:
                    candidate = results[0]
                    chars = await source.get_characters(candidate.source_id)
                    if chars:
                        media = candidate
                        characters = chars
                        break
                    elif not media:
                        media = candidate
            except Exception as e:
                logger.debug(f"Source {source.__class__.__name__} failed for {search_title}: {e}")

        # Persist to relational DB tables & api_cache on success
        if media:
            self.persist_media_and_characters(media, characters)

        if media and characters:
            try:
                self.db.set_cache(
                    cache_key,
                    {
                        "media": media.model_dump(),
                        "anime": media.model_dump(),
                        "characters": [c.model_dump() for c in characters]
                    },
                    source="MediaMetadataService",
                    ttl_seconds=86400 * 14
                )
            except Exception as ex:
                logger.debug(f"Failed to cache media metadata: {ex}")

        return media, characters

    # Backward compatibility
    resolve_anime_and_characters = resolve_media_and_characters

    async def search_multiple_media(
        self, search_title: str, filter_type: str = "all"
    ) -> List[MediaInfo]:
        """Search across providers for movies, TV series, and anime."""
        self._ensure_shared_client()
        if not search_title or not search_title.strip():
            return []

        results: List[MediaInfo] = []
        clean_title = search_title.strip()
        tasks = []

        # Update TMDB api key dynamically from settings
        settings = get_settings()
        self.tmdb.api_key = getattr(settings, "tmdb_api_key", "")

        if filter_type in ("all", "tv"):
            tasks.append(self.tvmaze.search_shows(clean_title))
        if filter_type in ("all", "movie", "tv"):
            tasks.append(self.cinemeta.search_media(clean_title, media_type="all" if filter_type == "all" else filter_type))
            if self.tmdb.api_key:
                tasks.append(self.tmdb.search_media(clean_title, media_type="all" if filter_type == "all" else filter_type))
        if filter_type in ("all", "anime"):
            tasks.append(self.anilist.search_anime(clean_title))

        gathered = await asyncio.gather(*tasks, return_exceptions=True)
        seen_keys = set()

        for res in gathered:
            if isinstance(res, list):
                for item in res:
                    key = (item.title.lower().strip(), item.year, item.format.lower())
                    if key not in seen_keys:
                        seen_keys.add(key)
                        results.append(item)

        return results

    # Backward compatibility
    search_multiple_anime = search_multiple_media

    async def get_characters_for_media(self, media: MediaInfo) -> List[CharacterProfile]:
        """Get characters for a specific media based on its source."""
        self._ensure_shared_client()
        try:
            chars: List[CharacterProfile] = []
            if media.source_name == "TVMaze":
                chars = await self.tvmaze.get_characters(media.source_id)
            elif media.source_name == "Cinemeta":
                chars = await self.cinemeta.get_characters(media.source_id)
            elif media.source_name == "TMDB":
                chars = await self.tmdb.get_characters(media.source_id)
            elif media.source_name == "AniList":
                chars = await self.anilist.get_characters(media.source_id)
            elif media.source_name == "Jikan":
                chars = await self.jikan.get_characters(media.source_id)
            elif media.source_name == "Kitsu":
                chars = await self.kitsu.get_characters(media.source_id)

            if chars:
                self.persist_media_and_characters(media, chars)
            return chars
        except Exception as e:
            logger.error(f"Failed to fetch characters from {media.source_name}: {e}")
        return []

    # Backward compatibility
    get_characters_for_anime = get_characters_for_media


# Backward compatibility alias
AnimeMetadataService = MediaMetadataService
