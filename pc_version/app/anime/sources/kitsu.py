import httpx
from typing import List
from app.models.anime import AnimeInfo, CharacterProfile, GenderEnum
from app.anime.sources.base import BaseAnimeSource
from app.core.exceptions import ProviderError

class KitsuSource(BaseAnimeSource):
    """Kitsu REST API source for anime metadata."""
    
    BASE_URL = "https://kitsu.io/api/edge"
    
    async def search_anime(self, query: str) -> List[AnimeInfo]:
        url = f"{self.BASE_URL}/anime"
        headers = {
            'Accept': 'application/vnd.api+json',
            'Content-Type': 'application/vnd.api+json'
        }
        try:
            client = await self.get_http_client()
            response = await client.get(
                url,
                params={"filter[text]": query, "page[limit]": 10},
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()

            results = []
            for item in data.get("data", []):
                attr = item.get("attributes", {})
                titles = attr.get("titles", {})
                results.append(AnimeInfo(
                    title_romaji=titles.get("en_jp") or attr.get("canonicalTitle", ""),
                    title_english=titles.get("en") or "",
                    title_native=titles.get("ja_jp") or "",
                    episodes=attr.get("episodeCount"),
                    format=attr.get("subtype", ""),
                    status=attr.get("status", ""),
                    cover_image_url=attr.get("posterImage", {}).get("large", ""),
                    source_name="Kitsu",
                    source_id=str(item.get("id"))
                ))
            return results
        except Exception as e:
            raise ProviderError(f"Kitsu search failed: {e}")

    async def get_characters(self, anime_id: str) -> List[CharacterProfile]:
        url = f"{self.BASE_URL}/anime/{anime_id}/characters"
        headers = {
            'Accept': 'application/vnd.api+json',
            'Content-Type': 'application/vnd.api+json'
        }
        try:
            client = await self.get_http_client()
            # Kitsu relationships don't include character details directly in this endpoint.
            # It requires 'include=character' to get the actual character details.
            response = await client.get(
                url,
                params={"include": "character", "page[limit]": 20},
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()

            results = []

            # Characters are in 'included' array
            included = data.get("included", [])
            char_map = {item["id"]: item["attributes"] for item in included if item["type"] == "characters"}

            for item in data.get("data", []):
                attr = item.get("attributes", {})
                role = attr.get("role", "")

                char_id = item.get("relationships", {}).get("character", {}).get("data", {}).get("id")
                if not char_id or char_id not in char_map:
                    continue

                char_attr = char_map[char_id]
                name = char_attr.get("canonicalName", "")
                about = char_attr.get("description", "") or ""

                # Count pronoun frequencies in bio text to determine majority
                import re
                gender = GenderEnum.UNKNOWN
                confidence = 0.0
                about_lower = about.lower()

                female_matches = len(re.findall(r'\b(she|her|hers|woman|girl|female)\b', about_lower))
                male_matches = len(re.findall(r'\b(he|him|his|man|boy|male)\b', about_lower))

                if female_matches > male_matches:
                    gender = GenderEnum.FEMALE
                    confidence = min(0.95, 0.60 + (female_matches - male_matches) * 0.05)
                elif male_matches > female_matches:
                    gender = GenderEnum.MALE
                    confidence = min(0.95, 0.60 + (male_matches - female_matches) * 0.05)

                results.append(CharacterProfile(
                    canonical_name=name,
                    gender=gender,
                    gender_source="Kitsu (Parsed)",
                    gender_confidence=confidence,
                    role=role,
                    description=about
                ))
            return results
        except Exception as e:
            raise ProviderError(f"Kitsu character fetch failed: {e}")
