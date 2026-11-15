import logging
import re
from typing import List, Optional
from urllib.parse import quote_plus
import httpx
from app.anime.sources.base import BaseAnimeSource
from app.models.anime import MediaInfo, CharacterProfile, GenderEnum

logger = logging.getLogger(__name__)

class TVMazeSource(BaseAnimeSource):
    """TVMaze metadata source for TV series and miniseries (Free, public API, no key required)."""
    BASE_URL = "https://api.tvmaze.com"

    async def search_anime(self, query: str) -> List[MediaInfo]:
        """Search TV series using TVMaze."""
        return await self.search_shows(query)

    async def search_shows(self, query: str) -> List[MediaInfo]:
        """Search TV series and return MediaInfo list."""
        if not query or not query.strip():
            return []
        url = f"{self.BASE_URL}/search/shows?q={quote_plus(query.strip())}"
        try:
            client = await self.get_http_client()
            resp = await client.get(url)
            if resp.status_code != 200:
                return []
            items = resp.json()
            results = []
            for item in items:
                show = item.get("show", {})
                if not show:
                    continue
                premiered = show.get("premiered") or ""
                year = int(premiered[:4]) if len(premiered) >= 4 and premiered[:4].isdigit() else None
                image = show.get("image") or {}
                cover = image.get("medium") or image.get("original") or ""
                
                genres = show.get("genres") or []
                summary = show.get("summary") or ""
                clean_summary = re.sub(r'<.*?>', '', summary).strip()

                media = MediaInfo(
                    media_type="tv",
                    title=show.get("name") or "",
                    title_english=show.get("name") or "",
                    title_romaji=show.get("name") or "",
                    year=year,
                    format=show.get("type") or "Scripted",
                    status=show.get("status") or "",
                    cover_image_url=cover,
                    source_name="TVMaze",
                    source_id=str(show.get("id")),
                    overview=clean_summary,
                    genres=genres
                )
                results.append(media)
            return results
        except Exception as e:
            logger.warning(f"TVMaze search failed: {e}")
            return []

    async def get_characters(self, show_id: str) -> List[CharacterProfile]:
        """Get character and cast members with genders for a show ID."""
        url = f"{self.BASE_URL}/shows/{show_id}/cast"
        try:
            client = await self.get_http_client()
            resp = await client.get(url)
            if resp.status_code != 200:
                return []
            cast = resp.json()
            characters = []
            for entry in cast:
                char_obj = entry.get("character") or {}
                person_obj = entry.get("person") or {}
                
                char_name = char_obj.get("name") or ""
                actor_name = person_obj.get("name") or ""
                
                if not char_name and not actor_name:
                    continue
                
                canonical = char_name or actor_name
                aliases = [actor_name] if actor_name and actor_name != canonical else []
                
                gender_str = (person_obj.get("gender") or "").strip().lower()
                if gender_str == "male":
                    gender = GenderEnum.MALE
                elif gender_str == "female":
                    gender = GenderEnum.FEMALE
                else:
                    gender = GenderEnum.UNKNOWN
                    
                profile = CharacterProfile(
                    canonical_name=canonical,
                    gender=gender,
                    gender_source="TVMaze",
                    gender_confidence=0.95 if gender != GenderEnum.UNKNOWN else 0.0,
                    role="MAIN",
                    voice_actor=actor_name,
                    aliases=aliases,
                    description=f"Played by {actor_name}" if actor_name else ""
                )
                characters.append(profile)
            return characters
        except Exception as e:
            logger.warning(f"TVMaze get_characters failed: {e}")
            return []
