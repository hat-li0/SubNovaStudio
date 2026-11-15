import re
from typing import List, Dict, Any, Optional, Tuple
from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex
from PySide6.QtGui import QColor
from app.models.subtitle import SubtitleEvent
from app.subtitle.timecode import (
    parse_timecode_ms,
    parse_timecode_ms_safe,
    format_timecode,
    normalize_timecode,
)

class SubtitleTableModel(QAbstractTableModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.headers = ["#", "Start", "End", "Speaker", "Original Subtitle", "Translation", "Status"]
        self.events: List[SubtitleEvent] = []
        self.statuses: Dict[int, str] = {}  # Map row idx to status string
        self.on_data_changed_callback = None

    def rowCount(self, parent=QModelIndex()) -> int:
        return len(self.events)

    def columnCount(self, parent=QModelIndex()) -> int:
        return len(self.headers)

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return self.headers[section]
        return None

    def flags(self, index: QModelIndex) -> Qt.ItemFlags:
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags

        base_flags = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        col = index.column()
        # Direct in-place editing allowed for Start (1), End (2), Speaker (3), Original (4), Translation (5)
        if col in (1, 2, 3, 4, 5):
            return base_flags | Qt.ItemFlag.ItemIsEditable
        return base_flags

    def calculate_cps(self, event: SubtitleEvent) -> float:
        """Calculate characters per second (CPS) for reading speed metrics with micro-caching."""
        cached = getattr(event, '_cached_cps', None)
        if cached is not None:
            return cached
        try:
            start_ms = parse_timecode_ms(event.start_time)
            end_ms = parse_timecode_ms(event.end_time)
            if start_ms is None or end_ms is None:
                val = 0.0
            else:
                dur_sec = (end_ms - start_ms) / 1000.0
                if dur_sec <= 0.1:
                    val = 0.0
                else:
                    raw_text = event.translated_text or event.original_text or ""
                    # Strip ASS tags, comments, and line breaks for true reading length
                    clean_text = re.sub(r"\{.*?\}", "", raw_text).replace("\\N", " ").strip()
                    val = len(clean_text) / dur_sec
        except Exception:
            val = 0.0
        setattr(event, '_cached_cps', val)
        return val

    def _parse_time_to_ms(self, time_str: str) -> int:
        return parse_timecode_ms_safe(time_str, default=0)

    def _ms_to_time_str(self, ms: int, template_str: str = "0:00:00.00", fmt: Optional[str] = None) -> str:
        return format_timecode(ms, template_str=template_str, fmt=fmt)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None

        row = index.row()
        col = index.column()
        event = self.events[row]

        if role == Qt.ItemDataRole.DisplayRole or role == Qt.ItemDataRole.EditRole:
            if col == 0:
                return str(event.id)
            elif col == 1:
                return event.start_time
            elif col == 2:
                return event.end_time
            elif col == 3:
                return event.speaker
            elif col == 4:
                return event.original_text
            elif col == 5:
                trans = event.translated_text if event.translated_text else ""
                # Directional isolation marker for Arabic RTL text
                return f"\u200F{trans}\u200F" if trans else ""
            elif col == 6:
                st = self.statuses.get(row)
                if st:
                    return st
                if event.translated_text:
                    return "Done"
                if hasattr(event, "has_translatable_text") and event.has_translatable_text():
                    return "Pending"
                if hasattr(event, "is_visual_effect") and event.is_visual_effect():
                    return "مؤثرات (FX)"
                return "Pending"

        elif role == Qt.ItemDataRole.TextAlignmentRole:
            if col in [0, 1, 2, 6]:
                return Qt.AlignmentFlag.AlignCenter
            elif col == 5:
                return Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            return Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter

        elif role == Qt.ItemDataRole.BackgroundRole:
            # Color code reading speed CPS warnings
            if col in (4, 5):
                cps = self.calculate_cps(event)
                if cps > 22.0:
                    return QColor(185, 28, 28, 80) # Red: too fast to read
                elif cps > 18.0:
                    return QColor(217, 119, 6, 60) # Amber: slightly fast

        elif role == Qt.ItemDataRole.ToolTipRole:
            if col in (1, 2, 4, 5):
                cps = self.calculate_cps(event)
                if cps > 22.0:
                    return f"⚠️ تنبيه: سرعة القراءة مرتفعة جداً ({cps:.1f} حرف/ثانية)! يُنصح بألا تتجاوز 18-20 حرف/ث."
                elif cps > 18.0:
                    return f"⚡ سرعة القراءة سريعة ({cps:.1f} حرف/ثانية)."
                elif cps > 0:
                    return f"⏱️ سرعة القراءة ممتازة ومريحة ({cps:.1f} حرف/ثانية)."

        return None

    def setData(self, index: QModelIndex, value: Any, role: int = Qt.ItemDataRole.EditRole) -> bool:
        if not index.isValid() or role not in (Qt.ItemDataRole.EditRole, Qt.ItemDataRole.DisplayRole):
            return False

        row = index.row()
        col = index.column()
        event = self.events[row]
        str_val = str(value).strip().replace("\u200F", "").replace("\u2067", "").replace("\u2069", "")

        old_val = ""
        if col == 1:
            norm = normalize_timecode(
                str_val,
                template_str=event.start_time or str_val,
                fmt=getattr(event.format_type, "value", None),
            )
            if norm is None:
                return False  # Reject unparseable / out-of-range timecode strictly
            old_val = event.start_time
            str_val = norm
            event.start_time = str_val
        elif col == 2:
            norm = normalize_timecode(
                str_val,
                template_str=event.end_time or str_val,
                fmt=getattr(event.format_type, "value", None),
            )
            if norm is None:
                return False  # Reject unparseable / out-of-range timecode strictly
            old_val = event.end_time
            str_val = norm
            event.end_time = str_val
        elif col == 3:
            old_val = event.speaker
            event.speaker = str_val
        elif col == 4:
            old_val = event.original_text
            event.original_text = str_val
        elif col == 5:
            old_val = event.translated_text or ""
            event.translated_text = str_val
            self.statuses[row] = "Edited"
        else:
            return False

        setattr(event, '_cached_cps', None)
        self.dataChanged.emit(index, index, [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole, Qt.ItemDataRole.BackgroundRole])
        if self.on_data_changed_callback:
            self.on_data_changed_callback(row, col, old_val, str_val)
        return True

    def set_cell_value_direct(self, row: int, col: int, value: str):
        """Directly update a cell value and emit dataChanged (used by Undo/Redo and Inline Editor)."""
        if not (0 <= row < len(self.events)):
            return
        event = self.events[row]
        str_val = str(value).strip().replace("\u200F", "").replace("\u2067", "").replace("\u2069", "")
        if col == 1:
            if parse_timecode_ms(str_val) is None:
                return
            event.start_time = str_val
        elif col == 2:
            if parse_timecode_ms(str_val) is None:
                return
            event.end_time = str_val
        elif col == 3:
            event.speaker = str_val
        elif col == 4:
            event.original_text = str_val
        elif col == 5:
            event.translated_text = str_val
            self.statuses[row] = "Edited"
        setattr(event, '_cached_cps', None)
        idx = self.index(row, col)
        self.dataChanged.emit(idx, idx, [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole, Qt.ItemDataRole.BackgroundRole])

    def apply_row_state(self, row: int, state: Tuple[Any, ...]):
        """Atomically restores or applies full row state (start, end, speaker, orig, trans[, status])."""
        if not (0 <= row < len(self.events)) or len(state) < 5:
            return
        start, end, spk, orig, trans = state[:5]
        status = state[5] if len(state) >= 6 else None
        event = self.events[row]
        fmt = getattr(event.format_type, "value", None)

        if start and parse_timecode_ms(str(start)) is not None:
            norm_s = normalize_timecode(str(start), template_str=event.start_time or str(start), fmt=fmt)
            if norm_s is not None:
                event.start_time = norm_s
        if end and parse_timecode_ms(str(end)) is not None:
            norm_e = normalize_timecode(str(end), template_str=event.end_time or str(end), fmt=fmt)
            if norm_e is not None:
                event.end_time = norm_e

        event.speaker = str(spk or "").strip()
        event.original_text = str(orig or "").strip()
        event.translated_text = str(trans or "").strip()
        setattr(event, '_cached_cps', None)

        if status:
            self.statuses[row] = status
        elif event.translated_text:
            self.statuses[row] = "Done"
        else:
            self.statuses[row] = "Pending"

        self.dataChanged.emit(
            self.index(row, 1),
            self.index(row, 6),
            [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole, Qt.ItemDataRole.BackgroundRole],
        )

    def restore_events_snapshot(self, events_snapshot: List[SubtitleEvent], statuses_snapshot: Dict[int, str]):
        """Restores full events list in place (preserving document.events identity) and statuses on Undo/Redo."""
        from copy import deepcopy
        self.beginResetModel()
        self.events[:] = [deepcopy(e) for e in events_snapshot]
        self.statuses = dict(statuses_snapshot)
        self.endResetModel()

    def shift_timings(self, offset_ms: int, row_indices: Optional[List[int]] = None):
        """
        Shift start and end timings of all or selected subtitles by offset_ms.
        Preserves display duration when clamping start_time at 00:00:00.
        """
        if not self.events:
            return
        target_rows = row_indices if row_indices is not None and len(row_indices) > 0 else range(len(self.events))
        valid_rows = [r for r in target_rows if 0 <= r < len(self.events)]
        if not valid_rows:
            return
        for r in valid_rows:
            event = self.events[r]
            orig_s = parse_timecode_ms(event.start_time)
            orig_e = parse_timecode_ms(event.end_time)
            if orig_s is None or orig_e is None:
                continue
            orig_dur = max(0, orig_e - orig_s)
            raw_s = orig_s + offset_ms
            if raw_s < 0:
                s_ms = 0
                # Preserve original display duration rather than truncating against 00:00:00
                e_ms = orig_dur
            else:
                s_ms = raw_s
                e_ms = max(s_ms, orig_e + offset_ms)

            fmt = getattr(event.format_type, "value", None)
            event.start_time = format_timecode(s_ms, template_str=event.start_time, fmt=fmt)
            event.end_time = format_timecode(e_ms, template_str=event.end_time, fmt=fmt)
            setattr(event, '_cached_cps', None)

        first_row = min(valid_rows)
        last_row = max(valid_rows)
        self.dataChanged.emit(self.index(first_row, 1), self.index(last_row, 2), [Qt.ItemDataRole.DisplayRole])

    def restore_timings_snapshot(self, snapshot: List[Tuple[int, str, str]]):
        """Restores exact (row_idx, start_time, end_time) strings on Undo."""
        if not snapshot or not self.events:
            return
        valid_rows = []
        for r, s_str, e_str in snapshot:
            if 0 <= r < len(self.events):
                ev = self.events[r]
                ev.start_time = s_str
                ev.end_time = e_str
                setattr(ev, '_cached_cps', None)
                valid_rows.append(r)
        if valid_rows:
            self.dataChanged.emit(self.index(min(valid_rows), 1), self.index(max(valid_rows), 2), [Qt.ItemDataRole.DisplayRole])

    def merge_lines(self, row_indices: List[int]) -> bool:
        """Merge multiple selected contiguous/adjacent lines into the first line."""
        if not row_indices or len(row_indices) < 2:
            return False
        sorted_rows = sorted(row_indices)
        first_idx = sorted_rows[0]
        if first_idx >= len(self.events):
            return False

        first_event = self.events[first_idx]
        last_event = self.events[sorted_rows[-1]]
        
        # Merge timing: start of first to end of last
        first_event.end_time = last_event.end_time

        # Merge texts using format-appropriate linebreak
        fmt_val = getattr(first_event.format_type, "value", "ass")
        joiner = " \\N " if fmt_val == "ass" else "\n"
        merged_orig = []
        merged_trans = []
        for r in sorted_rows:
            ev = self.events[r]
            merged_orig.append(ev.original_text or "")
            if ev.translated_text:
                merged_trans.append(ev.translated_text)

        first_event.original_text = joiner.join(merged_orig)
        if merged_trans:
            first_event.translated_text = joiner.join(merged_trans)
        setattr(first_event, '_cached_cps', None)
        self.statuses[first_idx] = "Edited"

        # Remove the merged rows (from bottom to top)
        self.beginResetModel()
        for r in sorted(sorted_rows[1:], reverse=True):
            if 0 <= r < len(self.events):
                del self.events[r]
        # Re-index
        for idx, ev in enumerate(self.events):
            ev.id = idx + 1
        self.statuses = {
            i: ("مؤثرات (FX)" if (hasattr(e, "is_visual_effect") and e.is_visual_effect() and not (hasattr(e, "has_translatable_text") and e.has_translatable_text())) else self.statuses.get(i, "Pending"))
            for i, e in enumerate(self.events)
        }
        self.endResetModel()
        return True

    @staticmethod
    def _split_text_halves(text: str) -> Tuple[str, str]:
        if not text:
            return "", ""
        if "\\N" in text:
            parts = text.split("\\N", 1)
            return parts[0].strip(), parts[1].strip()
        if "\n" in text:
            parts = text.split("\n", 1)
            return parts[0].strip(), parts[1].strip()
        words = text.split()
        if len(words) <= 1:
            return text.strip(), ""
        half = max(1, len(words) // 2)
        return " ".join(words[:half]), " ".join(words[half:])

    def split_line(self, row_idx: int, split_at_ms: Optional[int] = None) -> bool:
        """
        Split a subtitle line into two synchronized parts.
        Uses exact `split_at_ms` (e.g. active video playback time) when inside the line,
        otherwise distributes duration proportionally by text length rather than a blind 50/50 split.
        """
        if not (0 <= row_idx < len(self.events)):
            return False

        ev = self.events[row_idx]
        s_ms = parse_timecode_ms(ev.start_time)
        e_ms = parse_timecode_ms(ev.end_time)
        if s_ms is None or e_ms is None:
            return False
        dur = e_ms - s_ms
        if dur <= 400:
            return False  # Too short to split safely

        # Split original and translated texts first so character ratio can guide timing
        orig1, orig2 = self._split_text_halves(ev.original_text or "")
        trans1, trans2 = self._split_text_halves(ev.translated_text or "")

        if split_at_ms is not None and (s_ms + 200) <= split_at_ms <= (e_ms - 200):
            mid_ms = int(split_at_ms)
        else:
            ref1 = re.sub(r"\{.*?\}", "", trans1 or orig1).strip()
            ref2 = re.sub(r"\{.*?\}", "", trans2 or orig2).strip()
            total_len = len(ref1) + len(ref2)
            ratio = (len(ref1) / total_len) if total_len > 0 else 0.5
            ratio = max(0.20, min(0.80, ratio))
            mid_ms = s_ms + int(round(dur * ratio))

        from copy import deepcopy
        ev2 = deepcopy(ev)
        fmt = getattr(ev.format_type, "value", None)

        # Adjust first half
        ev.end_time = format_timecode(mid_ms, template_str=ev.end_time, fmt=fmt)
        ev.original_text = orig1
        if ev.translated_text:
            ev.translated_text = trans1
        setattr(ev, '_cached_cps', None)

        # Adjust second half
        ev2.start_time = format_timecode(mid_ms, template_str=ev2.start_time, fmt=fmt)
        ev2.original_text = orig2
        if ev2.translated_text:
            ev2.translated_text = trans2
        setattr(ev2, '_cached_cps', None)

        self.beginResetModel()
        self.events.insert(row_idx + 1, ev2)
        for idx, e in enumerate(self.events):
            e.id = idx + 1
        self.statuses = {
            i: ("مؤثرات (FX)" if (hasattr(e, "is_visual_effect") and e.is_visual_effect() and not (hasattr(e, "has_translatable_text") and e.has_translatable_text())) else self.statuses.get(i, "Pending"))
            for i, e in enumerate(self.events)
        }
        self.endResetModel()
        return True

    def update_event(self, row_idx: int, translated: str, status: str):
        if 0 <= row_idx < len(self.events):
            self.events[row_idx].translated_text = translated
            setattr(self.events[row_idx], '_cached_cps', None)
            self.statuses[row_idx] = status
            idx1 = self.index(row_idx, 5)
            idx2 = self.index(row_idx, 6)
            self.dataChanged.emit(idx1, idx2, [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.BackgroundRole])

    def _emit_contiguous_rows_changed(self, rows: List[int], first_col: int = 5, last_col: int = 6):
        """Groups affected row indices into contiguous spans so dataChanged stays O(batches) without layoutChanged."""
        if not rows:
            return
        sorted_rows = sorted(set(rows))
        roles = [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole, Qt.ItemDataRole.BackgroundRole]
        span_start = sorted_rows[0]
        span_end = sorted_rows[0]
        for r in sorted_rows[1:]:
            if r == span_end + 1:
                span_end = r
            else:
                self.dataChanged.emit(self.index(span_start, first_col), self.index(span_end, last_col), roles)
                span_start = r
                span_end = r
        self.dataChanged.emit(self.index(span_start, first_col), self.index(span_end, last_col), roles)

    def set_batch_status(self, event_ids: List[int], status: str):
        """Update status and live translation cells for a batch using targeted range dataChanged."""
        id_to_row = {e.id: idx for idx, e in enumerate(self.events)}
        dirty_rows: List[int] = []
        for eid in event_ids:
            if eid in id_to_row:
                row = id_to_row[eid]
                self.statuses[row] = status
                if status == "Done":
                    setattr(self.events[row], '_cached_cps', None)
                dirty_rows.append(row)
        self._emit_contiguous_rows_changed(dirty_rows, 5, 6)

    def update_events_batch(self, translations: Dict[int, str], status: str = "Done"):
        """Update translated text and status for multiple events using contiguous dataChanged spans."""
        id_to_row = {e.id: idx for idx, e in enumerate(self.events)}
        dirty_rows: List[int] = []
        for eid, trans in translations.items():
            if eid in id_to_row:
                row = id_to_row[eid]
                self.events[row].translated_text = trans
                setattr(self.events[row], '_cached_cps', None)
                self.statuses[row] = status
                dirty_rows.append(row)
        self._emit_contiguous_rows_changed(dirty_rows, 5, 6)

    def set_events(self, events: List[SubtitleEvent]):
        self.beginResetModel()
        self.events = events
        self.statuses = {
            i: ("مؤثرات (FX)" if (hasattr(e, "is_visual_effect") and e.is_visual_effect() and not (hasattr(e, "has_translatable_text") and e.has_translatable_text())) else ("Done" if e.translated_text else "Pending"))
            for i, e in enumerate(events)
        }
        self.endResetModel()
