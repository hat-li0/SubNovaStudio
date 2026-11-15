from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QTabWidget, QMenuBar, QMenu, QScrollArea, QFrame, QMessageBox, QLabel,
    QPushButton, QApplication
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QDragEnterEvent, QDropEvent, QIcon, QUndoStack, QKeySequence, QShortcut
from app.ui.widgets.file_panel import FilePanel
from app.ui.widgets.provider_panel import ProviderPanel
from app.ui.widgets.settings_panel import SettingsPanel
from app.ui.widgets.healing_panel import HealingPanel
from app.ui.widgets.character_panel import CharacterPanel
from app.ui.widgets.subtitle_table import SubtitleTableView
from app.ui.widgets.progress_panel import ProgressPanel
from app.ui.widgets.log_panel import LogPanel
from app.ui.widgets.live_preview_widget import LivePreviewWidget
from app.ui.widgets.video_player_widget import SubNovaVideoPlayerWidget
from app.ui.widgets.find_replace_bar import FindReplaceBar
from app.ui.widgets.inline_editor_widget import InlineSubtitleEditor
from app.ui.models.subtitle_table_model import SubtitleTableModel
from app.ui.dialogs.character_editor import CharacterEditorDialog
from app.ui.dialogs.glossary_editor import GlossaryEditorDialog
from app.ui.dialogs.anime_search import AnimeSearchDialog
from app.ui.dialogs.review_dialog import TranslationReviewDialog
from app.ui.dialogs.video_track_selector import VideoTrackSelectorDialog
from app.ui.dialogs.progress_dialog import ExtractionProgressDialog
from app.ui.dialogs.about_dialog import AboutDialog
from app.ui.dialogs.timing_dialog import ShiftTimingsDialog
from app.ui.commands import EditCellCommand, EditRowCommand, ShiftTimingsCommand, SnapshotEventsCommand
from app.ui.bus import EventBus
from app.subtitle import parse_subtitle, write_subtitle
from app.subtitle.video_extractor import VideoSubtitleExtractor
from app.translation.engine import TranslationEngine
from app.translation.batcher import TokenBatcher
from app.storage.memory_repo import TranslationMemoryRepository
from app.storage.glossary_repo import GlossaryRepository
from app.storage.checkpoint import CheckpointManager
from app.providers import get_provider
from app.core.database import DatabaseManager
from app.anime.metadata_service import AnimeMetadataService
from app.quality.healer import SubtitleHealer
from app.core.language_detector import LanguageDetector
from app.core.resources import resource_path
from app.models.subtitle import SubtitleEvent
from typing import List, Optional, Dict, Any
import asyncio
from copy import deepcopy
import os
import tempfile
from pathlib import Path

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SubNova Studio — استوديو سوب نوفا | المترجم والمدقق الخارق للشاشة")
        self.setMinimumSize(1260, 860)
        self.setAcceptDrops(True)

        # Set window icon with dynamic asset resolution
        icon_path = resource_path(os.path.join("app", "resources", "icons", "subnova_icon.ico"))
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        
        self.document = None
        self.current_file_path = None
        self.selected_files = []
        self.source_files = []
        self.output_files = {}
        self.source_video_origin = {}
        self.db = DatabaseManager()
        self.glossary_repo = GlossaryRepository(self.db)
        self.current_anime_id = None
        self.glossary_entries = self.glossary_repo.get_all_for_anime(None)
        self._inline_pre_edit_status = {}
        self.metadata_service = AnimeMetadataService(self.db)
        self._translation_task = None
        
        # Video extraction & Language detection state
        self.video_origin_map = {}  # Map: temp_extracted_file_path -> original_video_path
        self.temp_extracted_files = set()  # Set of temp file paths to clean up
        self.detected_source_lang = None
        self.stream_lang_code = None
        self.is_fresh_session = True
        
        # Central widget and main layout
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(6)
        
        # Splitter (Left Controls vs Right Studio Canvas)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        main_layout.addWidget(splitter)
        
        # Left Panel (Controls & Tabbed Settings)
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(6, 6, 12, 6)
        left_layout.setSpacing(8)
        left_panel.setMinimumWidth(400)
        
        # Top Card: File & Video Import Actions
        self.file_panel = FilePanel()
        left_layout.addWidget(self.file_panel)
        
        # Main Tabbed Controls (Anchored Tab Bar, individual scrollable tabs)
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)

        self.provider_panel = ProviderPanel()
        self.healing_panel = HealingPanel()
        self.settings_panel = SettingsPanel()
        self.character_panel = CharacterPanel()

        self.tabs.addTab(self.provider_panel, "🤖 المزود")
        self.tabs.addTab(self.healing_panel, "🛡️ التنقية")
        self.tabs.addTab(self.settings_panel, "⚙️ الإعدادات")
        self.tabs.addTab(self.character_panel, "🎭 الشخصيات")

        self.tabs.setTabToolTip(0, "🤖 مزود الذكاء الاصطناعي واختيار النموذج (LM Studio, Ollama, Gemini, OpenAI)")
        self.tabs.setTabToolTip(1, "🛡️ محرك التنقية الذاتي وحصانة وسوم ASS وملاحظات السياق")
        self.tabs.setTabToolTip(2, "⚙️ إعدادات لغات الترجمة وحجم الدفعات والحرارة والتزامن")
        self.tabs.setTabToolTip(3, "🎭 جدول إدارة وتعديل أسماء وأجناس الشخصيات")
        
        # Two-way sync for max_context and parallel/concurrency between ProviderPanel and SettingsPanel
        self.provider_panel.sb_max_context.valueChanged.connect(self.settings_panel.sb_max_context.setValue)
        self.settings_panel.sb_max_context.valueChanged.connect(self.provider_panel.sb_max_context.setValue)
        self.provider_panel.sb_parallel.valueChanged.connect(self.settings_panel.sb_concurrency.setValue)
        self.settings_panel.sb_concurrency.valueChanged.connect(self.provider_panel.sb_parallel.setValue)
        
        left_layout.addWidget(self.tabs, 1)
        
        # Right Panel (The Main Workspace)
        right_panel = QWidget()
        right_panel.setMinimumWidth(560)
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(4, 4, 4, 4)
        right_layout.setSpacing(6)

        # Undo Stack
        self.undo_stack = QUndoStack(self)
        self._is_undo_redo_active = False

        # 1. Media Player Toggle Bar (Always visible at top of right panel)
        self.btn_toggle_video = QPushButton("🎬 مشغل الوسائط والمعاينة الحية (طافي لتوفير موارد الجهاز - اضغط للفتح)")
        self.btn_toggle_video.setFixedHeight(28)
        self.btn_toggle_video.setCursor(Qt.PointingHandCursor)
        self.btn_toggle_video.setStyleSheet("""
            QPushButton {
                background-color: #18181b;
                color: #94a3b8;
                font-weight: 600;
                font-size: 8.5pt;
                border: 1px solid #27272a;
                border-radius: 5px;
                padding: 3px 12px;
            }
            QPushButton:hover {
                background-color: #27272a;
                color: #38bdf8;
                border-color: #0284c7;
            }
        """)
        self.btn_toggle_video.clicked.connect(self._toggle_video_player)

        # 2. Collapsible Video Player Container (Completely unloaded & off by default)
        self.video_container = QWidget()
        v_layout = QVBoxLayout(self.video_container)
        v_layout.setContentsMargins(0, 0, 0, 0)
        v_layout.setSpacing(2)

        self.video_player = SubNovaVideoPlayerWidget()
        v_layout.addWidget(self.video_player)
        self.video_container.setVisible(False)
        self.current_video_file = None

        # Find and Replace Bar (Ctrl+F)
        self.find_replace_bar = FindReplaceBar()
        self.find_replace_bar.setVisible(False)

        # Subtitle Table View & Inline Editor Container
        table_container = QWidget()
        t_layout = QVBoxLayout(table_container)
        t_layout.setContentsMargins(0, 0, 0, 0)
        t_layout.setSpacing(4)

        t_layout.addWidget(self.find_replace_bar)

        # Table Controls Toolbar
        tbl_toolbar = QHBoxLayout()
        tbl_toolbar.setContentsMargins(2, 2, 2, 2)
        tbl_toolbar.setSpacing(6)

        self.btn_toggle_fx = QPushButton("🛡️ إخفاء أسطر المؤثرات (FX)")
        self.btn_toggle_fx.setCheckable(True)
        self.btn_toggle_fx.setChecked(False)
        self.btn_toggle_fx.setFixedHeight(26)
        self.btn_toggle_fx.setStyleSheet("""
            QPushButton {
                background-color: #1e293b;
                color: #e2e8f0;
                font-weight: 600;
                font-size: 8.5pt;
                border: 1px solid #334155;
                border-radius: 4px;
                padding: 3px 10px;
            }
            QPushButton:hover {
                background-color: #334155;
                color: #ffffff;
                border-color: #6366f1;
            }
            QPushButton:checked {
                background-color: #4f46e5;
                color: #ffffff;
                border-color: #818cf8;
            }
        """)
        self.btn_toggle_fx.setToolTip("إخفاء أسطر المؤثرات البصرية والتايبست والكاراوكي لعرض الحوار فقط (Ctrl+H)")
        self.btn_toggle_fx.clicked.connect(self._toggle_hide_effects)
        tbl_toolbar.addWidget(self.btn_toggle_fx)

        self.lbl_table_filter_stats = QLabel("")
        self.lbl_table_filter_stats.setStyleSheet("color: #94a3b8; font-size: 8pt; font-weight: 500;")
        tbl_toolbar.addWidget(self.lbl_table_filter_stats)

        tbl_toolbar.addStretch()

        self.btn_sync_timing = QPushButton("⏱️ ضبط التوقيت (Ctrl+T)")
        self.btn_sync_timing.setFixedHeight(26)
        self.btn_sync_timing.setStyleSheet("""
            QPushButton {
                background-color: #1e293b;
                color: #38bdf8;
                font-size: 8.5pt;
                font-weight: 600;
                border: 1px solid #0284c7;
                border-radius: 4px;
                padding: 3px 8px;
            }
            QPushButton:hover {
                background-color: #0369a1;
                color: #ffffff;
            }
        """)
        self.btn_sync_timing.clicked.connect(self._open_shift_timings_dialog)
        tbl_toolbar.addWidget(self.btn_sync_timing)

        self.btn_open_find = QPushButton("🔍 بحث (Ctrl+F)")
        self.btn_open_find.setFixedHeight(26)
        self.btn_open_find.setStyleSheet("""
            QPushButton {
                background-color: #1e293b;
                color: #94a3b8;
                font-size: 8.5pt;
                border: 1px solid #334155;
                border-radius: 4px;
                padding: 3px 8px;
            }
            QPushButton:hover {
                background-color: #334155;
                color: #f8fafc;
            }
        """)
        self.btn_open_find.clicked.connect(self._toggle_find_bar)
        tbl_toolbar.addWidget(self.btn_open_find)

        t_layout.addLayout(tbl_toolbar)

        self.table_model = SubtitleTableModel()
        self.table_view = SubtitleTableView()
        self.table_view.setModel(self.table_model)
        self.table_view.setMinimumHeight(240)
        t_layout.addWidget(self.table_view, 1)

        self.inline_editor = InlineSubtitleEditor()
        t_layout.addWidget(self.inline_editor)

        # Collapsible Live Preview Card
        self.live_preview = LivePreviewWidget()

        # Log Panel
        self.log_panel = LogPanel()
        self.log_panel.setMinimumHeight(120)
        self.log_panel.expand_toggled.connect(self._on_log_expand_toggled)

        # Vertical splitter for Table Area and Log
        self.v_splitter = QSplitter(Qt.Orientation.Vertical)
        self.v_splitter.setChildrenCollapsible(False)
        self.v_splitter.addWidget(table_container)
        self.v_splitter.addWidget(self.log_panel)
        self.v_splitter.setCollapsible(0, False)
        self.v_splitter.setCollapsible(1, False)
        self.v_splitter.setStretchFactor(0, 4)
        self.v_splitter.setStretchFactor(1, 1)
        self.v_splitter.setSizes([450, 180])

        # Bottom Action Bar
        self.progress_panel = ProgressPanel()

        right_layout.addWidget(self.btn_toggle_video)
        right_layout.addWidget(self.video_container)
        right_layout.addWidget(self.v_splitter, 1)
        right_layout.addWidget(self.live_preview)
        right_layout.addWidget(self.progress_panel)
        
        # Add to main splitter
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setCollapsible(0, False)
        splitter.setCollapsible(1, False)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([460, 840])
        
        self._setup_menus()
        self._setup_status_bar()
        self._setup_events()

    def _setup_status_bar(self):
        status_bar = self.statusBar()
        status_bar.setStyleSheet("QStatusBar { background-color: #111827; border-top: 1px solid #1f2937; color: #9ca3af; }")
        
        lbl_brand_status = QLabel("SubNova Studio v2.0 | تم التطوير بواسطة: حاتم الحربي (Hatim Alharbi) © 2026")
        lbl_brand_status.setStyleSheet("color: #38bdf8; font-size: 8pt; font-weight: 600; padding: 0 8px;")
        status_bar.addPermanentWidget(lbl_brand_status)
        
    def _setup_events(self):
        EventBus.instance().file_selected.connect(self._on_file_selected)
        EventBus.instance().files_cleared.connect(self._new_session)
        EventBus.instance().translation_started.connect(self._on_translation_started)
        EventBus.instance().improvement_started.connect(self._on_improvement_started)
        EventBus.instance().translation_cancelled.connect(self._on_cancel_requested)
        EventBus.instance().character_updated.connect(self._on_character_updated)
        self.progress_panel.quick_heal_requested.connect(self._on_quick_heal_requested)
        
        # Connect panel buttons to dialogs
        self.character_panel.btn_search.clicked.connect(self._open_anime_search)
        self.character_panel.btn_add.clicked.connect(self._open_char_add)
        self.character_panel.btn_edit.clicked.connect(self._open_char_editor)

        # Connect Undo/Redo callback from direct table cell edits
        self.table_model.on_data_changed_callback = self._on_table_data_changed_for_undo

        # Connect Table selection change to Inline Editor and Video Player
        self.table_view.selectionModel().currentRowChanged.connect(self._on_table_row_changed)

        # Connect Inline Editor actions
        self.inline_editor.line_updated.connect(self._on_inline_editor_updated)
        self.inline_editor.line_committed.connect(self._on_inline_editor_committed)
        self.inline_editor.nav_previous_requested.connect(self._on_nav_previous)
        self.inline_editor.nav_next_requested.connect(self._on_nav_next)
        self.inline_editor.play_in_video_requested.connect(self._on_play_line_in_video)

        # Connect Find and Replace Bar
        self.find_replace_bar.find_next_requested.connect(self._on_find_next)
        self.find_replace_bar.replace_requested.connect(self._on_replace_current)
        self.find_replace_bar.replace_all_requested.connect(self._on_replace_all)

        # Connect Table Custom Context Menu
        self.table_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table_view.customContextMenuRequested.connect(self._show_table_context_menu)

        # Shortcuts
        self._sc_undo = QShortcut(QKeySequence("Ctrl+Z"), self)
        self._sc_undo.activated.connect(self._on_undo)
        self._sc_redo = QShortcut(QKeySequence("Ctrl+Y"), self)
        self._sc_redo.activated.connect(self._on_redo)
        self._sc_redo2 = QShortcut(QKeySequence("Ctrl+Shift+Z"), self)
        self._sc_redo2.activated.connect(self._on_redo)
        self._sc_find = QShortcut(QKeySequence("Ctrl+F"), self)
        self._sc_find.activated.connect(self._toggle_find_bar)
        self._sc_toggle_fx = QShortcut(QKeySequence("Ctrl+H"), self)
        self._sc_toggle_fx.activated.connect(self.btn_toggle_fx.click)
        self._sc_shift_timing = QShortcut(QKeySequence("Ctrl+T"), self)
        self._sc_shift_timing.activated.connect(self._open_shift_timings_dialog)

        # Connect model reset to auto-reapply effect visibility filter
        self.table_model.modelReset.connect(lambda: self.apply_effects_filter(self.btn_toggle_fx.isChecked()))

    def _on_log_expand_toggled(self, is_expanded: bool):
        if is_expanded:
            self.v_splitter.setSizes([160, 480])
        else:
            self.v_splitter.setSizes([420, 220])

    def _on_cancel_requested(self):
        if self._translation_task and not self._translation_task.done():
            self._translation_task.cancel()
            EventBus.instance().log_message.emit("🛑 تم إرسال طلب إلغاء المعالجة / Cancellation requested.")

    def _on_character_updated(self, data: dict):
        row = data.get("row")
        canonical = data.get("canonical", "")
        arabic = data.get("arabic", "")
        gender = data.get("gender", "Unknown")
        japanese = data.get("japanese", "")
        aliases = data.get("aliases", [])
        style = data.get("style", "")
        notes = data.get("notes", "")
        if row is not None and row >= 0:
            self.character_panel.update_character_row(
                row, canonical, arabic, gender, "1.0", "User Override",
                japanese=japanese, aliases=aliases, style=style, notes=notes,
            )
        else:
            self.character_panel.add_character(
                canonical, arabic, gender, 1.0, "User Added",
                japanese=japanese, aliases=aliases, style=style, notes=notes,
            )
        EventBus.instance().log_message.emit(f"Updated character: {canonical} ({arabic}) - {gender}")

    def _show_msg_box_safe(self, box_type: str, title: str, text: str):
        """Safely display a message box via QTimer to prevent nested Qt event loop clashes in asyncio."""
        def _do_show():
            if box_type == "warning":
                QMessageBox.warning(self, title, text)
            elif box_type == "critical":
                QMessageBox.critical(self, title, text)
            else:
                QMessageBox.information(self, title, text)
        QTimer.singleShot(0, _do_show)

    async def _exec_dialog_async(self, dlg) -> int:
        """Await a modal QDialog without nested dlg.exec() loops under qasync."""
        loop = asyncio.get_running_loop()
        fut = loop.create_future()

        def _on_finished(result: int):
            if not fut.done():
                fut.set_result(result)

        dlg.finished.connect(_on_finished)
        dlg.open()
        try:
            return await fut
        finally:
            try:
                dlg.finished.disconnect(_on_finished)
            except Exception:
                pass

    def _on_file_selected(self, file_paths: list):
        if not file_paths:
            return
        try:
            loop = asyncio.get_running_loop()
            if loop.is_running():
                loop.create_task(self._process_incoming_files_async(file_paths))
                return
        except RuntimeError:
            pass
        asyncio.run(self._process_incoming_files_async(file_paths))

    async def _process_incoming_files_async(self, file_paths: list):
        self.provider_panel.pause_auto_detect()
        dlg = ExtractionProgressDialog(self, title="SubNova Studio — جاري استيراد ومعالجة الملفات", initial_msg="🎬 جاري فحص ملفات الترجمة والفيديو...")
        dlg.show()

        try:
            video_files = [f for f in file_paths if VideoSubtitleExtractor.is_video_file(f)]
            subtitle_files = [f for f in file_paths if not VideoSubtitleExtractor.is_video_file(f)]

            auto_start = False
            final_subtitle_paths = list(subtitle_files)

            if video_files:
                temp_dir = os.path.join(tempfile.gettempdir(), "unlimited_subs_extracted")
                os.makedirs(temp_dir, exist_ok=True)

                if len(video_files) == 1 and not subtitle_files:
                    v_path = video_files[0]
                    self.current_video_file = v_path
                    v_name = os.path.basename(v_path)
                    self.btn_toggle_video.setText(f"🎬 مشغل الوسائط جاهز: {v_name} (طافي لتوفير الأداء - اضغط للفتح)")
                    self.btn_toggle_video.setStyleSheet("background: #18181b; color: #38bdf8; font-weight: 600; font-size: 8.5pt; border: 1px solid #0284c7; border-radius: 5px; padding: 4px 12px;")
                    dlg.set_status("🔍 فحص مسارات الترجمة المدمجة...", v_name)
                    EventBus.instance().log_message.emit(f"🔍 فحص مسارات الترجمة المدمجة داخل الفيديو: {v_name}...")
                    
                    streams = await asyncio.to_thread(VideoSubtitleExtractor.probe_subtitle_streams, v_path)
                    if not streams:
                        dlg.close()
                        self._show_msg_box_safe("warning", "تنبيه", f"لا يوجد أي مسار ترجمة مدمج داخل ملف الفيديو:\n{v_name}")
                        EventBus.instance().log_message.emit(f"⚠️ No embedded subtitle streams found in {v_name}")
                        return
                    
                    rec_stream = VideoSubtitleExtractor.select_best_stream(streams, self.settings_panel.get_source_lang_clean())
                    chosen_idx = rec_stream.index if rec_stream else 0
                    self.stream_lang_code = rec_stream.language if rec_stream else None
                    auto_start = True
                    prefer_ass = True

                    stream_title = f" «{rec_stream.title}»" if rec_stream and rec_stream.title else ""
                    lang_code = rec_stream.language.upper() if rec_stream and rec_stream.language else "ENG"
                    codec_code = rec_stream.codec_name.upper() if rec_stream and rec_stream.codec_name else "ASS"
                    lines_info = f" ({rec_stream.frame_count} سطر)" if rec_stream and getattr(rec_stream, "frame_count", 0) > 0 else ""
                    EventBus.instance().log_message.emit(
                        f"🎬 تم تحديد أفضل مسار حوار تلقائياً بدون توقف: [المسار {chosen_idx + 1}] [{lang_code}] ({codec_code}){stream_title}{lines_info}"
                    )

                    temp_out_path = os.path.join(temp_dir, f"{Path(v_path).stem}_raw.ass")
                    dlg.set_status("🎬 جاري استخراج مسار الترجمة وحفظ تنسيقات Aegisub...", f"المسار {chosen_idx + 1} ({codec_code})")
                    EventBus.instance().log_message.emit("🎬 جاري استخراج الترجمة مؤقتاً للمعالجة مع حفظ كامل تنسيقات Aegisub...")
                    
                    ok, out_path, err = await asyncio.to_thread(
                        VideoSubtitleExtractor.extract_subtitle, v_path, chosen_idx, output_path=temp_out_path, prefer_ass=prefer_ass
                    )
                    if not ok:
                        dlg.close()
                        self._show_msg_box_safe("critical", "خطأ في الاستخراج", f"فشل استخراج الترجمة من الفيديو:\n{err}")
                        return
                    self.video_origin_map[out_path] = v_path
                    self.temp_extracted_files.add(out_path)
                    final_subtitle_paths.append(out_path)
                    EventBus.instance().log_message.emit("✅ تم تجهيز مسار الترجمة مؤقتاً لبدء المعالجة التلقائية.")
                else:
                    for i, v_path in enumerate(video_files):
                        v_name = os.path.basename(v_path)
                        dlg.set_status(f"🎬 جاري استخراج مسار الحوار ({i+1}/{len(video_files)})...", v_name)
                        EventBus.instance().log_message.emit(f"🎬 جاري استخراج مسار الحوار مؤقتاً من: {v_name}...")
                        temp_out_path = os.path.join(temp_dir, f"{Path(v_path).stem}_raw.ass")
                        ok, out_path, err = await asyncio.to_thread(
                            VideoSubtitleExtractor.auto_extract_and_prepare,
                            v_path, preferred_lang=self.settings_panel.get_source_lang_clean(), prefer_ass=True, output_path=temp_out_path
                        )
                        if ok:
                            self.video_origin_map[out_path] = v_path
                            self.temp_extracted_files.add(out_path)
                            final_subtitle_paths.append(out_path)
                            EventBus.instance().log_message.emit(f"✅ تم استخراج مسار الحوار مؤقتاً من: {v_name}")
                        else:
                            EventBus.instance().log_message.emit(f"⚠️ تعذر استخراج {v_name}: {err}")
                    auto_start = True

            if not final_subtitle_paths:
                dlg.close()
                return

            dlg.set_status("📥 جاري قراءة وتحليل ملف الترجمة...", os.path.basename(final_subtitle_paths[0]))
            await self._load_subtitle_files_async(final_subtitle_paths, auto_start_processing=auto_start, progress_dlg=dlg)
        except Exception as e:
            EventBus.instance().log_message.emit(f"خطأ أثناء معالجة الملفات: {e}")
        finally:
            dlg.close()
            self.provider_panel.resume_auto_detect()

    def _open_video_manual_dialog(self):
        from PySide6.QtWidgets import QFileDialog
        file_paths, _ = QFileDialog.getOpenFileNames(
            self, "اختر ملف الفيديو لتحديد مسار الترجمة يدوياً", "",
            "ملفات الفيديو (*.mkv *.mp4 *.avi *.mov *.webm *.flv *.ts *.m4v);;كل الملفات (*.*)"
        )
        if not file_paths:
            return
        v_path = file_paths[0]
        try:
            loop = asyncio.get_running_loop()
            if loop.is_running():
                loop.create_task(self._handle_manual_video_async(v_path))
                return
        except RuntimeError:
            pass
        asyncio.run(self._handle_manual_video_async(v_path))

    async def _handle_manual_video_async(self, v_path: str):
        self.provider_panel.pause_auto_detect()
        try:
            dlg = ExtractionProgressDialog(self, title="SubNova Studio — فحص الفيديو", initial_msg="🔍 جاري فحص مسارات الفيديو...")
            dlg.show()
            try:
                streams = await asyncio.to_thread(VideoSubtitleExtractor.probe_subtitle_streams, v_path)
            except Exception as e:
                dlg.close()
                self._show_msg_box_safe("critical", "خطأ", f"تعذر فحص ملف الفيديو:\n{e}")
                return
            finally:
                dlg.close()

            if not streams:
                self._show_msg_box_safe("warning", "تنبيه", f"لا يوجد أي مسار ترجمة مدمج داخل ملف الفيديو:\n{os.path.basename(v_path)}")
                return

            rec_stream = VideoSubtitleExtractor.select_best_stream(streams, self.settings_panel.get_source_lang_clean())
            rec_idx = rec_stream.index if rec_stream else 0
            dlg_select = VideoTrackSelectorDialog(self, os.path.basename(v_path), streams, rec_idx)
            if await self._exec_dialog_async(dlg_select):
                chosen_idx = dlg_select.selected_stream_index
                chosen_stream = next((s for s in streams if s.index == chosen_idx), None)
                self.stream_lang_code = chosen_stream.language if chosen_stream else (rec_stream.language if rec_stream else None)
                prefer_ass = getattr(dlg_select, 'prefer_ass', True)
                auto_start = getattr(dlg_select, 'auto_start_processing', True)
                
                ext_dlg = ExtractionProgressDialog(self, title="SubNova Studio — استخراج الترجمة", initial_msg="🎬 جاري استخراج مسار الترجمة المختار...")
                ext_dlg.show()
                try:
                    temp_dir = os.path.join(tempfile.gettempdir(), "unlimited_subs_extracted")
                    os.makedirs(temp_dir, exist_ok=True)
                    temp_out_path = os.path.join(temp_dir, f"{Path(v_path).stem}_raw.ass")
                    ok, out_path, err = await asyncio.to_thread(
                        VideoSubtitleExtractor.extract_subtitle, v_path, chosen_idx, output_path=temp_out_path, prefer_ass=prefer_ass
                    )
                    if ok:
                        self.video_origin_map[out_path] = v_path
                        self.temp_extracted_files.add(out_path)
                        self.current_video_file = v_path
                        v_name = os.path.basename(v_path)
                        self.btn_toggle_video.setText(f"🎬 مشغل الوسائط جاهز: {v_name} (طافي لتوفير الأداء - اضغط للفتح)")
                        self.btn_toggle_video.setStyleSheet("background: #18181b; color: #38bdf8; font-weight: 600; font-size: 8.5pt; border: 1px solid #0284c7; border-radius: 5px; padding: 4px 12px;")
                        ext_dlg.set_status("📥 جاري تحميل أسطر الترجمة...", os.path.basename(out_path))
                        await self._load_subtitle_files_async([out_path], auto_start_processing=auto_start, progress_dlg=ext_dlg)
                    else:
                        ext_dlg.close()
                        self._show_msg_box_safe("critical", "خطأ في الاستخراج", f"فشل استخراج الترجمة من الفيديو:\n{err}")
                finally:
                    ext_dlg.close()
        finally:
            self.provider_panel.resume_auto_detect()

    def _load_subtitle_files(self, file_paths: list, auto_start_processing: bool = False):
        try:
            loop = asyncio.get_running_loop()
            if loop.is_running():
                loop.create_task(self._load_subtitle_files_async(file_paths, auto_start_processing))
                return
        except RuntimeError:
            pass
        asyncio.run(self._load_subtitle_files_async(file_paths, auto_start_processing))

    async def _load_subtitle_files_async(self, file_paths: list, auto_start_processing: bool = False, progress_dlg=None):
        try:
            self.selected_files = list(file_paths)
            self.source_files = list(file_paths)
            self.output_files = {}
            self.source_video_origin = {
                p: self.video_origin_map[p]
                for p in file_paths
                if p in self.video_origin_map
            }
            first_file = file_paths[0]
            self.current_file_path = first_file
            self._inline_pre_edit_status.clear()
            if hasattr(self, "undo_stack"):
                self.undo_stack.clear()
            
            separate_fx = self.healing_panel.get_healing_options().get("separate_inline_effects", True) if hasattr(self, 'healing_panel') else True
            
            if progress_dlg:
                progress_dlg.set_status("📥 جاري قراءة وتحليل ملف الترجمة...", os.path.basename(first_file))

            self.document = await asyncio.to_thread(parse_subtitle, first_file, separate_effects=separate_fx)
            
            # If fresh session, clear any old translation cache from events
            if getattr(self, 'is_fresh_session', False):
                for ev in self.document.events:
                    ev.translated_text = None
            self.table_model.set_events(self.document.events)
            self.live_preview.clear()

            # Sync video player overlay and auto-select first row
            if hasattr(self, 'video_player'):
                self.video_player.set_subtitles_for_overlay(self.document.events)
                v_orig = self.video_origin_map.get(first_file)
                if v_orig and os.path.exists(v_orig):
                    self.current_video_file = v_orig
                    v_name = os.path.basename(v_orig)
                    self.btn_toggle_video.setText(f"🎬 مشغل الوسائط جاهز: {v_name} (طافي لتوفير الأداء - اضغط للفتح)")
                    self.btn_toggle_video.setStyleSheet("background: #18181b; color: #38bdf8; font-weight: 600; font-size: 8.5pt; border: 1px solid #0284c7; border-radius: 5px; padding: 4px 12px;")
                    if self.video_container.isVisible():
                        self.video_player.load_video(v_orig)

            if len(self.document.events) > 0:
                self.table_view.selectRow(0)
                self._inline_pre_edit_status[0] = self.table_model.statuses.get(0, "")
                self.inline_editor.load_event(0, self.document.events[0], len(self.document.events))
            else:
                self.inline_editor.clear()
            
            display_name = os.path.basename(self.video_origin_map.get(first_file, first_file))
            EventBus.instance().log_message.emit(f"📥 تم تحميل {len(self.document.events)} سطر ترجمة من {display_name} (إجمالي الملفات: {len(file_paths)})")
            
            # Automatic Language Detection
            if progress_dlg:
                progress_dlg.set_status("🌐 التعرف التلقائي على لغة الترجمة...", display_name)

            source_pref = self.settings_panel.get_source_lang_clean()
            detected_lang = await asyncio.to_thread(
                LanguageDetector.resolve_source_language,
                preferred_setting=source_pref,
                events=self.document.events,
                stream_code=getattr(self, 'stream_lang_code', None)
            )
            self.detected_source_lang = detected_lang.name
            self.settings_panel.set_detected_language(detected_lang.display_name)
            EventBus.instance().log_message.emit(
                f"🌐 تم التعرف على لغة الترجمة تلقائياً: {detected_lang.display_name} (دقة: {int(detected_lang.confidence * 100)}%)"
            )

            # Auto-detect media (movie, series, anime) using the original video or file name
            origin_for_meta = self.video_origin_map.get(first_file, first_file)
            async def auto_detect():
                try:
                    EventBus.instance().log_message.emit(f"🔍 التعرف التلقائي على العمل من اسم الملف: {os.path.basename(origin_for_meta)}...")
                    media, characters = await self.metadata_service.resolve_media_and_characters(origin_for_meta)
                    if media:
                        self.current_anime_id = getattr(media, "id", None)
                        title = media.display_title
                        m_type = "TV Series" if media.media_type == "tv" else ("Movie" if media.media_type == "movie" else "Anime")
                        self.character_panel.lbl_anime_title.setText(f"{m_type}: {title} (مكتشف تلقائياً)")
                        self.character_panel.table.setRowCount(0)
                        for char in characters:
                            if hasattr(char, 'gender') and hasattr(char.gender, 'value'):
                                gender_str = char.gender.value
                            elif hasattr(char, 'gender_info') and hasattr(char.gender_info.gender, 'value'):
                                gender_str = char.gender_info.gender.value
                            else:
                                gender_str = str(getattr(char, 'gender', 'UNKNOWN'))

                            conf = getattr(char, 'gender_confidence', None)
                            if conf is None and hasattr(char, 'gender_info'):
                                conf = getattr(char.gender_info, 'confidence', 0.0)

                            src = getattr(char, 'gender_source', None)
                            if src is None and hasattr(char, 'gender_info'):
                                src = getattr(char.gender_info, 'source', '')

                            self.character_panel.add_character(
                                char.canonical_name or "",
                                char.arabic_name or SubtitleHealer.transliterate_name_to_arabic(char.canonical_name or ""),
                                gender_str or "",
                                conf if conf is not None else 0.0,
                                src or "",
                                profile=char,
                            )
                        if self.current_anime_id is not None:
                            db_glossary = self.glossary_repo.get_all_for_anime(self.current_anime_id)
                            if db_glossary:
                                self.glossary_entries = db_glossary
                        EventBus.instance().log_message.emit(f"🎬 تم اكتشاف العمل: {title} ({len(characters)} شخصية مسجلة).")
                    else:
                        EventBus.instance().log_message.emit("لم يتم العثور على تطابق في قواعد البيانات للعمل.")
                except Exception as e:
                    EventBus.instance().log_message.emit(f"Auto-detect error: {e}")
                    
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(auto_detect())
            except RuntimeError:
                pass

            if auto_start_processing:
                EventBus.instance().log_message.emit("⚡ تفعيل خط المعالجة التلقائي الشامل للفيديو (استخراج -> ترجمة -> تدقيق فائق -> حفظ)...")
                self.progress_panel.lbl_stats.setText("⏳ جاري بدء خط المعالجة التلقائي...")
                self.progress_panel._set_busy(True)
                QTimer.singleShot(400, self._on_translation_started)
            
        except Exception as e:
            EventBus.instance().log_message.emit(f"Failed to load extracted subtitle: {e}")

    def _on_translation_started(self):
        if self._translation_task and not self._translation_task.done():
            EventBus.instance().log_message.emit("⚠️ هناك عملية ترجمة جارية بالفعل.")
            return

        if not self.selected_files:
            EventBus.instance().log_message.emit("No files selected.")
            EventBus.instance().translation_cancelled.emit()
            return
            
        config = self.provider_panel.get_provider_config()
        model = self.provider_panel.get_selected_model()
        if not model:
            # Fallback to saved model from settings if combobox is refreshing
            saved_m = getattr(self.provider_panel.settings, 'model_name', '') or getattr(self.provider_panel.settings, 'lmstudio_model', '')
            if saved_m:
                model = saved_m
                self.provider_panel.cb_models.setCurrentText(saved_m)
            else:
                EventBus.instance().log_message.emit("⚠️ الرجاء اختيار نموذج الذكاء الاصطناعي (Model) أولاً.")
                EventBus.instance().translation_cancelled.emit()
                return

        # Ensure UI busy state is active and responsive
        self.progress_panel._set_busy(True)
        self.progress_panel.lbl_stats.setText("⏳ جاري بدء خط المعالجة الفائق (الترجمة والتحسين)...")
            
        provider = get_provider(config)
        batch_size = self.settings_panel.sb_batch_size.value()
        max_toks = self.settings_panel.sb_max_tokens.value()
        max_ctx = getattr(self.settings_panel, 'sb_max_context', None)
        max_context = max_ctx.value() if max_ctx else getattr(self.provider_panel.sb_max_context, 'value', lambda: 4096)()
        is_local_eng = config and any(k in str(getattr(config, "provider_type", "")).lower() for k in ("lmstudio", "ollama", "lm_studio"))
        local_limit = min(15, batch_size) if is_local_eng else batch_size
        batcher = TokenBatcher(max_tokens=max_toks, max_events=batch_size, local_max_events=local_limit, max_context=max_context)
        engine = TranslationEngine(batcher=batcher, tm_repo=TranslationMemoryRepository(self.db))
        
        async def run_translation():
            files_to_translate = list(self.source_files or self.selected_files)
            total_files = len(files_to_translate)
            concurrency = self.settings_panel.sb_concurrency.value()
            temp = self.settings_panel.sb_temp.value()
            source_lang_pref = self.settings_panel.get_source_lang_clean()
            target_lang = self.settings_panel.get_target_lang_clean()
            story_notes = self.healing_panel.get_story_notes()
            auto_heal = self.healing_panel.chk_auto_heal.isChecked()
            auto_improve = self.healing_panel.chk_auto_improve.isChecked()
            healing_opts = self.healing_panel.get_healing_options()
            play_sound = self.healing_panel.chk_play_sound.isChecked()
            use_cache = self.settings_panel.chk_use_cache.isChecked() if hasattr(self.settings_panel, 'chk_use_cache') else False
            force_fresh = getattr(self, 'is_fresh_session', False) or (not use_cache)
            
            separate_fx = healing_opts.get("separate_inline_effects", True)
            cached_batch_action = None
            self.provider_panel.pause_auto_detect()
            try:
                for idx, file_path in enumerate(files_to_translate, 1):
                    # If previous run deleted extracted temp subtitle, re-extract cleanly from source video
                    if not os.path.exists(file_path) and file_path in self.source_video_origin:
                        v_path = self.source_video_origin[file_path]
                        if v_path and os.path.exists(v_path):
                            ok_re, out_re, err_re = await asyncio.to_thread(
                                VideoSubtitleExtractor.auto_extract_and_prepare,
                                v_path,
                                preferred_lang=source_lang_pref,
                                prefer_ass=True,
                                output_path=file_path,
                            )
                            if ok_re and out_re and os.path.exists(out_re):
                                self.video_origin_map[out_re] = v_path
                                self.temp_extracted_files.add(out_re)
                                file_path = out_re

                    self.current_file_path = file_path
                    self.document = await asyncio.to_thread(parse_subtitle, file_path, separate_effects=separate_fx)
                    if force_fresh or not use_cache:
                        CheckpointManager.cleanup(file_path)
                        for ev in self.document.events:
                            ev.translated_text = None
                    self._inline_pre_edit_status.clear()
                    self.table_model.set_events(self.document.events)
                    if len(self.document.events) > 0:
                        self.table_view.selectRow(0)
                        self._inline_pre_edit_status[0] = self.table_model.statuses.get(0, "")
                        self.inline_editor.load_event(0, self.document.events[0], len(self.document.events))
                    else:
                        self.inline_editor.clear()

                    # Auto detect language if preferred setting is Auto Detect
                    if "auto" in source_lang_pref.lower() or not source_lang_pref:
                        det = await asyncio.to_thread(
                            LanguageDetector.resolve_source_language,
                            "Auto Detect",
                            events=self.document.events,
                            stream_code=getattr(self, 'stream_lang_code', None)
                        )
                        source_lang = det.name
                        self.detected_source_lang = det.name
                        self.settings_panel.set_detected_language(det.display_name)
                    else:
                        source_lang = source_lang_pref
                    
                    orig_display = os.path.basename(self.video_origin_map.get(file_path, file_path))
                    EventBus.instance().log_message.emit(
                        f"🚀 Starting file {idx}/{total_files}: {orig_display} [{source_lang} -> {target_lang}]"
                    )
                    
                    file_start_time = None
                    def curried_progress(*args):
                        nonlocal file_start_time
                        import time
                        if file_start_time is None:
                            file_start_time = time.time()
                        if len(args) >= 5:
                            c_batch, t_batch, c_lines, t_lines, tokens = args[:5]
                        else:
                            c_batch, t_batch = args[:2]
                            c_lines, t_lines, tokens = c_batch, t_batch, 0
                        elapsed = max(0.1, time.time() - file_start_time)
                        speed = c_lines / elapsed if c_lines > 0 else 0.0
                        remaining = max(0, t_lines - c_lines)
                        eta_secs = int(remaining / speed) if speed > 0 else 0
                        eta_m, eta_s = divmod(eta_secs, 60)
                        eta_str = f"{eta_m:02d}:{eta_s:02d}"
                        
                        is_improving = len(args) >= 6 and args[5] == "improving"
                        stage_prefix = "✨ التدقيق اللغوي والتحسين الدرامي" if is_improving else "🚀 الترجمة الفائقة"
                        status = f"{stage_prefix}: {c_lines}/{t_lines} سطر | السرعة: {speed:.1f} س/ث | المتبقي: {eta_str} | (الملف {idx}/{total_files})"
                        EventBus.instance().translation_progress.emit(c_lines, t_lines, status)
                        
                    active_chars = self.character_panel.get_characters()
                    glossary = self.glossary_entries
                    use_cache = self.settings_panel.chk_use_cache.isChecked() if hasattr(self.settings_panel, 'chk_use_cache') else False
                    force_fresh = getattr(self, 'is_fresh_session', False) or (not use_cache)

                    await engine.translate_document(
                        self.document, provider, model,
                        source_lang=source_lang, target_lang=target_lang,
                        on_progress=curried_progress,
                        on_batch_status=self.table_model.set_batch_status,
                        concurrency=concurrency, temperature=temp, max_tokens=max_toks,
                        max_context=max_context,
                        characters=active_chars, glossary=glossary,
                        story_notes=story_notes,
                        source_file_path=file_path,
                        auto_heal=auto_heal,
                        healing_options=healing_opts,
                        auto_improve=auto_improve,
                        use_cache=use_cache,
                        force_fresh=force_fresh,
                        top_p=self.settings_panel.sb_top_p.value() if hasattr(self.settings_panel, 'sb_top_p') else getattr(self.settings_panel.settings, 'top_p', 0.85),
                        min_p=getattr(self.settings_panel.settings, 'min_p', 0.05),
                        repetition_penalty=self.settings_panel.sb_rep_penalty.value() if hasattr(self.settings_panel, 'sb_rep_penalty') else getattr(self.settings_panel.settings, 'repetition_penalty', 1.0)
                    )
                    if self.document and self.document.events:
                        self.table_model._emit_contiguous_rows_changed(list(range(len(self.document.events))), 5, 6)
                        curr_r = self.table_view.currentIndex().row()
                        if 0 <= curr_r < len(self.document.events):
                            self.inline_editor.load_event(curr_r, self.document.events[curr_r], len(self.document.events))
                    # Check for untranslated lines before finalizing/saving
                    skip_fx = healing_opts.get("skip_visual_effects", True)
                    trans_signs = healing_opts.get("translate_signs", False)
                    untranslated = engine.find_untranslated_events(
                        self.document,
                        target_lang=target_lang,
                        skip_effects=skip_fx,
                        include_signs=trans_signs,
                    )

                    user_action = None
                    if untranslated:
                        if cached_batch_action:
                            user_action = cached_batch_action
                        else:
                            from app.ui.dialogs.untranslated_dialog import UntranslatedLinesDialog
                            dlg = UntranslatedLinesDialog(
                                parent=self,
                                events=untranslated,
                                filename=orig_display,
                                is_batch=(total_files > 1)
                            )
                            dlg.exec()
                            user_action = dlg.selected_action
                            if dlg.should_apply_to_batch():
                                cached_batch_action = user_action

                    if user_action == "TRANSLATE":
                        EventBus.instance().log_message.emit(
                            f"🚀 جاري استكمال ترجمة {len(untranslated)} سطر غير مترجم بالسياق الكامل..."
                        )
                        self.progress_panel.lbl_stats.setText(
                            f"🚀 استكمال ترجمة {len(untranslated)} سطر بالسياق الكامل..."
                        )
                        await engine.translate_remaining_events(
                            document=self.document,
                            remaining_events=untranslated,
                            provider=provider,
                            model=model,
                            source_lang=source_lang,
                            target_lang=target_lang,
                            characters=active_chars,
                            glossary=glossary,
                            story_notes=story_notes,
                            on_batch_status=self.table_model.set_batch_status,
                            concurrency=concurrency,
                            temperature=temp,
                            max_tokens=max_toks,
                            max_context=max_context,
                            auto_heal=auto_heal,
                            healing_options=healing_opts,
                            top_p=self.settings_panel.sb_top_p.value() if hasattr(self.settings_panel, 'sb_top_p') else getattr(self.settings_panel.settings, 'top_p', 0.85),
                            min_p=getattr(self.settings_panel.settings, 'min_p', 0.05),
                            repetition_penalty=self.settings_panel.sb_rep_penalty.value() if hasattr(self.settings_panel, 'sb_rep_penalty') else getattr(self.settings_panel.settings, 'repetition_penalty', 1.0)
                        )
                        if self.document and self.document.events:
                            self.table_model._emit_contiguous_rows_changed(list(range(len(self.document.events))), 5, 6)
                            curr_r = self.table_view.currentIndex().row()
                            if 0 <= curr_r < len(self.document.events):
                                self.inline_editor.load_event(curr_r, self.document.events[curr_r], len(self.document.events))
                        await self._save_file_auto_async(file_path, source_key=file_path)
                        EventBus.instance().log_message.emit(f"✅ Finished file {idx}/{total_files} (تم استكمال الترجمة وحفظ الملف)")
                    elif user_action == "CANCEL":
                        EventBus.instance().log_message.emit(
                            f"🛑 تم إيقاف الحفظ التلقائي للملف {orig_display} لمراجعة الأسطر غير المترجمة ({len(untranslated)} سطر) يدوياً."
                        )
                    else:
                        if user_action == "SAVE_AS_IS":
                            EventBus.instance().log_message.emit(
                                f"💾 تم اعتماد حفظ الملف {orig_display} كما هو مع إبقاء {len(untranslated)} سطر دون ترجمة بناءً على اختيارك."
                            )
                        await self._save_file_auto_async(file_path, source_key=file_path)
                        EventBus.instance().log_message.emit(f"✅ Finished file {idx}/{total_files}")
                    
                self.is_fresh_session = False
                    
                EventBus.instance().log_message.emit("🎉 اكتمل خط المعالجة التلقائي بالكامل بأعلى جودة سينمائية وتم حفظ الملف المعتمد!")
                self.progress_panel.lbl_stats.setText("🎉 اكتملت الترجمة والتدقيق الفائق 100% وتم حفظ الملف النهائي بنجاح!")
                if play_sound:
                    try:
                        import winsound
                        winsound.MessageBeep(winsound.MB_ICONASTERISK)
                    except Exception:
                        pass
                EventBus.instance().translation_finished.emit(self.current_file_path or "")
            except asyncio.CancelledError:
                EventBus.instance().log_message.emit("🛑 تم إيقاف عملية الترجمة / Translation cancelled.")
            except Exception as e:
                EventBus.instance().log_message.emit(f"Translation error: {e}")
            finally:
                self.provider_panel.resume_auto_detect()
                if provider:
                    await provider.close()
                self._translation_task = None
                self.progress_panel._reset_controls()
                EventBus.instance().translation_cancelled.emit()
                
        try:
            loop = asyncio.get_running_loop()
            self._translation_task = loop.create_task(run_translation())
        except RuntimeError:
            pass

    def _on_improvement_started(self):
        files_to_process = self.selected_files or ([self.current_file_path] if self.current_file_path else [])
        if not files_to_process and not self.document:
            EventBus.instance().log_message.emit("No files or document loaded to improve.")
            EventBus.instance().translation_cancelled.emit()
            return
            
        config = self.provider_panel.get_provider_config()
        model = self.provider_panel.get_selected_model()
        if not model:
            EventBus.instance().log_message.emit("No model selected for improvement.")
            EventBus.instance().translation_cancelled.emit()
            return
            
        provider = get_provider(config)
        batch_size = self.settings_panel.sb_batch_size.value()
        max_toks = self.settings_panel.sb_max_tokens.value()
        max_ctx = getattr(self.settings_panel, 'sb_max_context', None)
        max_context = max_ctx.value() if max_ctx else getattr(self.provider_panel.sb_max_context, 'value', lambda: 4096)()
        is_local_eng = config and any(k in str(getattr(config, "provider_type", "")).lower() for k in ("lmstudio", "ollama", "lm_studio"))
        local_limit = min(15, batch_size) if is_local_eng else batch_size
        batcher = TokenBatcher(max_tokens=max_toks, max_events=batch_size, local_max_events=local_limit, max_context=max_context)
        engine = TranslationEngine(batcher=batcher)
        
        async def run_improvement():
            concurrency = self.settings_panel.sb_concurrency.value()
            temp = self.settings_panel.sb_temp.value()
            source_lang_pref = self.settings_panel.get_source_lang_clean()
            target_lang = self.settings_panel.get_target_lang_clean()
            story_notes = self.healing_panel.get_story_notes()
            auto_heal = self.healing_panel.chk_auto_heal.isChecked()
            healing_opts = self.healing_panel.get_healing_options()
            play_sound = self.healing_panel.chk_play_sound.isChecked()
            
            self.provider_panel.pause_auto_detect()
            try:
                improve_inputs = list(self.source_files or self.selected_files)
                if improve_inputs:
                    total_files = len(improve_inputs)
                    for idx, file_path in enumerate(improve_inputs, 1):
                        self.current_file_path = file_path
                        
                        # Prefer latest translated output (.ara.*) when improving multi-episode folders
                        target_file_to_parse = None
                        mapped_out = self.output_files.get(file_path)
                        if mapped_out and os.path.exists(mapped_out):
                            target_file_to_parse = mapped_out
                        else:
                            p = Path(file_path)
                            if not p.stem.endswith(".ara"):
                                cand_ext = p.suffix if p.suffix.lower() in ('.ass', '.srt', '.vtt') else '.ass'
                                candidate_ara = str(p.with_name(f"{p.stem}.ara{cand_ext}"))
                                if os.path.exists(candidate_ara):
                                    target_file_to_parse = candidate_ara
                            if not target_file_to_parse:
                                v_origin = self.video_origin_map.get(file_path) or self.source_video_origin.get(file_path)
                                if v_origin:
                                    v_p = Path(v_origin)
                                    candidate_video_ara = str(v_p.with_name(f"{v_p.stem}.ara.ass"))
                                    if os.path.exists(candidate_video_ara):
                                        target_file_to_parse = candidate_video_ara
                            if not target_file_to_parse and os.path.exists(file_path):
                                target_file_to_parse = file_path
                        
                        if target_file_to_parse and os.path.exists(target_file_to_parse):
                            self.document = await asyncio.to_thread(parse_subtitle, target_file_to_parse)
                            self.current_file_path = target_file_to_parse
                        elif self.document and self.document.events:
                            EventBus.instance().log_message.emit("ℹ️ Using in-memory subtitle document for improvement.")
                        else:
                            EventBus.instance().log_message.emit(f"⚠️ Could not find subtitle file to improve: {file_path}")
                            continue

                        self._inline_pre_edit_status.clear()
                        self.table_model.set_events(self.document.events)
                        if len(self.document.events) > 0:
                            self.table_view.selectRow(0)
                            self._inline_pre_edit_status[0] = self.table_model.statuses.get(0, "")
                            self.inline_editor.load_event(0, self.document.events[0], len(self.document.events))
                        else:
                            self.inline_editor.clear()

                        if "auto" in source_lang_pref.lower() or not source_lang_pref:
                            det = await asyncio.to_thread(
                                LanguageDetector.resolve_source_language,
                                "Auto Detect",
                                events=self.document.events,
                                stream_code=getattr(self, 'stream_lang_code', None)
                            )
                            source_lang = det.name
                            self.detected_source_lang = det.name
                            self.settings_panel.set_detected_language(det.display_name)
                        else:
                            source_lang = source_lang_pref

                        orig_display = os.path.basename(self.video_origin_map.get(file_path, file_path))
                        EventBus.instance().log_message.emit(
                            f"✨ Starting master improvement on file {idx}/{total_files}: {orig_display}..."
                        )
                        file_start_time = None
                        def curried_progress(*args):
                            nonlocal file_start_time
                            import time
                            if file_start_time is None:
                                file_start_time = time.time()
                            c_batch, t_batch = args[0], args[1]
                            c_lines = args[2] if len(args) >= 3 else c_batch
                            t_lines = args[3] if len(args) >= 4 else t_batch
                            tokens = args[4] if len(args) >= 5 else 0
                            elapsed = max(0.1, time.time() - file_start_time)
                            speed = c_lines / elapsed if c_lines > 0 else 0.0
                            remaining = max(0, t_lines - c_lines)
                            eta_secs = int(remaining / speed) if speed > 0 else 0
                            eta_m, eta_s = divmod(eta_secs, 60)
                            status = f"Improving: {c_lines}/{t_lines} | Speed: {speed:.1f} l/s | ETA: {eta_m:02d}:{eta_s:02d} | Tokens: {tokens} (File {idx}/{total_files})"
                            EventBus.instance().translation_progress.emit(c_lines, t_lines, status)

                        characters = self.character_panel.get_characters()
                        glossary = self.glossary_entries
                        await engine.improve_document(
                            self.document, provider, model,
                            source_lang=source_lang, target_lang=target_lang,
                            characters=characters, glossary=glossary,
                            story_notes=story_notes,
                            on_progress=curried_progress,
                            on_batch_status=self.table_model.set_batch_status,
                            concurrency=concurrency, temperature=temp, max_tokens=max_toks,
                            auto_heal=auto_heal, healing_options=healing_opts,
                            max_context=max_context
                        )
                        if self.document and self.document.events:
                            self.table_model._emit_contiguous_rows_changed(list(range(len(self.document.events))), 5, 6)
                            curr_r = self.table_view.currentIndex().row()
                            if 0 <= curr_r < len(self.document.events):
                                self.inline_editor.load_event(curr_r, self.document.events[curr_r], len(self.document.events))
                        await self._save_file_auto_async(target_file_to_parse or file_path, source_key=file_path)
                        EventBus.instance().log_message.emit(f"✅ Finished improving file {idx}/{total_files}")
                elif self.document:
                    if "auto" in source_lang_pref.lower() or not source_lang_pref:
                        det = await asyncio.to_thread(
                            LanguageDetector.resolve_source_language,
                            "Auto Detect",
                            events=self.document.events,
                            stream_code=getattr(self, 'stream_lang_code', None)
                        )
                        source_lang = det.name
                    else:
                        source_lang = source_lang_pref
                    characters = self.character_panel.get_characters()
                    glossary = self.glossary_entries
                    EventBus.instance().log_message.emit("✨ Starting master improvement on current document...")
                    await engine.improve_document(
                        self.document, provider, model,
                        source_lang=source_lang, target_lang=target_lang,
                        characters=characters, glossary=glossary,
                        story_notes=story_notes,
                        on_batch_status=self.table_model.set_batch_status,
                        concurrency=concurrency, temperature=temp, max_tokens=max_toks,
                        auto_heal=auto_heal, healing_options=healing_opts,
                        max_context=max_context
                    )
                    if self.document and self.document.events:
                        self.table_model._emit_contiguous_rows_changed(list(range(len(self.document.events))), 5, 6)
                    await self._save_file_auto_async()
                    EventBus.instance().log_message.emit("✅ Master Improvement completed for current document.")
                    
                EventBus.instance().log_message.emit("🎉 All improvement and de-noising operations completed successfully!")
                if play_sound:
                    try:
                        import winsound
                        winsound.MessageBeep(winsound.MB_ICONASTERISK)
                    except Exception:
                        pass
            except asyncio.CancelledError:
                EventBus.instance().log_message.emit("🛑 تم إيقاف عملية التحسين / Improvement cancelled.")
            except Exception as e:
                EventBus.instance().log_message.emit(f"Improvement error: {e}")
            finally:
                self.provider_panel.resume_auto_detect()
                if provider:
                    await provider.close()
                self._translation_task = None
                EventBus.instance().translation_cancelled.emit()
                
        try:
            loop = asyncio.get_running_loop()
            self._translation_task = loop.create_task(run_improvement())
        except RuntimeError:
            pass

    def _on_quick_heal_requested(self):
        if not self.document:
            EventBus.instance().log_message.emit("No document loaded to auto-heal.")
            return
        self._flush_inline_editor()
        healing_opts = self.healing_panel.get_healing_options()
        engine = TranslationEngine()
        healed_count = engine.quick_heal_document(self.document, healing_opts)
        self.table_model.set_events(self.document.events)
        self._save_file_auto()
        EventBus.instance().log_message.emit(f"🧹 تم تنقية وتصحيح {healed_count} سطر بنجاح وإزالة الشوائب فورياً بدون استهلاك رموز ذكاء اصطناعي!")

    def _setup_menus(self):
        menubar = self.menuBar()
        
        # File
        file_menu = menubar.addMenu("File / ملف")
        file_menu.addAction("New Session / جلسة جديدة").triggered.connect(self._new_session)
        file_menu.addAction("Open Video (Full Auto)... / استيراد فيديو ومعالجة تلقائية شاملة").triggered.connect(self.file_panel._select_video)
        file_menu.addAction("Open Video (Choose Track)... / استيراد فيديو واختيار المسار يدوياً").triggered.connect(self._open_video_manual_dialog)
        file_menu.addAction("Open Files... / فتح ملفات ترجمة").triggered.connect(self.file_panel._select_file)
        file_menu.addAction("Open Folder... / فتح مجلد").triggered.connect(self.file_panel._select_folder)
        file_menu.addAction("Save / حفظ").triggered.connect(self._save_file)
        
        # Edit
        edit_menu = menubar.addMenu("Edit / تحرير")
        act_undo = edit_menu.addAction("Undo / تراجع (Ctrl+Z)")
        act_undo.triggered.connect(self._on_undo)
        act_redo = edit_menu.addAction("Redo / إعادة (Ctrl+Y)")
        act_redo.triggered.connect(self._on_redo)
        edit_menu.addSeparator()
        act_find = edit_menu.addAction("Find & Replace / بحث واستبدال (Ctrl+F)")
        act_find.triggered.connect(self._toggle_find_bar)

        # View
        view_menu = menubar.addMenu("View / عرض")
        act_view_fx = view_menu.addAction("إخفاء / إظهار أسطر المؤثرات (FX) - Ctrl+H")
        act_view_fx.setCheckable(True)
        act_view_fx.setChecked(self.btn_toggle_fx.isChecked())
        act_view_fx.triggered.connect(self.btn_toggle_fx.click)
        self.btn_toggle_fx.toggled.connect(act_view_fx.setChecked)

        act_view_vid = view_menu.addAction("إظهار / إخفاء مشغل الفيديو")
        act_view_vid.triggered.connect(self._toggle_video_player)

        # Tools
        tools_menu = menubar.addMenu("Tools / أدوات الجودة والتحسين")
        tools_menu.addAction("Master Subtitle Improvement (تحسين وتدقيق الترجمة)").triggered.connect(self._on_improvement_started)
        tools_menu.addAction("Instant Smart Auto-Healing (تنقية فورية للشوائب)").triggered.connect(self._on_quick_heal_requested)
        tools_menu.addAction("Review & Diff Translations (مراجعة ومقارنة الترجمات)").triggered.connect(self._open_review_dialog)
        tools_menu.addAction("🔍 Check Untranslated Lines (فحص الأسطر غير المترجمة)...").triggered.connect(self._open_untranslated_dialog)
        tools_menu.addSeparator()
        tools_menu.addAction("⏱️ Shift Timings (تقديم / تأخير التوقيت)...").triggered.connect(self._open_shift_timings_dialog)
        tools_menu.addAction("🔗 Merge Lines (دمج الأسطر المحددة)").triggered.connect(self._merge_selected_lines)
        tools_menu.addAction("✂️ Split Line (تقسيم السطر)").triggered.connect(self._split_selected_line)
        tools_menu.addAction("🎬 Toggle Video Player (مشغل الفيديو)").triggered.connect(self._toggle_video_player)
        tools_menu.addSeparator()
        tools_menu.addAction("Character Editor (محرر الشخصيات)").triggered.connect(self._open_char_editor)
        tools_menu.addAction("Glossary Editor (المعجم والمصطلحات)").triggered.connect(self._open_glossary_editor)
        tools_menu.addAction("Search Anime & Movies (بحث عن العمل)").triggered.connect(self._open_anime_search)
        
        # Help
        help_menu = menubar.addMenu("Help / مساعدة")
        help_menu.addAction("About / حول البرنامج").triggered.connect(self._show_about)
        
    def _show_about(self):
        dlg = AboutDialog(self)
        dlg.exec()

    def _flush_inline_editor(self):
        if hasattr(self, "inline_editor") and hasattr(self.inline_editor, "commit_pending_edit"):
            self.inline_editor.commit_pending_edit()

    def _on_undo(self):
        self._flush_inline_editor()
        if self.undo_stack.canUndo():
            self._is_undo_redo_active = True
            try:
                self.undo_stack.undo()
            finally:
                self._is_undo_redo_active = False
            if self.document:
                self.document.events = self.table_model.events
            curr_row = self.table_view.currentIndex().row()
            if self.document and 0 <= curr_row < len(self.document.events):
                self._inline_pre_edit_status[curr_row] = self.table_model.statuses.get(curr_row, "")
                self.inline_editor.load_event(curr_row, self.document.events[curr_row], len(self.document.events))
            if hasattr(self, 'video_player') and self.document:
                self.video_player.set_subtitles_for_overlay(self.document.events)

    def _on_redo(self):
        self._flush_inline_editor()
        if self.undo_stack.canRedo():
            self._is_undo_redo_active = True
            try:
                self.undo_stack.redo()
            finally:
                self._is_undo_redo_active = False
            if self.document:
                self.document.events = self.table_model.events
            curr_row = self.table_view.currentIndex().row()
            if self.document and 0 <= curr_row < len(self.document.events):
                self._inline_pre_edit_status[curr_row] = self.table_model.statuses.get(curr_row, "")
                self.inline_editor.load_event(curr_row, self.document.events[curr_row], len(self.document.events))
            if hasattr(self, 'video_player') and self.document:
                self.video_player.set_subtitles_for_overlay(self.document.events)

    def _on_table_data_changed_for_undo(self, row: int, col: int, old_val: str, new_val: str):
        if getattr(self, '_is_undo_redo_active', False):
            return
        cmd = EditCellCommand(self.table_model, row, col, old_val, new_val)
        self.undo_stack.push(cmd)
        if self.document and 0 <= row < len(self.document.events):
            self._inline_pre_edit_status[row] = self.table_model.statuses.get(row, "")
            self.inline_editor.load_event(row, self.document.events[row], len(self.document.events))
            if hasattr(self, 'video_player'):
                self.video_player.set_subtitles_for_overlay(self.document.events)

    def _on_table_row_changed(self, current_index, previous_index):
        if not getattr(self, '_is_undo_redo_active', False):
            self._flush_inline_editor()
        if not current_index.isValid() or not self.document:
            return
        row = current_index.row()
        if 0 <= row < len(self.document.events):
            event = self.document.events[row]
            self._inline_pre_edit_status[row] = self.table_model.statuses.get(row, "")
            self.inline_editor.load_event(row, event, len(self.document.events))
            if event.start_time and hasattr(self, 'video_player') and not self.video_container.isHidden():
                self.video_player.seek_to_time_str(event.start_time)

    def _on_inline_editor_updated(self, row: int, start: str, end: str, spk: str, orig: str, trans: str):
        if not self.document or not (0 <= row < len(self.document.events)):
            return
        from app.subtitle.timecode import parse_timecode_ms, normalize_timecode
        if row not in self._inline_pre_edit_status:
            self._inline_pre_edit_status[row] = self.table_model.statuses.get(row, "")
        event = self.document.events[row]
        s_ms = parse_timecode_ms(start)
        e_ms = parse_timecode_ms(end)
        if s_ms is not None and e_ms is not None and e_ms >= s_ms:
            fmt = getattr(event.format_type, "value", None)
            norm_s = normalize_timecode(start, template_str=event.start_time or start, fmt=fmt)
            norm_e = normalize_timecode(end, template_str=event.end_time or end, fmt=fmt)
            if norm_s is not None:
                event.start_time = norm_s
            if norm_e is not None:
                event.end_time = norm_e
        event.speaker = spk
        event.original_text = orig
        event.translated_text = trans
        setattr(event, '_cached_cps', None)
        if self.table_model.statuses.get(row) != "Done":
            self.table_model.statuses[row] = "Edited"
        top_left = self.table_model.index(row, 1)
        bottom_right = self.table_model.index(row, 6)
        self.table_model.dataChanged.emit(
            top_left, bottom_right,
            [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole, Qt.ItemDataRole.BackgroundRole]
        )
        if hasattr(self, 'video_player'):
            self.video_player.set_subtitles_for_overlay(self.document.events)

    def _on_inline_editor_committed(self, row: int, old_vals: tuple, new_vals: tuple):
        if getattr(self, '_is_undo_redo_active', False):
            return
        if not self.document or not (0 <= row < len(self.document.events)):
            return
        old_status = self._inline_pre_edit_status.pop(row, self.table_model.statuses.get(row, ""))
        new_status = self.table_model.statuses.get(row, "Edited")
        cmd = EditRowCommand(
            self.table_model,
            row,
            (*old_vals, old_status),
            (*new_vals, new_status),
        )
        self.undo_stack.push(cmd)

    def _on_nav_previous(self):
        self._flush_inline_editor()
        curr_row = self.table_view.currentIndex().row()
        target = curr_row - 1
        while target >= 0 and self.table_view.isRowHidden(target):
            target -= 1
        if target >= 0:
            self.table_view.selectRow(target)
            self.table_view.scrollTo(self.table_model.index(target, 0))

    def _on_nav_next(self):
        self._flush_inline_editor()
        curr_row = self.table_view.currentIndex().row()
        target = curr_row + 1
        max_r = self.table_model.rowCount()
        while target < max_r and self.table_view.isRowHidden(target):
            target += 1
        if target < max_r:
            self.table_view.selectRow(target)
            self.table_view.scrollTo(self.table_model.index(target, 0))

    def _on_play_line_in_video(self, start_time: str):
        if hasattr(self, 'video_player') and start_time:
            if self.video_container.isHidden():
                self._toggle_video_player()
            self.video_player.seek_to_time_str(start_time)
            if self.video_player.player:
                self.video_player.player.play()

    def _toggle_video_player(self):
        is_vis = self.video_container.isHidden()
        self.video_container.setVisible(is_vis)
        if is_vis:
            self.btn_toggle_video.setText("▲ إغلاق مشغل الوسائط (إيقاف لتوفير أداء وموارد الجهاز)")
            self.btn_toggle_video.setStyleSheet("""
                QPushButton {
                    background-color: #0284c7;
                    color: white;
                    font-weight: bold;
                    font-size: 8.5pt;
                    border: 1px solid #38bdf8;
                    border-radius: 5px;
                    padding: 3px 12px;
                }
                QPushButton:hover {
                    background-color: #0369a1;
                }
            """)
            if getattr(self, 'current_video_file', None) and os.path.exists(self.current_video_file):
                self.video_player.load_video(self.current_video_file)
            if self.document:
                self.video_player.set_subtitles_for_overlay(self.document.events)
        else:
            if hasattr(self, 'video_player'):
                self.video_player.cleanup()
            v_name = os.path.basename(self.current_video_file) if getattr(self, 'current_video_file', None) else ""
            lbl = f"🎬 مشغل الوسائط جاهز: {v_name} (طافي لتوفير الأداء - اضغط للفتح)" if v_name else "🎬 مشغل الوسائط والمعاينة الحية (طافي لتوفير موارد الجهاز - اضغط للفتح)"
            self.btn_toggle_video.setText(lbl)
            self.btn_toggle_video.setStyleSheet("""
                QPushButton {
                    background-color: #18181b;
                    color: #94a3b8;
                    font-weight: 600;
                    font-size: 8.5pt;
                    border: 1px solid #27272a;
                    border-radius: 5px;
                    padding: 3px 12px;
                }
                QPushButton:hover {
                    background-color: #27272a;
                    color: #38bdf8;
                    border-color: #0284c7;
                }
            """)

    def _toggle_find_bar(self):
        if self.find_replace_bar.isVisible():
            self.find_replace_bar.hide_bar()
        else:
            self.find_replace_bar.show_bar()

    def _toggle_hide_effects(self, checked: bool = None):
        if checked is None:
            checked = self.btn_toggle_fx.isChecked()
        self.apply_effects_filter(checked)

    def apply_effects_filter(self, hide_effects: bool):
        total_rows = len(self.table_model.events)
        fx_hidden_count = 0
        diag_count = 0

        for row_idx, ev in enumerate(self.table_model.events):
            has_text = hasattr(ev, "has_translatable_text") and ev.has_translatable_text()
            is_pure_fx = hasattr(ev, "is_visual_effect") and ev.is_visual_effect() and not has_text
            if is_pure_fx:
                self.table_view.setRowHidden(row_idx, hide_effects)
                fx_hidden_count += 1
            else:
                self.table_view.setRowHidden(row_idx, False)
                diag_count += 1

        if hide_effects:
            self.btn_toggle_fx.setText(f"👁️ إظهار كافة الأسطر (تم إخفاء: {fx_hidden_count})")
            self.btn_toggle_fx.setChecked(True)
            self.lbl_table_filter_stats.setText(f"💬 حوار فقط: {diag_count} سطر | 🛡️ تم إخفاء {fx_hidden_count} سطر مؤثرات")
            curr_row = self.table_view.currentIndex().row()
            if curr_row >= 0 and self.table_view.isRowHidden(curr_row):
                for r in range(total_rows):
                    if not self.table_view.isRowHidden(r):
                        self.table_view.selectRow(r)
                        break
        else:
            self.btn_toggle_fx.setText("🛡️ إخفاء أسطر المؤثرات (FX)")
            self.btn_toggle_fx.setChecked(False)
            if fx_hidden_count > 0:
                self.lbl_table_filter_stats.setText(f"عرض الكل: {total_rows} سطر (يتضمن {fx_hidden_count} سطر مؤثرات)")
            else:
                self.lbl_table_filter_stats.setText(f"عرض الكل: {total_rows} سطر" if total_rows > 0 else "")

    def _on_find_next(self, search_text: str, case_sensitive: bool):
        if not self.table_model.events or not search_text:
            return
        curr_row = self.table_view.currentIndex().row()
        matches = []
        target_row = -1
        for r, ev in enumerate(self.table_model.events):
            if self.table_view.isRowHidden(r):
                continue
            t1 = ev.original_text or ""
            t2 = ev.translated_text or ""
            if not case_sensitive:
                t1, t2, q = t1.lower(), t2.lower(), search_text.lower()
            else:
                q = search_text
            if q in t1 or q in t2:
                matches.append(r)
                if target_row == -1 and r > curr_row:
                    target_row = r

        if matches and target_row == -1:
            target_row = matches[0]

        if target_row >= 0:
            self.table_view.selectRow(target_row)
            self.table_view.scrollTo(self.table_model.index(target_row, 0))
            idx = matches.index(target_row) + 1
            self.find_replace_bar.set_match_status(idx, len(matches))
        else:
            self.find_replace_bar.set_match_status(0, 0)

    def _on_replace_current(self, find_text: str, replace_text: str, case_sensitive: bool):
        curr_row = self.table_view.currentIndex().row()
        if not (0 <= curr_row < len(self.table_model.events)):
            self._on_find_next(find_text, case_sensitive)
            curr_row = self.table_view.currentIndex().row()
            if curr_row < 0:
                return

        ev = self.table_model.events[curr_row]
        old_trans = ev.translated_text or ""
        if not case_sensitive:
            import re
            pattern = re.compile(re.escape(find_text), re.IGNORECASE)
            new_trans = pattern.sub(replace_text, old_trans)
        else:
            new_trans = old_trans.replace(find_text, replace_text)

        if new_trans != old_trans:
            cmd = EditCellCommand(self.table_model, curr_row, 5, old_trans, new_trans)
            self.undo_stack.push(cmd)
        self._on_find_next(find_text, case_sensitive)

    def _on_replace_all(self, find_text: str, replace_text: str, case_sensitive: bool):
        if not self.table_model.events:
            return
        count = 0
        import re
        pattern = re.compile(re.escape(find_text), 0 if case_sensitive else re.IGNORECASE)
        for r, ev in enumerate(self.table_model.events):
            old_trans = ev.translated_text or ""
            if old_trans and pattern.search(old_trans):
                new_trans = pattern.sub(replace_text, old_trans)
                cmd = EditCellCommand(self.table_model, r, 5, old_trans, new_trans)
                self.undo_stack.push(cmd)
                count += 1
        EventBus.instance().log_message.emit(f"🔍 تم استبدال «{find_text}» بـ «{replace_text}» في {count} سطر بنجاح.")
        self.find_replace_bar.set_match_status(0, 0)

    def _show_table_context_menu(self, pos):
        menu = QMenu(self)
        menu.setStyleSheet("QMenu { background-color: #1e293b; color: #f1f5f9; border: 1px solid #334155; } QMenu::item:selected { background-color: #0284c7; }")

        act_play = menu.addAction("🎬 تشغيل في مشغل الفيديو")
        act_play.triggered.connect(self._play_selected_in_video)

        menu.addSeparator()
        act_shift = menu.addAction("⏱️ تقديم / تأخير التوقيت (Shift Timings)...")
        act_shift.triggered.connect(self._open_shift_timings_dialog)

        act_merge = menu.addAction("🔗 دمج الأسطر المحددة (Merge Lines)")
        act_merge.triggered.connect(self._merge_selected_lines)

        act_split = menu.addAction("✂️ تقسيم السطر (Split Line)")
        act_split.triggered.connect(self._split_selected_line)

        menu.addSeparator()
        act_copy_trans = menu.addAction("📋 نسخ النص المترجم")
        act_copy_trans.triggered.connect(self._copy_selected_translation)

        act_copy_orig = menu.addAction("📋 نسخ النص الأصلي")
        act_copy_orig.triggered.connect(self._copy_selected_original)

        menu.addSeparator()
        act_undo = menu.addAction("🔄 تراجع (Undo) - Ctrl+Z")
        act_undo.setEnabled(self.undo_stack.canUndo())
        act_undo.triggered.connect(self._on_undo)

        act_redo = menu.addAction("🔁 إعادة (Redo) - Ctrl+Y")
        act_redo.setEnabled(self.undo_stack.canRedo())
        act_redo.triggered.connect(self._on_redo)

        menu.addSeparator()
        is_hiding_fx = self.btn_toggle_fx.isChecked()
        act_toggle_fx = menu.addAction("👁️ إظهار أسطر المؤثرات (FX)" if is_hiding_fx else "🛡️ إخفاء أسطر المؤثرات (FX) - Ctrl+H")
        act_toggle_fx.triggered.connect(self.btn_toggle_fx.click)

        menu.exec(self.table_view.viewport().mapToGlobal(pos))

    def _play_selected_in_video(self):
        selected = [idx.row() for idx in self.table_view.selectionModel().selectedRows()]
        if selected and self.document:
            ev = self.document.events[selected[0]]
            if ev.start_time:
                self._on_play_line_in_video(ev.start_time)

    def _copy_selected_translation(self):
        selected = [idx.row() for idx in self.table_view.selectionModel().selectedRows()]
        if selected and self.document:
            texts = [self.document.events[r].translated_text or "" for r in selected if r < len(self.document.events)]
            QApplication.clipboard().setText("\n".join(texts))

    def _copy_selected_original(self):
        selected = [idx.row() for idx in self.table_view.selectionModel().selectedRows()]
        if selected and self.document:
            texts = [self.document.events[r].original_text or "" for r in selected if r < len(self.document.events)]
            QApplication.clipboard().setText("\n".join(texts))

    def _open_shift_timings_dialog(self):
        if not self.table_model.events:
            QMessageBox.information(self, "تنبيه", "لا توجد أسطر ترجمة محملة لتعديل التوقيت.")
            return
        self._flush_inline_editor()
        selected_rows = [idx.row() for idx in self.table_view.selectionModel().selectedRows()]
        has_selection = len(selected_rows) > 0
        sample_time = ""
        if has_selection and selected_rows[0] < len(self.table_model.events):
            sample_time = self.table_model.events[selected_rows[0]].start_time
        elif self.table_model.events:
            sample_time = self.table_model.events[0].start_time

        dlg = ShiftTimingsDialog(self, has_selection=has_selection, sample_start_time=sample_time)
        if dlg.exec():
            offset_ms = dlg.get_offset_ms()
            rows_to_shift = selected_rows if (dlg.is_selected_only() and has_selection) else None
            cmd = ShiftTimingsCommand(self.table_model, offset_ms, rows_to_shift)
            self.undo_stack.push(cmd)
            direction_str = "تأخير الظهور (+)" if offset_ms > 0 else "تقديم الظهور (-)"
            count_str = f"{len(rows_to_shift)} سطر محدد" if rows_to_shift else "كل أسطر الترجمة"
            EventBus.instance().log_message.emit(f"⏱️ تم {direction_str} بمقدار {abs(offset_ms)} مللي ثانية لـ ({count_str}).")
            curr_row = self.table_view.currentIndex().row()
            if self.document and 0 <= curr_row < len(self.document.events) and hasattr(self, 'inline_editor'):
                self.inline_editor.load_event(curr_row, self.document.events[curr_row], len(self.document.events))
            if self.document:
                self._save_file_auto()
                if hasattr(self, 'video_player'):
                    self.video_player.set_subtitles_for_overlay(self.document.events)

    def _merge_selected_lines(self):
        self._flush_inline_editor()
        selected_rows = [idx.row() for idx in self.table_view.selectionModel().selectedRows()]
        if len(selected_rows) < 2:
            QMessageBox.information(self, "تنبيه", "الرجاء تحديد سطرين أو أكثر لدمجهما معاً.")
            return
        before_events = [deepcopy(e) for e in self.table_model.events]
        before_statuses = dict(self.table_model.statuses)
        ok = self.table_model.merge_lines(selected_rows)
        if ok:
            if self.document:
                self.document.events = self.table_model.events
            cmd = SnapshotEventsCommand(
                self.table_model,
                before_events,
                before_statuses,
                self.table_model.events,
                self.table_model.statuses,
                description="دمج الأسطر المحددة",
                skip_initial_redo=True,
            )
            self.undo_stack.push(cmd)
            EventBus.instance().log_message.emit(f"🔗 تم دمج {len(selected_rows)} أسطر بنجاح.")
            first_row = min(selected_rows)
            if self.document and 0 <= first_row < len(self.document.events) and hasattr(self, 'inline_editor'):
                self._inline_pre_edit_status[first_row] = self.table_model.statuses.get(first_row, "")
                self.inline_editor.load_event(first_row, self.document.events[first_row], len(self.document.events))
            if self.document:
                self._save_file_auto()
                if hasattr(self, 'video_player'):
                    self.video_player.set_subtitles_for_overlay(self.document.events)

    def _split_selected_line(self):
        self._flush_inline_editor()
        selected_rows = [idx.row() for idx in self.table_view.selectionModel().selectedRows()]
        if not selected_rows:
            QMessageBox.information(self, "تنبيه", "الرجاء تحديد السطر المراد تقسيمه أولاً.")
            return
        target_row = selected_rows[0]
        split_at_ms = None
        if hasattr(self, 'video_player') and not self.video_container.isHidden():
            split_at_ms = self.video_player.get_current_position_ms()
        before_events = [deepcopy(e) for e in self.table_model.events]
        before_statuses = dict(self.table_model.statuses)
        ok = self.table_model.split_line(target_row, split_at_ms=split_at_ms)
        if ok:
            if self.document:
                self.document.events = self.table_model.events
            cmd = SnapshotEventsCommand(
                self.table_model,
                before_events,
                before_statuses,
                self.table_model.events,
                self.table_model.statuses,
                description="تقسيم السطر",
                skip_initial_redo=True,
            )
            self.undo_stack.push(cmd)
            EventBus.instance().log_message.emit(f"✂️ تم تقسيم السطر #{target_row + 1} إلى سطرين بنجاح.")
            if self.document and 0 <= target_row < len(self.document.events) and hasattr(self, 'inline_editor'):
                self._inline_pre_edit_status[target_row] = self.table_model.statuses.get(target_row, "")
                self.inline_editor.load_event(target_row, self.document.events[target_row], len(self.document.events))
            if self.document:
                self._save_file_auto()
                if hasattr(self, 'video_player'):
                    self.video_player.set_subtitles_for_overlay(self.document.events)

    def _cleanup_temp_files(self):
        for p in list(self.temp_extracted_files):
            try:
                if os.path.exists(p):
                    os.remove(p)
            except Exception:
                pass
        self.temp_extracted_files.clear()

    def closeEvent(self, event):
        if self._translation_task and not self._translation_task.done():
            self._translation_task.cancel()
        if hasattr(self, 'provider_panel') and hasattr(self.provider_panel, 'stop_background_tasks'):
            self.provider_panel.stop_background_tasks()
        if hasattr(self, 'metadata_service') and hasattr(self.metadata_service, 'aclose'):
            try:
                loop = asyncio.get_running_loop()
                if loop.is_running():
                    loop.create_task(self.metadata_service.aclose())
            except RuntimeError:
                pass
        self._cleanup_temp_files()
        if hasattr(self, 'video_player'):
            self.video_player.cleanup()
        if hasattr(self, 'db') and hasattr(self.db, 'close'):
            self.db.close()
        super().closeEvent(event)

    def _new_session(self):
        self._cleanup_temp_files()
        if self.current_file_path:
            CheckpointManager.cleanup(self.current_file_path)
        for f in list(self.selected_files) + list(self.source_files):
            CheckpointManager.cleanup(f)
            
        self.video_origin_map.clear()
        self.source_video_origin.clear()
        self.temp_extracted_files.clear()
        self.detected_source_lang = None
        self.stream_lang_code = None
        self.settings_panel.set_detected_language("")
        self.document = None
        self.current_file_path = None
        self.selected_files = []
        self.source_files = []
        self.output_files = {}
        self.current_anime_id = None
        self.glossary_entries = self.glossary_repo.get_all_for_anime(None)
        self._inline_pre_edit_status.clear()
        self.table_model.set_events([])
        self.character_panel.table.setRowCount(0)
        self.character_panel.lbl_anime_title.setText("العمل: لم يتم الكشف بعد (No Media Detected)")
        self.file_panel.lbl_selected.setText("اسحب وأفلت الفيديوهات أو ملفات الترجمة هنا مباشرة (Drag & Drop)")
        self.log_panel.text_edit.clear()
        self.live_preview.clear()
        if hasattr(self, 'inline_editor'):
            self.inline_editor.clear()
        if hasattr(self, 'undo_stack'):
            self.undo_stack.clear()
        if hasattr(self, 'find_replace_bar'):
            self.find_replace_bar.hide_bar()
        if hasattr(self, 'video_player'):
            self.video_player.subtitles = []
            self.video_player.cleanup()
        self.current_video_file = None
        self.video_container.setVisible(False)
        self.btn_toggle_video.setText("🎬 مشغل الوسائط والمعاينة الحية (طافي لتوفير موارد الجهاز - اضغط للفتح)")
        self.btn_toggle_video.setStyleSheet("""
            QPushButton {
                background-color: #18181b;
                color: #94a3b8;
                font-weight: 600;
                font-size: 8.5pt;
                border: 1px solid #27272a;
                border-radius: 5px;
                padding: 3px 12px;
            }
            QPushButton:hover {
                background-color: #27272a;
                color: #38bdf8;
                border-color: #0284c7;
            }
        """)
        self.progress_panel.lbl_stats.setText("جاهز للعمل | الأسطر: 0/0 | السرعة: 0.0 سطر/ث | الوقت المتبقي: --:--")
        self.progress_panel.progress_bar.setValue(0)
        self.is_fresh_session = True
            
        EventBus.instance().log_message.emit("🧹 تم بدء جلسة جديدة للواجهة مع الحفاظ على ذاكرة الترجمة وبيانات الأعمال المحفوظة (Fresh UI Session).")

    def _open_review_dialog(self):
        if not self.document:
            EventBus.instance().log_message.emit("No document loaded to review.")
            return
        self._flush_inline_editor()
        dlg = TranslationReviewDialog(self, document=self.document)
        if dlg.exec():
            self.table_model.set_events(self.document.events)
            self._save_file_auto()
            EventBus.instance().log_message.emit("Translation edits saved and updated in document.")

    def _open_untranslated_dialog(self):
        if not self.document or not self.document.events:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.information(self, "تنبيه", "لا يوجد ملف ترجمة محمل حالياً.")
            return

        self._flush_inline_editor()
        from app.translation.engine import TranslationEngine
        from app.ui.dialogs.untranslated_dialog import UntranslatedLinesDialog
        from PySide6.QtWidgets import QMessageBox

        target_lang = self.settings_panel.get_target_lang_clean()
        healing_opts = self.healing_panel.get_healing_options()
        skip_fx = healing_opts.get("skip_visual_effects", True)
        trans_signs = healing_opts.get("translate_signs", False)

        untranslated = TranslationEngine.find_untranslated_events(
            self.document,
            target_lang=target_lang,
            skip_effects=skip_fx,
            include_signs=trans_signs,
        )

        if not untranslated:
            QMessageBox.information(
                self,
                "اكتملت الترجمة 100%",
                "🎉 رائع! جميع أسطر الحوار في هذا الملف مترجمة ومكتملة ولا توجد أي أسطر متبقية."
            )
            return

        orig_display = os.path.basename(self.current_file_path or "ملف الترجمة")
        dlg = UntranslatedLinesDialog(
            parent=self,
            events=untranslated,
            filename=orig_display,
            is_batch=False
        )
        if dlg.exec():
            if dlg.selected_action == UntranslatedLinesDialog.ACTION_TRANSLATE:
                self._on_translate_remaining_requested(untranslated)
            elif dlg.selected_action == UntranslatedLinesDialog.ACTION_SAVE_AS_IS:
                self._save_file_auto(self.current_file_path)

    def _on_translate_remaining_requested(self, untranslated_events: List[SubtitleEvent]):
        if not untranslated_events or not self.document:
            return

        from app.providers.factory import ProviderFactory
        from app.translation.batcher import TokenBatcher
        from app.translation.engine import TranslationEngine
        from app.core.database import TranslationMemoryRepository

        config = self.provider_panel.get_active_config()
        if not config:
            EventBus.instance().log_message.emit("Please select a provider first.")
            return
        provider = ProviderFactory.create_provider(config)
        model = self.provider_panel.get_selected_model()

        batch_size = self.settings_panel.sb_batch_size.value()
        max_toks = self.settings_panel.sb_max_tokens.value()
        max_ctx = getattr(self.settings_panel, 'sb_max_context', None)
        max_context = max_ctx.value() if max_ctx else 4096
        is_local_eng = config and any(k in str(getattr(config, "provider_type", "")).lower() for k in ("lmstudio", "ollama", "lm_studio"))
        local_limit = min(15, batch_size) if is_local_eng else batch_size
        batcher = TokenBatcher(max_tokens=max_toks, max_events=batch_size, local_max_events=local_limit, max_context=max_context)
        engine = TranslationEngine(batcher=batcher, tm_repo=TranslationMemoryRepository(self.db))

        source_lang_pref = self.settings_panel.get_source_lang_clean()
        source_lang = getattr(self, "detected_source_lang", None) or source_lang_pref or "en"
        target_lang = self.settings_panel.get_target_lang_clean()
        story_notes = self.healing_panel.get_story_notes()
        auto_heal = self.healing_panel.chk_auto_heal.isChecked()
        healing_opts = self.healing_panel.get_healing_options()
        concurrency = self.settings_panel.sb_concurrency.value()
        temp = self.settings_panel.sb_temp.value()
        active_chars = self.character_panel.get_characters()
        glossary = self.glossary_entries

        async def run_remaining():
            self.provider_panel.pause_auto_detect()
            try:
                self.progress_panel.lbl_stats.setText(f"🚀 استكمال ترجمة {len(untranslated_events)} سطر متبقي بالسياق الكامل...")
                await engine.translate_remaining_events(
                    document=self.document,
                    remaining_events=untranslated_events,
                    provider=provider,
                    model=model,
                    source_lang=source_lang,
                    target_lang=target_lang,
                    characters=active_chars,
                    glossary=glossary,
                    story_notes=story_notes,
                    on_batch_status=self.table_model.set_batch_status,
                    concurrency=concurrency,
                    temperature=temp,
                    max_tokens=max_toks,
                    max_context=max_context,
                    auto_heal=auto_heal,
                    healing_options=healing_opts,
                    top_p=self.settings_panel.sb_top_p.value() if hasattr(self.settings_panel, 'sb_top_p') else 0.85,
                    min_p=getattr(self.settings_panel.settings, 'min_p', 0.05),
                    repetition_penalty=self.settings_panel.sb_rep_penalty.value() if hasattr(self.settings_panel, 'sb_rep_penalty') else 1.0,
                )
                if self.document and self.document.events:
                    self.table_model._emit_contiguous_rows_changed(list(range(len(self.document.events))), 5, 6)
                    curr_r = self.table_view.currentIndex().row()
                    if 0 <= curr_r < len(self.document.events):
                        self.inline_editor.load_event(curr_r, self.document.events[curr_r], len(self.document.events))
                await self._save_file_auto_async(self.current_file_path, source_key=self.current_file_path)
                self.progress_panel.lbl_stats.setText("🎉 اكتملت ترجمة الأسطر المتبقية وتم حفظ الملف بنجاح!")
                EventBus.instance().log_message.emit("🎉 اكتملت ترجمة الأسطر المتبقية وتم حفظ الملف النهائي بنجاح!")
            except Exception as ex:
                EventBus.instance().log_message.emit(f"خطأ أثناء ترجمة الأسطر المتبقية: {ex}")
            finally:
                self.provider_panel.resume_auto_detect()
                if provider:
                    await provider.close()
                self.progress_panel._reset_controls()

        try:
            loop = asyncio.get_running_loop()
            self._translation_task = loop.create_task(run_remaining())
        except RuntimeError:
            pass

    def _save_file(self):
        if not self.document or not self.current_file_path:
            EventBus.instance().log_message.emit("No document to save.")
            return
        self._flush_inline_editor()
            
        from PySide6.QtWidgets import QFileDialog
        from pathlib import Path
        
        orig_target = self.video_origin_map.get(self.current_file_path, self.current_file_path)
        orig_path = Path(orig_target)
        target_ext = orig_path.suffix if orig_path.suffix.lower() in ('.ass', '.srt', '.vtt') else '.ass'
        default_save_path = str(orig_path.with_name(f"{orig_path.stem}.ara{target_ext}"))
        
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Translated Subtitle",
            default_save_path,
            "ASS Subtitle (*.ass);;SRT Subtitle (*.srt);;All Files (*)"
        )
        
        if file_path:
            try:
                write_subtitle(self.document, file_path)
                EventBus.instance().log_message.emit(f"Successfully saved to {file_path}")
                self.current_file_path = file_path
            except Exception as e:
                EventBus.instance().log_message.emit(f"Failed to save file: {e}")
                from PySide6.QtWidgets import QMessageBox
                fallback_path = Path.home() / "Documents" / Path(file_path).name
                reply = QMessageBox.question(
                    self,
                    "تعذر الحفظ في المجلد المحدد",
                    f"تعذر الحفظ في المسار المختار بسبب قيود الصلاحيات في ويندوز:\n{e}\n\nهل ترغب بحفظ الملف في مجلد المستندات بدلاً من ذلك؟\n{fallback_path}",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.Yes
                )
                if reply == QMessageBox.Yes:
                    try:
                        fallback_path.parent.mkdir(parents=True, exist_ok=True)
                        write_subtitle(self.document, str(fallback_path))
                        EventBus.instance().log_message.emit(f"Successfully saved to fallback: {fallback_path}")
                        self.current_file_path = str(fallback_path)
                    except Exception as fb_err:
                        EventBus.instance().log_message.emit(f"Fallback save failed: {fb_err}")

    def _build_auto_save_plan(self, file_path: str = None, source_key: str = None):
        target_path = file_path or self.current_file_path
        if not target_path:
            return None

        cleanup_paths = []
        is_video_temp = target_path in self.video_origin_map or target_path in self.temp_extracted_files
        v_origin = self.video_origin_map.get(target_path) or self.source_video_origin.get(target_path)

        if v_origin:
            video_path = Path(v_origin)
            video_dir = video_path.parent
            video_stem = video_path.stem
            if not video_dir.exists():
                parent_dir = video_dir.parent
                if parent_dir.exists():
                    candidates = list(parent_dir.glob(f"**/{video_path.name}"))
                    if candidates:
                        video_path = candidates[0]
                        video_dir = video_path.parent
                        if target_path in self.video_origin_map:
                            self.video_origin_map[target_path] = str(video_path)
                        self.source_video_origin[target_path] = str(video_path)
            os.makedirs(video_dir, exist_ok=True)
            auto_save_path = str(video_dir / f"{video_stem}.ara.ass")
            cleanup_paths.append(target_path)
            stray_raw_ass = video_dir / f"{video_stem}.ass"
            if stray_raw_ass.exists() and str(stray_raw_ass) != auto_save_path:
                cleanup_paths.append(str(stray_raw_ass))
            stem = video_stem
            bi_save_path = str(video_dir / f"{video_stem}.bi.ass")
        else:
            orig_path = Path(target_path)
            stem = orig_path.stem
            if stem.endswith(".ara"):
                stem = stem[:-4]
            elif stem.endswith("_improved"):
                stem = stem[:-9]
            auto_save_path = str(orig_path.with_name(f"{stem}.ara{orig_path.suffix}"))
            bi_save_path = str(orig_path.with_name(f"{stem}.bi{orig_path.suffix}"))

        export_mode = self.settings_panel.cb_export.currentText()
        want_bi = ("Bilingual" in export_mode or "ثنائي" in export_mode)
        bi_doc = None
        if want_bi:
            bi_doc = deepcopy(self.document)
            for ev in bi_doc.events:
                if ev.translated_text:
                    clean_orig = ev.get_clean_text()
                    if getattr(bi_doc, "format", None) and getattr(bi_doc.format, "value", "") == "ass":
                        ev.translated_text = f"{ev.translated_text}\\N{{\\rDefault\\fs14\\c&HCCCCCC&}}{clean_orig}"
                    else:
                        ev.translated_text = f"{ev.translated_text}\n{clean_orig}"

        return {
            "target_path": target_path,
            "source_key": source_key or target_path,
            "auto_save_path": auto_save_path,
            "is_video_temp": is_video_temp,
            "cleanup_paths": cleanup_paths,
            "bi_doc": bi_doc,
            "bi_save_path": bi_save_path if want_bi else None,
            "file_path_arg": file_path,
        }

    def _finalize_auto_save(self, plan: dict):
        target_path = plan["target_path"]
        auto_save_path = plan["auto_save_path"]
        src_key = plan["source_key"]

        for p_clean in plan["cleanup_paths"]:
            try:
                if p_clean and p_clean != auto_save_path and os.path.exists(p_clean):
                    os.remove(p_clean)
                self.temp_extracted_files.discard(p_clean)
            except Exception as e:
                EventBus.instance().log_message.emit(f"Notice: Cleaning temp extracted file: {e}")

        EventBus.instance().log_message.emit(f"💾 تم حفظ ملف الترجمة المعتمد والمصقول في: {auto_save_path}")
        self.current_file_path = auto_save_path
        self.output_files[src_key] = auto_save_path
        if src_key != target_path:
            self.output_files[target_path] = auto_save_path

        # Preserve video temp->output transition in selected_files while keeping source_files immutable
        if plan["is_video_temp"]:
            if target_path in self.selected_files:
                idx = self.selected_files.index(target_path)
                self.selected_files[idx] = auto_save_path
            elif plan["file_path_arg"] and plan["file_path_arg"] in self.selected_files:
                idx = self.selected_files.index(plan["file_path_arg"])
                self.selected_files[idx] = auto_save_path

        if plan["bi_save_path"]:
            EventBus.instance().log_message.emit(f"Auto-saved bilingual file to: {plan['bi_save_path']}")

    def _save_file_auto(self, file_path: str = None, source_key: str = None):
        if not self.document:
            return
        plan = self._build_auto_save_plan(file_path=file_path, source_key=source_key)
        if not plan:
            self._save_file()
            return
        try:
            write_subtitle(self.document, plan["auto_save_path"])
            if plan["bi_doc"] is not None and plan["bi_save_path"]:
                write_subtitle(plan["bi_doc"], plan["bi_save_path"])
            self._finalize_auto_save(plan)
        except Exception as e:
            EventBus.instance().log_message.emit(f"Failed auto-save: {e}")
            fallback_saved = False
            for fb_dir in [Path.home() / "Documents" / "SubNovaStudio", Path.home() / "Desktop"]:
                try:
                    fb_dir.mkdir(parents=True, exist_ok=True)
                    fb_path = str(fb_dir / Path(plan["auto_save_path"]).name)
                    write_subtitle(self.document, fb_path)
                    plan["auto_save_path"] = fb_path
                    if plan["bi_doc"] is not None and plan["bi_save_path"]:
                        fb_bi = str(fb_dir / Path(plan["bi_save_path"]).name)
                        write_subtitle(plan["bi_doc"], fb_bi)
                        plan["bi_save_path"] = fb_bi
                    self._finalize_auto_save(plan)
                    EventBus.instance().log_message.emit(
                        f"🛡️ تم حفظ الملف بنجاح في المسار الآمن البديل: {fb_path}"
                    )
                    fallback_saved = True
                    break
                except Exception:
                    continue
            if not fallback_saved:
                self._save_file()

    async def _save_file_auto_async(self, file_path: str = None, source_key: str = None):
        if not self.document:
            return
        plan = self._build_auto_save_plan(file_path=file_path, source_key=source_key)
        if not plan:
            return
        try:
            await asyncio.to_thread(write_subtitle, self.document, plan["auto_save_path"])
            if plan["bi_doc"] is not None and plan["bi_save_path"]:
                await asyncio.to_thread(write_subtitle, plan["bi_doc"], plan["bi_save_path"])
            self._finalize_auto_save(plan)
        except Exception as e:
            EventBus.instance().log_message.emit(f"Failed auto-save: {e}")
            fallback_saved = False
            for fb_dir in [Path.home() / "Documents" / "SubNovaStudio", Path.home() / "Desktop"]:
                try:
                    fb_dir.mkdir(parents=True, exist_ok=True)
                    fb_path = str(fb_dir / Path(plan["auto_save_path"]).name)
                    await asyncio.to_thread(write_subtitle, self.document, fb_path)
                    plan["auto_save_path"] = fb_path
                    if plan["bi_doc"] is not None and plan["bi_save_path"]:
                        fb_bi = str(fb_dir / Path(plan["bi_save_path"]).name)
                        await asyncio.to_thread(write_subtitle, plan["bi_doc"], fb_bi)
                        plan["bi_save_path"] = fb_bi
                    self._finalize_auto_save(plan)
                    EventBus.instance().log_message.emit(
                        f"🛡️ تم حفظ الملف بنجاح في المسار الآمن البديل: {fb_path}"
                    )
                    fallback_saved = True
                    break
                except Exception:
                    continue
            if not fallback_saved:
                self._save_file()

    def _save_file_improved(self, file_path: str = None):
        """Deprecated: Saves directly into the unified single .ara file."""
        self._save_file_auto(file_path)
        
    def _open_char_add(self):
        dlg = CharacterEditorDialog(self, initial_data={"row": None})
        dlg.exec()

    def _open_char_editor(self):
        selected_data = self.character_panel.get_selected_character()
        dlg = CharacterEditorDialog(self, initial_data=selected_data)
        dlg.exec()
        
    def _open_glossary_editor(self):
        dlg = GlossaryEditorDialog(self, initial_entries=self.glossary_entries, anime_id=self.current_anime_id)
        if dlg.exec():
            edited_entries = dlg.get_glossary_entries()
            self.glossary_entries = self.glossary_repo.replace_entries_for_anime(self.current_anime_id, edited_entries)
            EventBus.instance().log_message.emit(
                f"Saved {len(self.glossary_entries)} glossary entries ({'anime-linked' if self.current_anime_id else 'global'})."
            )
        
    def _open_anime_search(self):
        dlg = AnimeSearchDialog(self, metadata_service=self.metadata_service)
        if dlg.exec():
            selected = dlg.selected_media or dlg.selected_anime
            if selected:
                if getattr(selected, "id", None) is None:
                    self.metadata_service.persist_media_and_characters(selected, dlg.selected_characters)
                self.current_anime_id = getattr(selected, "id", None)
                title = selected.display_title
                m_type = "TV Series" if selected.media_type == "tv" else ("Movie" if selected.media_type == "movie" else "Anime")
                self.character_panel.lbl_anime_title.setText(f"{m_type}: {title}")
                self.character_panel.table.setRowCount(0)
                try:
                    for char in dlg.selected_characters:
                        if hasattr(char, 'gender') and hasattr(char.gender, 'value'):
                            gender_str = char.gender.value
                        elif hasattr(char, 'gender_info') and hasattr(char.gender_info.gender, 'value'):
                            gender_str = char.gender_info.gender.value
                        else:
                            gender_str = str(getattr(char, 'gender', 'UNKNOWN'))

                        conf = getattr(char, 'gender_confidence', None)
                        if conf is None and hasattr(char, 'gender_info'):
                            conf = getattr(char.gender_info, 'confidence', 0.0)

                        src = getattr(char, 'gender_source', None)
                        if src is None and hasattr(char, 'gender_info'):
                            src = getattr(char.gender_info, 'source', '')

                        self.character_panel.add_character(
                            char.canonical_name or "",
                            char.arabic_name or "",
                            gender_str or "",
                            conf if conf is not None else 0.0,
                            src or "",
                            profile=char,
                        )
                    if self.current_anime_id is not None:
                        db_glossary = self.glossary_repo.get_all_for_anime(self.current_anime_id)
                        if db_glossary:
                            self.glossary_entries = db_glossary
                except Exception as e:
                    EventBus.instance().log_message.emit(f"Error adding characters: {e}")
                    import traceback
                    traceback.print_exc()

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            return
        event.ignore()

    def dropEvent(self, event: QDropEvent):
        urls = event.mimeData().urls()
        if urls:
            paths = [url.toLocalFile() for url in urls if url.isLocalFile()]
            if paths:
                self.file_panel._handle_incoming_paths(paths)
                event.acceptProposedAction()
