from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QRadioButton,
    QButtonGroup, QPushButton, QCheckBox, QFrame, QScrollArea, QWidget
)
from PySide6.QtCore import Qt
from typing import List, Optional
from app.subtitle.video_extractor import SubtitleStreamInfo

class VideoTrackSelectorDialog(QDialog):
    """
    Dialog allowing the user to view all embedded subtitle tracks in a video,
    choose the desired track (with smart recommendation), and choose whether to
    auto-start the translation/improvement immediately, and guarantee .ass extraction.
    """
    def __init__(self, parent=None, video_name: str = "", streams: List[SubtitleStreamInfo] = None, recommended_index: int = 0):
        super().__init__(parent)
        self.setWindowTitle("🎬 اختيار مسار الترجمة من الفيديو (Select Subtitle Track)")
        self.setMinimumWidth(540)
        self.setModal(True)
        
        self.streams = streams or []
        self.selected_stream_index = recommended_index
        self.auto_start_processing = True
        self.prefer_ass = True

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # Header Title
        lbl_head = QLabel("🎬 تم اكتشاف مسارات ترجمة مدمجة داخل ملف الفيديو:")
        lbl_head.setStyleSheet("font-weight: 600; color: #38bdf8; font-size: 11pt;")
        layout.addWidget(lbl_head)

        lbl_vname = QLabel(f"ملف الفيديو: {video_name}")
        lbl_vname.setStyleSheet("color: #a1a1aa; font-size: 9pt;")
        lbl_vname.setWordWrap(True)
        layout.addWidget(lbl_vname)

        # Scroll area for tracks
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMaximumHeight(260)
        scroll.setStyleSheet("QScrollArea { border: 1px solid #27272a; border-radius: 6px; }")

        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        scroll_layout.setSpacing(8)

        self.btn_group = QButtonGroup(self)

        for s in self.streams:
            is_rec = (s.index == recommended_index)
            rec_tag = " ⭐ (المسار الموصى به - حوار كامل)" if is_rec else ""
            
            lang_label = s.language.upper() if s.language and s.language != "und" else "غير محدد"
            title_label = f" «{s.title}»" if s.title else ""
            codec_label = s.codec_name.upper()
            lines_label = f" ({s.frame_count} سطر)" if getattr(s, 'frame_count', 0) > 0 else ""
            
            extra_tags = []
            if s.is_image_based:
                extra_tags.append("⚠️ [صورة PGS - غير نصي]")
            if s.is_hearing_impaired:
                extra_tags.append("[SDH]")
            if s.is_forced:
                extra_tags.append("[Forced]")
            extra_str = f" {' '.join(extra_tags)}" if extra_tags else ""

            rb_text = f"مسار {s.index + 1}: [{lang_label}] بصيغة ({codec_label}){title_label}{lines_label}{extra_str}{rec_tag}"
            rb = QRadioButton(rb_text)
            
            if is_rec:
                rb.setChecked(True)
                rb.setStyleSheet("font-weight: 600; color: #4ade80;")
            elif s.is_image_based:
                rb.setStyleSheet("color: #f87171;")
            else:
                rb.setStyleSheet("color: #e4e4e7;")
                
            self.btn_group.addButton(rb, s.index)
            scroll_layout.addWidget(rb)

        scroll_layout.addStretch()
        scroll.setWidget(scroll_widget)
        layout.addWidget(scroll)

        # Options Box
        opt_box = QFrame()
        opt_box.setStyleSheet("background-color: #18181b; border: 1px solid #27272a; border-radius: 6px; padding: 6px;")
        opt_layout = QVBoxLayout(opt_box)
        opt_layout.setSpacing(6)

        # Guarantee ASS option
        self.chk_prefer_ass = QCheckBox("✨ استخراج بصيغة ASS الاحترافية (Aegisub Format) للحفاظ على التنسيقات")
        self.chk_prefer_ass.setChecked(True)
        self.chk_prefer_ass.setStyleSheet("font-weight: 600; color: #38bdf8;")
        opt_layout.addWidget(self.chk_prefer_ass)

        # Automation Checkbox
        self.chk_auto_start = QCheckBox("🚀 البدء الفوري بالترجمة والتحسين التلقائي بعد الاستخراج مباشرة")
        self.chk_auto_start.setChecked(True)
        self.chk_auto_start.setStyleSheet("font-weight: 600; color: #fbbf24;")
        opt_layout.addWidget(self.chk_auto_start)

        layout.addWidget(opt_box)

        # Buttons
        btn_box = QHBoxLayout()
        btn_box.setSpacing(10)
        
        self.btn_confirm = QPushButton("استخراج وبدء العمل")
        self.btn_confirm.setStyleSheet("background-color: #0284c7; color: white; font-weight: 600; padding: 6px 14px;")
        self.btn_confirm.clicked.connect(self._on_confirm)

        self.btn_cancel = QPushButton("إلغاء")
        self.btn_cancel.clicked.connect(self.reject)

        btn_box.addStretch()
        btn_box.addWidget(self.btn_cancel)
        btn_box.addWidget(self.btn_confirm)
        layout.addLayout(btn_box)

    def _on_confirm(self):
        sel_id = self.btn_group.checkedId()
        if sel_id >= 0:
            self.selected_stream_index = sel_id
        self.auto_start_processing = self.chk_auto_start.isChecked()
        self.prefer_ass = self.chk_prefer_ass.isChecked()
        self.accept()
