import asyncio
import sqlite3
from pathlib import Path
from unittest.mock import MagicMock, patch
import httpx
import pytest

from app.anime.metadata_service import MediaMetadataService
from app.anime.sources.base import BaseAnimeSource
from app.anime.sources.jikan import JikanSource
from app.character.database import CharacterRepository
from app.core.database import DatabaseManager
from app.core.language_detector import LanguageDetector
from app.models.anime import CharacterProfile, GenderEnum, GlossaryEntry, MediaInfo
from app.models.provider import ChatResponse
from app.models.subtitle import SubtitleDocument, SubtitleEvent, SubtitleFormat
from app.providers.base import ProviderBase
from app.quality.healer import SubtitleHealer
from app.quality.translation_validator import QualityValidator
from app.storage.memory_repo import TranslationMemoryRepository
from app.subtitle.effect_separator import EffectPayloadIsolator
from app.subtitle.video_extractor import SubtitleStreamInfo, VideoSubtitleExtractor
from app.subtitle.writers.ass import ASSWriter
from app.translation.batcher import TokenBatcher
from app.translation.context import ContextBuilder
from app.translation.engine import TranslationEngine
from app.translation.validator import GenderValidator


# ---------------------------------------------------------------------------
# BUG 1: Speaker-gender-safe deduplication & Translation Memory (<4 word guard)
# ---------------------------------------------------------------------------

def test_translation_memory_speaker_guard_and_schema_migration(tmp_path):
    db_file = tmp_path / "tm_legacy_migration.db"

    # Simulate legacy schema WITHOUT speaker / speaker_gender columns in translation_memory
    conn = sqlite3.connect(str(db_file))
    conn.executescript("""
        CREATE TABLE translation_memory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_hash TEXT NOT NULL,
            source_text TEXT NOT NULL,
            translated_text TEXT NOT NULL,
            source_lang TEXT NOT NULL,
            target_lang TEXT NOT NULL,
            anime_id INTEGER,
            character_id INTEGER,
            provider TEXT,
            model TEXT,
            usage_count INTEGER DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        INSERT INTO translation_memory (source_hash, source_text, translated_text, source_lang, target_lang)
        VALUES ('dummyhash', 'Old long cached phrase', 'عبارة قديمة', 'en', 'ar');
    """)
    conn.commit()
    conn.close()

    # Opening DatabaseManager MUST migrate translation_memory non-destructively
    db = DatabaseManager(str(db_file))
    try:
        cols = {row["name"] for row in db.fetch_all("PRAGMA table_info(translation_memory)")}
        assert "speaker" in cols
        assert "speaker_gender" in cols
        legacy_row = db.fetch_one("SELECT translated_text FROM translation_memory WHERE source_text='Old long cached phrase'")
        assert legacy_row["translated_text"] == "عبارة قديمة"

        repo = TranslationMemoryRepository(db)
        # Save <4-word phrase for female speaker Luna
        repo.save_translation(
            "Wait!", "انتظري!", "en", "ar",
            speaker="Luna", speaker_gender="FEMALE",
        )
        # Anonymous lookup or different speaker MUST NOT hit
        assert repo.lookup("Wait!", "en", "ar", speaker="", speaker_gender="UNKNOWN") is None
        assert repo.lookup("Wait!", "en", "ar", speaker="Hero", speaker_gender="MALE") is None
        # Case-insensitive matching speaker + gender DOES hit
        assert repo.lookup("Wait!", "en", "ar", speaker="luna", speaker_gender="female") == "انتظري!"

        # Save >=4-word phrase -> hits regardless of speaker
        repo.save_translation(
            "Where are we going now?", "إلى أين نحن ذاهبون الآن؟", "en", "ar",
            speaker="Hero", speaker_gender="MALE",
        )
        assert repo.lookup("Where are we going now?", "en", "ar", speaker="", speaker_gender="") == "إلى أين نحن ذاهبون الآن؟"
    finally:
        db.close()


@pytest.mark.asyncio
async def test_engine_does_not_dedup_short_cross_speaker_or_anonymous_lines():
    class _SpyProvider(ProviderBase):
        def __init__(self):
            self.calls = []

        async def chat_completion(self, messages, model, temperature=0.1, max_tokens=None, **kwargs):
            user_msg = messages[-1].content
            self.calls.append(user_msg)
            import re
            out = []
            for m in re.finditer(r"\[(\d+)\]\s*(.+)", user_msg):
                lid = int(m.group(1))
                out.append(f"[{lid:03d}] ترجمة رقم {lid}")
            return ChatResponse(content="\n".join(out), model=model)

        async def is_available(self):
            return True

        async def list_models(self):
            return []

        async def test_connection(self):
            return True

    chars = [
        CharacterProfile(canonical_name="Hero", gender=GenderEnum.MALE),
        CharacterProfile(canonical_name="Luna", gender=GenderEnum.FEMALE),
    ]
    doc = SubtitleDocument(
        format=SubtitleFormat.ASS,
        events=[
            # 3 short lines (<4 words): Hero (MALE), Luna (FEMALE), Anonymous ("") -> NONE should dedup into another
            SubtitleEvent(id=1, start_time="0:00:01.00", end_time="0:00:02.00", speaker="Hero", original_text="Are you serious?"),
            SubtitleEvent(id=2, start_time="0:00:03.00", end_time="0:00:04.00", speaker="Luna", original_text="Are you serious?"),
            SubtitleEvent(id=3, start_time="0:00:05.00", end_time="0:00:06.00", speaker="", original_text="Are you serious?"),
            # Same speaker Hero repeats short line -> SHOULD dedup (4 sent, 1 skipped? wait: 5 events, 1 skipped)
            SubtitleEvent(id=4, start_time="0:00:07.00", end_time="0:00:08.00", speaker="Hero", original_text="Are you serious?"),
            # >=4 words repeats across speakers -> SHOULD dedup
            SubtitleEvent(id=5, start_time="0:00:09.00", end_time="0:00:11.00", speaker="Hero", original_text="Welcome to the grand guild hall."),
            SubtitleEvent(id=6, start_time="0:00:12.00", end_time="0:00:14.00", speaker="Luna", original_text="Welcome to the grand guild hall."),
        ],
    )

    provider = _SpyProvider()
    engine = TranslationEngine(batcher=TokenBatcher(max_tokens=4000, max_events=30))
    await engine.translate_document(
        doc, provider, model="mock", source_lang="English", target_lang="Arabic",
        characters=chars, auto_heal=False, auto_improve=False,
    )

    # Events sent to LLM must be IDs 1, 2, 3, 5 (4 lines total; 4 & 6 deduplicated safely)
    import re
    sent_items = re.findall(r"\[(\d{3})\]", provider.calls[0])
    assert sent_items == ["001", "002", "003", "004"]


# ---------------------------------------------------------------------------
# BUG 2 & ENHANCEMENT 1 & 4: Scene-aware batching, context boundary, BPE tokens
# ---------------------------------------------------------------------------

def test_batcher_splits_on_id_jumps_and_scene_silences_and_bpe_tokens():
    # Enhancement 4: Arabic non-ASCII charges ~1.0 token/char while ASCII ~1 token per 3.5 chars
    ar_toks = TokenBatcher.estimate_tokens_static("مرحباً يا صديقي العزيز في هذه المدينة")
    en_toks = TokenBatcher.estimate_tokens_static("Hello my dear friend in this big city")
    assert ar_toks >= 30
    assert en_toks < ar_toks

    batcher = TokenBatcher(max_tokens=4000, max_events=30, max_context=8192)
    events = [
        SubtitleEvent(id=1, start_time="0:00:01.00", end_time="0:00:03.00", original_text="First line"),
        SubtitleEvent(id=2, start_time="0:00:03.20", end_time="0:00:05.00", original_text="Second line"),
        # ID jump > 5 (2 -> 10) must force batch break
        SubtitleEvent(id=10, start_time="0:00:05.50", end_time="0:00:07.00", original_text="After ID gap"),
        # Scene silence > 4.0s (7.00s -> 15.00s = 8000ms) must force batch break
        SubtitleEvent(id=11, start_time="0:00:15.00", end_time="0:00:17.00", original_text="New scene line"),
        SubtitleEvent(id=12, start_time="0:00:17.50", end_time="0:00:19.00", original_text="Same scene"),
    ]
    batches = batcher.create_batches(events, is_local=False)
    assert [[e.id for e in b] for b in batches] == [[1, 2], [10], [11, 12]]

    # Bug 2: ContextBuilder stops walking across >15s scene breaks
    ctx_events = [
        SubtitleEvent(id=1, start_time="0:00:01.00", end_time="0:00:03.00", original_text="Earlier unrelated scene"),
        SubtitleEvent(id=2, start_time="0:00:30.00", end_time="0:00:32.00", original_text="Current scene opener"),
        SubtitleEvent(id=3, start_time="0:00:32.50", end_time="0:00:34.00", original_text="Target batch line"),
        SubtitleEvent(id=4, start_time="0:01:05.00", end_time="0:01:07.00", original_text="Next unrelated scene"),
    ]
    ctx = ContextBuilder(prev_count=3, next_count=3).build_context(ctx_events, [ctx_events[2]])
    assert "Current scene opener" in ctx["prev_text"]
    assert "Earlier unrelated scene" not in ctx["prev_text"]
    assert "Next unrelated scene" not in ctx["next_text"]


# ---------------------------------------------------------------------------
# BUG 3 & BUG 4: Idempotent tag reconstruction + mid-line internal tag spans
# ---------------------------------------------------------------------------

def test_effect_isolator_idempotence_and_internal_tag_preservation():
    raw_internal = r"{\an8}Look at {\c&H0000FF&}this crimson sword{\r} right now!"
    clean, skeleton = EffectPayloadIsolator.extract_clean_payload(raw_internal)
    assert "{" not in clean and "\\" not in clean
    assert "this crimson sword" in clean
    assert len(skeleton["segments"][0]["internal_spans"]) == 2

    translated = "انظر إلى هذا السيف القرمزي الآن!"
    once = EffectPayloadIsolator.reconstruct_effect_text(translated, skeleton)
    assert once.startswith(r"{\an8}")
    assert r"{\c&H0000FF&}" in once
    assert r"{\r}" in once

    # Bug 3: Repeated reconstruction & ASSWriter passes are 100% idempotent
    twice = EffectPayloadIsolator.reconstruct_effect_text(once, skeleton)
    assert twice == once

    # Drawing block + leading/trailing tags must NEVER duplicate
    raw_drawing = r"{\p1}m 0 0 l 20 20{\p0}{\pos(100,200)}Warning Sign"
    clean_d, skel_d = EffectPayloadIsolator.extract_clean_payload(raw_drawing)
    assert clean_d == "Warning Sign"
    ev = SubtitleEvent(id=1, start_time="0:00:01.00", end_time="0:00:03.00", original_text=raw_drawing, format_type=SubtitleFormat.ASS)
    r1 = ev.rebuild_text("تحذير هام")
    r2 = ev.rebuild_text(r1)
    assert r1 == r2
    assert r2.count(r"{\p1}") == 1
    assert r2.count(r"{\pos(100,200)}") == 1


# ---------------------------------------------------------------------------
# BUG 5: Lossless native ASS preservation vs converted SRT/VTT styling
# ---------------------------------------------------------------------------

def test_purify_extracted_subtitle_preserves_native_ass_but_fixes_converted_srt(tmp_path):
    # Native lossless ASS: PlayResX=1920, Fontsize=60 must stay untouched!
    native_ass = tmp_path / "native.ass"
    native_ass.write_text(
        "[Script Info]\nPlayResX: 1920\nPlayResY: 1080\nWrapStyle: 2\n\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour\n"
        "Style: Default,Noto Naskh Arabic,60,&H00FFFFFF\n\n"
        "[Events]\nDialogue: 0,0:00:01.00,0:00:03.00,Default,,0,0,0,,Hello\n",
        encoding="utf-8",
    )
    VideoSubtitleExtractor.purify_extracted_subtitle(str(native_ass), video_resolution=(1280, 720), is_source_ass=True)
    res_native = native_ass.read_text(encoding="utf-8-sig")
    assert "PlayResX: 1920" in res_native
    assert "PlayResY: 1080" in res_native
    assert "Style: Default,Noto Naskh Arabic,60," in res_native

    # Converted SRT->ASS: PlayRes=384x288 & small font=16 SHOULD upgrade
    conv_ass = tmp_path / "converted.ass"
    conv_ass.write_text(
        "[Script Info]\nPlayResX: 384\nPlayResY: 288\n\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
        "Style: Default,Arial,16,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,2,0,2,10,10,10,1\n\n"
        "[Events]\nDialogue: 0,0:00:01.00,0:00:03.00,Default,,0,0,0,,Hello\n",
        encoding="utf-8",
    )
    VideoSubtitleExtractor.purify_extracted_subtitle(str(conv_ass), video_resolution=(1280, 720), is_source_ass=False)
    res_conv = conv_ass.read_text(encoding="utf-8-sig")
    assert "PlayResX: 1280" in res_conv
    assert "PlayResY: 720" in res_conv
    assert "Arial,16," not in res_conv


# ---------------------------------------------------------------------------
# BUG 6: CharacterResolver integration in both Validators (aliases & first names)
# ---------------------------------------------------------------------------

def test_validators_resolve_character_aliases_and_first_names():
    seiya = CharacterProfile(
        canonical_name="Seiya Ryuguin",
        first_name="Seiya",
        aliases=["Overly Cautious Hero"],
        gender=GenderEnum.MALE,
    )
    events = [
        SubtitleEvent(
            id=1,
            speaker="Seiya",  # First-name speaker, not full canonical name
            original_text="Prepare everything.",
            translated_text="هل أنتِ متأكدة يا هذا؟",  # Feminine أنتِ on MALE speaker
        ),
        SubtitleEvent(
            id=2,
            speaker="Overly Cautious Hero",  # Alias speaker
            original_text="Don't rush.",
            translated_text="لا تتعجلي يا فتاة، لقد فعلتِ هذا خطأً.",
        ),
    ]

    qv = QualityValidator()
    # Accepts List[CharacterProfile] as well as Dict
    report_list = qv.run_quality_checks(events, [seiya], [])
    assert report_list["warnings_count"] >= 2
    assert len(report_list["flagged_events"]) == 2

    gv = GenderValidator()
    issues = gv.validate({1: events[0].translated_text, 2: events[1].translated_text}, events, [seiya])
    assert len(issues) == 2


# ---------------------------------------------------------------------------
# BUG 7: Jikan lazy /characters/{mal_id} enrichment for gender & aliases
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_jikan_fetches_character_detail_bio_and_aliases():
    async def _mock_get(url, headers=None, params=None):
        req = httpx.Request("GET", url)
        if url.endswith("/anime/999/characters"):
            return httpx.Response(
                200,
                request=req,
                json={
                    "data": [
                        {
                            "role": "Main",
                            "character": {"mal_id": 101, "name": "Ristarte"},
                        },
                        {
                            "role": "Main",
                            "character": {"mal_id": 102, "name": "Seiya Ryuguin"},
                        },
                    ]
                },
            )
        if url.endswith("/characters/101"):
            return httpx.Response(
                200,
                request=req,
                json={
                    "data": {
                        "mal_id": 101,
                        "name": "Ristarte",
                        "name_kanji": "リスタルテ",
                        "nicknames": ["Lista", "Goddess of Healing"],
                        "about": "She is the goddess of healing who summons him.",
                    }
                },
            )
        if url.endswith("/characters/102"):
            return httpx.Response(
                200,
                request=req,
                json={
                    "data": {
                        "mal_id": 102,
                        "name": "Seiya Ryuguin",
                        "nicknames": [],
                        "about": "Gender: Male\nHe prepares three sets of armor.",
                    }
                },
            )
        return httpx.Response(404, request=req)

    jikan = JikanSource()
    fake_client = MagicMock()
    fake_client.is_closed = False
    fake_client.get = _mock_get
    jikan.set_shared_client(fake_client)

    with patch.object(JikanSource, "_rate_limit_delay", return_value=None):
        chars = await jikan.get_characters("999")

    by_name = {c.canonical_name: c for c in chars}
    assert by_name["Ristarte"].gender == GenderEnum.FEMALE
    assert by_name["Ristarte"].native_name == "リスタルテ"
    assert "Lista" in by_name["Ristarte"].aliases
    assert by_name["Seiya Ryuguin"].gender == GenderEnum.MALE
    assert by_name["Seiya Ryuguin"].gender_confidence >= 0.9


# ---------------------------------------------------------------------------
# BUG 8: Proportion-based LanguageDetector immune to 1 foreign credit line
# ---------------------------------------------------------------------------

def test_language_detector_handles_dominant_english_with_single_arabic_or_japanese_credit():
    mixed_events = [
        SubtitleEvent(id=i, original_text="The hero walked into the dungeon quietly to scout ahead.")
        for i in range(1, 50)
    ]
    # Add 1 Arabic fan-credit line and 1 Japanese karaoke credit line
    mixed_events.append(SubtitleEvent(id=50, original_text="ترجمة: فريق النجوم"))
    mixed_events.append(SubtitleEvent(id=51, original_text="オープニングテーマ"))

    detected = LanguageDetector.detect_from_events(mixed_events)
    assert detected.code == "en"

    # Genuine Japanese still detects as Japanese
    ja_det = LanguageDetector.detect_from_text("これは日本語の字幕テストです。大丈夫ですか？")
    assert ja_det.code == "ja"
    assert ja_det.confidence >= 0.9

    # Genuine Arabic still detects as Arabic
    ar_det = LanguageDetector.detect_from_text("مرحباً بكم في هذه المغامرة الرائعة للغاية.")
    assert ar_det.code == "ar"


# ---------------------------------------------------------------------------
# BUG 9 & ENHANCEMENT 3: RTL BiDi RLM anchoring + Arabic >52 CPL wrapping
# ---------------------------------------------------------------------------

def test_rtl_bidi_rlm_preservation_and_arabic_cpl_wrapping(tmp_path):
    # Bug 9: RLM anchors weak punctuation & dialogue dashes in ASS output and survives re-healing
    doc = SubtitleDocument(
        format=SubtitleFormat.ASS,
        events=[
            SubtitleEvent(
                id=1, start_time="0:00:01.00", end_time="0:00:04.00",
                original_text=r"{\an8}- Really?!\N- Yes!",
                translated_text=r"{\an8}- حقاً؟!\N- أجل!",
            )
        ],
    )
    ass_text = ASSWriter().write_text(doc)
    assert r"{\an8}\u200f- حقاً؟!" not in ass_text  # literal escape shouldn't appear
    assert "\u200f- حقاً" in ass_text
    assert "أجل!\u200f" in ass_text
    # Idempotence on re-heal: clean_invisible_and_unicode_artifacts must NOT strip \u200f
    assert "\u200f" in SubtitleHealer.clean_invisible_and_unicode_artifacts("\u200f- حقاً!")

    # Enhancement 3: Smart >52 CPL wrapping splits long single-line Arabic safely
    long_ar = r"{\i1}لقد سافرنا عبر هذه الجبال الشاهقة والغابات الكثيفة طوال ثلاثة أيام متواصلة دون راحة، ولكننا لم نعثر على القلعة بعد.{\i0}"
    balanced = SubtitleHealer.balance_ass_linebreaks(long_ar, original_text="Long single line sentence.", max_cpl=52)
    assert r"\N" in balanced
    assert balanced.startswith(r"{\i1}") and balanced.endswith(r"{\i0}")

    # Positioned graphic signs must NOT be wrapped unexpectedly
    pos_sign = r"{\pos(320,180)}لافتة إرشادية طويلة جداً تقع في منتصف الشاشة لعرض اسم المملكة القديمة"
    assert SubtitleHealer.balance_ass_linebreaks(pos_sign, "", max_cpl=52) == pos_sign


# ---------------------------------------------------------------------------
# BUG 10: CharacterRepository anime/characters/aliases/notes persistence
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_character_repository_and_metadata_service_persist_relational_tables(tmp_path):
    db_path = tmp_path / "chars_persist.db"
    db = DatabaseManager(str(db_path))
    try:
        repo = CharacterRepository(db)
        media = MediaInfo(
            title="Cautious Hero",
            title_romaji="Shinchou Yuusha",
            title_english="Cautious Hero",
            episodes=12,
            format="TV",
            source_name="AniList",
            source_id="105156",
        )
        anime_id = repo.save_anime(media)
        assert anime_id > 0

        chars = [
            CharacterProfile(
                canonical_name="Seiya Ryuguin",
                aliases=["Overly Cautious Hero", "Seiya"],
                gender=GenderEnum.MALE,
                gender_source="AniList",
                gender_confidence=0.98,
                role="MAIN",
                speech_style="Cold and deadpan masculine tone",
                translation_notes="Always use stern masculine imperatives.",
            )
        ]
        repo.save_characters_for_anime(anime_id, chars)

        loaded_media = repo.get_anime_by_source("AniList", "105156")
        assert loaded_media is not None
        assert loaded_media.id == anime_id

        loaded_chars = repo.get_characters_for_anime(anime_id)
        assert len(loaded_chars) == 1
        assert loaded_chars[0].speech_style == "Cold and deadpan masculine tone"
        assert loaded_chars[0].translation_notes == "Always use stern masculine imperatives."
        assert set(loaded_chars[0].aliases) == {"Overly Cautious Hero", "Seiya"}
    finally:
        db.close()


# ---------------------------------------------------------------------------
# ENHANCEMENT 2: Dynamic Running Glossary across batches
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_dynamic_running_glossary_propagates_discovered_names_to_next_batch():
    class _TwoBatchGlossaryProvider(ProviderBase):
        def __init__(self):
            self.calls = []

        async def chat_completion(self, messages, model, temperature=0.1, max_tokens=None, **kwargs):
            sys_msg = messages[0].content
            user_msg = messages[-1].content
            self.calls.append({"system": sys_msg, "user": user_msg})
            if "Edolas Kingdom" in user_msg:
                return ChatResponse(content="[001] وصلنا إلى مملكة إدولاس اليوم!", model=model)
            return ChatResponse(content="[001] سنغادر مملكة إدولاس غداً.", model=model)

        async def is_available(self):
            return True

        async def list_models(self):
            return []

        async def test_connection(self):
            return True

    doc = SubtitleDocument(
        format=SubtitleFormat.ASS,
        events=[
            SubtitleEvent(id=1, start_time="0:00:01.00", end_time="0:00:03.00", original_text="We arrived at the Edolas Kingdom today!"),
            # Force second batch via silence gap >4s
            SubtitleEvent(id=2, start_time="0:00:15.00", end_time="0:00:17.00", original_text="We leave the Edolas Kingdom tomorrow."),
        ],
    )
    provider = _TwoBatchGlossaryProvider()
    engine = TranslationEngine(batcher=TokenBatcher(max_tokens=4000, max_events=1))

    # Run with concurrency=1 so batch 1 completes before batch 2 builds its prompt
    await engine.translate_document(
        doc, provider, model="mock", source_lang="English", target_lang="Arabic",
        concurrency=1, auto_heal=False, auto_improve=False,
    )

    assert len(provider.calls) == 2
    assert "Edolas" in provider.calls[1]["user"]
    assert "Auto-Glossary" in provider.calls[1]["user"]


# ---------------------------------------------------------------------------
# ENHANCEMENT 5: Persistent shared AsyncClient lifecycle in MediaMetadataService
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_metadata_service_shares_and_closes_persistent_http_client(tmp_path):
    db = DatabaseManager(str(tmp_path / "http_pool.db"))
    try:
        svc = MediaMetadataService(db)
        c1 = svc._ensure_shared_client()
        c2 = svc._ensure_shared_client()
        assert isinstance(c1, httpx.AsyncClient)
        assert c1 is c2
        assert await svc.jikan.get_http_client() is c1
        assert await svc.anilist.get_http_client() is c1

        await svc.aclose()
        assert c1.is_closed is True
        assert svc._shared_client is None
    finally:
        db.close()
