import httpx
from typing import List
from app.models.anime import AnimeInfo, CharacterProfile, GenderEnum
from app.anime.sources.base import BaseAnimeSource
from app.core.exceptions import ProviderError

class AniListSource(BaseAnimeSource):
    """AniList GraphQL API source for anime metadata."""
    
    URL = "https://graphql.anilist.co"
    
    async def search_anime(self, query: str) -> List[AnimeInfo]:
        graphql_query = """
        query ($search: String) {
          Page(page: 1, perPage: 10) {
            media(search: $search, type: ANIME) {
              id
              title {
                romaji
                english
                native
              }
              episodes
              format
              status
              coverImage {
                large
              }
            }
          }
        }
        """
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0',
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'Origin': 'https://anilist.co',
            'Referer': 'https://anilist.co/'
        }
        try:
            client = await self.get_http_client()
            response = await client.post(
                self.URL,
                json={"query": graphql_query, "variables": {"search": query}},
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()

            results = []
            for item in data.get("data", {}).get("Page", {}).get("media", []):
                title = item.get("title", {})
                results.append(AnimeInfo(
                    title_romaji=title.get("romaji", "") or "",
                    title_english=title.get("english", "") or "",
                    title_native=title.get("native", "") or "",
                    episodes=item.get("episodes"),
                    format=item.get("format", "") or "",
                    status=item.get("status", "") or "",
                    cover_image_url=item.get("coverImage", {}).get("large", ""),
                    source_name="AniList",
                    source_id=str(item.get("id"))
                ))
            return results
        except Exception as e:
            raise ProviderError(f"AniList search failed: {e}")

    async def get_characters(self, anime_id: str) -> List[CharacterProfile]:
        graphql_query = """
        query ($id: Int) {
          Media(id: $id) {
            characters {
              edges {
                role
                node {
                  id
                  name {
                    full
                    native
                    alternative
                  }
                  gender
                  age
                  description
                }
              }
            }
          }
        }
        """
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0',
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'Origin': 'https://anilist.co',
            'Referer': 'https://anilist.co/'
        }
        try:
            client = await self.get_http_client()
            response = await client.post(
                self.URL,
                json={"query": graphql_query, "variables": {"id": int(anime_id)}},
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()

            results = []
            edges = data.get("data", {}).get("Media", {}).get("characters", {}).get("edges", [])
            for edge in edges:
                node = edge.get("node", {})
                name_obj = node.get("name", {})
                gender_str = node.get("gender", "")

                gender = GenderEnum.UNKNOWN
                if gender_str == "Male":
                    gender = GenderEnum.MALE
                elif gender_str == "Female":
                    gender = GenderEnum.FEMALE
                elif gender_str == "Non-binary":
                    gender = GenderEnum.NON_BINARY

                results.append(CharacterProfile(
                    canonical_name=name_obj.get("full", "") or "",
                    native_name=name_obj.get("native", "") or "",
                    aliases=name_obj.get("alternative", []) or [],
                    gender=gender,
                    gender_source="AniList",
                    gender_confidence=0.95 if gender != GenderEnum.UNKNOWN else 0.0,
                    role=edge.get("role", "") or "",
                    age=node.get("age", "") or "",
                    description=node.get("description", "") or ""
                ))
            return results
        except Exception as e:
            raise ProviderError(f"AniList character fetch failed: {e}")
