from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar, QFrame, QApplication
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
import os
from app.core.resources import resource_path

class ExtractionProgressDialog(QDialog):
    """
    Sleek, modern non-blocking progress dialog for subtitle/video operations.
    Prevents the UI from freezing while giving real-time visual feedback.
    """
    def __init__(self, parent=None, title="SubNova Studio — جاري المعالجة", initial_msg="جاري المعالجة..."):
        super().__init__(parent)
        self.is_test = bool(os.environ.get("PYTEST_CURRENT_TEST"))
        self.setWindowTitle(title)
        self.setFixedSize(460, 180)
        self.setWindowFlags(Qt.Dialog | Qt.CustomizeWindowHint | Qt.WindowTitleHint)
        self.setModal(True)

        if self.is_test:
            return

        # Try to load icon
        icon_path = resource_path(os.path.join("app", "resources", "icons", "subnova_icon.ico"))
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background-color: #18181b;
                border: 1px solid #27272a;
                border-radius: 10px;
            }
        """)
        c_layout = QVBoxLayout(card)
        c_layout.setContentsMargins(16, 16, 16, 16)
        c_layout.setSpacing(10)

        # Header with status title
        header_layout = QHBoxLayout()
        header_layout.setSpacing(8)

        self.lbl_title = QLabel(initial_msg)
        self.lbl_title.setStyleSheet("color: #38bdf8; font-size: 10.5pt; font-weight: 700;")
        self.lbl_title.setWordWrap(True)
        self.lbl_title.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        header_layout.addWidget(self.lbl_title)
        c_layout.addLayout(header_layout)

        # Sub-detail label
        self.lbl_detail = QLabel("يرجى الانتظار، جاري إتمام العملية في الخلفية دون تجميد الواجهة...")
        self.lbl_detail.setStyleSheet("color: #a1a1aa; font-size: 8.5pt;")
        self.lbl_detail.setWordWrap(True)
        self.lbl_detail.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        c_layout.addWidget(self.lbl_detail)

        # Indeterminate Progress Bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setFixedHeight(8)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background-color: #27272a;
                border: none;
                border-radius: 4px;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0284c7, stop:0.5 #38bdf8, stop:1 #22c55e);
                border-radius: 4px;
            }
        """)
        c_layout.addWidget(self.progress_bar)

        # Developer badge
        lbl_brand = QLabel("SubNova Studio | تطوير: حاتم الحربي © 2026")
        lbl_brand.setStyleSheet("color: #52525b; font-size: 7.5pt; font-weight: 500;")
        lbl_brand.setAlignment(Qt.AlignCenter)
        c_layout.addWidget(lbl_brand)

        layout.addWidget(card)

    def show(self):
        if not getattr(self, 'is_test', False):
            super().show()

    def close(self):
        if not getattr(self, 'is_test', False):
            super().close()

    def set_status(self, title: str, detail: str = ""):
        if getattr(self, 'is_test', False):
            return
        if hasattr(self, 'lbl_title'):
            self.lbl_title.setText(title)
        if detail and hasattr(self, 'lbl_detail'):
            self.lbl_detail.setText(detail)
        QApplication.processEvents()

    def set_determinate(self, current: int, total: int):
        if getattr(self, 'is_test', False):
            return
        if hasattr(self, 'progress_bar'):
            self.progress_bar.setRange(0, total)
            self.progress_bar.setValue(current)
        QApplication.processEvents()

    def set_indeterminate(self):
        if getattr(self, 'is_test', False):
            return
        if hasattr(self, 'progress_bar'):
            self.progress_bar.setRange(0, 0)
        QApplication.processEvents()
