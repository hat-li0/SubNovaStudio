from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar,
    QPushButton, QFrame
)
from PySide6.QtCore import Qt, Signal
from app.ui.bus import EventBus

class ProgressPanel(QWidget):
    quick_heal_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(2, 2, 2, 2)
        self.layout.setSpacing(6)

        card = QFrame()
        card.setStyleSheet("""
            QFrame#progress_card {
                background-color: #18181b;
                border: 1px solid #27272a;
                border-radius: 8px;
            }
        """)
        card.setObjectName("progress_card")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(12, 8, 12, 10)
        card_layout.setSpacing(6)
        
        # 1. Progress bar (10px height, smooth aesthetic gradient)
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedHeight(10)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background-color: #27272a;
                border: none;
                border-radius: 5px;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0284c7, stop:1 #22c55e);
                border-radius: 5px;
            }
        """)
        card_layout.addWidget(self.progress_bar)
        
        # 2. Stats and ETA row
        self.lbl_stats = QLabel("جاهز للعمل | الأسطر: 0/0 | السرعة: 0.0 سطر/ث | الوقت المتبقي: --:--")
        self.lbl_stats.setStyleSheet("color: #a1a1aa; font-size: 8.5pt; font-weight: 500;")
        self.lbl_stats.setWordWrap(True)
        card_layout.addWidget(self.lbl_stats)
        
        # 3. Action Buttons Row (Clean, uncluttered, balanced)
        ctrl_layout = QHBoxLayout()
        ctrl_layout.setSpacing(8)

        # Left Tool action: Instant Zero-AI Healing
        self.btn_quick_heal = QPushButton("🧹 تنقية فورية")
        self.btn_quick_heal.setFixedHeight(34)
        self.btn_quick_heal.setMinimumWidth(100)
        self.btn_quick_heal.setToolTip("تطبيق الفلترة الذاتية فورياً: ضبط الفواصل والاستفهام، إزالة الشوائب اللاتينية، وحصانة وسوم ASS دون استهلاك رصيد")
        self.btn_quick_heal.setStyleSheet("""
            QPushButton {
                background-color: #27272a;
                border: 1px solid #3f3f46;
                color: #e4e4e7;
                font-weight: 500;
                padding: 0 12px;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #3f3f46;
                border-color: #52525b;
            }
        """)

        # Right side AI Actions
        self.btn_improve = QPushButton("✨ تحسين وتدقيق")
        self.btn_improve.setFixedHeight(34)
        self.btn_improve.setMinimumWidth(110)
        self.btn_improve.setToolTip("تشغيل التدقيق والتحسين الدرامي واللغوي الفائق للأسطر الحالية")
        self.btn_improve.setStyleSheet("""
            QPushButton {
                background-color: #0369a1;
                border: 1px solid #0284c7;
                color: white;
                font-weight: 600;
                padding: 0 14px;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #0284c7;
            }
        """)

        self.btn_start = QPushButton("🚀 بدء الترجمة")
        self.btn_start.setFixedHeight(34)
        self.btn_start.setMinimumWidth(120)
        self.btn_start.setObjectName("primary_action")
        self.btn_start.setToolTip("بدء دورة الترجمة الشاملة والتدقيق التلقائي لكامل الملف")
        self.btn_start.setStyleSheet("""
            QPushButton {
                background-color: #16a34a;
                border: 1px solid #22c55e;
                color: white;
                font-weight: 700;
                font-size: 9.5pt;
                padding: 0 16px;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #15803d;
            }
            QPushButton:disabled {
                background-color: #1f2937;
                border-color: #374151;
                color: #6b7280;
            }
        """)

        self.btn_cancel = QPushButton("🛑 إلغاء")
        self.btn_cancel.setFixedHeight(34)
        self.btn_cancel.setFixedWidth(75)
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.setToolTip("إيقاف عملية الترجمة الحالية فوراً")
        self.btn_cancel.setStyleSheet("""
            QPushButton {
                background-color: #991b1b;
                border: 1px solid #b91c1c;
                color: white;
                font-weight: 600;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #b91c1c;
            }
            QPushButton:disabled {
                background-color: #1f2937;
                border-color: #374151;
                color: #6b7280;
            }
        """)

        ctrl_layout.addWidget(self.btn_quick_heal)
        ctrl_layout.addStretch()
        ctrl_layout.addWidget(self.btn_improve)
        ctrl_layout.addWidget(self.btn_start)
        ctrl_layout.addWidget(self.btn_cancel)
        card_layout.addLayout(ctrl_layout)

        self.layout.addWidget(card)
        
        self.btn_start.clicked.connect(self._on_start)
        self.btn_improve.clicked.connect(self._on_improve)
        self.btn_quick_heal.clicked.connect(self._on_quick_heal)
        self.btn_cancel.clicked.connect(self._on_cancel)
        
        EventBus.instance().translation_progress.connect(self._on_progress)
        EventBus.instance().translation_started.connect(self._on_external_started)
        EventBus.instance().improvement_started.connect(self._on_external_started)
        EventBus.instance().translation_cancelled.connect(self._reset_controls)
        EventBus.instance().translation_finished.connect(lambda _: self._reset_controls())
        
    def _on_start(self):
        self._set_busy(True)
        EventBus.instance().translation_started.emit()

    def _on_improve(self):
        self._set_busy(True)
        EventBus.instance().improvement_started.emit()

    def _on_external_started(self):
        self._set_busy(True)
        self.lbl_stats.setText("⏳ جاري بدء الترجمة والتدقيق التلقائي...")

    def _on_quick_heal(self):
        self.quick_heal_requested.emit()
        
    def _on_cancel(self):
        self.btn_cancel.setEnabled(False)
        EventBus.instance().translation_cancelled.emit()
        
    def _set_busy(self, is_busy: bool):
        self.btn_start.setEnabled(not is_busy)
        self.btn_improve.setEnabled(not is_busy)
        self.btn_quick_heal.setEnabled(not is_busy)
        self.btn_cancel.setEnabled(is_busy)

    def _reset_controls(self):
        self._set_busy(False)
        
    def _on_progress(self, current, total, status):
        if total > 0:
            val = min(100, max(0, int((current / total) * 100)))
            self.progress_bar.setValue(val)
        self.lbl_stats.setText(status)
