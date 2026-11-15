from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QFormLayout, QComboBox, QSpinBox,
    QDoubleSpinBox, QPushButton, QLabel, QGroupBox, QLineEdit, QScrollArea, QFrame, QCheckBox
)
from PySide6.QtCore import Qt, Signal, QTimer
from app.core.config import get_settings
from app.core.constants import SOURCE_LANGUAGES, TARGET_LANGUAGES


class IntStepper(QWidget):
    """
    Spacious, rock-solid integer stepper with large, clearly clickable [+] and [-] buttons.
    Prevents microscopic arrow issues and provides direct input, mouse-wheel scrolling,
    and instantaneous visual response.
    """
    valueChanged = Signal(int)

    def __init__(self, min_val: int = 1, max_val: int = 100, val: int = 10, step: int = 1, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(3)

        self.btn_minus = QPushButton("−")
        self.btn_minus.setFixedSize(28, 28)
        self.btn_minus.setFocusPolicy(Qt.NoFocus)
        self.btn_minus.setCursor(Qt.PointingHandCursor)
        self.btn_minus.setStyleSheet("""
            QPushButton {
                background-color: #27272a;
                color: #f4f4f5;
                border: 1px solid #3f3f46;
                border-radius: 5px;
                font-weight: bold;
                font-size: 13pt;
                padding-bottom: 2px;
            }
            QPushButton:hover {
                background-color: #3f3f46;
                border-color: #38bdf8;
                color: #38bdf8;
            }
            QPushButton:pressed {
                background-color: #18181b;
            }
        """)

        self.spin = QSpinBox()
        self.spin.setRange(min_val, max_val)
        self.spin.setValue(val)
        self.spin.setSingleStep(step)
        self.spin.setAlignment(Qt.AlignCenter)
        self.spin.setFixedHeight(30)
        self.spin.setButtonSymbols(QSpinBox.NoButtons)
        self.spin.setStyleSheet("""
            QSpinBox {
                background-color: #1c1c20;
                border: 1px solid #323238;
                border-radius: 5px;
                color: #fafafa;
                font-weight: 700;
                font-size: 10pt;
                padding: 0 4px;
            }
            QSpinBox:focus {
                border: 1px solid #38bdf8;
                background-color: #202026;
            }
        """)

        self.btn_plus = QPushButton("+")
        self.btn_plus.setFixedSize(28, 28)
        self.btn_plus.setFocusPolicy(Qt.NoFocus)
        self.btn_plus.setCursor(Qt.PointingHandCursor)
        self.btn_plus.setStyleSheet("""
            QPushButton {
                background-color: #27272a;
                color: #f4f4f5;
                border: 1px solid #3f3f46;
                border-radius: 5px;
                font-weight: bold;
                font-size: 13pt;
                padding-bottom: 2px;
            }
            QPushButton:hover {
                background-color: #3f3f46;
                border-color: #38bdf8;
                color: #38bdf8;
            }
            QPushButton:pressed {
                background-color: #18181b;
            }
        """)

        self.btn_minus.clicked.connect(self.spin.stepDown)
        self.btn_plus.clicked.connect(self.spin.stepUp)
        self.spin.valueChanged.connect(self.valueChanged.emit)

        layout.addWidget(self.btn_minus)
        layout.addWidget(self.spin, 1)
        layout.addWidget(self.btn_plus)

    def value(self) -> int:
        return self.spin.value()

    def setValue(self, v: int):
        self.spin.setValue(v)

    def setRange(self, mn: int, mx: int):
        self.spin.setRange(mn, mx)

    def setSingleStep(self, s: int):
        self.spin.setSingleStep(s)

    def setToolTip(self, t: str):
        super().setToolTip(t)
        self.spin.setToolTip(t)
        self.btn_minus.setToolTip(f"إنقاص القيمة ({t})")
        self.btn_plus.setToolTip(f"زيادة القيمة ({t})")


class DoubleStepper(QWidget):
    """
    Spacious floating-point stepper for temperature and fine parameter tuning.
    """
    valueChanged = Signal(float)

    def __init__(self, min_val: float = 0.0, max_val: float = 1.5, val: float = 0.2, step: float = 0.05, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(3)

        self.btn_minus = QPushButton("−")
        self.btn_minus.setFixedSize(28, 28)
        self.btn_minus.setFocusPolicy(Qt.NoFocus)
        self.btn_minus.setCursor(Qt.PointingHandCursor)
        self.btn_minus.setStyleSheet("""
            QPushButton {
                background-color: #27272a;
                color: #f4f4f5;
                border: 1px solid #3f3f46;
                border-radius: 5px;
                font-weight: bold;
                font-size: 13pt;
                padding-bottom: 2px;
            }
            QPushButton:hover {
                background-color: #3f3f46;
                border-color: #38bdf8;
                color: #38bdf8;
            }
            QPushButton:pressed {
                background-color: #18181b;
            }
        """)

        self.spin = QDoubleSpinBox()
        self.spin.setRange(min_val, max_val)
        self.spin.setValue(val)
        self.spin.setSingleStep(step)
        self.spin.setAlignment(Qt.AlignCenter)
        self.spin.setFixedHeight(30)
        self.spin.setButtonSymbols(QDoubleSpinBox.NoButtons)
        self.spin.setStyleSheet("""
            QDoubleSpinBox {
                background-color: #1c1c20;
                border: 1px solid #323238;
                border-radius: 5px;
                color: #fafafa;
                font-weight: 700;
                font-size: 10pt;
                padding: 0 4px;
            }
            QDoubleSpinBox:focus {
                border: 1px solid #38bdf8;
                background-color: #202026;
            }
        """)

        self.btn_plus = QPushButton("+")
        self.btn_plus.setFixedSize(28, 28)
        self.btn_plus.setFocusPolicy(Qt.NoFocus)
        self.btn_plus.setCursor(Qt.PointingHandCursor)
        self.btn_plus.setStyleSheet("""
            QPushButton {
                background-color: #27272a;
                color: #f4f4f5;
                border: 1px solid #3f3f46;
                border-radius: 5px;
                font-weight: bold;
                font-size: 13pt;
                padding-bottom: 2px;
            }
            QPushButton:hover {
                background-color: #3f3f46;
                border-color: #38bdf8;
                color: #38bdf8;
            }
            QPushButton:pressed {
                background-color: #18181b;
            }
        """)

        self.btn_minus.clicked.connect(self.spin.stepDown)
        self.btn_plus.clicked.connect(self.spin.stepUp)
        self.spin.valueChanged.connect(self.valueChanged.emit)

        layout.addWidget(self.btn_minus)
        layout.addWidget(self.spin, 1)
        layout.addWidget(self.btn_plus)

    def value(self) -> float:
        return self.spin.value()

    def setValue(self, v: float):
        self.spin.setValue(v)

    def setRange(self, mn: float, mx: float):
        self.spin.setRange(mn, mx)

    def setSingleStep(self, s: float):
        self.spin.setSingleStep(s)

    def setToolTip(self, t: str):
        super().setToolTip(t)
        self.spin.setToolTip(t)
        self.btn_minus.setToolTip(f"إنقاص القيمة ({t})")
        self.btn_plus.setToolTip(f"زيادة القيمة ({t})")


class SettingsPanel(QWidget):
    """
    Spacious, clean settings panel for Translation Languages, Batching,
    Concurrency, Temperature, and API Cache parameters.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.settings = get_settings()

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        container = QWidget()
        main_layout = QVBoxLayout(container)
        main_layout.setContentsMargins(6, 6, 12, 6)
        main_layout.setSpacing(10)

        # 1. Languages Group
        grp_lang = QGroupBox("🌐 لغات وصيغ الترجمة (Languages)")
        grp_lang.setStyleSheet("QGroupBox::title { color: #38bdf8; }")
        layout_lang = QFormLayout(grp_lang)
        layout_lang.setSpacing(8)
        layout_lang.setContentsMargins(10, 12, 10, 10)

        self.cb_source = QComboBox()
        self.cb_source.addItems(SOURCE_LANGUAGES)
        saved_source = self.settings.source_lang
        matched_idx = -1
        for i in range(self.cb_source.count()):
            text = self.cb_source.itemText(i)
            if saved_source and (saved_source in text or text.startswith(saved_source)):
                matched_idx = i
                break
        self.cb_source.setCurrentIndex(matched_idx if matched_idx >= 0 else 0)

        self.cb_target = QComboBox()
        self.cb_target.addItems(TARGET_LANGUAGES)
        saved_target = self.settings.target_lang
        matched_t_idx = -1
        for i in range(self.cb_target.count()):
            text = self.cb_target.itemText(i)
            if saved_target and (saved_target in text or text.startswith(saved_target)):
                matched_t_idx = i
                break
        self.cb_target.setCurrentIndex(matched_t_idx if matched_t_idx >= 0 else 0)

        self.cb_export = QComboBox()
        self.cb_export.addItems([
            "ملف مترجم مستقل (.ara.ass)",
            "ملف ثنائي اللغة للمراجعة (.bi.ass)"
        ])

        self.lbl_detected_badge = QLabel("✨ الكشف التلقائي نشط (جاهز للتعرف)")
        self.lbl_detected_badge.setStyleSheet("color: #4ade80; font-size: 8pt; font-weight: 500;")

        layout_lang.addRow("لغة المصدر:", self.cb_source)
        layout_lang.addRow("الحالة المكتشفة:", self.lbl_detected_badge)
        layout_lang.addRow("لغة الهدف:", self.cb_target)
        layout_lang.addRow("صيغة التصدير:", self.cb_export)
        main_layout.addWidget(grp_lang)

        # 2. Performance & Generation Parameters
        grp_params = QGroupBox("⚙️ الأداء ومعاملات التوليد (Performance)")
        grp_params.setStyleSheet("QGroupBox::title { color: #38bdf8; }")
        layout_params = QVBoxLayout(grp_params)
        layout_params.setSpacing(10)
        layout_params.setContentsMargins(10, 14, 10, 12)

        # Mode row
        mode_row = QHBoxLayout()
        lbl_mode = QLabel("نمط التقسيم:")
        lbl_mode.setStyleSheet("color: #a1a1aa; font-size: 8.5pt;")
        self.cb_mode = QComboBox()
        self.cb_mode.addItems(["Token-Aware (ذكية حسب النص)", "Fixed Count (أسطر ثابتة)"])
        mode_row.addWidget(lbl_mode)
        mode_row.addWidget(self.cb_mode, 1)
        layout_params.addLayout(mode_row)

        # 2-column Grid for numeric steppers
        grid_spin = QGridLayout()
        grid_spin.setHorizontalSpacing(14)
        grid_spin.setVerticalSpacing(10)

        # 1. Batch Size
        batch_container = QWidget()
        b_lay = QVBoxLayout(batch_container)
        b_lay.setContentsMargins(0, 0, 0, 0)
        b_lay.setSpacing(3)
        lbl_batch = QLabel("حجم الدفعة (سطر):")
        lbl_batch.setStyleSheet("color: #a1a1aa; font-size: 8.5pt;")
        self.sb_batch_size = IntStepper(min_val=1, max_val=100, val=self.settings.batch_size, step=1)
        self.sb_batch_size.setToolTip("عدد أسطر الترجمة في الدفعة الواحدة (10-15 ينصح بها)")
        b_lay.addWidget(lbl_batch)
        b_lay.addWidget(self.sb_batch_size)

        # 2. Concurrency / Parallel
        conc_container = QWidget()
        c_lay = QVBoxLayout(conc_container)
        c_lay.setContentsMargins(0, 0, 0, 0)
        c_lay.setSpacing(3)
        lbl_conc = QLabel("التوازي (Parallel):")
        lbl_conc.setStyleSheet("color: #a1a1aa; font-size: 8.5pt;")
        self.sb_concurrency = IntStepper(min_val=1, max_val=16, val=getattr(self.settings, 'concurrency', 1), step=1)
        self.sb_concurrency.setToolTip("عدد الطلبات المتزامنة للموديل (ينصح بـ 1 أو 2 للأجهزة المحلية لعدم إثقال المعالج والكرت)")
        c_lay.addWidget(lbl_conc)
        c_lay.addWidget(self.sb_concurrency)

        # 3. Max Context
        ctx_container = QWidget()
        ctx_lay = QVBoxLayout(ctx_container)
        ctx_lay.setContentsMargins(0, 0, 0, 0)
        ctx_lay.setSpacing(3)
        lbl_ctx = QLabel("سياق النموذج (Max Context):")
        lbl_ctx.setStyleSheet("color: #a1a1aa; font-size: 8.5pt;")
        self.sb_max_context = IntStepper(min_val=512, max_val=262144, val=getattr(self.settings, 'max_context', 4096), step=512)
        self.sb_max_context.setToolTip("الحد الأقصى لسياق النموذج بالتوكنز (يتم تحديثه تلقائياً بناءً على مواصفات الموديل الشغال)")
        ctx_lay.addWidget(lbl_ctx)
        ctx_lay.addWidget(self.sb_max_context)

        # 4. Temperature
        temp_container = QWidget()
        t_lay = QVBoxLayout(temp_container)
        t_lay.setContentsMargins(0, 0, 0, 0)
        t_lay.setSpacing(3)
        lbl_temp = QLabel("الحرارة (Temp):")
        lbl_temp.setStyleSheet("color: #a1a1aa; font-size: 8.5pt;")
        self.sb_temp = DoubleStepper(min_val=0.0, max_val=1.5, val=self.settings.temperature, step=0.05)
        self.sb_temp.setToolTip("درجة الحرارة والإبداع (0.1 تعطي أعلى دقة وانضباط ومطابقة للترجمة)")
        t_lay.addWidget(lbl_temp)
        t_lay.addWidget(self.sb_temp)

        # 5. Max Tokens
        tok_container = QWidget()
        tok_lay = QVBoxLayout(tok_container)
        tok_lay.setContentsMargins(0, 0, 0, 0)
        tok_lay.setSpacing(3)
        lbl_tokens = QLabel("أقصى رموز:")
        lbl_tokens.setStyleSheet("color: #a1a1aa; font-size: 8.5pt;")
        self.sb_max_tokens = IntStepper(min_val=500, max_val=32000, val=self.settings.max_tokens, step=500)
        tok_lay.addWidget(lbl_tokens)
        tok_lay.addWidget(self.sb_max_tokens)

        # 6. Top_P
        topp_container = QWidget()
        topp_lay = QVBoxLayout(topp_container)
        topp_lay.setContentsMargins(0, 0, 0, 0)
        topp_lay.setSpacing(3)
        lbl_topp = QLabel("حصر التوكنات (Top_P):")
        lbl_topp.setStyleSheet("color: #a1a1aa; font-size: 8.5pt;")
        self.sb_top_p = DoubleStepper(min_val=0.1, max_val=1.0, val=getattr(self.settings, 'top_p', 0.85), step=0.05)
        self.sb_top_p.setToolTip("حصر التوكنات (0.85 يقطع التوكنات الشاذة مثل الحروف الصينية)")
        topp_lay.addWidget(lbl_topp)
        topp_lay.addWidget(self.sb_top_p)

        # 7. Repetition Penalty
        rep_container = QWidget()
        rep_lay = QVBoxLayout(rep_container)
        rep_lay.setContentsMargins(0, 0, 0, 0)
        rep_lay.setSpacing(3)
        lbl_rep = QLabel("عقوبة التكرار (Rep Penalty):")
        lbl_rep.setStyleSheet("color: #a1a1aa; font-size: 8.5pt;")
        self.sb_rep_penalty = DoubleStepper(min_val=1.0, max_val=2.0, val=getattr(self.settings, 'repetition_penalty', 1.0), step=0.05)
        self.sb_rep_penalty.setToolTip("عقوبة التكرار (1.0 إلزامي ومثالي لمنع تشوه أكواد ASS)")
        rep_lay.addWidget(lbl_rep)
        rep_lay.addWidget(self.sb_rep_penalty)

        # Add to Grid:
        # Row 0 -> Batch Size & Concurrency (Parallel)
        # Row 1 -> Max Context & Max Tokens
        # Row 2 -> Temp & Top_P
        # Row 3 -> Rep Penalty
        grid_spin.addWidget(batch_container, 0, 0)
        grid_spin.addWidget(conc_container, 0, 1)
        grid_spin.addWidget(ctx_container, 1, 0)
        grid_spin.addWidget(tok_container, 1, 1)
        grid_spin.addWidget(temp_container, 2, 0)
        grid_spin.addWidget(topp_container, 2, 1)
        grid_spin.addWidget(rep_container, 3, 0, 1, 2)

        layout_params.addLayout(grid_spin)
        main_layout.addWidget(grp_params)

        # 3. Metadata & External APIs
        grp_meta = QGroupBox("🔍 الذاكرة المؤقتة وبيانات الأعمال")
        grp_meta.setStyleSheet("QGroupBox::title { color: #a1a1aa; }")
        layout_meta = QVBoxLayout(grp_meta)
        layout_meta.setSpacing(8)
        layout_meta.setContentsMargins(10, 12, 10, 10)

        tmdb_row = QHBoxLayout()
        lbl_tmdb = QLabel("مفتاح TMDB:")
        lbl_tmdb.setStyleSheet("color: #a1a1aa; font-size: 8.5pt;")
        self.le_tmdb_key = QLineEdit()
        self.le_tmdb_key.setPlaceholderText("اختياري - مفتاح TMDB لجلب تفاصيل وشخصيات أوسع")
        self.le_tmdb_key.setText(getattr(self.settings, 'tmdb_api_key', ''))
        tmdb_row.addWidget(lbl_tmdb)
        tmdb_row.addWidget(self.le_tmdb_key, 1)
        layout_meta.addLayout(tmdb_row)

        self.chk_use_cache = QCheckBox("⚡ إعادة استخدام الترجمات السابقة (Reuse Cache & Resume)")
        self.chk_use_cache.setChecked(False)
        self.chk_use_cache.setStyleSheet("color: #e4e4e7; font-size: 8.5pt;")
        self.chk_use_cache.setToolTip("عند تعطيله (الافتراضي)، يترجم البرنامج كل سطر من الصفر عبر الذكاء الاصطناعي دون استرجاع ترجمات قديمة من الجلسات السابقة")
        layout_meta.addWidget(self.chk_use_cache)

        self.btn_clear_cache = QPushButton("🧹 تفريغ ذاكرة الترجمة والكاش بالكامل (Purge All Cache & TM)")
        self.btn_clear_cache.setStyleSheet("background-color: #27272a; color: #e4e4e7; font-size: 8.5pt; padding: 6px;")
        layout_meta.addWidget(self.btn_clear_cache)
        main_layout.addWidget(grp_meta)

        main_layout.addStretch()
        scroll.setWidget(container)
        outer_layout.addWidget(scroll)

        self._connect_signals()

    def _connect_signals(self):
        self.sb_batch_size.valueChanged.connect(self._save_settings)
        self.sb_max_tokens.valueChanged.connect(self._save_settings)
        self.sb_max_context.valueChanged.connect(self._save_settings)
        self.sb_concurrency.valueChanged.connect(self._save_settings)
        self.sb_temp.valueChanged.connect(self._save_settings)
        self.sb_top_p.valueChanged.connect(self._save_settings)
        self.sb_rep_penalty.valueChanged.connect(self._save_settings)
        self.cb_source.currentTextChanged.connect(self._save_settings)
        self.cb_target.currentTextChanged.connect(self._save_settings)
        self.le_tmdb_key.textChanged.connect(self._save_settings)
        self.btn_clear_cache.clicked.connect(self._clear_cache)

    def _save_settings(self):
        self.settings.batch_size = self.sb_batch_size.value()
        self.settings.max_tokens = self.sb_max_tokens.value()
        self.settings.max_context = self.sb_max_context.value()
        self.settings.concurrency = self.sb_concurrency.value()
        self.settings.temperature = self.sb_temp.value()
        self.settings.top_p = self.sb_top_p.value()
        self.settings.repetition_penalty = self.sb_rep_penalty.value()
        self.settings.source_lang = self.cb_source.currentText()
        self.settings.target_lang = self.cb_target.currentText()
        self.settings.tmdb_api_key = self.le_tmdb_key.text().strip()
        self.settings.save_to_file()

    def set_detected_language(self, lang_display: str):
        self.lbl_detected_badge.setText(f"🌐 {lang_display}")
        self.lbl_detected_badge.setStyleSheet("color: #38bdf8; font-weight: 600; font-size: 8.5pt;")

    def get_source_lang_clean(self) -> str:
        text = self.cb_source.currentText()
        if "كشف تلقائي" in text or "Auto" in text:
            return "Auto Detect"
        if " " in text:
            return text.split(" ")[0].strip()
        return text

    def get_target_lang_clean(self) -> str:
        text = self.cb_target.currentText()
        if " " in text:
            return text.split(" ")[0].strip()
        return text

    def _clear_cache(self):
        from PySide6.QtWidgets import QMessageBox
        from app.core.database import DatabaseManager
        from app.ui.bus import EventBus
        reply = QMessageBox.question(
            self,
            "تأكيد مسح الذاكرة المؤقتة",
            "هل تريد بالتأكيد تفريغ ذاكرة الترجمة (Translation Memory) وكاش الأعمال بالكامل؟\nلا يمكن التراجع عن هذا الإجراء.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        db = None
        try:
            db = DatabaseManager()
            db.clear_cache()
            self.btn_clear_cache.setText("✅ تم مسح كل ذواكر الترجمة المؤقتة والكاش بنجاح!")
            QTimer.singleShot(2500, lambda: self.btn_clear_cache.setText("🧹 تفريغ ذاكرة الترجمة والكاش بالكامل (Purge All Cache & TM)"))
            EventBus.instance().log_message.emit("🧹 All translation memory, checkpoints and API caches cleared successfully.")
        except Exception as e:
            EventBus.instance().log_message.emit(f"Failed to clear cache: {e}")
        finally:
            if db is not None:
                try:
                    db.close()
                except Exception:
                    pass
