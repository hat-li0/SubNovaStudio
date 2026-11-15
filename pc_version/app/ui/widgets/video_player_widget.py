import re
from typing import List, Optional
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QSlider, QLabel, QFrame
)
from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QIcon
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtMultimediaWidgets import QVideoWidget
from app.subtitle.timecode import parse_timecode_ms, parse_timecode_ms_safe

class SubNovaVideoPlayerWidget(QWidget):
    """
    SubNova Studio — Integrated High-Performance Video Player.
    Features live subtitle synchronization, seek bar, timecode tracking,
    and video overlay for in-context translator review.
    """
    position_changed_signal = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_video_path = None
        self.subtitles = []  # List of (start_ms, end_ms, text)
        self._is_seeking = False

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(4)

        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background-color: #09090b;
                border: 1px solid #27272a;
                border-radius: 8px;
            }
        """)
        c_layout = QVBoxLayout(card)
        c_layout.setContentsMargins(6, 6, 6, 6)
        c_layout.setSpacing(4)

        # Video container
        self.video_container = QWidget()
        self.video_container.setMinimumHeight(200)
        v_box = QVBoxLayout(self.video_container)
        v_box.setContentsMargins(0, 0, 0, 0)
        v_box.setSpacing(0)

        self.video_widget = QVideoWidget()
        self.video_widget.setStyleSheet("background-color: #000000; border-radius: 6px;")
        v_box.addWidget(self.video_widget)

        # Subtitle overlay text banner
        self.lbl_subtitle_overlay = QLabel("شريط المعاينة الحية المتزامنة مع الفيديو")
        self.lbl_subtitle_overlay.setAlignment(Qt.AlignCenter)
        self.lbl_subtitle_overlay.setWordWrap(True)
        self.lbl_subtitle_overlay.setStyleSheet("""
            QLabel {
                background-color: rgba(15, 23, 42, 0.85);
                color: #38bdf8;
                font-size: 10.5pt;
                font-weight: 700;
                padding: 6px 12px;
                border-top: 1px solid #0284c7;
            }
        """)
        v_box.addWidget(self.lbl_subtitle_overlay)

        c_layout.addWidget(self.video_container)

        # Player Controls Row
        ctrl_layout = QHBoxLayout()
        ctrl_layout.setSpacing(6)

        self.btn_play = QPushButton("▶ تشغيل")
        self.btn_play.setFixedWidth(70)
        self.btn_play.setFixedHeight(26)
        self.btn_play.setStyleSheet("background-color: #0284c7; color: white; font-weight: bold; border-radius: 4px;")
        self.btn_play.clicked.connect(self.toggle_play)
        ctrl_layout.addWidget(self.btn_play)

        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 1000)
        self.slider.sliderPressed.connect(self._on_slider_pressed)
        self.slider.sliderReleased.connect(self._on_slider_released)
        self.slider.sliderMoved.connect(self._on_slider_moved)
        ctrl_layout.addWidget(self.slider)

        self.lbl_time = QLabel("00:00 / 00:00")
        self.lbl_time.setStyleSheet("color: #a1a1aa; font-size: 8pt; font-family: monospace;")
        ctrl_layout.addWidget(self.lbl_time)

        # Volume slider
        lbl_vol = QLabel("🔊")
        lbl_vol.setStyleSheet("color: #71717a; font-size: 8pt;")
        ctrl_layout.addWidget(lbl_vol)

        self.vol_slider = QSlider(Qt.Orientation.Horizontal)
        self.vol_slider.setRange(0, 100)
        self.vol_slider.setValue(70)
        self.vol_slider.setFixedWidth(60)
        self.vol_slider.valueChanged.connect(self._on_volume_changed)
        ctrl_layout.addWidget(self.vol_slider)

        c_layout.addLayout(ctrl_layout)
        self.layout.addWidget(card)

        # Lazy QMediaPlayer reference
        self.player = None
        self.audio_output = None

    def _ensure_player(self):
        if self.player is None:
            self.player = QMediaPlayer(self)
            self.audio_output = QAudioOutput(self)
            self.audio_output.setVolume(self.vol_slider.value() / 100.0)
            self.player.setAudioOutput(self.audio_output)
            self.player.setVideoOutput(self.video_widget)
            self.player.positionChanged.connect(self._on_position_changed)
            self.player.durationChanged.connect(self._on_duration_changed)
        return self.player

    def cleanup(self):
        """Completely terminates and unloads QMediaPlayer, releasing DirectShow/Media Foundation and GPU decoder."""
        try:
            if hasattr(self, 'player') and self.player is not None:
                self.player.stop()
                self.player.setSource(QUrl())
                self.player.setVideoOutput(None)
                self.player.setAudioOutput(None)
                self.player.deleteLater()
                self.player = None
                self.audio_output = None
                self.btn_play.setText("▶ تشغيل")
                self.lbl_subtitle_overlay.setText("مشغل الفيديو في وضع الإيقاف لتوفير موارد الجهاز")
        except Exception:
            pass

    def closeEvent(self, event):
        self.cleanup()
        super().closeEvent(event)

    def load_video(self, file_path: str):
        if not file_path:
            return
        self.current_video_path = file_path
        self._ensure_player()
        self.player.setSource(QUrl.fromLocalFile(file_path))
        self.btn_play.setText("▶ تشغيل")
        self.lbl_subtitle_overlay.setText("تم تحميل الفيديو: جاهز للمزامنة مع الأسطر")

    def toggle_play(self):
        self._ensure_player()
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
            self.btn_play.setText("▶ تشغيل")
        else:
            self.player.play()
            self.btn_play.setText("⏸ إيقاف")

    def seek_to_ms(self, ms: int):
        if self.player is not None:
            self.player.setPosition(max(0, int(ms)))

    def seek_to_time_str(self, time_str: str):
        ms = parse_timecode_ms(time_str)
        if ms is None:
            return
        self.seek_to_ms(ms)

    def get_current_position_ms(self) -> Optional[int]:
        """Returns current playback timestamp in milliseconds if player is active."""
        if self.player is not None:
            pos = self.player.position()
            if pos >= 0:
                return int(pos)
        return None

    def show_live_translation(self, translated_text: str, original_text: str = "", time_str: str = ""):
        """Immediately displays incoming live translated subtitle on the video overlay without seeking."""
        clean_trans = re.sub(r"\{.*?\}", "", translated_text).replace("\\N", " ").replace("\n", " ").strip()
        clean_orig = re.sub(r"\{.*?\}", "", original_text).replace("\\N", " ").replace("\n", " ").strip() if original_text else ""
        if clean_orig:
            self.lbl_subtitle_overlay.setText(f"\u200F⚡ {clean_trans}\u200F\n({clean_orig})")
        else:
            self.lbl_subtitle_overlay.setText(f"\u200F⚡ {clean_trans}\u200F")

    def set_subtitles_for_overlay(self, events):
        """Cache valid playable subtitle lines for live video overlay synchronization."""
        self.subtitles = []
        for ev in events:
            if getattr(ev, "is_comment", False):
                continue
            has_text = hasattr(ev, "has_translatable_text") and ev.has_translatable_text()
            is_pure_fx = hasattr(ev, "is_visual_effect") and ev.is_visual_effect() and not has_text
            if is_pure_fx:
                continue
            s_ms = parse_timecode_ms(getattr(ev, "start_time", ""))
            e_ms = parse_timecode_ms(getattr(ev, "end_time", ""))
            if s_ms is None or e_ms is None or e_ms <= s_ms:
                continue
            txt = ev.translated_text or ev.original_text or ""
            clean_txt = re.sub(r"\{.*?\}", "", txt).replace("\\N", " ").replace("\\n", " ").replace("\n", " ")
            clean_txt = re.sub(r"\s+", " ", clean_txt).strip()
            if clean_txt:
                self.subtitles.append((s_ms, e_ms, clean_txt))

    def get_active_subtitles_at(self, pos_ms: int) -> List[str]:
        """Returns all unique active subtitle lines overlapping half-open interval [s_ms, e_ms)."""
        active_lines: List[str] = []
        for s_ms, e_ms, txt in self.subtitles:
            if s_ms <= pos_ms < e_ms:
                if txt and txt not in active_lines:
                    active_lines.append(txt)
        return active_lines

    def _on_position_changed(self, pos_ms: int):
        if not self.player:
            return
        if not self._is_seeking:
            dur = self.player.duration()
            if dur > 0:
                self.slider.setValue(int((pos_ms / dur) * 1000))
            self.lbl_time.setText(f"{self._format_ms(pos_ms)} / {self._format_ms(dur)}")

        # Update overlay subtitle line(s) using half-open [start, end)
        active_lines = self.get_active_subtitles_at(pos_ms)
        if active_lines:
            display = "\n".join(active_lines[:3])
            self.lbl_subtitle_overlay.setText(f"\u200F{display}\u200F")
        else:
            self.lbl_subtitle_overlay.setText("...")

        self.position_changed_signal.emit(pos_ms)

    def _on_duration_changed(self, dur_ms: int):
        if self.player:
            self.lbl_time.setText(f"{self._format_ms(self.player.position())} / {self._format_ms(dur_ms)}")

    def _on_slider_pressed(self):
        self._is_seeking = True

    def _on_slider_released(self):
        self._is_seeking = False
        if self.player:
            dur = self.player.duration()
            if dur > 0:
                target_ms = int((self.slider.value() / 1000.0) * dur)
                self.player.setPosition(target_ms)

    def _on_slider_moved(self, val: int):
        if self.player:
            dur = self.player.duration()
            if dur > 0:
                pos_ms = int((val / 1000.0) * dur)
                self.lbl_time.setText(f"{self._format_ms(pos_ms)} / {self._format_ms(dur)}")

    def _on_volume_changed(self, val: int):
        if self.audio_output:
            self.audio_output.setVolume(val / 100.0)

    def _parse_time_to_ms(self, time_str: str) -> int:
        return parse_timecode_ms_safe(time_str, default=0)

    def _format_ms(self, ms: int) -> str:
        total_s = max(0, ms // 1000)
        m = (total_s % 3600) // 60
        s = total_s % 60
        return f"{m:02d}:{s:02d}"
