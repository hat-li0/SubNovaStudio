import asyncio
from typing import List, Tuple, Dict
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox, QLabel, QComboBox,
    QLineEdit, QPushButton, QFrame, QScrollArea, QSizePolicy, QApplication
)
from PySide6.QtCore import Qt, QTimer

from app.models.provider import ProviderConfig, ProviderType, ModelInfo
from app.providers import get_provider
from app.providers.gemini import GEMINI_DEFAULT_MODELS
from app.providers.openai import OPENAI_DEFAULT_MODELS
from app.ui.bus import EventBus
from app.core.config import get_settings
from app.ui.widgets.settings_panel import IntStepper


PROVIDER_MODEL_PRESETS: Dict[str, List[Tuple[str, str]]] = {
    "gemini": [
        ("gemini-2.5-flash", "⚡ فائق السرعة والأحدث (موصى به للترجمة)"),
        ("gemini-2.5-pro", "🧠 الأعلى ذكاءً وجودة سياقية"),
        ("gemini-2.0-flash", "⚡ سرعة قياسية واستجابة فورية"),
        ("gemini-1.5-flash", "🌟 خفيف وموثوق"),
        ("gemini-1.5-pro", "💎 تدقيق وترجمة متعمقة ورصينة"),
    ],
    "openai": [
        ("gpt-4o", "🌟 الرائد الأعلى دقة من OpenAI"),
        ("gpt-4o-mini", "⚡ فائق السرعة واقتصادي جداً (موصى به)"),
        ("o3-mini", "🧠 تفكير تحليلي متقدم"),
        ("o1-mini", "🔬 تفكير عميق ومنطقي"),
        ("gpt-4-turbo", "💎 الإصدار الكلاسيكي المتقدم"),
    ],
    "lmstudio": [
        ("allam-7b-arabic-sft", "🇸🇦 علام 7B العربي (SFT عالي الدقة)"),
        ("allam-7b-instruct-preview", "🇸🇦 علام 7B الاستدلالي"),
        ("qwen2.5-7b-instruct", "🏆 الأفضل في الترجمة (7B)"),
        ("qwen2.5-14b-instruct", "🚀 جودة ترجمة استثنائية (14B)"),
        ("mistral-nemo-12b", "⚡ نموذج متوازن متعدد اللغات"),
        ("deepseek-r1-distill-qwen-7b", "🧠 تفكير منطقي متميز"),
    ],
    "ollama": [
        ("allam:7b", "🇸🇦 علام 7B العربي (فائق الدقة)"),
        ("qwen2.5:7b", "🏆 الأفضل في الترجمة (7B)"),
        ("qwen2.5:14b", "🚀 جودة ترجمة استثنائية (14B)"),
        ("llama3.2:latest", "⚡ نموذج Meta خفيف وسريع"),
        ("deepseek-r1:8b", "🧠 تفكير استدلالي"),
    ],
    "openai_compatible": [
        ("deepseek-chat", "🌟 DeepSeek V3 عالي الدقة"),
        ("deepseek-reasoner", "🧠 DeepSeek R1 تفكير تحليلي"),
        ("qwen-plus", "🏆 Qwen السحابي فائق الجودة"),
        ("gpt-4o-mini", "⚡ متوافق مع OpenAI"),
    ]
}


class ProviderPanel(QWidget):
    """
    SubNova Studio — Dynamic Provider Panel.
    Supports real-time provider switching, instant model presets, dynamic remote model discovery,
    and developer credits.
    """

    PROVIDER_ITEMS = [
        ("🤖 LM Studio (Local / محلي)", "lmstudio"),
        ("🦙 Ollama (Local / محلي)", "ollama"),
        ("✨ Google Gemini (سحابي)", "gemini"),
        ("⚡ OpenAI (ChatGPT)", "openai"),
        ("🌐 Custom OpenAI-Compatible (مخصص)", "openai_compatible"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.settings = get_settings()
        self._is_populating = False
        self._probe_running = False
        self._probe_task = None
        self._refresh_task = None
        self._test_task = None
        self._pause_depth = 0
        self._stopped = False
        
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        container = QWidget()
        self.layout = QVBoxLayout(container)
        self.layout.setSpacing(10)
        self.layout.setContentsMargins(8, 8, 12, 8)
        self._discovered_models: Dict[str, ModelInfo] = {}

        # 1. Provider Selector Box
        lbl_p = QLabel("مزود الذكاء الاصطناعي (AI Provider):")
        lbl_p.setStyleSheet("font-weight: 600; color: #38bdf8; font-size: 9pt;")
        self.layout.addWidget(lbl_p)

        self.cb_provider = QComboBox()
        for label, val in self.PROVIDER_ITEMS:
            self.cb_provider.addItem(label, val)
        self.layout.addWidget(self.cb_provider)

        # Separator line
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color: #27272a;")
        self.layout.addWidget(sep)

        # 2. Server / Base URL container (for LM Studio, Ollama, Custom)
        self.url_container = QWidget()
        url_layout = QVBoxLayout(self.url_container)
        url_layout.setContentsMargins(0, 0, 0, 0)
        url_layout.setSpacing(4)
        self.lbl_url = QLabel("عنوان الخادم (Server URL):")
        self.lbl_url.setStyleSheet("color: #a1a1aa; font-size: 8.5pt;")
        url_layout.addWidget(self.lbl_url)
        self.le_url = QLineEdit()
        self.le_url.setPlaceholderText("e.g. http://localhost:1234/v1")
        url_layout.addWidget(self.le_url)
        self.layout.addWidget(self.url_container)

        # 3. API Key container (for Gemini, OpenAI, Custom)
        self.key_container = QWidget()
        key_layout = QVBoxLayout(self.key_container)
        key_layout.setContentsMargins(0, 0, 0, 0)
        key_layout.setSpacing(4)
        self.lbl_key = QLabel("مفتاح API Key:")
        self.lbl_key.setStyleSheet("color: #a1a1aa; font-size: 8.5pt;")
        key_layout.addWidget(self.lbl_key)

        key_input_row = QHBoxLayout()
        key_input_row.setSpacing(6)
        self.le_key = QLineEdit()
        self.le_key.setEchoMode(QLineEdit.Password)
        self.le_key.setPlaceholderText("أدخل مفتاح الـ API الخاص بك هنا...")
        key_input_row.addWidget(self.le_key)

        self.btn_toggle_key = QPushButton("👁️")
        self.btn_toggle_key.setFixedWidth(36)
        self.btn_toggle_key.setToolTip("إظهار / إخفاء المفتاح")
        self.btn_toggle_key.clicked.connect(self._toggle_key_visibility)
        key_input_row.addWidget(self.btn_toggle_key)
        key_layout.addLayout(key_input_row)
        self.layout.addWidget(self.key_container)

        # 4. Model Selection Container (Header with Refresh Button + Dropdown + Quick Preset Chips)
        model_hdr = QHBoxLayout()
        lbl_m = QLabel("النموذج المختار (Model):")
        lbl_m.setStyleSheet("font-weight: 600; color: #38bdf8; font-size: 9pt;")
        model_hdr.addWidget(lbl_m)
        model_hdr.addStretch()

        self.btn_refresh = QPushButton("⟳ جلب النماذج")
        self.btn_refresh.setFixedWidth(95)
        self.btn_refresh.setFixedHeight(26)
        self.btn_refresh.setToolTip("الاتصال بالمزود والبحث عن كافة النماذج المتوفرة")
        self.btn_refresh.setStyleSheet("background-color: #27272a; color: #38bdf8; font-size: 8pt; padding: 2px 6px; border-radius: 4px; border: 1px solid #3f3f46;")
        model_hdr.addWidget(self.btn_refresh)
        self.layout.addLayout(model_hdr)

        self.cb_models = QComboBox()
        self.cb_models.setEditable(True)  # Allows typing custom model names
        self.cb_models.setMinimumHeight(30)
        self.layout.addWidget(self.cb_models)

        # Quick Model Preset Chips Container
        lbl_presets = QLabel("نماذج مقترحة سريعة (اضغط للاختيار الفوري):")
        lbl_presets.setStyleSheet("color: #71717a; font-size: 7.5pt; margin-top: 2px;")
        self.layout.addWidget(lbl_presets)

        self.preset_chips_widget = QWidget()
        self.preset_chips_layout = QGridLayout(self.preset_chips_widget)
        self.preset_chips_layout.setContentsMargins(0, 0, 0, 0)
        self.preset_chips_layout.setSpacing(4)
        self.layout.addWidget(self.preset_chips_widget)

        # 5. Model Execution Parameters (Max Context & Parallel Requests)
        grp_engine = QGroupBox("⚡ معاملات تشغيل النموذج (Context & Parallel)")
        grp_engine.setStyleSheet("QGroupBox { margin-top: 6px; } QGroupBox::title { color: #38bdf8; }")
        layout_engine = QVBoxLayout(grp_engine)
        layout_engine.setSpacing(6)
        layout_engine.setContentsMargins(10, 14, 10, 10)

        # Context Stepper Row
        ctx_row = QHBoxLayout()
        lbl_ctx = QLabel("سياق النموذج (Max Context):")
        lbl_ctx.setStyleSheet("color: #a1a1aa; font-size: 8.5pt;")
        self.sb_max_context = IntStepper(min_val=512, max_val=262144, val=getattr(self.settings, 'max_context', 4096), step=512)
        self.sb_max_context.setToolTip("الحد الأقصى لسياق النموذج بالتوكنز (يتم تحديثه تلقائياً بناءً على مواصفات الموديل الشغال)")
        ctx_row.addWidget(lbl_ctx)
        ctx_row.addWidget(self.sb_max_context, 1)
        layout_engine.addLayout(ctx_row)

        self.lbl_context_badge = QLabel("⚡ يتحدد تلقائياً حسب النموذج المختار")
        self.lbl_context_badge.setStyleSheet("color: #4ade80; font-size: 7.5pt; font-weight: 500;")
        layout_engine.addWidget(self.lbl_context_badge)

        # Parallel Concurrency Stepper Row
        par_row = QHBoxLayout()
        lbl_par = QLabel("توازي الطلبات (Parallel):")
        lbl_par.setStyleSheet("color: #a1a1aa; font-size: 8.5pt;")
        self.sb_parallel = IntStepper(min_val=1, max_val=16, val=getattr(self.settings, 'concurrency', 1), step=1)
        self.sb_parallel.setToolTip("عدد الطلبات المتوازية للموديل (ينصح بـ 1 أو 2 للنماذج المحلية مثل علام لعدم إثقال كرت الشاشة والمعالج)")
        par_row.addWidget(lbl_par)
        par_row.addWidget(self.sb_parallel, 1)
        layout_engine.addLayout(par_row)

        self.layout.addWidget(grp_engine)

        # 6. Connection Test & Status Card
        test_box = QFrame()
        test_box.setStyleSheet("background-color: #18181b; border: 1px solid #27272a; border-radius: 6px; padding: 6px;")
        test_layout = QVBoxLayout(test_box)
        test_layout.setSpacing(6)
        test_layout.setContentsMargins(8, 8, 8, 8)

        self.btn_test = QPushButton("⚡ فحص واختبار الاتصال بالمزود")
        self.btn_test.setFixedHeight(30)
        self.btn_test.setStyleSheet("background-color: #27272a; color: #f4f4f5; font-weight: 600; border-radius: 4px; border: 1px solid #3f3f46;")
        test_layout.addWidget(self.btn_test)

        self.lbl_status = QLabel("الحالة: جاهز للاتصال")
        self.lbl_status.setStyleSheet("color: #a1a1aa; font-size: 8.5pt;")
        self.lbl_status.setWordWrap(True)
        self.lbl_status.setAlignment(Qt.AlignCenter)
        test_layout.addWidget(self.lbl_status)
        self.layout.addWidget(test_box)

        self.layout.addStretch()

        # 6. Developer Footer Card (SubNova Studio Credits)
        dev_card = QFrame()
        dev_card.setStyleSheet("background-color: #0f172a; border: 1px solid #1e293b; border-radius: 8px; padding: 6px;")
        dev_c_layout = QVBoxLayout(dev_card)
        dev_c_layout.setContentsMargins(8, 6, 8, 6)
        dev_c_layout.setSpacing(2)

        lbl_dev_title = QLabel("👑 SubNova Studio v2.0")
        lbl_dev_title.setStyleSheet("color: #38bdf8; font-size: 8pt; font-weight: 700;")
        lbl_dev_title.setAlignment(Qt.AlignCenter)

        lbl_dev_credits = QLabel("تطوير: حاتم الحربي (Hatim Alharbi) © 2026")
        lbl_dev_credits.setStyleSheet("color: #94a3b8; font-size: 7.5pt; font-weight: 500;")
        lbl_dev_credits.setAlignment(Qt.AlignCenter)

        dev_c_layout.addWidget(lbl_dev_title)
        dev_c_layout.addWidget(lbl_dev_credits)
        self.layout.addWidget(dev_card)

        scroll.setWidget(container)
        outer_layout.addWidget(scroll)

        # Connect UI signals
        self.cb_provider.currentIndexChanged.connect(self._on_provider_changed)
        self.le_url.textChanged.connect(self._on_url_edited)
        self.le_key.textChanged.connect(self._on_key_edited)
        self.cb_models.currentTextChanged.connect(self._on_model_edited)
        self.btn_refresh.clicked.connect(self.refresh_models)
        self.btn_test.clicked.connect(self.test_connection)
        self.sb_max_context.valueChanged.connect(self._on_max_context_changed)
        self.sb_parallel.valueChanged.connect(self._on_parallel_changed)

        # Setup Background Auto-Detector Timer for LM Studio / Ollama
        self._startup_refresh_timer = QTimer(self)
        self._startup_refresh_timer.setSingleShot(True)
        self._startup_refresh_timer.timeout.connect(self._safe_startup_refresh)

        self.auto_detect_timer = QTimer(self)
        self.auto_detect_timer.setInterval(10000)
        self.auto_detect_timer.timeout.connect(self._auto_detect_tick)
        self.auto_detect_timer.start()

        # Initialize current provider selection from settings
        self._load_initial_provider()

    def pause_auto_detect(self) -> None:
        """Pause background auto-detection ticks (reference-counted)."""
        self._pause_depth += 1

    def resume_auto_detect(self) -> None:
        """Resume background auto-detection ticks once all active pauses finish."""
        if self._pause_depth > 0:
            self._pause_depth -= 1

    def stop_background_tasks(self) -> None:
        """Stop timers and cancel pending background async tasks cleanly on shutdown."""
        self._stopped = True
        for timer_attr in ("_startup_refresh_timer", "auto_detect_timer"):
            timer = getattr(self, timer_attr, None)
            if timer is not None and timer.isActive():
                timer.stop()
        for attr in ("_probe_task", "_refresh_task", "_test_task"):
            task = getattr(self, attr, None)
            if task is not None and not task.done():
                task.cancel()
            setattr(self, attr, None)

    def _can_run_background_probe(self) -> bool:
        if getattr(self, "_stopped", False) or getattr(self, "_pause_depth", 0) > 0:
            return False
        if self._is_populating or getattr(self, "_probe_running", False):
            return False
        if QApplication.activeModalWidget() is not None or QApplication.activePopupWidget() is not None:
            return False
        for attr in ("_probe_task", "_refresh_task", "_test_task"):
            task = getattr(self, attr, None)
            if task is not None and not task.done():
                return False
        return True

    def _safe_startup_refresh(self) -> None:
        if getattr(self, "_stopped", False) or getattr(self, "_pause_depth", 0) > 0:
            return
        if QApplication.activeModalWidget() is not None or QApplication.activePopupWidget() is not None:
            return
        if self._refresh_task is not None and not self._refresh_task.done():
            return
        try:
            loop = asyncio.get_running_loop()
            self._refresh_task = loop.create_task(self._async_refresh_models())
        except RuntimeError:
            pass

    def get_current_provider_type(self) -> str:
        """Returns the currently selected provider type string."""
        return self.cb_provider.currentData() or "lmstudio"

    def _auto_detect_tick(self):
        try:
            ptype = self.get_current_provider_type()
            if ptype in ("lmstudio", "ollama") and self._can_run_background_probe():
                try:
                    loop = asyncio.get_running_loop()
                    self._probe_task = loop.create_task(self._probe_auto_detect(ptype))
                except RuntimeError:
                    pass
        except Exception:
            pass

    async def _probe_auto_detect(self, ptype: str):
        if getattr(self, '_probe_running', False) or getattr(self, '_stopped', False):
            return
        self._probe_running = True
        provider = None
        try:
            config = self.get_provider_config()
            provider = get_provider(config)
            models = await provider.list_models()
            if models and not getattr(self, '_stopped', False):
                for m in models:
                    self._discovered_models[m.id] = m
                current_selected = self.get_selected_model() or self.settings.model_name
                new_ids = [m.id for m in models]
                existing_ids = [self.cb_models.itemData(i) or self.cb_models.itemText(i) for i in range(self.cb_models.count())]
                
                if new_ids != existing_ids:
                    self._is_populating = True
                    self.cb_models.clear()
                    for m in models:
                        self.cb_models.addItem(m.name, userData=m.id)

                    # Preserve user selection
                    target_idx = -1
                    if current_selected:
                        for i in range(self.cb_models.count()):
                            if self.cb_models.itemData(i) == current_selected or self.cb_models.itemText(i) == current_selected:
                                target_idx = i
                                break

                    # Prioritize ALLaM if available locally
                    if target_idx < 0:
                        for i in range(self.cb_models.count()):
                            mid = str(self.cb_models.itemData(i) or "").lower()
                            if "allam" in mid:
                                target_idx = i
                                break

                    if target_idx < 0:
                        for i in range(self.cb_models.count()):
                            mid = str(self.cb_models.itemData(i) or "").lower()
                            if "qwen2.5" in mid or "qwen-2.5" in mid:
                                target_idx = i
                                break

                    if target_idx < 0:
                        for i in range(self.cb_models.count()):
                            txt = self.cb_models.itemText(i)
                            if "نموذج صور" not in txt and "vlm" not in str(self.cb_models.itemData(i) or "").lower():
                                target_idx = i
                                break

                    self.cb_models.setCurrentIndex(target_idx if target_idx >= 0 else 0)
                    chosen = self.get_selected_model()
                    self._is_populating = False
                    self.lbl_status.setText(f"🟢 متصل تلقائياً: [{chosen}]")
                    self.lbl_status.setStyleSheet("color: #4ade80; font-weight: 600;")
                    if chosen:
                        self._detect_and_apply_context(chosen)
                elif not self.cb_models.currentText() and new_ids:
                    chosen = self.get_selected_model()
                    self.lbl_status.setText(f"🟢 متصل: [{chosen}]")
                    self.lbl_status.setStyleSheet("color: #4ade80;")
                    if chosen:
                        self._detect_and_apply_context(chosen)
        except asyncio.CancelledError:
            pass
        except (ConnectionRefusedError, Exception):
            if not getattr(self, '_stopped', False):
                if "متصل" in self.lbl_status.text() or "الحالة: جاهز" in self.lbl_status.text():
                    self.lbl_status.setText(f"⚪ بانتظار تشغيل خادم {ptype} محلياً...")
                    self.lbl_status.setStyleSheet("color: #71717a;")
        finally:
            if provider:
                try:
                    await provider.close()
                except Exception:
                    pass
            self._probe_running = False
            self._probe_task = None

    def _load_initial_provider(self):
        saved_type = self.settings.provider_type or "lmstudio"
        idx = 0
        for i in range(self.cb_provider.count()):
            if self.cb_provider.itemData(i) == saved_type:
                idx = i
                break
        self.cb_provider.setCurrentIndex(idx)
        self._apply_provider_ui(saved_type, is_initial=True)

    def _update_preset_chips(self, ptype: str):
        """Build clickable quick model preset chips arranged in a compact 2-column grid."""
        # Clear existing chips
        while self.preset_chips_layout.count():
            item = self.preset_chips_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        presets = PROVIDER_MODEL_PRESETS.get(ptype, [])
        for idx, (model_id, desc) in enumerate(presets[:6]):
            short_title = model_id.split("/")[-1].replace(":latest", "")
            btn_chip = QPushButton(short_title)
            btn_chip.setToolTip(f"{model_id}\n{desc}")
            btn_chip.setFixedHeight(24)
            btn_chip.setStyleSheet("""
                QPushButton {
                    background-color: #1f2937;
                    color: #93c5fd;
                    border: 1px solid #374151;
                    border-radius: 12px;
                    padding: 0 8px;
                    font-size: 7.5pt;
                    font-weight: 600;
                }
                QPushButton:hover {
                    background-color: #1e3a8a;
                    color: #ffffff;
                    border-color: #3b82f6;
                }
            """)
            btn_chip.clicked.connect(lambda checked=False, m=model_id: self._select_preset_chip(m))
            row = idx // 2
            col = idx % 2
            self.preset_chips_layout.addWidget(btn_chip, row, col)

    def _select_preset_chip(self, model_id: str):
        """Callback when a preset chip button is clicked."""
        self._is_populating = True
        # Look for model in combobox
        target_idx = -1
        for i in range(self.cb_models.count()):
            if self.cb_models.itemData(i) == model_id:
                target_idx = i
                break

        if target_idx >= 0:
            self.cb_models.setCurrentIndex(target_idx)
        else:
            self.cb_models.addItem(model_id, userData=model_id)
            self.cb_models.setCurrentIndex(self.cb_models.count() - 1)

        self._is_populating = False
        self._on_model_edited(model_id)
        self.lbl_status.setText(f"⚡ تم تفعيل النموذج: {model_id}")
        self.lbl_status.setStyleSheet("color: #38bdf8; font-weight: 600;")

    def _apply_provider_ui(self, ptype: str, is_initial: bool = False):
        """Show only relevant input fields based on the selected provider."""
        self._is_populating = True
        self.cb_models.clear()

        # Update quick preset chips
        self._update_preset_chips(ptype)

        # Get presets for this provider
        presets = PROVIDER_MODEL_PRESETS.get(ptype, [])

        if ptype == "lmstudio":
            self.url_container.setVisible(True)
            self.lbl_url.setText("عنوان خادم LM Studio (URL):")
            self.le_url.setText(self.settings.lmstudio_url or "http://localhost:1234/v1")
            self.key_container.setVisible(False)
            self.le_key.clear()
            self.btn_refresh.setEnabled(True)

            for m_id, desc in presets:
                self.cb_models.addItem(f"{m_id} ({desc})", userData=m_id)

            saved_m = self.settings.lmstudio_model or self.settings.model_name or "qwen2.5-7b-instruct"
            self._select_or_add_model(saved_m)

        elif ptype == "ollama":
            self.url_container.setVisible(True)
            self.lbl_url.setText("عنوان خادم Ollama (URL):")
            self.le_url.setText(self.settings.ollama_url or "http://localhost:11434")
            self.key_container.setVisible(False)
            self.le_key.clear()
            self.btn_refresh.setEnabled(True)

            for m_id, desc in presets:
                self.cb_models.addItem(f"{m_id} ({desc})", userData=m_id)

            saved_m = self.settings.ollama_model or "qwen2.5:7b"
            self._select_or_add_model(saved_m)

        elif ptype == "gemini":
            self.url_container.setVisible(False)
            self.key_container.setVisible(True)
            self.lbl_key.setText("مفتاح Google Gemini API Key:")
            self.le_key.setText(self.settings.gemini_api_key or "")
            self.btn_refresh.setEnabled(True)

            for m_id, desc in presets:
                self.cb_models.addItem(f"{m_id} ({desc})", userData=m_id)

            saved_m = self.settings.gemini_model or "gemini-2.5-flash"
            self._select_or_add_model(saved_m)

        elif ptype == "openai":
            self.url_container.setVisible(False)
            self.key_container.setVisible(True)
            self.lbl_key.setText("مفتاح OpenAI API Key:")
            self.le_key.setText(self.settings.openai_api_key or "")
            self.btn_refresh.setEnabled(True)

            for m_id, desc in presets:
                self.cb_models.addItem(f"{m_id} ({desc})", userData=m_id)

            saved_m = self.settings.openai_model or "gpt-4o-mini"
            self._select_or_add_model(saved_m)

        elif ptype == "openai_compatible":
            self.url_container.setVisible(True)
            self.lbl_url.setText("عنوان الـ Base URL:")
            self.le_url.setText(self.settings.custom_url or "https://api.openai.com/v1")
            self.key_container.setVisible(True)
            self.lbl_key.setText("مفتاح API Key:")
            self.le_key.setText(self.settings.custom_api_key or "")
            self.btn_refresh.setEnabled(True)

            for m_id, desc in presets:
                self.cb_models.addItem(f"{m_id} ({desc})", userData=m_id)

            saved_m = self.settings.custom_model or "deepseek-chat"
            self._select_or_add_model(saved_m)

        self._is_populating = False

        # Schedule automatic refresh for local providers on startup safely
        if is_initial and ptype in ("lmstudio", "ollama") and hasattr(self, "_startup_refresh_timer"):
            self._startup_refresh_timer.start(400)

    def _select_or_add_model(self, model_name: str):
        """Helper to find and select a model or append it."""
        if not model_name:
            if self.cb_models.count() > 0:
                self.cb_models.setCurrentIndex(0)
            return

        target_idx = -1
        for i in range(self.cb_models.count()):
            if self.cb_models.itemData(i) == model_name or self.cb_models.itemText(i) == model_name:
                target_idx = i
                break

        if target_idx >= 0:
            self.cb_models.setCurrentIndex(target_idx)
        else:
            self.cb_models.addItem(model_name, userData=model_name)
            self.cb_models.setCurrentIndex(self.cb_models.count() - 1)

    def _toggle_key_visibility(self):
        if self.le_key.echoMode() == QLineEdit.Password:
            self.le_key.setEchoMode(QLineEdit.Normal)
            self.btn_toggle_key.setText("🔒")
        else:
            self.le_key.setEchoMode(QLineEdit.Password)
            self.btn_toggle_key.setText("👁️")

    def _on_provider_changed(self, index: int):
        """Immediately responds to provider selection without requiring reload."""
        ptype = self.cb_provider.currentData()
        self.settings.provider_type = ptype
        self.settings.save_to_file()

        # Apply UI layout and presets immediately
        self._apply_provider_ui(ptype)

        current_label = self.cb_provider.currentText()
        selected_m = self.get_selected_model()
        self.lbl_status.setText(f"🟢 تم التبديل إلى: {current_label}")
        self.lbl_status.setStyleSheet("color: #38bdf8; font-weight: 600;")

        if selected_m:
            EventBus.instance().model_selected.emit(selected_m)

        # Auto-refresh if local server
        if ptype in ("lmstudio", "ollama"):
            self.refresh_models()

    def _on_url_edited(self, text: str):
        if self._is_populating:
            return
        ptype = self.cb_provider.currentData()
        clean_text = text.strip()
        if ptype == "lmstudio":
            self.settings.lmstudio_url = clean_text
            self.settings.provider_url = clean_text
        elif ptype == "ollama":
            self.settings.ollama_url = clean_text
            self.settings.provider_url = clean_text
        elif ptype == "openai_compatible":
            self.settings.custom_url = clean_text
            self.settings.provider_url = clean_text
        self.settings.save_to_file()

    def _on_key_edited(self, text: str):
        if self._is_populating:
            return
        ptype = self.cb_provider.currentData()
        clean_key = text.strip()
        if ptype == "gemini":
            self.settings.gemini_api_key = clean_key
        elif ptype == "openai":
            self.settings.openai_api_key = clean_key
        elif ptype == "openai_compatible":
            self.settings.custom_api_key = clean_key
        self.settings.save_to_file()

    def _on_model_edited(self, model: str):
        if self._is_populating or not model:
            return
        if any(keyword in model for keyword in ("Error", "Searching", "Loading", "No models", "لم يتم")):
            return
            
        clean_model = self.get_selected_model()
        if not clean_model:
            return

        ptype = self.cb_provider.currentData()
        if ptype == "lmstudio":
            self.settings.lmstudio_model = clean_model
        elif ptype == "ollama":
            self.settings.ollama_model = clean_model
        elif ptype == "gemini":
            self.settings.gemini_model = clean_model
        elif ptype == "openai":
            self.settings.openai_model = clean_model
        elif ptype == "openai_compatible":
            self.settings.custom_model = clean_model
            
        self.settings.model_name = clean_model
        self.settings.save_to_file()
        self._detect_and_apply_context(clean_model)
        EventBus.instance().model_selected.emit(clean_model)

    def _on_max_context_changed(self, val: int):
        self.settings.max_context = val
        self.settings.save_to_file()

    def _on_parallel_changed(self, val: int):
        self.settings.concurrency = val
        self.settings.save_to_file()

    def _detect_and_apply_context(self, model_id: str):
        if not model_id:
            return
        m_lower = model_id.lower()
        auto_ctx = None

        if hasattr(self, '_discovered_models') and model_id in self._discovered_models:
            m_info = self._discovered_models[model_id]
            if m_info.context_length:
                auto_ctx = m_info.context_length

        if not auto_ctx:
            if "allam" in m_lower:
                auto_ctx = 4096
            elif "qwen2.5" in m_lower or "qwen-2.5" in m_lower:
                auto_ctx = 32768
            elif "ministral" in m_lower or "mistral" in m_lower:
                auto_ctx = 32768
            elif "gemma" in m_lower:
                auto_ctx = 8192
            elif "gemini" in m_lower:
                auto_ctx = 128000
            elif any(k in m_lower for k in ("gpt-4", "o1", "o3", "deepseek")):
                auto_ctx = 64000
            else:
                auto_ctx = getattr(self.settings, 'max_context', 4096)

        if auto_ctx:
            self.sb_max_context.setValue(auto_ctx)
            self.settings.max_context = auto_ctx
            self.settings.save_to_file()
            self.lbl_context_badge.setText(f"✓ سياق تلقائي للنموذج: {auto_ctx} توكن")
            self.lbl_context_badge.setStyleSheet("color: #4ade80; font-size: 7.5pt; font-weight: 600;")

    def get_provider_config(self) -> ProviderConfig:
        """Constructs ProviderConfig with the selected provider, URL, and API key."""
        ptype_str = self.cb_provider.currentData()
        
        if ptype_str == "gemini":
            return ProviderConfig(
                provider_type=ProviderType.GEMINI,
                base_url="https://generativelanguage.googleapis.com/v1beta/openai",
                api_key=self.le_key.text().strip(),
                timeout=120
            )
        elif ptype_str == "openai":
            return ProviderConfig(
                provider_type=ProviderType.OPENAI,
                base_url="https://api.openai.com/v1",
                api_key=self.le_key.text().strip(),
                timeout=120
            )
        elif ptype_str == "ollama":
            return ProviderConfig(
                provider_type=ProviderType.OLLAMA,
                base_url=self.le_url.text().strip() or "http://localhost:11434",
                timeout=120
            )
        elif ptype_str == "openai_compatible":
            return ProviderConfig(
                provider_type=ProviderType.OPENAI_COMPATIBLE,
                base_url=self.le_url.text().strip() or "https://api.openai.com/v1",
                api_key=self.le_key.text().strip() or None,
                timeout=120
            )
        else:  # lmstudio
            return ProviderConfig(
                provider_type=ProviderType.LM_STUDIO,
                base_url=self.le_url.text().strip() or "http://localhost:1234/v1",
                timeout=120
            )

    def get_selected_model(self) -> str:
        """Returns the actual model identifier, stripping any descriptive annotations."""
        idx = self.cb_models.currentIndex()
        if idx >= 0:
            data = self.cb_models.itemData(idx)
            if data:
                return str(data).strip()
        model = self.cb_models.currentText().strip()
        if not model or any(k in model for k in ("Error", "Loading", "Searching", "No models", "لم يتم")):
            return ""
        if " (" in model:
            model = model.split(" (")[0].strip()
        if " [" in model:
            model = model.split(" [")[0].strip()
        return model

    def refresh_models(self):
        if getattr(self, "_stopped", False):
            return
        if self._refresh_task is not None and not self._refresh_task.done():
            return
        try:
            loop = asyncio.get_running_loop()
            self._refresh_task = loop.create_task(self._async_refresh_models())
        except RuntimeError:
            pass

    def test_connection(self):
        if getattr(self, "_stopped", False):
            return
        if self._test_task is not None and not self._test_task.done():
            return
        try:
            loop = asyncio.get_running_loop()
            self._test_task = loop.create_task(self._async_test_connection())
        except RuntimeError:
            pass

    async def _async_refresh_models(self):
        self.btn_refresh.setEnabled(False)
        self.lbl_status.setText("الحالة: جاري جلب النماذج من المزود...")
        self.lbl_status.setStyleSheet("color: #38bdf8;")

        config = self.get_provider_config()
        provider = None

        try:
            provider = get_provider(config)
            models = await provider.list_models()
            if getattr(self, "_stopped", False):
                return
            self._is_populating = True
            current_selected = self.get_selected_model() or self.settings.model_name
            self.cb_models.clear()

            if models:
                for m in models:
                    self._discovered_models[m.id] = m
                    self.cb_models.addItem(m.name, userData=m.id)
                self.lbl_status.setText(f"الحالة: متصل بنجاح ({len(models)} نموذج متاح) ✅")
                self.lbl_status.setStyleSheet("color: #10B981; font-weight: 600;")

                # Restore previously selected model or pick recommended (prioritizing ALLaM)
                target_idx = -1
                if current_selected:
                    for i in range(self.cb_models.count()):
                        if self.cb_models.itemData(i) == current_selected or self.cb_models.itemText(i) == current_selected:
                            target_idx = i
                            break

                if target_idx < 0:
                    for i in range(self.cb_models.count()):
                        mid = str(self.cb_models.itemData(i) or "").lower()
                        if "allam" in mid:
                            target_idx = i
                            break

                if target_idx < 0:
                    for i in range(self.cb_models.count()):
                        mid = str(self.cb_models.itemData(i) or "").lower()
                        if "qwen2.5" in mid or "qwen-2.5" in mid:
                            target_idx = i
                            break

                if target_idx < 0:
                    for i in range(self.cb_models.count()):
                        txt = self.cb_models.itemText(i)
                        if "نموذج صور" not in txt and "vlm" not in str(self.cb_models.itemData(i) or "").lower():
                            target_idx = i
                            break

                self.cb_models.setCurrentIndex(target_idx if target_idx >= 0 else 0)
                selected_clean = self.get_selected_model()
                if selected_clean:
                    self._detect_and_apply_context(selected_clean)
                EventBus.instance().log_message.emit(
                    f"Found {len(models)} models from {config.provider_type.value}. Selected: {selected_clean}"
                )
                EventBus.instance().model_selected.emit(selected_clean)
            else:
                self.cb_models.addItem("No models found")
                self.lbl_status.setText("الحالة: لم يتم العثور على نماذج ⚠️")
                self.lbl_status.setStyleSheet("color: #F59E0B;")
        except asyncio.CancelledError:
            pass
        except Exception as e:
            if not getattr(self, "_stopped", False):
                self.lbl_status.setText("الحالة: تعذر الاتصال بالخادم ❌")
                self.lbl_status.setStyleSheet("color: #EF4444;")
                EventBus.instance().log_message.emit(f"Provider connection error: {str(e)}")
        finally:
            if provider:
                try:
                    await provider.close()
                except Exception:
                    pass
            self._is_populating = False
            self._refresh_task = None
            if not getattr(self, "_stopped", False):
                self.btn_refresh.setEnabled(True)

    async def _async_test_connection(self):
        self.btn_test.setEnabled(False)
        self.lbl_status.setText("الحالة: جاري فحص الاتصال بالمزود...")
        self.lbl_status.setStyleSheet("color: #38bdf8;")
        
        config = self.get_provider_config()
        provider = None

        try:
            provider = get_provider(config)
            avail = await provider.is_available()
            if getattr(self, "_stopped", False):
                return
            if avail:
                self.lbl_status.setText("الحالة: متصل وجاهز للعمل بنجاح ✅")
                self.lbl_status.setStyleSheet("color: #10B981; font-weight: 600;")
                EventBus.instance().log_message.emit(f"Successfully connected to {config.provider_type.value}!")
            else:
                self.lbl_status.setText("الحالة: الخادم غير متصل أو لا يستجيب ❌")
                self.lbl_status.setStyleSheet("color: #EF4444; font-weight: 600;")
                EventBus.instance().log_message.emit(f"Failed to connect to {config.provider_type.value}. Check URL or API Key.")
        except asyncio.CancelledError:
            pass
        except Exception as e:
            if not getattr(self, "_stopped", False):
                self.lbl_status.setText("الحالة: خطأ في الاتصال ❌")
                self.lbl_status.setStyleSheet("color: #EF4444;")
                EventBus.instance().log_message.emit(f"Test connection error: {str(e)}")
        finally:
            if provider:
                try:
                    await provider.close()
                except Exception:
                    pass
            self._test_task = None
            if not getattr(self, "_stopped", False):
                self.btn_test.setEnabled(True)
