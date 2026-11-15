import html
import datetime
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QPushButton,
    QApplication, QDialog, QLineEdit, QLabel
)
from PySide6.QtGui import QTextCursor
from PySide6.QtCore import Signal, Qt
from app.ui.bus import EventBus

class FullLogDialog(QDialog):
    """Spacious, searchable full-window log viewer for detailed debugging and error tracebacks."""
    def __init__(self, parent=None, full_text=""):
        super().__init__(parent)
        self.setWindowTitle("📜 سجل العمليات والأخطاء التفصيلي (Full System & Error Log)")
        self.setMinimumSize(850, 600)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # Search Bar
        search_row = QHBoxLayout()
        search_lbl = QLabel("🔍 بحث في السجل:")
        search_lbl.setStyleSheet("font-weight: 600; color: #38bdf8;")
        self.le_search = QLineEdit()
        self.le_search.setPlaceholderText("اكتب كلمة للبحث (مثل: error, ffmpeg, timeout)...")
        self.le_search.textChanged.connect(self._filter_log)
        search_row.addWidget(search_lbl)
        search_row.addWidget(self.le_search, 1)
        layout.addLayout(search_row)

        # Big Text Area
        self.text_view = QTextEdit()
        self.text_view.setReadOnly(True)
        self.text_view.setAcceptRichText(True)
        self.text_view.setHtml(full_text)
        self.full_html = full_text
        layout.addWidget(self.text_view, 1)

        # Bottom Actions
        act_row = QHBoxLayout()
        self.btn_copy_all = QPushButton("📋 نسخ السجل بالكامل")
        self.btn_copy_all.clicked.connect(self._copy_all)
        self.btn_close = QPushButton("إغلاق")
        self.btn_close.clicked.connect(self.accept)

        act_row.addWidget(self.btn_copy_all)
        act_row.addStretch()
        act_row.addWidget(self.btn_close)
        layout.addLayout(act_row)

    def _filter_log(self, query: str):
        if not query:
            self.text_view.setHtml(self.full_html)
            return
        plain = self.text_view.toPlainText()
        lines = [line for line in plain.splitlines() if query.lower() in line.lower()]
        self.text_view.setPlainText("\n".join(lines))

    def _copy_all(self):
        QApplication.clipboard().setText(self.text_view.toPlainText())
        self.btn_copy_all.setText("✅ تم النسخ!")


class LogPanel(QWidget):
    expand_toggled = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._is_expanded = False
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(4, 4, 4, 4)
        self.layout.setSpacing(6)
        
        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        self.text_edit.setAcceptRichText(True)
        self.text_edit.setStyleSheet("""
            QTextEdit {
                background-color: #121214;
                border: 1px solid #27272a;
                border-radius: 6px;
                color: #e4e4e7;
                font-family: Consolas, "Cascadia Code", "Segoe UI", monospace;
                font-size: 9pt;
                padding: 6px;
            }
        """)
        self.layout.addWidget(self.text_edit)
        
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        self.btn_expand = QPushButton("⤢ تكبير السجل")
        self.btn_expand.setToolTip("تكبير نافذة السجل لرؤية رسائل الأخطاء بوضوح")
        self.btn_expand.clicked.connect(self._toggle_expand)

        self.btn_popout = QPushButton("🔍 نافذة السجل الكامل")
        self.btn_popout.setToolTip("فتح السجل في نافذة مستقلة كاملة مع إمكانية البحث")
        self.btn_popout.clicked.connect(self._open_popout)

        self.btn_copy = QPushButton("📋 نسخ السجل")
        self.btn_copy.clicked.connect(self._copy_log)

        self.btn_clear = QPushButton("🧹 مسح")
        self.btn_clear.clicked.connect(self.text_edit.clear)
        
        btn_layout.addWidget(self.btn_expand)
        btn_layout.addWidget(self.btn_popout)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_copy)
        btn_layout.addWidget(self.btn_clear)
        self.layout.addLayout(btn_layout)
        
        EventBus.instance().log_message.connect(self.append_log)
        
    def _toggle_expand(self):
        self._is_expanded = not self._is_expanded
        self.btn_expand.setText("⤡ استعادة الحجم" if self._is_expanded else "⤢ تكبير السجل")
        self.expand_toggled.emit(self._is_expanded)

    def _open_popout(self):
        dlg = FullLogDialog(self, full_text=self.text_edit.toHtml())
        dlg.exec()

    def append_log(self, message: str):
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        safe_msg = html.escape(str(message))
        
        lower_msg = message.lower()
        if any(err in lower_msg for err in ("[error]", "[fatal]", "failed", "exception", "خطأ", "فشل")):
            color = "#f87171"
            badge = "🔴"
            weight = "bold"
            # Render a prominent alert box for errors so the user can easily diagnose issues
            formatted_html = (
                f"<div style='background-color: #271515; border: 1px solid #ef4444; border-radius: 4px; padding: 4px 8px; margin: 3px 0;'>"
                f"<span style='color: #a1a1aa; font-size: 8pt;'>[{timestamp}]</span> "
                f"<span style='color: {color}; font-weight: {weight};'>{badge} {safe_msg}</span>"
                f"</div>"
            )
        elif any(warn in lower_msg for warn in ("[warn]", "warning", "rate limit", "retrying", "تنبيه")):
            color = "#fbbf24"
            badge = "🟡"
            weight = "600"
            formatted_html = (
                f"<div style='margin-bottom: 2px;'>"
                f"<span style='color: #71717a; font-size: 8pt;'>[{timestamp}]</span> "
                f"<span style='color: {color}; font-weight: {weight};'>{badge} {safe_msg}</span>"
                f"</div>"
            )
        elif any(succ in lower_msg for succ in ("[success]", "finished", "completed", "saved", "connected", "نجاح", "تم")):
            color = "#4ade80"
            badge = "🟢"
            weight = "500"
            formatted_html = (
                f"<div style='margin-bottom: 2px;'>"
                f"<span style='color: #71717a; font-size: 8pt;'>[{timestamp}]</span> "
                f"<span style='color: {color}; font-weight: {weight};'>{badge} {safe_msg}</span>"
                f"</div>"
            )
        else:
            color = "#e4e4e7"
            badge = "ℹ️"
            weight = "normal"
            formatted_html = (
                f"<div style='margin-bottom: 2px;'>"
                f"<span style='color: #71717a; font-size: 8pt;'>[{timestamp}]</span> "
                f"<span style='color: {color}; font-weight: {weight};'>{badge} {safe_msg}</span>"
                f"</div>"
            )

        self.text_edit.append(formatted_html)
        self.text_edit.moveCursor(QTextCursor.End)

    def _copy_log(self):
        plain_text = self.text_edit.toPlainText()
        if plain_text:
            QApplication.clipboard().setText(plain_text)
            self.btn_copy.setText("✅ تم النسخ!")
            self.append_log("Log copied to clipboard! (تم نسخ السجل للحافظة)")
            from PySide6.QtCore import QTimer
            QTimer.singleShot(2000, lambda: self.btn_copy.setText("📋 نسخ السجل"))
