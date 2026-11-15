import pytest
from app.anime.identifier import MediaIdentifier
from app.models.anime import MediaInfo, AnimeInfo, CharacterProfile, GenderEnum
from app.anime.sources.tvmaze import TVMazeSource
from app.anime.sources.cinemeta import CinemetaSource
from app.anime.metadata_service import MediaMetadataService
from app.core.database import DatabaseManager

def test_media_identifier_tv():
    identifier = MediaIdentifier()
    
    info1 = identifier.identify_media_info("Breaking.Bad.S01E05.720p.HDTV.x264.srt")
    assert info1["title"] == "Breaking Bad"
    assert info1["episode"] == "05"
    assert info1["season"] == "01"
    assert info1["media_type"] == "tv"
    
    info2 = identifier.identify_media_info("Game.of.Thrones.1x05.HDTV.srt")
    assert info2["title"] == "Game of Thrones"
    assert info2["episode"] == "05"
    assert info2["season"] == "1"
    assert info2["media_type"] == "tv"

def test_media_identifier_movie():
    identifier = MediaIdentifier()
    
    info1 = identifier.identify_media_info("Oppenheimer.2023.1080p.WEBRip.x264.AAC.srt")
    assert info1["title"] == "Oppenheimer"
    assert info1["year"] == "2023"
    assert info1["media_type"] == "movie"
    
    info2 = identifier.identify_media_info("Inception (2010) [1080p].srt")
    assert info2["title"] == "Inception"
    assert info2["year"] == "2010"
    assert info2["media_type"] == "movie"

def test_media_identifier_anime():
    identifier = MediaIdentifier()
    
    info1 = identifier.identify_media_info("[SubsPlease] Sousou no Frieren - 05 (1080p) [XXXXX].ass")
    assert info1["title"] == "Sousou no Frieren"
    assert info1["episode"] == "05"
    assert info1["media_type"] == "anime"
    
    # Backwards compatibility check
    title, ep = identifier.identify_from_path("Sousou no Frieren - 05.ass")
    assert title == "Sousou no Frieren"
    assert ep == "05"

def test_media_info_model_compatibility():
    # Test title synchronization
    m = MediaInfo(title="The Matrix", year=1999, media_type="movie")
    assert m.title_romaji == "The Matrix"
    assert m.display_title == "The Matrix"
    
    # Test AnimeInfo alias
    a = AnimeInfo(title_romaji="Naruto", episodes=220)
    assert a.title == "Naruto"
    assert a.display_title == "Naruto"

@pytest.mark.asyncio
async def test_metadata_service_cache_and_routing():
    db = DatabaseManager(':memory:')
    svc = MediaMetadataService(db)
    
    # Simulate caching a movie
    m = MediaInfo(title="Interstellar", year=2014, media_type="movie", source_name="Cinemeta")
    chars = [
        CharacterProfile(canonical_name="Cooper", gender=GenderEnum.MALE, gender_confidence=1.0)
    ]
    
    db.set_cache(
        "media_meta_interstellar",
        {"media": m.model_dump(), "characters": [c.model_dump() for c in chars]},
        source="Test",
        ttl_seconds=3600
    )
    
    res_m, res_chars = await svc.resolve_media_and_characters("Interstellar.2014.1080p.srt")
    assert res_m is not None
    assert res_m.title == "Interstellar"
    assert len(res_chars) == 1
    assert res_chars[0].canonical_name == "Cooper"
    assert res_chars[0].gender == GenderEnum.MALE
