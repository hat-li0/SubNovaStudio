from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QCheckBox,
    QTextEdit, QGroupBox, QFrame, QScrollArea
)
from PySide6.QtCore import Qt
from app.core.config import get_settings

class HealingPanel(QWidget):
    """
    Spacious, beautifully organized panel for the Smart Auto-Healing Engine,
    Punctuation Normalization, Tag Immunity, and Story/Scene Context.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.settings = get_settings()

        # Wrap in a ScrollArea to guarantee zero vertical or horizontal crampedness
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(10)

        # Helper to create option item with title + wrapped description
        def create_option_block(chk: QCheckBox, desc_text: str):
            box = QWidget()
            b_layout = QVBoxLayout(box)
            b_layout.setContentsMargins(0, 0, 0, 4)
            b_layout.setSpacing(1)
            b_layout.addWidget(chk)
            lbl_desc = QLabel(desc_text)
            lbl_desc.setWordWrap(True)
            lbl_desc.setStyleSheet("color: #71717a; font-size: 8pt; margin-right: 24px;")
            b_layout.addWidget(lbl_desc)
            return box

        # 1. Smart Auto-Healing Group
        grp_healing = QGroupBox("🛡️ محرك التنقية الذاتي (Auto-Healing)")
        grp_healing.setStyleSheet("QGroupBox::title { color: #4ade80; }")
        layout_healing = QVBoxLayout(grp_healing)
        layout_healing.setSpacing(6)
        layout_healing.setContentsMargins(10, 12, 10, 10)

        self.chk_auto_heal = QCheckBox("تفعيل الفلترة الذاتية الشاملة")
        self.chk_auto_heal.setChecked(getattr(self.settings, 'enable_smart_healing', True))
        self.chk_auto_heal.setStyleSheet("font-weight: 600; color: #4ade80;")
        layout_healing.addWidget(create_option_block(self.chk_auto_heal, "تطبيق سلسلة المعالجة والتنقية الذاتية فور اكتمال الترجمة"))

        self.chk_arabic_punct = QCheckBox("تصحيح علامات الترقيم العربية")
        self.chk_arabic_punct.setChecked(getattr(self.settings, 'enable_arabic_punct', True))
        layout_healing.addWidget(create_option_block(self.chk_arabic_punct, "تحويل الفواصل '،' وعلامات الاستفهام '؟' والمنقوطة '؛' تلقائياً"))

        self.chk_latin_clean = QCheckBox("إزالة الشوائب والضمائر اللاتينية")
        self.chk_latin_clean.setChecked(getattr(self.settings, 'enable_latin_clean', True))
        layout_healing.addWidget(create_option_block(self.chk_latin_clean, "تنظيف الحروف المعزولة مثل (\\NI, \\Na, {Hmm.}) العالقة حول الأسطر"))

        self.chk_quote_fix = QCheckBox("معالجة علامات التنصيص اليتيمة")
        self.chk_quote_fix.setChecked(getattr(self.settings, 'enable_quote_fix', True))
        layout_healing.addWidget(create_option_block(self.chk_quote_fix, "إغلاق وموازنة علامات الاقتباس والأقواس غير المكتملة في أطراف الجمل"))

        self.chk_tag_immunity = QCheckBox("حصانة وسوم ASS ومؤثرات Aegisub")
        self.chk_tag_immunity.setChecked(getattr(self.settings, 'protect_tags', True))
        layout_healing.addWidget(create_option_block(self.chk_tag_immunity, "حماية كاملة 100% للوسوم ({\\pos}, {\\an8}) ومنع تشويهها أو ترجمتها"))

        self.chk_skip_fx = QCheckBox("حفظ المؤثرات والتايبست المعقد دون ترجمته (FX)")
        self.chk_skip_fx.setChecked(getattr(self.settings, 'skip_visual_effects', True))
        layout_healing.addWidget(create_option_block(self.chk_skip_fx, "حفظ أسطر المؤثرات البصرية (FX)، والرسومات، والتايبست المعقد، والكاراوكي في الملف كما هي، وترجمة الحوار فقط"))

        self.chk_translate_signs = QCheckBox("ترجمة اللوحات والعناوين النصية الثابتة (Signs)")
        self.chk_translate_signs.setChecked(getattr(self.settings, 'translate_signs', False))
        layout_healing.addWidget(create_option_block(self.chk_translate_signs, "إرسال نصوص اللوحات والعناوين الثابتة (Sign/Title) للترجمة حتى عند تفعيل حفظ المؤثرات"))

        self.chk_separate_effects = QCheckBox("فصل المؤثرات عن الحوار في نفس السطر")
        self.chk_separate_effects.setChecked(getattr(self.settings, 'separate_inline_effects', True))
        layout_healing.addWidget(create_option_block(self.chk_separate_effects, "فصل الأسطر المشتركة التي تجمع بين المؤثرات البصرية/الشارات وحوار الشخصيات إلى أسطر مستقلة متزامنة"))

        self.chk_dedup_lines = QCheckBox("عدم تكرار ترجمة الأسطر المتطابقة (توفير التوكنز)")
        self.chk_dedup_lines.setChecked(getattr(self.settings, 'deduplicate_identical_lines', True))
        layout_healing.addWidget(create_option_block(self.chk_dedup_lines, "ترجمة أسطر الحوار المكررة مرة واحدة فقط وتمرير الترجمة تلقائياً للمكررات لحماية النموذج من الإجهاد وتوفير التوكنز"))

        layout.addWidget(grp_healing)

        # 2. Linguistic Polish & Alerts Group
        grp_polish = QGroupBox("✨ التدقيق اللغوي والتحسين الفائق")
        grp_polish.setStyleSheet("QGroupBox::title { color: #38bdf8; }")
        layout_polish = QVBoxLayout(grp_polish)
        layout_polish.setSpacing(6)
        layout_polish.setContentsMargins(10, 12, 10, 10)

        self.chk_auto_improve = QCheckBox("التدقيق والتحسين الدرامي تلقائياً (مرحلة ثانية)")
        self.chk_auto_improve.setChecked(getattr(self.settings, 'auto_improve', False))
        layout_polish.addWidget(create_option_block(self.chk_auto_improve, "مرحلة ثانية اختيارية للمراجعة (ينصح بإلغائها مع النماذج المحلية لتسريع الترجمة ومنع التقارير)"))

        self.chk_play_sound = QCheckBox("تنبيه صوتي عند الاكتمال")
        self.chk_play_sound.setChecked(getattr(self.settings, 'play_sound_on_finish', True))
        layout_polish.addWidget(create_option_block(self.chk_play_sound, "تشغيل نغمة صوتية خفيفة عند اكتمال معالجة الملف بالكامل"))

        layout.addWidget(grp_polish)

        # 3. Story & Scene Notes Group
        grp_notes = QGroupBox("🎬 سياق العمل ونبرة الحوار (Story Notes)")
        grp_notes.setStyleSheet("QGroupBox::title { color: #fbbf24; }")
        layout_notes = QVBoxLayout(grp_notes)
        layout_notes.setSpacing(6)
        layout_notes.setContentsMargins(10, 12, 10, 10)

        lbl_hint = QLabel("💡 ملاحظات السياق لحقنها في النموذج لضمان دقة الضمائر ومنع الركاكة:")
        lbl_hint.setStyleSheet("color: #a1a1aa; font-size: 8pt;")
        lbl_hint.setWordWrap(True)
        layout_notes.addWidget(lbl_hint)

        self.te_story_notes = QTextEdit()
        self.te_story_notes.setPlaceholderText("اكتب هنا طبيعة العمل (مثال: أنمي درامي مدرسي، استخدام صيغة المؤنث بصرامة مع أسماء الفتيات)...")
        self.te_story_notes.setMinimumHeight(75)
        self.te_story_notes.setMaximumHeight(120)
        self.te_story_notes.setText(getattr(self.settings, 'story_notes', ''))
        layout_notes.addWidget(self.te_story_notes)
        layout.addWidget(grp_notes)

        layout.addStretch()
        scroll.setWidget(container)
        outer_layout.addWidget(scroll)

        self._connect_signals()

    def _connect_signals(self):
        self.chk_auto_heal.stateChanged.connect(self._save_settings)
        self.chk_arabic_punct.stateChanged.connect(self._save_settings)
        self.chk_latin_clean.stateChanged.connect(self._save_settings)
        self.chk_quote_fix.stateChanged.connect(self._save_settings)
        self.chk_tag_immunity.stateChanged.connect(self._save_settings)
        self.chk_skip_fx.stateChanged.connect(self._save_settings)
        self.chk_translate_signs.stateChanged.connect(self._save_settings)
        self.chk_separate_effects.stateChanged.connect(self._save_settings)
        self.chk_dedup_lines.stateChanged.connect(self._save_settings)
        self.chk_auto_improve.stateChanged.connect(self._save_settings)
        self.chk_play_sound.stateChanged.connect(self._save_settings)
        self.te_story_notes.textChanged.connect(self._save_settings)

    def _save_settings(self):
        self.settings.enable_smart_healing = self.chk_auto_heal.isChecked()
        self.settings.enable_arabic_punct = self.chk_arabic_punct.isChecked()
        self.settings.enable_latin_clean = self.chk_latin_clean.isChecked()
        self.settings.enable_quote_fix = self.chk_quote_fix.isChecked()
        self.settings.protect_tags = self.chk_tag_immunity.isChecked()
        self.settings.skip_visual_effects = self.chk_skip_fx.isChecked()
        self.settings.translate_signs = self.chk_translate_signs.isChecked()
        self.settings.separate_inline_effects = self.chk_separate_effects.isChecked()
        self.settings.deduplicate_identical_lines = self.chk_dedup_lines.isChecked()
        self.settings.auto_improve = self.chk_auto_improve.isChecked()
        self.settings.play_sound_on_finish = self.chk_play_sound.isChecked()
        self.settings.story_notes = self.te_story_notes.toPlainText().strip()
        self.settings.save_to_file()

    def get_healing_options(self) -> dict:
        return {
            "arabic_punct": self.chk_arabic_punct.isChecked(),
            "latin_clean": self.chk_latin_clean.isChecked(),
            "quote_fix": self.chk_quote_fix.isChecked(),
            "protect_tags": self.chk_tag_immunity.isChecked(),
            "skip_visual_effects": self.chk_skip_fx.isChecked(),
            "translate_signs": self.chk_translate_signs.isChecked(),
            "separate_inline_effects": self.chk_separate_effects.isChecked(),
            "deduplicate_identical_lines": self.chk_dedup_lines.isChecked()
        }

    def get_story_notes(self) -> str:
        return self.te_story_notes.toPlainText().strip()
