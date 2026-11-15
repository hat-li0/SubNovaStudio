import re
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QTextEdit, QPushButton, QFrame
)
from PySide6.QtCore import Qt, Signal, QTimer, QEvent
from app.subtitle.timecode import parse_timecode_ms, parse_timecode_ms_safe

class InlineSubtitleEditor(QWidget):
    """
    SubNova Studio — Dedicated Subtitle Inline Editor Panel.
    Provides immediate, high-productivity editing for the currently selected subtitle line
    (Start, End, Speaker, Original, Arabic Translation) with real-time CPS metrics.
    """
    line_updated = Signal(int, str, str, str, str, str)  # (row, start, end, speaker, orig, trans)
    line_committed = Signal(int, tuple, tuple)  # (row, old_state, new_state)
    nav_previous_requested = Signal()
    nav_next_requested = Signal()
    play_in_video_requested = Signal(str)  # (start_time_str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_row = -1
        self._is_loading = False
        self._baseline_row = -1
        self._baseline_state = None
        self._commit_timer = QTimer(self)
        self._commit_timer.setSingleShot(True)
        self._commit_timer.setInterval(400)
        self._commit_timer.timeout.connect(self.commit_pending_edit)

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 2, 0, 2)
        self.layout.setSpacing(4)

        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background-color: #0f172a;
                border: 1px solid #1e293b;
                border-radius: 8px;
            }
            QLabel {
                color: #94a3b8;
                font-size: 8.5pt;
                font-weight: 600;
            }
            QLineEdit {
                background-color: #1e293b;
                border: 1px solid #334155;
                color: #f8fafc;
                border-radius: 4px;
                padding: 4px 6px;
                font-size: 9pt;
            }
            QLineEdit:focus {
                border: 1px solid #38bdf8;
            }
            QTextEdit {
                background-color: #1e293b;
                border: 1px solid #334155;
                color: #f8fafc;
                border-radius: 4px;
                padding: 6px;
                font-size: 10pt;
            }
            QTextEdit:focus {
                border: 1px solid #38bdf8;
            }
            QPushButton {
                background-color: #1e293b;
                color: #cbd5e1;
                border: 1px solid #334155;
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 8.5pt;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #334155;
                color: #ffffff;
            }
        """)
        c_layout = QVBoxLayout(card)
        c_layout.setContentsMargins(8, 6, 8, 6)
        c_layout.setSpacing(6)

        # Top Bar: Row Info, Time Inputs, CPS, Navigation
        top_row = QHBoxLayout()
        top_row.setSpacing(8)

        self.lbl_row_info = QLabel("السطر: لم يُحدد")
        self.lbl_row_info.setStyleSheet("color: #38bdf8; font-weight: bold; font-size: 9.5pt;")
        top_row.addWidget(self.lbl_row_info)

        lbl_start = QLabel("البداية:")
        self.edit_start = QLineEdit()
        self.edit_start.setFixedWidth(80)
        self.edit_start.textChanged.connect(self._on_timing_changed)
        top_row.addWidget(lbl_start)
        top_row.addWidget(self.edit_start)

        lbl_end = QLabel("النهاية:")
        self.edit_end = QLineEdit()
        self.edit_end.setFixedWidth(80)
        self.edit_end.textChanged.connect(self._on_timing_changed)
        top_row.addWidget(lbl_end)
        top_row.addWidget(self.edit_end)

        lbl_spk = QLabel("المتحدث:")
        self.edit_speaker = QLineEdit()
        self.edit_speaker.setFixedWidth(90)
        self.edit_speaker.textChanged.connect(self._on_content_changed)
        top_row.addWidget(lbl_spk)
        top_row.addWidget(self.edit_speaker)

        self.lbl_cps = QLabel("CPS: 0.0")
        self.lbl_cps.setStyleSheet("color: #4ade80; font-weight: bold; font-size: 8.5pt;")
        top_row.addWidget(self.lbl_cps)

        top_row.addStretch()

        # Play in video button
        self.btn_play_video = QPushButton("🎬 تشغيل السطر")
        self.btn_play_video.setStyleSheet("background-color: #0369a1; color: white;")
        self.btn_play_video.clicked.connect(self._on_play_in_video)
        top_row.addWidget(self.btn_play_video)

        # Navigation buttons
        self.btn_prev = QPushButton("◀ السابق")
        self.btn_prev.clicked.connect(self.nav_previous_requested.emit)
        top_row.addWidget(self.btn_prev)

        self.btn_next = QPushButton("التالي ▶")
        self.btn_next.clicked.connect(self.nav_next_requested.emit)
        top_row.addWidget(self.btn_next)

        c_layout.addLayout(top_row)

        # Two-box Editor: Original (Left) vs Arabic Translation (Right)
        text_layout = QHBoxLayout()
        text_layout.setSpacing(8)

        # Original
        orig_box = QVBoxLayout()
        orig_box.setSpacing(2)
        lbl_orig_head = QLabel("النص الأصلي (Original):")
        self.edit_orig = QTextEdit()
        self.edit_orig.setFixedHeight(58)
        self.edit_orig.setStyleSheet("color: #94a3b8; font-size: 9.5pt;")
        self.edit_orig.textChanged.connect(self._on_content_changed)
        orig_box.addWidget(lbl_orig_head)
        orig_box.addWidget(self.edit_orig)
        text_layout.addLayout(orig_box, 1)

        # Translation
        trans_box = QVBoxLayout()
        trans_box.setSpacing(2)
        lbl_trans_head = QLabel("الترجمة والتدقيق العربي (Arabic Translation):")
        lbl_trans_head.setStyleSheet("color: #38bdf8; font-weight: bold;")
        self.edit_trans = QTextEdit()
        self.edit_trans.setFixedHeight(58)
        self.edit_trans.setAlignment(Qt.AlignRight)
        self.edit_trans.setStyleSheet("color: #38bdf8; font-size: 10.5pt; font-weight: 600;")
        self.edit_trans.textChanged.connect(self._on_trans_changed)
        trans_box.addWidget(lbl_trans_head)
        trans_box.addWidget(self.edit_trans)
        text_layout.addLayout(trans_box, 1)

        c_layout.addLayout(text_layout)
        self.layout.addWidget(card)

        for editor_widget in (self.edit_start, self.edit_end, self.edit_speaker, self.edit_orig, self.edit_trans):
            editor_widget.installEventFilter(self)

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.FocusOut:
            self.commit_pending_edit()
        return super().eventFilter(obj, event)

    def _capture_current_state(self):
        return (
            self.edit_start.text().strip(),
            self.edit_end.text().strip(),
            self.edit_speaker.text().strip(),
            self.edit_orig.toPlainText().strip(),
            self.edit_trans.toPlainText().strip(),
        )

    def commit_pending_edit(self):
        """Flushes debounced inline edits into an atomic Undo/Redo commit signal."""
        self._commit_timer.stop()
        if self._is_loading or self._baseline_row < 0 or self._baseline_state is None:
            return
        valid, _, _ = self._validate_timing_inputs()
        cur_state = self._capture_current_state()
        if not valid:
            cur_state = (self._baseline_state[0], self._baseline_state[1], cur_state[2], cur_state[3], cur_state[4])
        if cur_state != self._baseline_state:
            old_state = self._baseline_state
            row = self._baseline_row
            self._baseline_state = cur_state
            self.line_committed.emit(row, old_state, cur_state)

    def load_event(self, row: int, event, total_rows: int = 0):
        self._commit_timer.stop()
        if not event:
            self.clear()
            return
        self._is_loading = True
        self.current_row = row
        total_str = f" من {total_rows}" if total_rows > 0 else ""
        self.lbl_row_info.setText(f"السطر #{row + 1}{total_str}")
        self.edit_start.setText(event.start_time or "")
        self.edit_end.setText(event.end_time or "")
        self.edit_speaker.setText(event.speaker or "")
        self.edit_orig.setPlainText(event.original_text or "")
        self.edit_trans.setPlainText(event.translated_text or "")
        self._update_cps()
        self._baseline_row = row
        self._baseline_state = self._capture_current_state()
        self._is_loading = False

    def clear(self):
        self._commit_timer.stop()
        self._is_loading = True
        self.current_row = -1
        self._baseline_row = -1
        self._baseline_state = None
        self.lbl_row_info.setText("السطر: لم يُحدد")
        self.edit_start.setStyleSheet("")
        self.edit_end.setStyleSheet("")
        self.edit_start.clear()
        self.edit_end.clear()
        self.edit_speaker.clear()
        self.edit_orig.clear()
        self.edit_trans.clear()
        self.lbl_cps.setStyleSheet("color: #4ade80; font-weight: bold; font-size: 8.5pt;")
        self.lbl_cps.setText("CPS: 0.0")
        self._is_loading = False

    def _validate_timing_inputs(self):
        """Returns (is_valid, s_ms, e_ms) and visually highlights invalid time fields."""
        s_ms = parse_timecode_ms(self.edit_start.text())
        e_ms = parse_timecode_ms(self.edit_end.text())
        order_bad = (s_ms is not None and e_ms is not None and e_ms < s_ms)

        bad_style = "border: 1px solid #ef4444; background-color: #2a1215;"
        self.edit_start.setStyleSheet(bad_style if (s_ms is None or order_bad) else "")
        self.edit_end.setStyleSheet(bad_style if (e_ms is None or order_bad) else "")
        return (s_ms is not None and e_ms is not None and not order_bad), s_ms, e_ms

    def _on_timing_changed(self):
        if self._is_loading:
            return
        valid, _, _ = self._validate_timing_inputs()
        self._update_cps()
        if valid:
            self._emit_update()
            self._commit_timer.start()

    def _on_content_changed(self):
        if self._is_loading:
            return
        self._update_cps()
        self._emit_update()
        self._commit_timer.start()

    def _on_trans_changed(self):
        self._on_content_changed()

    def _emit_update(self):
        if self.current_row >= 0 and not self._is_loading:
            self.line_updated.emit(
                self.current_row,
                self.edit_start.text().strip(),
                self.edit_end.text().strip(),
                self.edit_speaker.text().strip(),
                self.edit_orig.toPlainText().strip(),
                self.edit_trans.toPlainText().strip()
            )

    def _on_play_in_video(self):
        start_time = self.edit_start.text().strip()
        if parse_timecode_ms(start_time) is not None:
            self.play_in_video_requested.emit(start_time)

    def _update_cps(self):
        try:
            valid, s_ms, e_ms = self._validate_timing_inputs()
            if s_ms is None or e_ms is None:
                self.lbl_cps.setStyleSheet("color: #ef4444; font-weight: bold; font-size: 8.5pt;")
                self.lbl_cps.setText("CPS: -- ⚠️ (توقيت غير صالح)")
                return
            if e_ms < s_ms:
                self.lbl_cps.setStyleSheet("color: #ef4444; font-weight: bold; font-size: 8.5pt;")
                self.lbl_cps.setText("CPS: -- ⚠️ (النهاية قبل البداية)")
                return
            dur = (e_ms - s_ms) / 1000.0
            if dur <= 0.1:
                self.lbl_cps.setStyleSheet("color: #94a3b8; font-weight: bold; font-size: 8.5pt;")
                self.lbl_cps.setText("CPS: --")
                return
            txt = self.edit_trans.toPlainText() or self.edit_orig.toPlainText()
            clean = re.sub(r"\{.*?\}", "", txt).replace("\\N", " ").strip()
            cps = len(clean) / dur
            if cps > 22.0:
                self.lbl_cps.setStyleSheet("color: #ef4444; font-weight: bold; font-size: 8.5pt;")
                self.lbl_cps.setText(f"CPS: {cps:.1f} ⚠️ (سريع جداً)")
            elif cps > 18.0:
                self.lbl_cps.setStyleSheet("color: #f59e0b; font-weight: bold; font-size: 8.5pt;")
                self.lbl_cps.setText(f"CPS: {cps:.1f} ⚡ (سريع)")
            else:
                self.lbl_cps.setStyleSheet("color: #4ade80; font-weight: bold; font-size: 8.5pt;")
                self.lbl_cps.setText(f"CPS: {cps:.1f} ✓ (ممتاز)")
        except Exception:
            self.lbl_cps.setText("CPS: --")

    def _parse_ms(self, s: str) -> int:
        return parse_timecode_ms_safe(s, default=0)
