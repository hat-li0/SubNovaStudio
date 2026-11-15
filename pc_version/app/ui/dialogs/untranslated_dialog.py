from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget,
    QTableWidgetItem, QPushButton, QLineEdit, QHeaderView,
    QAbstractItemView, QCheckBox, QFrame
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont
from typing import List, Optional
from app.models.subtitle import SubtitleEvent
import re


class UntranslatedLinesDialog(QDialog):
    """
    Modal dialog alerting the user when untranslated lines are detected.
    Provides options to:
    1. Re-translate the remaining lines preserving full scene context.
    2. Save the file as-is without translating remaining lines.
    3. Cancel/close for manual inspection.
    """

    ACTION_TRANSLATE = "TRANSLATE"
    ACTION_SAVE_AS_IS = "SAVE_AS_IS"
    ACTION_CANCEL = "CANCEL"

    def __init__(
        self,
        parent=None,
        events: Optional[List[SubtitleEvent]] = None,
        filename: str = "",
        is_batch: bool = False,
    ):
        super().__init__(parent)
        self.events: List[SubtitleEvent] = events or []
        self.filename = filename
        self.is_batch = is_batch
        self.selected_action = self.ACTION_CANCEL

        self.setWindowTitle("تنبيه الأسطر غير المترجمة | Untranslated Lines Alert")
        self.setMinimumSize(920, 580)
        self.setLayoutDirection(Qt.RightToLeft)

        self._setup_ui()
        self._populate_table(self.events)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        # Header Warning Banner
        header_frame = QFrame()
        header_frame.setStyleSheet("""
            QFrame {
                background-color: #21262d;
                border: 1px solid #d29922;
                border-radius: 8px;
                padding: 10px;
            }
        """)
        header_layout = QVBoxLayout(header_frame)
        header_layout.setSpacing(6)
        header_layout.setContentsMargins(10, 8, 10, 8)

        count_text = f"⚠️ تم رصد {len(self.events)} سطر لم تكتمل ترجمتها بعد"
        if self.filename:
            count_text += f" في الملف: {self.filename}"
        lbl_title = QLabel(count_text)
        title_font = QFont()
        title_font.setPointSize(12)
        title_font.setBold(True)
        lbl_title.setFont(title_font)
        lbl_title.setStyleSheet("color: #f2cc60;")
        header_layout.addWidget(lbl_title)

        lbl_desc = QLabel(
            "يمكنك اختيار ترجمة هذه الأسطر المتبقية الآن مع تزويد الذكاء الاصطناعي بسياق الحوار والمشهد المحيط بها كاملاً، "
            "أو اعتماد حفظ الملف بالوضع الحالي."
        )
        lbl_desc.setWordWrap(True)
        lbl_desc.setStyleSheet("color: #c9d1d9; font-size: 11px;")
        header_layout.addWidget(lbl_desc)

        layout.addWidget(header_frame)

        # Search Bar
        search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 بحث في الأسطر غير المترجمة أو المتحدث...")
        self.search_input.textChanged.connect(self._filter_table)
        search_layout.addWidget(self.search_input)
        layout.addLayout(search_layout)

        # Table
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels([
            "الرقم (#)",
            "البداية (Start)",
            "النهاية (End)",
            "المتحدث (Speaker)",
            "النص الأصلي (Original Text)"
        ])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet("""
            QTableWidget {
                background-color: #0d1117;
                alternate-background-color: #161b22;
                color: #c9d1d9;
                gridline-color: #30363d;
                border: 1px solid #30363d;
                border-radius: 6px;
            }
            QHeaderView::section {
                background-color: #161b22;
                color: #8b949e;
                padding: 6px;
                border: 1px solid #30363d;
                font-weight: bold;
            }
        """)
        layout.addWidget(self.table)

        # Batch check option (if multiple files)
        if self.is_batch:
            self.chk_batch = QCheckBox("تطبيق هذا الخيار تلقائياً على باقي ملفات الدفعة")
            self.chk_batch.setStyleSheet("color: #8b949e; font-weight: bold;")
            layout.addWidget(self.chk_batch)
        else:
            self.chk_batch = None

        # Action Buttons Layout
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        # Translate Button (Primary Action)
        self.btn_translate = QPushButton("🚀 ترجمة الأسطر المتبقية الآن (بالسياق الكامل)")
        self.btn_translate.setStyleSheet("""
            QPushButton {
                background-color: #238636;
                color: #ffffff;
                font-weight: bold;
                font-size: 12px;
                padding: 10px 18px;
                border-radius: 6px;
                border: 1px solid #2ea043;
            }
            QPushButton:hover {
                background-color: #2ea043;
            }
            QPushButton:pressed {
                background-color: #1b6a2b;
            }
        """)
        self.btn_translate.clicked.connect(self._on_translate_clicked)
        btn_layout.addWidget(self.btn_translate)

        # Save As-Is Button (Secondary Action)
        self.btn_save_as_is = QPushButton("💾 حفظ الملف كما هو الآن")
        self.btn_save_as_is.setStyleSheet("""
            QPushButton {
                background-color: #21262d;
                color: #58a6ff;
                font-weight: bold;
                font-size: 12px;
                padding: 10px 18px;
                border-radius: 6px;
                border: 1px solid #388bfd;
            }
            QPushButton:hover {
                background-color: #30363d;
            }
            QPushButton:pressed {
                background-color: #161b22;
            }
        """)
        self.btn_save_as_is.clicked.connect(self._on_save_as_is_clicked)
        btn_layout.addWidget(self.btn_save_as_is)

        btn_layout.addStretch()

        # Cancel / Review Button
        self.btn_cancel = QPushButton("إلغاء الأمر للمراجعة اليدوية")
        self.btn_cancel.setStyleSheet("""
            QPushButton {
                background-color: #21262d;
                color: #8b949e;
                padding: 10px 14px;
                border-radius: 6px;
                border: 1px solid #30363d;
            }
            QPushButton:hover {
                background-color: #30363d;
                color: #c9d1d9;
            }
        """)
        self.btn_cancel.clicked.connect(self._on_cancel_clicked)
        btn_layout.addWidget(self.btn_cancel)

        layout.addLayout(btn_layout)

    def _populate_table(self, events: List[SubtitleEvent]):
        self.table.setRowCount(0)
        self.table.setRowCount(len(events))

        for row, ev in enumerate(events):
            item_id = QTableWidgetItem(f"[{ev.id:03d}]")
            item_id.setTextAlignment(Qt.AlignCenter)
            item_id.setForeground(QColor("#79c0ff"))
            self.table.setItem(row, 0, item_id)

            item_start = QTableWidgetItem(str(ev.start or ""))
            item_start.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 1, item_start)

            item_end = QTableWidgetItem(str(ev.end or ""))
            item_end.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 2, item_end)

            item_speaker = QTableWidgetItem(str(ev.speaker or ""))
            item_speaker.setTextAlignment(Qt.AlignCenter)
            if ev.speaker:
                item_speaker.setForeground(QColor("#ff7b72"))
            self.table.setItem(row, 3, item_speaker)

            clean_text = ev.get_clean_text()
            item_text = QTableWidgetItem(clean_text)
            self.table.setItem(row, 4, item_text)

    def _filter_table(self, query: str):
        query = query.strip().lower()
        for row in range(self.table.rowCount()):
            if not query:
                self.table.setRowHidden(row, False)
                continue
            text_match = False
            for col in range(self.table.columnCount()):
                item = self.table.item(row, col)
                if item and query in item.text().lower():
                    text_match = True
                    break
            self.table.setRowHidden(row, not text_match)

    def _on_translate_clicked(self):
        self.selected_action = self.ACTION_TRANSLATE
        self.accept()

    def _on_save_as_is_clicked(self):
        self.selected_action = self.ACTION_SAVE_AS_IS
        self.accept()

    def _on_cancel_clicked(self):
        self.selected_action = self.ACTION_CANCEL
        self.reject()

    def should_apply_to_batch(self) -> bool:
        return bool(self.chk_batch and self.chk_batch.isChecked())
