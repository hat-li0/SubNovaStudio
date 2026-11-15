import logging
from typing import List, Optional
from urllib.parse import quote_plus
import httpx
from app.anime.sources.base import BaseAnimeSource
from app.models.anime import MediaInfo, CharacterProfile, GenderEnum

logger = logging.getLogger(__name__)

# Common first names gender hint heuristic for actors when detailed bio isn't returned
COMMON_FEMALE_FIRSTNAMES = {
    "emily", "emma", "sarah", "jennifer", "scarlett", "natalie", "anne", "kate", "jessica",
    "margot", "florence", "zendaya", "anya", "ana", "gal", "elizabeth", "mary", "rachel",
    "sandra", "charlize", "zoe", "amy", "reese", "millie", "olivia", "halle", "cate", "meryl"
}
COMMON_MALE_FIRSTNAMES = {
    "cillian", "matt", "robert", "leonardo", "brad", "tom", "john", "michael", "david",
    "chris", "christian", "ryan", "george", "keanu", "samuel", "morgan", "harrison",
    "will", "denzel", "joaquin", "ben", "mark", "jake", "paul", "daniel", "hugh", "bruce"
}

class CinemetaSource(BaseAnimeSource):
    """Cinemeta metadata source for movies and series (Free, public Stremio API)."""
    BASE_URL = "https://v3-cinemeta.strem.io"

    async def search_anime(self, query: str) -> List[MediaInfo]:
        """Search movies and series via Cinemeta."""
        return await self.search_media(query)

    async def search_media(self, query: str, media_type: str = "movie") -> List[MediaInfo]:
        """Search movies or series using Cinemeta catalog."""
        if not query or not query.strip():
            return []
            
        clean_q = quote_plus(query.strip())
        results = []
        
        types_to_search = ["movie", "series"] if media_type == "all" else [media_type if media_type in ("movie", "series") else "movie"]
        
        client = await self.get_http_client()
        for m_type in types_to_search:
            url = f"{self.BASE_URL}/catalog/{m_type}/top/search={clean_q}.json"
            try:
                resp = await client.get(url)
                if resp.status_code != 200:
                    continue
                metas = resp.json().get("metas", [])
                for item in metas[:15]:
                    year_val = item.get("releaseInfo") or item.get("year")
                    year = int(str(year_val)[:4]) if year_val and str(year_val)[:4].isdigit() else None
                    
                    media = MediaInfo(
                        media_type="movie" if m_type == "movie" else "tv",
                        title=item.get("name") or "",
                        title_english=item.get("name") or "",
                        title_romaji=item.get("name") or "",
                        year=year,
                        format="Movie" if m_type == "movie" else "Series",
                        status="Released",
                        cover_image_url=item.get("poster") or "",
                        source_name="Cinemeta",
                        source_id=f"{m_type}:{item.get('id')}",
                        overview=item.get("description") or "",
                        genres=item.get("genres") or []
                    )
                    results.append(media)
            except Exception as e:
                logger.warning(f"Cinemeta search failed for {m_type}: {e}")
                    
        return results

    async def get_characters(self, source_id: str) -> List[CharacterProfile]:
        """Get cast list for movie or series from Cinemeta."""
        m_type = "movie"
        imdb_id = source_id
        if ":" in source_id:
            m_type, imdb_id = source_id.split(":", 1)
            
        url = f"{self.BASE_URL}/meta/{m_type}/{imdb_id}.json"
        try:
            client = await self.get_http_client()
            resp = await client.get(url)
            if resp.status_code != 200:
                return []
            meta = resp.json().get("meta", {})
            cast = meta.get("cast", []) or []
            
            characters = []
            for actor in cast:
                if not actor or not isinstance(actor, str):
                    continue
                actor_clean = actor.strip()
                first_name = actor_clean.split(" ")[0].lower() if " " in actor_clean else actor_clean.lower()
                
                gender = GenderEnum.UNKNOWN
                confidence = 0.0
                if first_name in COMMON_FEMALE_FIRSTNAMES:
                    gender = GenderEnum.FEMALE
                    confidence = 0.85
                elif first_name in COMMON_MALE_FIRSTNAMES:
                    gender = GenderEnum.MALE
                    confidence = 0.85
                    
                profile = CharacterProfile(
                    canonical_name=actor_clean,
                    first_name=actor_clean.split(" ")[0] if " " in actor_clean else actor_clean,
                    last_name=actor_clean.split(" ")[-1] if " " in actor_clean else "",
                    gender=gender,
                    gender_source="Cinemeta (Cast)",
                    gender_confidence=confidence,
                    role="MAIN",
                    voice_actor=actor_clean,
                    description=f"Cast member in {meta.get('name', 'Media')}"
                )
                characters.append(profile)
            return characters
        except Exception as e:
            logger.warning(f"Cinemeta get_characters failed: {e}")
            return []
