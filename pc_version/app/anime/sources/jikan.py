import re
import asyncio
from typing import List, Tuple
from app.models.anime import AnimeInfo, CharacterProfile, GenderEnum
from app.anime.sources.base import BaseAnimeSource
from app.core.exceptions import ProviderError


class JikanSource(BaseAnimeSource):
    """Jikan REST API source for anime metadata."""

    BASE_URL = "https://api.jikan.moe/v4"
    MAX_CHARACTER_DETAIL_FETCHES = 15

    async def _rate_limit_delay(self):
        # Delay 0.35s to respect 3 req/sec limit
        await asyncio.sleep(0.35)

    @staticmethod
    def parse_gender_from_about(about: str) -> Tuple[GenderEnum, float]:
        """Extracts character gender and confidence from Jikan character biography text."""
        if not about:
            return GenderEnum.UNKNOWN, 0.0

        about_lower = about.lower()

        # Explicit structured field (common in MAL character bios: "Gender: Female")
        m_explicit = re.search(r'\b(?:gender|sex)\s*:\s*(female|male)\b', about_lower)
        if m_explicit:
            return (
                GenderEnum.FEMALE if m_explicit.group(1) == "female" else GenderEnum.MALE,
                0.95,
            )

        female_subject = len(re.findall(r'\bshe\b', about_lower))
        male_subject = len(re.findall(r'\bhe\b', about_lower))
        female_other = len(re.findall(
            r'\b(her|hers|herself|woman|girl|female|daughter|sister|princess|queen|wife|mother|goddess|lady|maiden|heroine|empress|witch|priestess|nun|aunt|grandmother|niece)\b',
            about_lower,
        ))
        male_other = len(re.findall(
            r'\b(him|his|himself|man|boy|male|son|brother|prince|king|husband|father|god|hero|emperor|wizard|priest|monk|uncle|grandfather|nephew|knight|lord)\b',
            about_lower,
        ))

        female_matches = (female_subject * 2) + female_other
        male_matches = (male_subject * 2) + male_other

        if female_matches > male_matches:
            return GenderEnum.FEMALE, min(0.95, 0.60 + (female_matches - male_matches) * 0.05)
        if male_matches > female_matches:
            return GenderEnum.MALE, min(0.95, 0.60 + (male_matches - female_matches) * 0.05)
        return GenderEnum.UNKNOWN, 0.0

    async def search_anime(self, query: str) -> List[AnimeInfo]:
        url = f"{self.BASE_URL}/anime"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) GPTSubtitler/2.0',
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        }

        last_error = None
        for attempt in range(3):
            await self._rate_limit_delay()
            try:
                client = await self.get_http_client()
                response = await client.get(url, params={"q": query, "limit": 10}, headers=headers)
                response.raise_for_status()
                data = response.json()

                results = []
                for item in data.get("data", []):
                    results.append(AnimeInfo(
                        title_romaji=item.get("title", "") or "",
                        title_english=item.get("title_english", "") or "",
                        title_native=item.get("title_japanese", "") or "",
                        episodes=item.get("episodes"),
                        format=item.get("type", "") or "",
                        status=item.get("status", "") or "",
                        cover_image_url=item.get("images", {}).get("jpg", {}).get("large_image_url", ""),
                        source_name="Jikan",
                        source_id=str(item.get("mal_id"))
                    ))
                return results
            except Exception as e:
                last_error = e
                await asyncio.sleep(1)

        raise ProviderError(f"Jikan search failed after 3 attempts: {last_error}")

    async def get_characters(self, anime_id: str) -> List[CharacterProfile]:
        url = f"{self.BASE_URL}/anime/{anime_id}/characters"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) GPTSubtitler/2.0',
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        }

        last_error = None
        for attempt in range(3):
            await self._rate_limit_delay()
            try:
                client = await self.get_http_client()
                response = await client.get(url, headers=headers)
                response.raise_for_status()
                data = response.json()

                items = data.get("data", []) or []
                # Prioritize Main characters first when fetching individual character bios for gender
                prioritized = sorted(
                    items,
                    key=lambda it: 0 if str(it.get("role", "")).lower() == "main" else 1
                )

                results = []
                detail_fetches = 0
                for item in prioritized:
                    char = item.get("character", {}) or {}
                    about = char.get("about", "") or ""
                    aliases = list(char.get("nicknames", []) or [])
                    native_name = char.get("name_kanji", "") or ""
                    mal_id = char.get("mal_id")

                    # /anime/{id}/characters omits 'about'; fetch /characters/{mal_id} lazily for top roles
                    if not about and mal_id and detail_fetches < self.MAX_CHARACTER_DETAIL_FETCHES:
                        detail_fetches += 1
                        try:
                            await self._rate_limit_delay()
                            detail_url = f"{self.BASE_URL}/characters/{mal_id}"
                            detail_resp = await client.get(detail_url, headers=headers)
                            if detail_resp.status_code == 429:
                                await asyncio.sleep(0.75)
                                detail_resp = await client.get(detail_url, headers=headers)
                            if detail_resp.status_code == 200:
                                c_data = detail_resp.json().get("data", {}) or {}
                                about = c_data.get("about", "") or ""
                                if not aliases:
                                    aliases = [n for n in (c_data.get("nicknames") or []) if isinstance(n, str) and n.strip()]
                                if not native_name:
                                    native_name = c_data.get("name_kanji", "") or ""
                        except Exception:
                            pass

                    gender, confidence = self.parse_gender_from_about(about)

                    results.append(CharacterProfile(
                        canonical_name=char.get("name", "") or "",
                        native_name=native_name,
                        aliases=aliases,
                        gender=gender,
                        gender_source="Jikan (Parsed)",
                        gender_confidence=confidence,
                        role=item.get("role", "") or "",
                        description=about
                    ))
                return results
            except Exception as e:
                last_error = e
                await asyncio.sleep(1)

        raise ProviderError(f"Jikan character fetch failed after 3 attempts: {last_error}")
