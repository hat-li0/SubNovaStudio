import logging
from typing import List, Optional
from urllib.parse import quote_plus
import httpx
from app.anime.sources.base import BaseAnimeSource
from app.models.anime import MediaInfo, CharacterProfile, GenderEnum

logger = logging.getLogger(__name__)

class TMDBSource(BaseAnimeSource):
    """The Movie Database (TMDB) metadata provider for movies and TV shows."""
    BASE_URL = "https://api.themoviedb.org/3"
    IMAGE_BASE_URL = "https://image.tmdb.org/t/p/w500"

    def __init__(self, api_key: str = "", shared_client: Optional[httpx.AsyncClient] = None):
        super().__init__(shared_client=shared_client)
        self.api_key = api_key

    async def search_anime(self, query: str) -> List[MediaInfo]:
        """Search media using TMDB."""
        return await self.search_media(query)

    async def search_media(self, query: str, media_type: str = "all", api_key: Optional[str] = None) -> List[MediaInfo]:
        """Search movies and TV shows via TMDB multi-search."""
        key = api_key or self.api_key
        if not key or not query or not query.strip():
            return []

        clean_q = quote_plus(query.strip())
        endpoint = "search/multi"
        if media_type == "movie":
            endpoint = "search/movie"
        elif media_type in ("tv", "series"):
            endpoint = "search/tv"

        url = f"{self.BASE_URL}/{endpoint}?api_key={key}&query={clean_q}&include_adult=false"
        try:
            client = await self.get_http_client()
            resp = await client.get(url)
            if resp.status_code != 200:
                return []
            data = resp.json()
            results = []
            for item in data.get("results", [])[:15]:
                item_type = item.get("media_type") or media_type
                if item_type not in ("movie", "tv"):
                    if "title" in item:
                        item_type = "movie"
                    elif "name" in item:
                        item_type = "tv"
                    else:
                        continue

                title = item.get("title") or item.get("name") or ""
                date_val = item.get("release_date") or item.get("first_air_date") or ""
                year = int(date_val[:4]) if len(date_val) >= 4 and date_val[:4].isdigit() else None
                poster = f"{self.IMAGE_BASE_URL}{item.get('poster_path')}" if item.get("poster_path") else ""

                media = MediaInfo(
                    media_type="movie" if item_type == "movie" else "tv",
                    title=title,
                    title_english=title,
                    title_romaji=title,
                    year=year,
                    format="Movie" if item_type == "movie" else "TV",
                    status="Released",
                    cover_image_url=poster,
                    source_name="TMDB",
                    source_id=f"{item_type}:{item.get('id')}",
                    overview=item.get("overview") or "",
                    genres=[]
                )
                results.append(media)
            return results
        except Exception as e:
            logger.warning(f"TMDB search failed: {e}")
            return []

    async def get_characters(self, source_id: str, api_key: Optional[str] = None) -> List[CharacterProfile]:
        """Fetch cast and characters with genders from TMDB."""
        key = api_key or self.api_key
        if not key:
            return []

        item_type = "movie"
        tmdb_id = source_id
        if ":" in source_id:
            item_type, tmdb_id = source_id.split(":", 1)

        url = f"{self.BASE_URL}/{item_type}/{tmdb_id}/credits?api_key={key}"
        try:
            client = await self.get_http_client()
            resp = await client.get(url)
            if resp.status_code != 200:
                return []
            data = resp.json()
            cast = data.get("cast", [])
            characters = []
            for member in cast[:25]:
                char_name = (member.get("character") or "").strip()
                actor_name = (member.get("name") or "").strip()
                if not char_name and not actor_name:
                    continue

                canonical = char_name or actor_name
                aliases = [actor_name] if actor_name and actor_name != canonical else []

                # TMDB gender: 1=Female, 2=Male, 3=Non-binary, 0=Unknown
                g_code = member.get("gender", 0)
                if g_code == 1:
                    gender = GenderEnum.FEMALE
                    confidence = 0.98
                elif g_code == 2:
                    gender = GenderEnum.MALE
                    confidence = 0.98
                elif g_code == 3:
                    gender = GenderEnum.NON_BINARY
                    confidence = 0.95
                else:
                    gender = GenderEnum.UNKNOWN
                    confidence = 0.0

                profile = CharacterProfile(
                    canonical_name=canonical,
                    gender=gender,
                    gender_source="TMDB",
                    gender_confidence=confidence,
                    role="MAIN" if member.get("order", 99) < 8 else "SUPPORTING",
                    voice_actor=actor_name,
                    aliases=aliases,
                    description=f"Played by {actor_name}" if actor_name else ""
                )
                characters.append(profile)
            return characters
        except Exception as e:
            logger.warning(f"TMDB get_characters failed: {e}")
            return []
