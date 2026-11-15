from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QLabel, QLineEdit, QPushButton, QCheckBox, QFrame
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeySequence, QShortcut

class FindReplaceBar(QFrame):
    """
    SubNova Studio — In-Table Search and Replace Bar (Ctrl+F).
    Supports finding occurrences, replacing current, and bulk replacing
    in original or translated subtitle text.
    """
    find_next_requested = Signal(str, bool)  # (search_text, case_sensitive)
    replace_requested = Signal(str, str, bool)  # (search_text, replace_text, case_sensitive)
    replace_all_requested = Signal(str, str, bool)  # (search_text, replace_text, case_sensitive)
    closed_signal = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("""
            FindReplaceBar {
                background-color: #0f172a;
                border: 1px solid #1e293b;
                border-radius: 6px;
                padding: 4px;
            }
            QLineEdit {
                background-color: #1e293b;
                border: 1px solid #334155;
                color: #f1f5f9;
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 9pt;
            }
            QLineEdit:focus {
                border: 1px solid #38bdf8;
            }
            QPushButton {
                background-color: #1e293b;
                color: #cbd5e1;
                border: 1px solid #334155;
                border-radius: 4px;
                padding: 4px 10px;
                font-size: 8.5pt;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #334155;
                color: #ffffff;
            }
            QCheckBox {
                color: #94a3b8;
                font-size: 8pt;
            }
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(6)

        lbl_icon = QLabel("🔍")
        layout.addWidget(lbl_icon)

        # Search box
        self.edit_find = QLineEdit()
        self.edit_find.setPlaceholderText("بحث في الأسطر (Find)...")
        self.edit_find.setFixedWidth(170)
        self.edit_find.returnPressed.connect(self._on_find_next)
        layout.addWidget(self.edit_find)

        # Replace box
        self.edit_replace = QLineEdit()
        self.edit_replace.setPlaceholderText("استبدال بـ (Replace with)...")
        self.edit_replace.setFixedWidth(170)
        self.edit_replace.returnPressed.connect(self._on_replace)
        layout.addWidget(self.edit_replace)

        # Case sensitivity checkbox
        self.chk_case = QCheckBox("Aa")
        self.chk_case.setToolTip("مطابقة حالة الأحرف (Case Sensitive)")
        layout.addWidget(self.chk_case)

        # Buttons
        self.btn_find = QPushButton("بحث عن التالي")
        self.btn_find.clicked.connect(self._on_find_next)
        layout.addWidget(self.btn_find)

        self.btn_replace = QPushButton("استبدال")
        self.btn_replace.clicked.connect(self._on_replace)
        layout.addWidget(self.btn_replace)

        self.btn_replace_all = QPushButton("استبدال الكل")
        self.btn_replace_all.setStyleSheet("background-color: #0369a1; color: white;")
        self.btn_replace_all.clicked.connect(self._on_replace_all)
        layout.addWidget(self.btn_replace_all)

        # Status match label
        self.lbl_matches = QLabel("")
        self.lbl_matches.setStyleSheet("color: #38bdf8; font-size: 8pt; font-weight: bold;")
        layout.addWidget(self.lbl_matches)

        layout.addStretch()

        # Close button
        btn_close = QPushButton("✕")
        btn_close.setFixedSize(22, 22)
        btn_close.setStyleSheet("background: transparent; border: none; color: #94a3b8; font-size: 10pt; font-weight: bold;")
        btn_close.clicked.connect(self.hide_bar)
        layout.addWidget(btn_close)

        # ESC shortcut to hide
        esc_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Escape), self)
        esc_shortcut.activated.connect(self.hide_bar)

    def show_bar(self):
        self.setVisible(True)
        self.edit_find.setFocus()
        self.edit_find.selectAll()

    def hide_bar(self):
        self.setVisible(False)
        self.closed_signal.emit()

    def set_match_status(self, current: int, total: int):
        if total > 0:
            self.lbl_matches.setText(f"{current}/{total} مطابقة")
        else:
            self.lbl_matches.setText("لا يوجد تطابق")

    def _on_find_next(self):
        text = self.edit_find.text()
        if text:
            self.find_next_requested.emit(text, self.chk_case.isChecked())

    def _on_replace(self):
        find_txt = self.edit_find.text()
        rep_txt = self.edit_replace.text()
        if find_txt:
            self.replace_requested.emit(find_txt, rep_txt, self.chk_case.isChecked())

    def _on_replace_all(self):
        find_txt = self.edit_find.text()
        rep_txt = self.edit_replace.text()
        if find_txt:
            self.replace_all_requested.emit(find_txt, rep_txt, self.chk_case.isChecked())
