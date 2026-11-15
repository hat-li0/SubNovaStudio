import asyncio
import sys
import threading
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

import app.core.resources as resources_mod
from app.core.config import get_settings
from app.core.database import DatabaseManager
from app.core.exceptions import ProviderError
from app.core.resources import get_app_data_dir, resource_path


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app
from app.models.character import CharacterProfile, GenderEnum, GenderInfo
from app.models.glossary import GlossaryEntry
from app.models.provider import ChatResponse, ProviderConfig, ProviderType
from app.models.subtitle import SubtitleDocument, SubtitleEvent, SubtitleFormat
from app.providers.gemini import GeminiProvider
from app.providers.openai import OpenAIProvider
from app.quality.consistency_validator import ConsistencyValidator
from app.quality.healer import SubtitleHealer
from app.storage.glossary_repo import GlossaryRepository
from app.storage.memory_repo import TranslationMemoryRepository
from app.subtitle import write_subtitle
from app.translation.engine import TranslationEngine, format_character_context, format_glossary_context
from app.translation.prompts import PromptBuilder
from app.translation.validator import PipelineValidator


# ---------------------------------------------------------------------------
# Bug #1: Glossary Dialog returns GlossaryEntry objects + DB persistence + Engine/Validator compatibility
# ---------------------------------------------------------------------------
def test_bug1_glossary_dialog_persistence_and_engine_integration(qapp, tmp_path):
    from app.ui.dialogs.glossary_editor import GlossaryEditorDialog

    initial = [
        GlossaryEntry(source_term="Survey Corps", target_term="فيلق الاستطلاع", is_exact_match=True, is_case_sensitive=True),
        "Titan -> عملاق",
    ]
    dlg = GlossaryEditorDialog(initial_entries=initial, anime_id=77)
    dlg.add_row_with_data("Ackerman", "أكرمان", is_exact=False, is_case=True)

    entries = dlg.get_glossary_entries()
    assert len(entries) == 3
    assert all(isinstance(e, GlossaryEntry) for e in entries)
    assert entries[0].source_term == "Survey Corps"
    assert entries[0].is_exact_match is True
    assert entries[0].is_case_sensitive is True
    assert entries[2].source_term == "Ackerman"
    assert entries[2].target_term == "أكرمان"
    assert entries[2].is_exact_match is False
    assert entries[2].is_case_sensitive is True

    # Verify engine formatter + ConsistencyValidator accept these objects without AttributeError
    ctx = format_glossary_context(entries)
    assert "Survey Corps -> فيلق الاستطلاع" in ctx
    assert "Ackerman -> أكرمان" in ctx

    events = [
        SubtitleEvent(id=1, start_ms=0, end_ms=1000, original_text="The Survey Corps will fight!", translated_text="سيقاتل الجميع!"),
    ]
    warnings = ConsistencyValidator().validate_consistency(events, entries)
    assert len(warnings) == 1
    assert warnings[0]["source_term"] == "Survey Corps"

    # Verify SQLite repository saves and reloads per anime and global (anime_id=None)
    db = DatabaseManager(str(tmp_path / "glossary.db"))
    try:
        repo = GlossaryRepository(db)
        saved_anime = repo.replace_entries_for_anime(None, [])  # ensure global clear works
        assert saved_anime == []
        db.execute("INSERT INTO anime (id, title_romaji) VALUES (?, ?)", (77, "Attack on Titan"))
        repo.replace_entries_for_anime(77, entries)
        reloaded = repo.get_all_for_anime(77)
        assert len(reloaded) == 3
        assert reloaded[2].is_exact_match is False
        assert reloaded[2].is_case_sensitive is True

        # Global glossary works when anime_id is None
        repo.replace_entries_for_anime(None, [GlossaryEntry(source_term="Guild", target_term="نقابة")])
        assert len(repo.get_all_for_anime(None)) == 1
        assert repo.get_all_for_anime(None)[0].target_term == "نقابة"
    finally:
        db.close()

    dlg.deleteLater()
    qapp.processEvents()


# ---------------------------------------------------------------------------
# Bug #2: Signs/FX NOT translated by default; explicit toggle in HealingPanel
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_bug2_signs_skipped_by_default_and_controlled_by_healing_panel(qapp):
    from app.ui.widgets.healing_panel import HealingPanel

    panel = HealingPanel()
    opts_default = panel.get_healing_options()
    assert "translate_signs" in opts_default
    assert opts_default["translate_signs"] is False

    doc = SubtitleDocument(
        format=SubtitleFormat.ASS,
        events=[
            SubtitleEvent(id=1, start_ms=0, end_ms=1000, style="Sign", original_text="Episode 1: Opening"),
            SubtitleEvent(id=2, start_ms=1000, end_ms=2000, style="Default", original_text="Let us go!"),
        ],
    )

    mock_provider = AsyncMock()
    mock_provider.chat_completion.return_value = ChatResponse(content="[1] لننطلق!", model="mock")
    engine = TranslationEngine()
    await engine.translate_document(
        doc, mock_provider, "mock-model",
        healing_options=opts_default,
        use_cache=False, force_fresh=True,
    )
    assert doc.events[0].translated_text in (None, "")
    assert "لننطلق" in (doc.events[1].translated_text or "")

    # Now enable sign translation explicitly
    panel.chk_translate_signs.setChecked(True)
    opts_enabled = panel.get_healing_options()
    assert opts_enabled["translate_signs"] is True

    doc2 = SubtitleDocument(
        format=SubtitleFormat.ASS,
        events=[
            SubtitleEvent(id=1, start_ms=0, end_ms=1000, style="Sign", original_text="Episode 1: Opening"),
            SubtitleEvent(id=2, start_ms=1000, end_ms=2000, style="Default", original_text="Let us go!"),
        ],
    )
    mock_provider.chat_completion.return_value = ChatResponse(content="[1] الحلقة 1: البداية\n[2] لننطلق!", model="mock")
    await engine.translate_document(
        doc2, mock_provider, "mock-model",
        healing_options=opts_enabled,
        use_cache=False, force_fresh=True,
    )
    assert "الحلقة" in (doc2.events[0].translated_text or "")

    panel.deleteLater()
    qapp.processEvents()


# ---------------------------------------------------------------------------
# Bug #3: Full CharacterProfile metadata preserved in UI -> Resolver -> Prompt Context
# ---------------------------------------------------------------------------
def test_bug3_character_metadata_preserved_end_to_end(qapp):
    from app.character.resolver import CharacterResolver
    from app.ui.windows.main_window import MainWindow

    win = MainWindow()
    prof = CharacterProfile(
        canonical_name="Edward Elric",
        first_name="Edward",
        last_name="Elric",
        native_name="エドワード・エルリック",
        arabic_name="إدوارد إلريك",
        aliases=["Fullmetal", "Ed"],
        gender_info=GenderInfo(gender=GenderEnum.MALE, confidence=1.0, source="AniList"),
        role="MAIN",
        speech_style="Confident, hot-headed, informal",
        translation_notes="Never call him short politely.",
    )
    win.character_panel.add_character(
        prof.canonical_name, prof.arabic_name, prof.gender.value, 1.0, "AniList", profile=prof
    )

    selected = win.character_panel.get_selected_character()
    assert selected["aliases"] == ["Fullmetal", "Ed"]
    assert selected["style"] == "Confident, hot-headed, informal"
    assert selected["notes"] == "Never call him short politely."

    # Update via MainWindow handler (simulating CharacterEditorDialog.save())
    win._on_character_updated({
        "row": 0,
        "canonical": "Edward Elric",
        "japanese": "エドワード・エルリック",
        "arabic": "إدوارد إلريك",
        "gender": "Male",
        "aliases": ["Fullmetal", "Ed", "Chief"],
        "style": "Direct and sarcastic",
        "notes": "Always masculine pronouns.",
    })

    chars = win.character_panel.get_characters()
    assert len(chars) == 1
    c = chars[0]
    assert c.first_name == "Edward"
    assert c.last_name == "Elric"
    assert c.role == "MAIN"
    assert c.aliases == ["Fullmetal", "Ed", "Chief"]
    assert c.speech_style == "Direct and sarcastic"
    assert c.translation_notes == "Always masculine pronouns."

    resolver = CharacterResolver(chars)
    assert resolver.resolve_speaker("Ed") is not None
    assert resolver.resolve_speaker("Edward") is not None

    prompt_ctx = format_character_context(chars, target_lang="ar")
    assert "Aliases: Fullmetal, Ed, Chief" in prompt_ctx
    assert "Style: Direct and sarcastic" in prompt_ctx
    assert "Notes: Always masculine pronouns." in prompt_ctx

    win.close()
    win.deleteLater()
    qapp.processEvents()


# ---------------------------------------------------------------------------
# Bug #4: Healer prevents forced transliteration of tech brands & English artifacts
# ---------------------------------------------------------------------------
def test_bug4_healer_preserves_tech_brands_and_avoids_blind_transliteration():
    healed_brands = SubtitleHealer.clean_stray_latin_and_fillers("أستخدم YouTube على iPhone عبر WiFi")
    assert "YouTube" in healed_brands
    assert "iPhone" in healed_brands
    assert "WiFi" in healed_brands

    # Lowercase non-vocative English word should NOT become Arabic phonetic transliteration
    healed_lower = SubtitleHealer.clean_stray_latin_and_fillers("أنا sorry حقاً")
    assert "سوري" not in healed_lower

    # Bilingual \N lines remain clean without corrupting English segment
    healed_bilingual = SubtitleHealer.heal("Hello world\\Nمرحباً بالعالم", "Hello world")
    assert "Hello world" in healed_bilingual
    assert "مرحباً بالعالم" in healed_bilingual

    # True vocative / known character names ARE transliterated
    healed_name = SubtitleHealer.clean_stray_latin_and_fillers("أين ذهب Levi اليوم؟", known_names={"Levi"})
    assert "ليفي" in healed_name

    healed_voc = SubtitleHealer.clean_stray_latin_and_fillers("يا Eren أنتبه!")
    assert "إيرين" in healed_voc


# ---------------------------------------------------------------------------
# Bug #5: English Target Language supported dynamically across Prompt, Validator, Healer & Engine
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_bug5_english_target_language_pipeline(tmp_path):
    pb = PromptBuilder()
    msgs = pb.build_prompt(
        source_lang="Japanese",
        target_lang="English",
        current_subtitles="[1] こんにちは",
    )
    sys_msg = msgs[0].content
    assert "English" in sys_msg
    assert "Modern Standard Arabic" not in sys_msg

    imp_msgs = pb.build_improvement_prompt(
        source_lang="Japanese",
        target_lang="English",
        current_subtitles="[1] Hello",
    )
    assert "English" in imp_msgs[0].content
    assert "Modern Standard Arabic" not in imp_msgs[0].content

    ev = SubtitleEvent(id=1, start_ms=0, end_ms=2000, original_text="こんにちは、元気ですか？")
    validator = PipelineValidator()
    ok, issues = validator.validate_batch_output({1: "Hello, how are you?"}, [ev], target_lang="English")
    assert ok is True
    assert issues == []

    # Healer must keep ASCII punctuation (comma / question mark) when target is English
    healed_en = SubtitleHealer.heal(
        "Hello, how are you?",
        ev.original_text,
        options={"target_lang": "English", "arabic_punct": True, "latin_clean": True},
    )
    assert healed_en == "Hello, how are you?"
    assert "؟" not in healed_en
    assert "،" not in healed_en

    doc = SubtitleDocument(format=SubtitleFormat.ASS, events=[ev])
    mock_provider = AsyncMock()
    mock_provider.chat_completion.return_value = ChatResponse(content="[1] Hello, how are you?", model="mock")
    engine = TranslationEngine()
    await engine.translate_document(
        doc, mock_provider, "mock-model",
        source_lang="Japanese", target_lang="English",
        use_cache=False, force_fresh=True,
    )
    assert doc.events[0].translated_text == "Hello, how are you?"

    out_path = tmp_path / "en_out.ass"
    write_subtitle(doc, str(out_path))
    content = out_path.read_text(encoding="utf-8")
    assert "Hello, how are you?" in content


# ---------------------------------------------------------------------------
# Bug #6: Incremental batch updates emit targeted dataChanged spans, never layoutChanged
# ---------------------------------------------------------------------------
def test_bug6_incremental_table_model_no_layout_changed(qapp):
    from app.ui.models.subtitle_table_model import SubtitleTableModel

    model = SubtitleTableModel()
    events = [SubtitleEvent(id=i, start_ms=i * 1000, end_ms=i * 1000 + 800, original_text=f"Line {i}") for i in range(1, 7)]
    model.set_events(events)

    layout_signals = []
    data_spans = []
    model.layoutChanged.connect(lambda: layout_signals.append(True))
    model.dataChanged.connect(lambda tl, br, roles=None: data_spans.append((tl.row(), br.row(), tl.column(), br.column())))

    model.set_batch_status([1, 2, 3, 5], "Done")
    assert len(layout_signals) == 0
    assert data_spans == [(0, 2, 5, 6), (4, 4, 5, 6)]


# ---------------------------------------------------------------------------
# Bug #7: Batch Folder source preservation, .ara routing on improve, and safe _new_session
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_bug7_batch_folder_and_new_session_preserves_db(qapp, tmp_path):
    from app.ui.windows.main_window import MainWindow

    ep1 = tmp_path / "ep01.ass"
    ep2 = tmp_path / "ep02.ass"
    ep1_ara = tmp_path / "ep01.ara.ass"
    ep2_ara = tmp_path / "ep02.ara.ass"
    sample_ass = "[Script Info]\nTitle: Ep\n[Events]\nDialogue: 0,0:00:01.00,0:00:03.00,Default,,0,0,0,,Hello\n"
    ep1.write_text(sample_ass, encoding="utf-8")
    ep2.write_text(sample_ass, encoding="utf-8")
    ep1_ara.write_text(sample_ass.replace("Hello", "مرحباً ١"), encoding="utf-8")
    ep2_ara.write_text(sample_ass.replace("Hello", "مرحباً ٢"), encoding="utf-8")

    win = MainWindow()
    await win._load_subtitle_files_async([str(ep1), str(ep2)], auto_start_processing=False)
    assert win.source_files == [str(ep1), str(ep2)]

    win.output_files[str(ep1)] = str(ep1_ara)
    win.output_files[str(ep2)] = str(ep2_ara)

    # Save on ep1 must keep source_files untouched
    win._save_file_auto(str(ep1), source_key=str(ep1))
    assert win.source_files == [str(ep1), str(ep2)]
    assert win.output_files[str(ep1)] == str(ep1_ara)

    # Seed TM and confirm _new_session preserves persistent DB tables
    tm = TranslationMemoryRepository(win.db)
    tm.save_translation("Hello my dear friend", "مرحباً يا صديقي العزيز", "en", "ar")
    assert tm.lookup("Hello my dear friend", "en", "ar") == "مرحباً يا صديقي العزيز"

    win._new_session()
    assert win.source_files == []
    assert win.output_files == {}
    assert tm.lookup("Hello my dear friend", "en", "ar") == "مرحباً يا صديقي العزيز"

    win.close()
    win.deleteLater()
    qapp.processEvents()


# ---------------------------------------------------------------------------
# Bug #8: Complete Undo/Redo for Inline Editor, Merge Lines, and Split Line
# ---------------------------------------------------------------------------
def test_bug8_undo_redo_inline_merge_and_split(qapp, tmp_path):
    from app.ui.windows.main_window import MainWindow

    sub_file = tmp_path / "undo_test.ass"
    win = MainWindow()
    win.current_file_path = str(sub_file)
    events = [
        SubtitleEvent(id=1, start_ms=1000, end_ms=3000, speaker="A", original_text="First line", translated_text="السطر الأول"),
        SubtitleEvent(id=2, start_ms=3500, end_ms=5500, speaker="B", original_text="Second line", translated_text="السطر الثاني"),
    ]
    win.document = SubtitleDocument(format=SubtitleFormat.ASS, events=events)
    win.table_model.set_events(win.document.events)
    win.table_view.selectRow(0)
    win.inline_editor.load_event(0, win.document.events[0], 2)

    # 1. Inline edit + flush commit -> Undo -> Redo
    win.inline_editor.edit_trans.setPlainText("السطر المعدّل")
    assert win.document.events[0].translated_text == "السطر المعدّل"
    win.inline_editor.commit_pending_edit()
    assert win.undo_stack.canUndo()

    win._on_undo()
    assert win.document.events[0].translated_text == "السطر الأول"
    assert win.inline_editor.edit_trans.toPlainText() == "السطر الأول"

    win._on_redo()
    assert win.document.events[0].translated_text == "السطر المعدّل"

    # 2. Structural Merge -> Undo -> Redo
    win.table_view.selectAll()
    win._merge_selected_lines()
    assert len(win.document.events) == 1
    assert len(win.table_model.events) == 1

    win._on_undo()
    assert len(win.document.events) == 2
    assert len(win.table_model.events) == 2
    assert win.document.events[0].original_text == "First line"

    win._on_redo()
    assert len(win.document.events) == 1

    # 3. Structural Split -> Undo -> Redo
    win.undo_stack.clear()
    win._on_undo()  # no-op
    win.table_model.events[0].end_time = "0:00:05.50"
    win.table_view.selectRow(0)
    win._split_selected_line()
    assert len(win.document.events) == 2

    win._on_undo()
    assert len(win.document.events) == 1

    win.close()
    win.deleteLater()
    qapp.processEvents()


# ---------------------------------------------------------------------------
# Bug #9: Cross-thread EventBus.emit_log_safe & backend logger decoupling
# ---------------------------------------------------------------------------
def test_bug9_cross_thread_logging_safe(qapp):
    from app.core.logging import get_logger
    from app.ui.bus import EventBus

    received = []
    bus = EventBus.instance()
    bus.log_message.connect(received.append)
    try:
        def worker():
            EventBus.emit_log_safe("worker-thread-safe-msg")
            get_logger("test.worker").warning("worker-logger-msg")

        t = threading.Thread(target=worker)
        t.start()
        t.join(timeout=5)
        for _ in range(10):
            qapp.processEvents()
        assert "worker-thread-safe-msg" in received
        assert any("worker-logger-msg" in m for m in received)
    finally:
        bus.log_message.disconnect(received.append)


# ---------------------------------------------------------------------------
# Bug #10, #11, #12, #14: AppData portability, PyInstaller spec/resources, workspace cleanliness
# ---------------------------------------------------------------------------
def test_bug10_11_12_14_packaging_appdata_and_workspace(monkeypatch, tmp_path):
    import os

    # Portable mode vs %APPDATA%
    fake_base = tmp_path / "app_dir"
    fake_file = fake_base / "app" / "core" / "resources.py"
    fake_file.parent.mkdir(parents=True, exist_ok=True)
    fake_file.write_text("", encoding="utf-8")
    portable_flag = fake_base / "portable.flag"
    portable_flag.write_text("", encoding="utf-8")

    monkeypatch.setattr(sys, "frozen", False, raising=False)
    monkeypatch.setattr(resources_mod, "__file__", str(fake_file))
    assert get_app_data_dir() == fake_base

    portable_flag.unlink()
    appdata_dir = tmp_path / "roaming"
    monkeypatch.setenv("APPDATA", str(appdata_dir))
    resolved = get_app_data_dir()
    assert resolved == appdata_dir / "SubNovaStudio"
    assert resolved.exists()

    # Packaging spec & dependencies check
    root_dir = Path(__file__).resolve().parent.parent
    spec_text = (root_dir / "SubNovaStudio.spec").read_text(encoding="utf-8")
    assert "app/resources" in spec_text
    assert "PySide6.QtMultimedia" in spec_text
    assert "subnova_icon.ico" in spec_text

    req_text = (root_dir / "requirements.txt").read_text(encoding="utf-8").lower()
    assert "charset-normalizer" in req_text

    assert (root_dir / ".gitignore").exists()
    assert (root_dir / "scripts" / "dev").is_dir()
    # Restore real __file__ implicitly via monkeypatch teardown or check directly via root_dir
    assert (root_dir / "app" / "resources" / "icons" / "subnova_icon.ico").exists()


# ---------------------------------------------------------------------------
# Bug #13: Gemini & OpenAI single-hop 429 fallback guard (no infinite recursion)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_bug13_provider_429_single_hop_fallback_guard():
    # Gemini provider: pro hits 429 -> single fallback to gemini-2.5-flash with params preserved -> then raises ProviderError
    gem = GeminiProvider(ProviderConfig(provider_type=ProviderType.GEMINI, api_key="k", model_name="gemini-2.5-pro"))
    gem_payloads = []

    async def fake_gem_post(url, json=None, headers=None, **kwargs):
        gem_payloads.append(dict(json or {}))
        resp = MagicMock()
        resp.status_code = 429
        resp.text = "rate limit"
        return resp

    gem_client = await gem.get_client()
    gem_client.post = fake_gem_post
    with pytest.raises(ProviderError, match="Rate Limit"):
        await gem.chat_completion([], model="gemini-2.5-pro", temperature=0.33, max_tokens=222, top_p=0.91)
    assert [p["model"] for p in gem_payloads] == ["gemini-2.5-pro", "gemini-2.5-flash"]
    assert gem_payloads[1]["temperature"] == 0.33
    assert gem_payloads[1]["max_tokens"] == 222
    assert gem_payloads[1]["top_p"] == 0.91
    await gem.close()

    # OpenAI provider: gpt-4o hits 429 -> single fallback to gpt-4o-mini with params preserved -> then raises ProviderError
    oa = OpenAIProvider(ProviderConfig(provider_type=ProviderType.OPENAI, api_key="k", model_name="gpt-4o"))
    oa_payloads = []

    async def fake_oa_post(url, json=None, headers=None, **kwargs):
        oa_payloads.append(dict(json or {}))
        resp = MagicMock()
        resp.status_code = 429
        resp.text = "rate limit"
        return resp

    oa_client = await oa.get_client()
    oa_client.post = fake_oa_post
    with pytest.raises(ProviderError, match="Rate Limit"):
        await oa.chat_completion([], model="gpt-4o", temperature=0.25, max_tokens=333, top_p=0.88)
    assert [p["model"] for p in oa_payloads] == ["gpt-4o", "gpt-4o-mini"]
    assert oa_payloads[1]["temperature"] == 0.25
    assert oa_payloads[1]["max_tokens"] == 333
    assert oa_payloads[1]["top_p"] == 0.88
    await oa.close()
