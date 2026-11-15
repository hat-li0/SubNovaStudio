import os
from pathlib import Path
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QFileDialog, QFrame
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtCore import Qt
from app.ui.bus import EventBus
from app.subtitle.video_extractor import VIDEO_EXTENSIONS

SUBTITLE_EXTS = ('.srt', '.ass', '.ssa', '.vtt', '.sbv', '.txt', '.json')
ALL_SUPPORTED_EXTS = SUBTITLE_EXTS + VIDEO_EXTENSIONS

class FilePanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(6)
        
        card = QFrame()
        card.setObjectName("file_card")
        card.setStyleSheet("""
            QFrame#file_card {
                background-color: #18181b;
                border: 1px dashed #0284c7;
                border-radius: 8px;
            }
        """)
        c_layout = QVBoxLayout(card)
        c_layout.setContentsMargins(10, 8, 10, 8)
        c_layout.setSpacing(6)

        lbl_header = QLabel("✨ SubNova Studio | منطقة استيراد الوسائط")
        lbl_header.setStyleSheet("color: #38bdf8; font-size: 8pt; font-weight: 700;")
        lbl_header.setAlignment(Qt.AlignCenter)
        c_layout.addWidget(lbl_header)

        btn_layout_1 = QHBoxLayout()
        btn_layout_1.setSpacing(6)
        
        self.btn_select_video = QPushButton("🎬 استيراد فيديو")
        self.btn_select_video.setObjectName("video_action")
        self.btn_select_video.setStyleSheet("background-color: #0284c7; color: white; font-weight: 600;")
        self.btn_select_video.setToolTip("استخراج مسار الترجمة بتنسيقه الأصلي الكامل وترجمته وتحسينه تلقائياً")
        self.btn_select_video.clicked.connect(self._select_video)

        self.btn_select = QPushButton("📂 استيراد ترجمة")
        self.btn_select.setObjectName("primary_action")
        self.btn_select.clicked.connect(self._select_file)

        btn_layout_1.addWidget(self.btn_select_video)
        btn_layout_1.addWidget(self.btn_select)

        btn_layout_2 = QHBoxLayout()
        btn_layout_2.setSpacing(6)
        
        self.btn_select_folder = QPushButton("📁 مجلد كامل")
        self.btn_select_folder.clicked.connect(self._select_folder)

        self.btn_new_session = QPushButton("🔄 مسح الجلسة")
        self.btn_new_session.clicked.connect(self._clear_all)

        btn_layout_2.addWidget(self.btn_select_folder)
        btn_layout_2.addWidget(self.btn_new_session)
        
        self.lbl_selected = QLabel("اسحب وأفلت الفيديوهات أو ملفات الترجمة هنا مباشرة")
        self.lbl_selected.setStyleSheet("color: #38bdf8; font-size: 8.5pt; font-weight: 500;")
        self.lbl_selected.setWordWrap(True)
        self.lbl_selected.setAlignment(Qt.AlignCenter)

        self.lbl_formats = QLabel("يدعم ملفات ASS, SRT, VTT واستخراج تلقائي مباشر من MKV, MP4")
        self.lbl_formats.setStyleSheet("color: #71717a; font-size: 7.5pt;")
        self.lbl_formats.setWordWrap(True)
        self.lbl_formats.setAlignment(Qt.AlignCenter)
        
        c_layout.addLayout(btn_layout_1)
        c_layout.addLayout(btn_layout_2)
        c_layout.addWidget(self.lbl_selected)
        c_layout.addWidget(self.lbl_formats)
        
        self.layout.addWidget(card)
        
    def _select_video(self):
        file_paths, _ = QFileDialog.getOpenFileNames(
            self, "اختر ملفات الفيديو لاستخراج الترجمة منها تلقائياً", "",
            "ملفات الفيديو (*.mkv *.mp4 *.avi *.mov *.webm *.flv *.ts *.m4v);;كل الملفات (*.*)"
        )
        if file_paths:
            self._handle_incoming_paths(file_paths)

    def _select_file(self):
        file_paths, _ = QFileDialog.getOpenFileNames(
            self, "اختر ملفات الترجمة", "", "ملفات الترجمة (*.srt *.ass *.ssa *.vtt *.sbv *.txt *.json);;كل الملفات (*.*)"
        )
        if file_paths:
            self._handle_incoming_paths(file_paths)

    def _select_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "اختر مجلداً يحتوي على ملفات الترجمة أو الفيديوهات")
        if folder:
            self._handle_incoming_paths([folder])

    def _clear_all(self):
        self.lbl_selected.setText("اسحب وأفلت الفيديوهات أو ملفات الترجمة هنا مباشرة")
        EventBus.instance().files_cleared.emit()

    def _handle_incoming_paths(self, paths):
        collected = []
        for p in paths:
            clean = os.path.normpath(str(p))
            if os.path.isfile(clean):
                if clean.lower().endswith(ALL_SUPPORTED_EXTS):
                    collected.append(clean)
            elif os.path.isdir(clean):
                for root, _, files in os.walk(clean):
                    for f in files:
                        if f.lower().endswith(ALL_SUPPORTED_EXTS):
                            collected.append(os.path.normpath(os.path.join(root, f)))
        
        collected = list(dict.fromkeys(collected))
        if collected:
            video_count = sum(1 for f in collected if f.lower().endswith(VIDEO_EXTENSIONS))
            sub_count = len(collected) - video_count
            desc = []
            if video_count > 0:
                desc.append(f"{video_count} فيديو")
            if sub_count > 0:
                desc.append(f"{sub_count} ملف ترجمة")
            self.lbl_selected.setText(f"جاهز: {', '.join(desc)}")
            EventBus.instance().file_selected.emit(collected)
        else:
            self.lbl_selected.setText("لم يتم العثور على ملفات ترجمة أو فيديو مدعومة.")

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            return
        event.ignore()

    def dropEvent(self, event: QDropEvent):
        urls = event.mimeData().urls()
        if urls:
            paths = [url.toLocalFile() for url in urls if url.isLocalFile()]
            if paths:
                self._handle_incoming_paths(paths)
                event.acceptProposedAction()
