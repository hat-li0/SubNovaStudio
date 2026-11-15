from abc import ABC, abstractmethod
import asyncio
from typing import List, Optional
import httpx
from app.models.anime import AnimeInfo, CharacterProfile

try:
    import h2  # noqa: F401
    _HTTP2_AVAILABLE = True
except ImportError:
    _HTTP2_AVAILABLE = False


def create_shared_http_client() -> httpx.AsyncClient:
    """Creates a pooled httpx AsyncClient with automatic HTTP/2 support when `h2` is available."""
    return httpx.AsyncClient(
        timeout=10.0,
        http2=_HTTP2_AVAILABLE,
        limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
    )


class BaseAnimeSource(ABC):
    """Abstract base class for anime/media metadata sources with shared connection pooling."""

    def __init__(self, shared_client: Optional[httpx.AsyncClient] = None):
        self._shared_client: Optional[httpx.AsyncClient] = shared_client
        self._owns_client: bool = False
        self._client_loop_id: Optional[int] = None

    def set_shared_client(self, client: Optional[httpx.AsyncClient]) -> None:
        self._shared_client = client
        self._owns_client = False
        try:
            self._client_loop_id = id(asyncio.get_running_loop())
        except RuntimeError:
            self._client_loop_id = None

    async def get_http_client(self) -> httpx.AsyncClient:
        """Returns an active shared httpx.AsyncClient bound safely to the current event loop."""
        try:
            cur_loop_id = id(asyncio.get_running_loop())
        except RuntimeError:
            cur_loop_id = None

        if (
            self._shared_client is not None
            and not getattr(self._shared_client, "is_closed", False)
            and (not self._owns_client or self._client_loop_id == cur_loop_id)
        ):
            return self._shared_client

        # Close stale loop-bound owned client if loop changed
        if self._shared_client is not None and self._owns_client:
            try:
                await self._shared_client.aclose()
            except Exception:
                pass

        self._shared_client = create_shared_http_client()
        self._owns_client = True
        self._client_loop_id = cur_loop_id
        return self._shared_client

    async def aclose(self) -> None:
        """Closes owned shared HTTP client resources cleanly."""
        if self._shared_client is not None and self._owns_client:
            try:
                if not getattr(self._shared_client, "is_closed", False):
                    await self._shared_client.aclose()
            except Exception:
                pass
            self._shared_client = None
            self._owns_client = False
            self._client_loop_id = None

    @abstractmethod
    async def search_anime(self, query: str) -> List[AnimeInfo]:
        """Search for anime by title query."""
        pass

    @abstractmethod
    async def get_characters(self, anime_id: str) -> List[CharacterProfile]:
        """Get characters for a specific anime ID."""
        pass
