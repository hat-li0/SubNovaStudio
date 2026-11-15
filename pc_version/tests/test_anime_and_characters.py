import pytest
from app.anime.identifier import AnimeIdentifier
from app.character.resolver import CharacterResolver
from app.character.gender import GenderResolver
from app.models.anime import CharacterProfile, GenderEnum, GlossaryEntry
from app.models.subtitle import SubtitleEvent

# Mock DB tests would require sqlite in-memory db setup
# Focusing on logic classes

def test_anime_identifier():
    identifier = AnimeIdentifier()
    
    t1, e1 = identifier.identify_from_path("[SubsPlease] Sousou no Frieren - 05 (1080p) [XXXXX].ass")
    assert t1 == "Sousou no Frieren"
    assert e1 == "05"
    
    t2, e2 = identifier.identify_from_path("My Hero Academia S06E12.srt")
    assert t2 == "My Hero Academia"
    assert e2 == "12"
    
    t3, e3 = identifier.identify_from_path("Naruto_E220.vtt")
    assert t3 == "Naruto"
    assert e3 == "220"

def test_character_resolver():
    profiles = [
        CharacterProfile(canonical_name="Naruto Uzumaki", first_name="Naruto", aliases=["Fox Boy"])
    ]
    resolver = CharacterResolver(profiles)
    
    # Exact match
    match = resolver.resolve_speaker("Naruto")
    assert match is not None
    assert match.match_type == "exact"
    
    # Alias match
    match = resolver.resolve_speaker("fox boy")
    assert match is not None
    assert match.match_type == "alias"
    
    # Fuzzy match
    match = resolver.resolve_speaker("Naruto Uzmak")
    assert match is not None
    assert match.match_type == "fuzzy"

def test_gender_resolver():
    resolver = GenderResolver()
    
    res1 = resolver.resolve_gender(GenderEnum.UNKNOWN, GenderEnum.MALE, GenderEnum.UNKNOWN)
    assert res1 == GenderEnum.MALE
    
    res2 = resolver.resolve_gender(GenderEnum.FEMALE, GenderEnum.MALE, GenderEnum.UNKNOWN)
    assert res2 == GenderEnum.FEMALE  # User override wins
    
    res3 = resolver.resolve_gender(GenderEnum.UNKNOWN, GenderEnum.MALE, GenderEnum.FEMALE)
    assert res3 == GenderEnum.CONFLICT

# Test memory repo hash logic
from app.storage.memory_repo import TranslationMemoryRepository
from app.core.database import DatabaseManager

def test_memory_repo_hash():
    # We can test the internal hash function without a real DB
    repo = TranslationMemoryRepository(None)
    hash_val = repo._hash_text("Hello World")
    assert isinstance(hash_val, str)
    assert len(hash_val) == 64  # SHA-256 length
