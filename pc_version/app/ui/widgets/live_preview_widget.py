from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QPushButton
)
from PySide6.QtCore import Qt
from app.ui.bus import EventBus

class LivePreviewWidget(QWidget):
    """
    Displays real-time side-by-side comparison of the original subtitle line
    and the AI-improved, healed translation as each line/batch finishes.
    Supports collapsing to save vertical space.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(4, 2, 4, 2)
        self.layout.setSpacing(4)

        # Header with Collapse Toggle
        hdr_layout = QHBoxLayout()
        hdr_layout.setContentsMargins(4, 0, 4, 0)
        
        lbl_title = QLabel("👁️ المعاينة الحية المباشرة (Live Subtitle Preview):")
        lbl_title.setStyleSheet("font-weight: 600; color: #38bdf8; font-size: 9.5pt;")
        hdr_layout.addWidget(lbl_title)
        hdr_layout.addStretch()

        self.btn_toggle = QPushButton("▼ إخفاء المعاينة")
        self.btn_toggle.setCheckable(True)
        self.btn_toggle.setChecked(False)
        self.btn_toggle.setFixedHeight(22)
        self.btn_toggle.setStyleSheet("background: transparent; border: none; color: #71717a; font-size: 8pt;")
        self.btn_toggle.clicked.connect(self._toggle_collapse)
        hdr_layout.addWidget(self.btn_toggle)
        self.layout.addLayout(hdr_layout)

        # Container Frame
        self.preview_box = QFrame()
        self.preview_box.setStyleSheet(
            "QFrame { background-color: #18181b; border: 1px solid #27272a; border-radius: 6px; padding: 4px; }"
        )
        box_layout = QHBoxLayout(self.preview_box)
        box_layout.setContentsMargins(8, 6, 8, 6)
        box_layout.setSpacing(12)

        # Original Line Box
        orig_container = QWidget()
        orig_layout = QVBoxLayout(orig_container)
        orig_layout.setContentsMargins(0, 0, 0, 0)
        orig_layout.setSpacing(2)
        
        lbl_orig_head = QLabel("النص الأصلي (Original Line):")
        lbl_orig_head.setStyleSheet("color: #71717a; font-size: 8pt; font-weight: 600;")
        
        self.lbl_orig = QLabel("بانتظار بدء المعالجة...")
        self.lbl_orig.setWordWrap(True)
        self.lbl_orig.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.lbl_orig.setStyleSheet("color: #e4e4e7; font-size: 9.5pt;")
        
        orig_layout.addWidget(lbl_orig_head)
        orig_layout.addWidget(self.lbl_orig)
        orig_layout.addStretch()

        # Divider
        v_sep = QFrame()
        v_sep.setFrameShape(QFrame.VLine)
        v_sep.setStyleSheet("color: #27272a;")

        # Improved Line Box
        imp_container = QWidget()
        imp_layout = QVBoxLayout(imp_container)
        imp_layout.setContentsMargins(0, 0, 0, 0)
        imp_layout.setSpacing(2)
        
        lbl_imp_head = QLabel("التحسين الفائق والمُصفى (Improved Line):")
        lbl_imp_head.setStyleSheet("color: #4ade80; font-size: 8pt; font-weight: 600;")
        
        self.lbl_imp = QLabel("بانتظار بدء المعالجة...")
        self.lbl_imp.setWordWrap(True)
        self.lbl_imp.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.lbl_imp.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.lbl_imp.setStyleSheet("color: #86efac; font-size: 10pt; font-weight: 600;")
        
        imp_layout.addWidget(lbl_imp_head)
        imp_layout.addWidget(self.lbl_imp)
        imp_layout.addStretch()

        box_layout.addWidget(orig_container, 1)
        box_layout.addWidget(v_sep)
        box_layout.addWidget(imp_container, 1)

        self.layout.addWidget(self.preview_box)

        # Connect to event bus
        EventBus.instance().live_preview_updated.connect(self.update_preview)

    def _toggle_collapse(self):
        collapsed = self.btn_toggle.isChecked()
        self.preview_box.setVisible(not collapsed)
        self.btn_toggle.setText("▲ إظهار المعاينة" if collapsed else "▼ إخفاء المعاينة")

    def update_preview(self, orig_text: str, imp_text: str):
        self.lbl_orig.setText(orig_text or "")
        self.lbl_imp.setText(imp_text or "")

    def clear(self):
        self.lbl_orig.setText("بانتظار بدء المعالجة...")
        self.lbl_imp.setText("بانتظار بدء المعالجة...")
