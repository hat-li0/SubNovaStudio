from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QPixmap
import os
from app.core.resources import resource_path

class AboutDialog(QDialog):
    """
    SubNova Studio — Official About & Developer Rights Dialog.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("حول SubNova Studio")
        self.setFixedSize(500, 420)
        self.setModal(True)

        ico_path = resource_path(os.path.join("app", "resources", "icons", "subnova_icon.ico"))
        png_path = resource_path(os.path.join("app", "resources", "icons", "subnova_icon.png"))

        if os.path.exists(ico_path):
            self.setWindowIcon(QIcon(ico_path))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background-color: #18181b;
                border: 1px solid #27272a;
                border-radius: 12px;
            }
        """)
        c_layout = QVBoxLayout(card)
        c_layout.setContentsMargins(20, 20, 20, 20)
        c_layout.setSpacing(12)

        # Logo and Title Header
        header = QHBoxLayout()
        header.setSpacing(16)

        if os.path.exists(png_path):
            lbl_icon = QLabel()
            pix = QPixmap(png_path).scaled(64, 64, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            lbl_icon.setPixmap(pix)
            header.addWidget(lbl_icon)

        title_col = QVBoxLayout()
        title_col.setSpacing(2)

        lbl_app_name = QLabel("SubNova Studio")
        lbl_app_name.setStyleSheet("color: #38bdf8; font-size: 16pt; font-weight: 800; font-family: 'Segoe UI', sans-serif;")
        lbl_app_sub = QLabel("استوديو سوب نوفا — المترجم والمدقق الخارق للشاشة")
        lbl_app_sub.setStyleSheet("color: #a1a1aa; font-size: 9pt; font-weight: 600;")
        lbl_ver = QLabel("الإصدار: v2.0.0 (نسخة الديسكتوب الرسمية)")
        lbl_ver.setStyleSheet("color: #4ade80; font-size: 8pt; font-weight: 500;")

        title_col.addWidget(lbl_app_name)
        title_col.addWidget(lbl_app_sub)
        title_col.addWidget(lbl_ver)
        header.addLayout(title_col)
        header.addStretch()

        c_layout.addLayout(header)

        # Separator line
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color: #27272a;")
        c_layout.addWidget(sep)

        # Developer Rights Box (Prominent)
        dev_box = QFrame()
        dev_box.setStyleSheet("""
            QFrame {
                background-color: #0f172a;
                border: 1px solid #0284c7;
                border-radius: 8px;
            }
        """)
        dev_layout = QVBoxLayout(dev_box)
        dev_layout.setContentsMargins(12, 10, 12, 10)
        dev_layout.setSpacing(4)

        lbl_dev_title = QLabel("👑 المطور وصاحب المشروع:")
        lbl_dev_title.setStyleSheet("color: #38bdf8; font-size: 9pt; font-weight: 700;")
        lbl_dev_name = QLabel("حاتم الحربي (Hatim Alharbi)")
        lbl_dev_name.setStyleSheet("color: #ffffff; font-size: 12pt; font-weight: 800;")
        lbl_rights = QLabel("© 2026 جميع الحقوق محفوظة لـ حاتم الحربي")
        lbl_rights.setStyleSheet("color: #94a3b8; font-size: 8.5pt;")

        dev_layout.addWidget(lbl_dev_title)
        dev_layout.addWidget(lbl_dev_name)
        dev_layout.addWidget(lbl_rights)
        c_layout.addWidget(dev_box)

        # App features / description
        lbl_desc = QLabel(
            "نظام مدمج متطور وشامل لترجمة وتدقيق نصوص الشاشة باحترافية سينمائية:\n"
            "• حصانة مطلقة وتامة لوسوم وتنسيقات Aegisub الكاملة (\\pos, \\an8, \\N, الرسم).\n"
            "• محرك التنقية الذاتي الخارق (Smart Auto-Healing) لضبط علامات الترقيم والشوائب.\n"
            "• تكامل متعدد مع أقوى مزودات الذكاء الاصطناعي (Gemini, OpenAI, Ollama, LM Studio).\n"
            "• استخراج لحظي فائق السرعة لمسارات الترجمة من ملفات الفيديو (MKV / MP4)."
        )
        lbl_desc.setStyleSheet("color: #cbd5e1; font-size: 8.5pt; line-height: 1.4;")
        lbl_desc.setWordWrap(True)
        c_layout.addWidget(lbl_desc)

        layout.addWidget(card)

        # Close Button
        btn_close = QPushButton("إغلاق")
        btn_close.setFixedHeight(34)
        btn_close.setStyleSheet("""
            QPushButton {
                background-color: #27272a;
                color: #ffffff;
                font-weight: 600;
                border-radius: 6px;
                border: 1px solid #3f3f46;
            }
            QPushButton:hover {
                background-color: #3f3f46;
            }
        """)
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close)
