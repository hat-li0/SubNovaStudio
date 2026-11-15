from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QRadioButton,
    QButtonGroup, QSpinBox, QPushButton, QDialogButtonBox, QFrame
)
from PySide6.QtCore import Qt
from app.subtitle.timecode import parse_timecode_ms, format_timecode

class ShiftTimingsDialog(QDialog):
    """
    SubNova Studio — Ultra-Precise Timing & Synchronization Dialog.
    Allows offsetting start and end timestamps forward or backward
    with millisecond precision and live timecode preview calculation.
    """
    def __init__(self, parent=None, has_selection: bool = False, sample_start_time: str = ""):
        super().__init__(parent)
        self.setWindowTitle("⏱️ ضبط وتزامن التوقيت الزمني (Time Sync & Delay Adjuster)")
        self.setMinimumWidth(440)
        self.sample_start_time = sample_start_time
        self.setStyleSheet("""
            QDialog {
                background-color: #0f172a;
                color: #e2e8f0;
            }
            QLabel {
                color: #cbd5e1;
                font-size: 9.5pt;
            }
            QRadioButton {
                color: #e2e8f0;
                font-size: 9pt;
            }
            QSpinBox {
                background-color: #1e293b;
                border: 1px solid #334155;
                color: #38bdf8;
                font-size: 11pt;
                font-weight: bold;
                padding: 4px;
                border-radius: 4px;
            }
            QPushButton {
                background-color: #0284c7;
                color: white;
                font-weight: 600;
                border-radius: 4px;
                padding: 6px 14px;
            }
            QPushButton:hover {
                background-color: #0369a1;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # Header
        lbl_head = QLabel("ضبط إزاحة وتزامن التوقيت الزمني للأسطر بدقة فائقة:")
        lbl_head.setStyleSheet("color: #38bdf8; font-weight: bold; font-size: 10.5pt;")
        layout.addWidget(lbl_head)

        # Direction Box
        dir_box = QFrame()
        dir_box.setStyleSheet("background-color: #1e293b; border-radius: 6px; padding: 6px;")
        dir_layout = QHBoxLayout(dir_box)

        self.dir_group = QButtonGroup(self)
        # Advancing display time (-) makes subtitles appear EARLIER on screen
        self.radio_advance = QRadioButton("⏪ تقديم الظهور (- / يظهر أبكر قبل الصوت)")
        self.radio_advance.toggled.connect(self._update_preview)
        # Delaying display time (+) makes subtitles appear LATER on screen
        self.radio_delay = QRadioButton("⏩ تأخير الظهور (+ / يظهر لاحقاً بعد الصوت)")
        self.radio_delay.setChecked(True)
        self.radio_delay.toggled.connect(self._update_preview)

        self.dir_group.addButton(self.radio_advance)
        self.dir_group.addButton(self.radio_delay)

        dir_layout.addWidget(self.radio_advance)
        dir_layout.addWidget(self.radio_delay)
        layout.addWidget(dir_box)

        # Offset input row
        offset_layout = QHBoxLayout()
        lbl_amount = QLabel("مقدار الإزاحة:")
        self.spn_ms = QSpinBox()
        self.spn_ms.setRange(1, 600000)
        self.spn_ms.setSingleStep(50)
        self.spn_ms.setValue(500)
        self.spn_ms.setSuffix(" مللي ثانية (ms)")
        self.spn_ms.valueChanged.connect(self._update_preview)
        offset_layout.addWidget(lbl_amount)
        offset_layout.addWidget(self.spn_ms)
        layout.addLayout(offset_layout)

        # Quick preset buttons (e.g. 100ms, 250ms, 500ms, 1s, 2s)
        presets_layout = QHBoxLayout()
        for ms_val, label in [
            (100, "0.1 ث"), (250, "0.25 ث"), (500, "0.5 ث"),
            (1000, "1.0 ث"), (2000, "2.0 ث")
        ]:
            btn = QPushButton(label)
            btn.setFixedHeight(26)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #334155;
                    font-size: 8.5pt;
                    font-weight: 500;
                    padding: 2px 8px;
                    border: 1px solid #475569;
                }
                QPushButton:hover {
                    background-color: #475569;
                    color: #38bdf8;
                }
            """)
            btn.clicked.connect(lambda checked, v=ms_val: self.spn_ms.setValue(v))
            presets_layout.addWidget(btn)
        layout.addLayout(presets_layout)

        # Live calculation preview
        self.lbl_preview = QLabel()
        self.lbl_preview.setStyleSheet("""
            QLabel {
                background-color: #0b1329;
                color: #22c55e;
                font-family: Consolas, monospace;
                font-size: 9pt;
                font-weight: bold;
                border: 1px dashed #334155;
                border-radius: 4px;
                padding: 6px 10px;
            }
        """)
        layout.addWidget(self.lbl_preview)
        self._update_preview()

        # Scope Box
        scope_box = QFrame()
        scope_box.setStyleSheet("background-color: #1e293b; border-radius: 6px; padding: 6px;")
        scope_layout = QVBoxLayout(scope_box)
        
        self.radio_selected = QRadioButton("الأسطر المحددة فقط")
        self.radio_all = QRadioButton("كل أسطر الترجمة في الملف")
        
        if has_selection:
            self.radio_selected.setChecked(True)
        else:
            self.radio_selected.setEnabled(False)
            self.radio_all.setChecked(True)

        scope_layout.addWidget(self.radio_selected)
        scope_layout.addWidget(self.radio_all)
        layout.addWidget(scope_box)

        # Dialog buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText("تطبيق التزامن")
        buttons.button(QDialogButtonBox.Cancel).setText("إلغاء")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _parse_time_to_ms(self, time_str: str) -> int:
        val = parse_timecode_ms(time_str)
        return val if val is not None else 0

    def _ms_to_time_str(self, ms: int, is_srt: bool = False) -> str:
        return format_timecode(ms, template_str="," if is_srt else (self.sample_start_time or ""))

    def _update_preview(self):
        if not hasattr(self, "lbl_preview"):
            return
        offset = self.get_offset_ms()
        sign_str = f"+{offset}ms" if offset >= 0 else f"{offset}ms"
        sec_abs = abs(offset) / 1000.0
        effect_desc = (
            f"ستظهر الترجمة لاحقاً بـ {sec_abs:.2f} ثانية"
            if offset >= 0
            else f"ستظهر الترجمة أبكر بـ {sec_abs:.2f} ثانية"
        )
        if self.sample_start_time:
            orig_ms = parse_timecode_ms(self.sample_start_time)
            if orig_ms is not None:
                raw_new_ms = orig_ms + offset
                new_ms = max(0, raw_new_ms)
                new_ts = format_timecode(new_ms, template_str=self.sample_start_time)
                clamp_note = " — (تم التثبيت عند البداية 0 مع حفظ مدة السطر)" if raw_new_ms < 0 else ""
                self.lbl_preview.setText(
                    f"معاينة: {self.sample_start_time} ➔ {new_ts} ({sign_str})\n{effect_desc}{clamp_note}"
                )
                return
        self.lbl_preview.setText(f"إزاحة التوقيت بمقدار: {sign_str} — {effect_desc}")

    def get_offset_ms(self) -> int:
        ms = self.spn_ms.value()
        return ms if self.radio_delay.isChecked() else -ms

    def is_selected_only(self) -> bool:
        return self.radio_selected.isChecked()
