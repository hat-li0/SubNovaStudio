from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QTableWidget, QTableWidgetItem,
    QPushButton, QHBoxLayout, QLineEdit, QComboBox, QHeaderView, QAbstractItemView
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QBrush
from typing import Optional
from app.models.subtitle import SubtitleDocument
import re

class TranslationReviewDialog(QDialog):
    def __init__(self, parent=None, document: Optional[SubtitleDocument] = None):
        super().__init__(parent)
        self.setWindowTitle("Review & Diff Translations / مراجعة وتدقيق الترجمات")
        self.setMinimumSize(950, 650)
        
        self.document = document
        self.layout = QVBoxLayout(self)
        self.layout.setSpacing(10)
        self.layout.setContentsMargins(12, 12, 12, 12)
        
        # Summary Header
        self.lbl_summary = QLabel("Total Events: 0 | Translated: 0 | Warnings: 0")
        self.lbl_summary.setStyleSheet("font-weight: bold; font-size: 13px; color: #58a6ff;")
        self.layout.addWidget(self.lbl_summary)
        
        # Filter & Search Bar
        filter_bar = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 Search in text or translation / بحث في النص أو الترجمة...")
        self.search_input.textChanged.connect(self._apply_filter)
        
        self.filter_combo = QComboBox()
        self.filter_combo.addItems([
            "All Events / كل الأسطر",
            "Translated / المترجمة فقط",
            "Untranslated / غير المترجمة فقط",
            "Warnings / أسطر تحتوي ملاحظات"
        ])
        self.filter_combo.currentIndexChanged.connect(self._apply_filter)
        
        filter_bar.addWidget(QLabel("Filter:"))
        filter_bar.addWidget(self.filter_combo)
        filter_bar.addWidget(self.search_input)
        self.layout.addLayout(filter_bar)
        
        # Table
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["ID", "Speaker", "Original / الأصل", "Translation / الترجمة", "Status & Warnings / الحالة"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.table.setEditTriggers(QAbstractItemView.DoubleClicked | QAbstractItemView.EditKeyPressed)
        self.layout.addWidget(self.table)
        
        # Buttons
        btn_layout = QHBoxLayout()
        self.btn_revert = QPushButton("Revert to Original / استعادة الأصل للسطر المحدد")
        self.btn_revert.clicked.connect(self._revert_selected)
        
        self.btn_save = QPushButton("💾 Save & Accept / حفظ واعتماد التعديلات")
        self.btn_save.setObjectName("primary_action")
        self.btn_save.clicked.connect(self._on_save)
        
        self.btn_cancel = QPushButton("Close / إغلاق")
        self.btn_cancel.clicked.connect(self.reject)
        
        btn_layout.addWidget(self.btn_revert)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_cancel)
        btn_layout.addWidget(self.btn_save)
        self.layout.addLayout(btn_layout)
        
        if self.document:
            self.load_document(self.document)
            
    def load_document(self, document: SubtitleDocument):
        self.document = document
        events = document.get_translatable_events() if hasattr(document, "get_translatable_events") else document.events
        
        self.table.setRowCount(0)
        total = len(events)
        translated_cnt = 0
        warnings_cnt = 0
        
        self.table.setSortingEnabled(False)
        self.table.setRowCount(total)
        
        for row, ev in enumerate(events):
            # ID
            item_id = QTableWidgetItem(str(ev.id))
            item_id.setFlags(item_id.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(row, 0, item_id)
            
            # Speaker
            speaker = getattr(ev, "speaker", "") or ""
            item_speaker = QTableWidgetItem(speaker)
            item_speaker.setFlags(item_speaker.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(row, 1, item_speaker)
            
            # Original
            orig_text = getattr(ev, "text", "") or ""
            item_orig = QTableWidgetItem(orig_text)
            item_orig.setFlags(item_orig.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(row, 2, item_orig)
            
            # Translation (Editable)
            trans_text = getattr(ev, "translated_text", "") or ""
            item_trans = QTableWidgetItem(trans_text)
            self.table.setItem(row, 3, item_trans)
            
            # Quality & Warnings Check
            warnings = []
            if trans_text:
                translated_cnt += 1
                if re.search(r'[a-zA-Z]{3,}', trans_text):
                    warnings.append("Leaked English")
                if trans_text.count('"') % 2 != 0 or trans_text.count('«') != trans_text.count('»'):
                    warnings.append("Orphan quote")
                
                from app.utils.metrics import calculate_cps
                start_ts = getattr(ev, "start", "") or getattr(ev, "start_time", "")
                end_ts = getattr(ev, "end", "") or getattr(ev, "end_time", "")
                cps = calculate_cps(trans_text, start_ts, end_ts)
                if cps > 18.0:
                    warnings.append(f"Fast reading ({cps:.1f} CPS)")
                lines = trans_text.replace("\\N", "\n").split("\n")
                if any(len(l.strip()) > 45 for l in lines):
                    warnings.append("Long line")
            else:
                warnings.append("Untranslated")
                
            warn_str = ", ".join(warnings) if warnings else "OK"
            item_status = QTableWidgetItem(warn_str)
            item_status.setFlags(item_status.flags() & ~Qt.ItemIsEditable)
            
            if warnings:
                warnings_cnt += 1
                if "Untranslated" in warnings:
                    item_status.setForeground(QBrush(QColor("#8b949e")))
                else:
                    item_status.setForeground(QBrush(QColor("#f85149")))
                    item_trans.setBackground(QBrush(QColor(60, 20, 20)))
            else:
                item_status.setForeground(QBrush(QColor("#3fb950")))
                
            self.table.setItem(row, 4, item_status)
            
        self.set_summary(total, translated_cnt, warnings_cnt)
        self._apply_filter()

    def set_summary(self, total: int, translated: int, warnings: int):
        self.lbl_summary.setText(f"Total Lines: {total} | Translated: {translated} | Warnings: {warnings}")
        
    def add_flagged_event(self, event_id: int, original: str, translated: str, warnings_list: list):
        row = self.table.rowCount()
        self.table.insertRow(row)
        
        item_id = QTableWidgetItem(str(event_id))
        item_id.setFlags(item_id.flags() & ~Qt.ItemIsEditable)
        self.table.setItem(row, 0, item_id)
        
        item_spk = QTableWidgetItem("")
        item_spk.setFlags(item_spk.flags() & ~Qt.ItemIsEditable)
        self.table.setItem(row, 1, item_spk)
        
        item_orig = QTableWidgetItem(original)
        item_orig.setFlags(item_orig.flags() & ~Qt.ItemIsEditable)
        self.table.setItem(row, 2, item_orig)
        
        item_trans = QTableWidgetItem(translated)
        self.table.setItem(row, 3, item_trans)
        
        warn_str = "\n".join(warnings_list)
        item_warn = QTableWidgetItem(warn_str)
        item_warn.setFlags(item_warn.flags() & ~Qt.ItemIsEditable)
        self.table.setItem(row, 4, item_warn)
        
    def _apply_filter(self):
        query = self.search_input.text().lower().strip()
        mode = self.filter_combo.currentIndex()
        # 0: All, 1: Translated, 2: Untranslated, 3: Warnings
        
        for row in range(self.table.rowCount()):
            item_orig = self.table.item(row, 2)
            item_trans = self.table.item(row, 3)
            item_status = self.table.item(row, 4)
            
            orig_text = item_orig.text() if item_orig else ""
            trans_text = item_trans.text() if item_trans else ""
            status_text = item_status.text() if item_status else ""
            
            # Match search
            matches_search = True
            if query:
                matches_search = (query in orig_text.lower()) or (query in trans_text.lower())
                
            # Match filter
            matches_filter = True
            if mode == 1: # Translated
                matches_filter = bool(trans_text.strip())
            elif mode == 2: # Untranslated
                matches_filter = not bool(trans_text.strip())
            elif mode == 3: # Warnings
                matches_filter = (status_text != "OK" and "Untranslated" not in status_text)
                
            self.table.setRowHidden(row, not (matches_search and matches_filter))

    def _revert_selected(self):
        curr_row = self.table.currentRow()
        if curr_row >= 0:
            item_orig = self.table.item(curr_row, 2)
            item_trans = self.table.item(curr_row, 3)
            if item_orig and item_trans:
                item_trans.setText(item_orig.text())

    def _on_save(self):
        if self.document:
            events_map = {e.id: e for e in self.document.events}
            for row in range(self.table.rowCount()):
                item_id = self.table.item(row, 0)
                item_trans = self.table.item(row, 3)
                if item_id and item_trans:
                    try:
                        eid = int(item_id.text())
                        if eid in events_map:
                            events_map[eid].translated_text = item_trans.text()
                    except ValueError:
                        pass
        self.accept()
