from copy import deepcopy
from typing import Any, Dict, List, Optional, Tuple
from PySide6.QtGui import QUndoCommand


class EditCellCommand(QUndoCommand):
    """Undoable command for editing a single subtitle cell (time, text, speaker)."""
    def __init__(self, model, row: int, col: int, old_val: str, new_val: str, description="تعديل سطر"):
        super().__init__(description)
        self.model = model
        self.row = row
        self.col = col
        self.old_val = old_val
        self.new_val = new_val

    def undo(self):
        self.model.set_cell_value_direct(self.row, self.col, self.old_val)

    def redo(self):
        self.model.set_cell_value_direct(self.row, self.col, self.new_val)


class EditRowCommand(QUndoCommand):
    """Undoable command capturing atomic edits made through the inline subtitle editor."""
    def __init__(
        self,
        model,
        row: int,
        old_state: Tuple[Any, ...],
        new_state: Tuple[Any, ...],
        description: str = "تعديل السطر من المحرر",
        skip_initial_redo: bool = True,
    ):
        super().__init__(description)
        self.model = model
        self.row = row
        self.old_state = tuple(old_state)
        self.new_state = tuple(new_state)
        self._skip_initial_redo = skip_initial_redo

    def undo(self):
        self.model.apply_row_state(self.row, self.old_state)

    def redo(self):
        if self._skip_initial_redo:
            self._skip_initial_redo = False
            return
        self.model.apply_row_state(self.row, self.new_state)


class SnapshotEventsCommand(QUndoCommand):
    """Undoable structural command (merge/split) restoring exact subtitle events snapshot."""
    def __init__(
        self,
        model,
        before_events: List[Any],
        before_statuses: Dict[int, str],
        after_events: List[Any],
        after_statuses: Dict[int, str],
        description: str = "تعديل هيكلي للأسطر",
        skip_initial_redo: bool = True,
    ):
        super().__init__(description)
        self.model = model
        self.before_events = [deepcopy(e) for e in before_events]
        self.before_statuses = dict(before_statuses)
        self.after_events = [deepcopy(e) for e in after_events]
        self.after_statuses = dict(after_statuses)
        self._skip_initial_redo = skip_initial_redo

    def undo(self):
        self.model.restore_events_snapshot(self.before_events, self.before_statuses)

    def redo(self):
        if self._skip_initial_redo:
            self._skip_initial_redo = False
            return
        self.model.restore_events_snapshot(self.after_events, self.after_statuses)


class ShiftTimingsCommand(QUndoCommand):
    """Undoable command for shifting subtitle timestamps with exact snapshot restore."""
    def __init__(self, model, offset_ms: int, row_indices: Optional[List[int]] = None, description="إزاحة التوقيت"):
        super().__init__(description)
        self.model = model
        self.offset_ms = offset_ms
        self.row_indices = list(row_indices) if row_indices is not None else None
        # Capture exact pre-shift timestamps so clamping at 0 never loses original state on Undo
        target_rows = self.row_indices if self.row_indices else range(len(model.events))
        self._snapshot = [
            (r, model.events[r].start_time, model.events[r].end_time)
            for r in target_rows
            if 0 <= r < len(model.events)
        ]

    def undo(self):
        if hasattr(self.model, "restore_timings_snapshot") and self._snapshot:
            self.model.restore_timings_snapshot(self._snapshot)
        else:
            self.model.shift_timings(-self.offset_ms, self.row_indices)

    def redo(self):
        self.model.shift_timings(self.offset_ms, self.row_indices)
