from typing import Optional, Iterable, List, Any
from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget, QTableWidgetItem, QCheckBox
from PySide6.QtCore import Qt
from app.models.glossary import GlossaryEntry


class GlossaryEditorDialog(QDialog):
    def __init__(self, parent=None, initial_entries: Optional[Iterable[Any]] = None, anime_id: Optional[int] = None):
        super().__init__(parent)
        self.anime_id = anime_id
        self.setWindowTitle("Glossary Editor")
        self.setMinimumSize(540, 420)
        
        self.layout = QVBoxLayout(self)
        
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Source Term", "Target Term", "Exact Match", "Case Sensitive"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.layout.addWidget(self.table)
        
        if initial_entries:
            for entry in initial_entries:
                if isinstance(entry, GlossaryEntry):
                    self.add_row_with_data(
                        entry.source_term,
                        entry.target_term,
                        is_exact=entry.is_exact_match,
                        is_case=entry.is_case_sensitive,
                        entry=entry,
                    )
                elif isinstance(entry, dict):
                    src = entry.get("source_term", "")
                    tgt = entry.get("target_term", "")
                    if src or tgt:
                        self.add_row_with_data(
                            src,
                            tgt,
                            is_exact=bool(entry.get("is_exact_match", True)),
                            is_case=bool(entry.get("is_case_sensitive", False)),
                            entry=GlossaryEntry(
                                id=entry.get("id"),
                                anime_id=entry.get("anime_id", self.anime_id),
                                source_term=src,
                                target_term=tgt,
                                is_exact_match=bool(entry.get("is_exact_match", True)),
                                is_case_sensitive=bool(entry.get("is_case_sensitive", False)),
                                notes=entry.get("notes", "") or "",
                            ),
                        )
                elif isinstance(entry, str) and " -> " in entry:
                    src, tgt = entry.split(" -> ", 1)
                    self.add_row_with_data(src.strip(), tgt.strip())
        
        btn_layout = QHBoxLayout()
        self.btn_add = QPushButton("Add Term")
        self.btn_del = QPushButton("Delete Term")
        self.btn_save = QPushButton("Save")
        
        self.btn_add.clicked.connect(self.add_row)
        self.btn_del.clicked.connect(self.del_row)
        self.btn_save.clicked.connect(self.accept)
        
        btn_layout.addWidget(self.btn_add)
        btn_layout.addWidget(self.btn_del)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_save)
        
        self.layout.addLayout(btn_layout)
        
    def add_row(self):
        self.add_row_with_data("", "")

    def add_row_with_data(
        self,
        src: str,
        tgt: str,
        is_exact: bool = True,
        is_case: bool = False,
        entry: Optional[GlossaryEntry] = None,
    ):
        row = self.table.rowCount()
        self.table.insertRow(row)

        src_item = QTableWidgetItem(str(src or ""))
        src_item.setData(
            Qt.UserRole,
            {
                "id": getattr(entry, "id", None) if entry else None,
                "anime_id": getattr(entry, "anime_id", self.anime_id) if entry else self.anime_id,
                "notes": getattr(entry, "notes", "") if entry else "",
            },
        )
        self.table.setItem(row, 0, src_item)
        self.table.setItem(row, 1, QTableWidgetItem(str(tgt or "")))
        
        cb_exact = QCheckBox()
        cb_exact.setChecked(bool(is_exact))
        self.table.setCellWidget(row, 2, cb_exact)
        
        cb_case = QCheckBox()
        cb_case.setChecked(bool(is_case))
        self.table.setCellWidget(row, 3, cb_case)
        
    def del_row(self):
        row = self.table.currentRow()
        if row >= 0:
            self.table.removeRow(row)

    def get_glossary_entries(self) -> List[GlossaryEntry]:
        entries: List[GlossaryEntry] = []
        for i in range(self.table.rowCount()):
            src_item = self.table.item(i, 0)
            tgt_item = self.table.item(i, 1)
            src = src_item.text().strip() if src_item else ""
            tgt = tgt_item.text().strip() if tgt_item else ""
            exact_w = self.table.cellWidget(i, 2)
            case_w = self.table.cellWidget(i, 3)
            meta = src_item.data(Qt.UserRole) if src_item else {}
            if not isinstance(meta, dict):
                meta = {}
            if src and tgt:
                entries.append(
                    GlossaryEntry(
                        id=meta.get("id"),
                        anime_id=meta.get("anime_id", self.anime_id),
                        source_term=src,
                        target_term=tgt,
                        is_exact_match=exact_w.isChecked() if isinstance(exact_w, QCheckBox) else True,
                        is_case_sensitive=case_w.isChecked() if isinstance(case_w, QCheckBox) else False,
                        notes=meta.get("notes", "") or "",
                    )
                )
        return entries
