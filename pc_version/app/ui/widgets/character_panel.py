from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QFrame, QLineEdit
)
from PySide6.QtCore import Qt

class CharacterPanel(QWidget):
    """
    Clean, spacious panel for managing Characters, Genders,
    Pronouns, and Arabic Names with live filtering and auto-enrichment.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(6, 6, 6, 6)
        self.layout.setSpacing(8)
        
        # Header Media Title Box
        media_box = QFrame()
        media_box.setStyleSheet("background-color: #18181b; border: 1px solid #27272a; border-radius: 6px; padding: 4px;")
        m_layout = QVBoxLayout(media_box)
        m_layout.setContentsMargins(8, 6, 8, 6)
        
        self.lbl_anime_title = QLabel("العمل: لم يتم الكشف بعد (No Media Detected)")
        self.lbl_anime_title.setStyleSheet("font-weight: 600; color: #fbbf24; font-size: 9pt;")
        self.lbl_anime_title.setWordWrap(True)
        self.lbl_media_title = self.lbl_anime_title  # alias
        m_layout.addWidget(self.lbl_anime_title)
        self.layout.addWidget(media_box)
        
        # Search Media Button (Full Width)
        self.btn_search = QPushButton("🔍 جلب بيانات العمل والشخصيات تلقائياً")
        self.btn_search.setStyleSheet("background-color: #0284c7; color: white; font-weight: 600; padding: 6px;")
        self.btn_search.setToolTip("البحث في قواعد بيانات الأنمي والمسلسلات والأفلام لجلب الشخصيات والأجناس تلقائياً")
        self.layout.addWidget(self.btn_search)

        # Quick Search / Filter Bar
        self.le_filter = QLineEdit()
        self.le_filter.setPlaceholderText("🔎 تصفية الشخصيات في الجدول...")
        self.le_filter.textChanged.connect(self._filter_table)
        self.layout.addWidget(self.le_filter)

        # Character Table (3 Clean Columns)
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["الاسم الأصلي", "الاسم بالعربية", "الجنس"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(2, 85)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.layout.addWidget(self.table)
        
        # Action Buttons Row
        ctrl_layout = QHBoxLayout()
        ctrl_layout.setSpacing(6)
        
        self.btn_add = QPushButton("➕ إضافة")
        self.btn_edit = QPushButton("✏️ تعديل")
        self.btn_delete = QPushButton("🗑️ حذف")
        self.btn_delete.setStyleSheet("background-color: #27272a; color: #f87171;")

        ctrl_layout.addWidget(self.btn_add)
        ctrl_layout.addWidget(self.btn_edit)
        ctrl_layout.addWidget(self.btn_delete)
        self.layout.addLayout(ctrl_layout)
        
        self.btn_delete.clicked.connect(self._delete_selected)

    def _filter_table(self, query: str):
        query = (query or "").strip().lower()
        for r in range(self.table.rowCount()):
            can = (self.table.item(r, 0).text() if self.table.item(r, 0) else "").lower()
            ara = (self.table.item(r, 1).text() if self.table.item(r, 1) else "").lower()
            gen = (self.table.item(r, 2).text() if self.table.item(r, 2) else "").lower()
            match = not query or (query in can or query in ara or query in gen)
            self.table.setRowHidden(r, not match)

    def _delete_selected(self):
        row = self.table.currentRow()
        if row >= 0:
            self.table.removeRow(row)
        
    def add_character(
        self,
        canonical,
        arabic="",
        gender="UNKNOWN",
        conf=1.0,
        source="",
        profile=None,
        japanese="",
        aliases=None,
        style="",
        notes="",
    ):
        from app.models.character import CharacterProfile, GenderInfo, GenderEnum

        row = self.table.rowCount()
        self.table.insertRow(row)

        can_str = str(canonical or "")
        ar_str = str(arabic or "")
        gen_str = str(gender or "UNKNOWN")

        item_can = QTableWidgetItem(can_str)
        item_ar = QTableWidgetItem(ar_str)
        item_gen = QTableWidgetItem(gen_str)
        item_gen.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

        try:
            conf_f = float(conf if conf is not None else 1.0)
        except (TypeError, ValueError):
            conf_f = 1.0

        if profile is not None and isinstance(profile, CharacterProfile):
            stored_profile = profile.model_copy(deep=True)
            if can_str:
                stored_profile.canonical_name = can_str
            if ar_str:
                stored_profile.arabic_name = ar_str
            if japanese:
                stored_profile.native_name = str(japanese)
            if aliases:
                stored_profile.aliases = list(aliases)
            if style:
                stored_profile.speech_style = str(style)
            if notes:
                stored_profile.translation_notes = str(notes)
            if gen_str:
                stored_profile.gender = GenderEnum(gen_str)
        else:
            stored_profile = CharacterProfile(
                canonical_name=can_str or "Unknown",
                arabic_name=ar_str,
                native_name=str(japanese or ""),
                aliases=list(aliases) if aliases else [],
                speech_style=str(style or ""),
                translation_notes=str(notes or ""),
                gender_info=GenderInfo(
                    gender=GenderEnum(gen_str),
                    confidence=conf_f,
                    source=str(source or ""),
                ),
            )

        # Store full profile + legacy metadata keys in item user data
        item_can.setData(
            Qt.UserRole,
            {
                "conf": str(conf if conf is not None else "1.0"),
                "source": str(source or ""),
                "profile": stored_profile,
            },
        )

        self.table.setItem(row, 0, item_can)
        self.table.setItem(row, 1, item_ar)
        self.table.setItem(row, 2, item_gen)

    def get_selected_character(self):
        row = self.table.currentRow()
        if row < 0 and self.table.rowCount() > 0:
            row = 0
        if row >= 0:
            item_can = self.table.item(row, 0)
            meta = item_can.data(Qt.UserRole) if item_can else {}
            prof = meta.get("profile") if isinstance(meta, dict) else None
            return {
                "row": row,
                "canonical": item_can.text() if item_can else "",
                "arabic": self.table.item(row, 1).text() if self.table.item(row, 1) else "",
                "gender": self.table.item(row, 2).text() if self.table.item(row, 2) else "",
                "conf": meta.get("conf", "1.0") if isinstance(meta, dict) else "1.0",
                "source": meta.get("source", "User") if isinstance(meta, dict) else "User",
                "japanese": getattr(prof, "native_name", "") if prof else "",
                "aliases": list(getattr(prof, "aliases", []) or []) if prof else [],
                "style": getattr(prof, "speech_style", "") if prof else "",
                "notes": getattr(prof, "translation_notes", "") if prof else "",
                "profile": prof,
            }
        return None

    def update_character_row(
        self,
        row: int,
        canonical: str,
        arabic: str,
        gender: str,
        conf: str = "1.0",
        source: str = "User Override",
        japanese: str = None,
        aliases: list = None,
        style: str = None,
        notes: str = None,
        profile=None,
    ):
        from app.models.character import CharacterProfile, GenderInfo, GenderEnum

        if 0 <= row < self.table.rowCount():
            old_item = self.table.item(row, 0)
            old_meta = old_item.data(Qt.UserRole) if old_item else {}
            base_prof = profile or (old_meta.get("profile") if isinstance(old_meta, dict) else None)

            try:
                conf_f = float(conf)
            except (TypeError, ValueError):
                conf_f = 1.0

            if base_prof is not None and isinstance(base_prof, CharacterProfile):
                stored_profile = base_prof.model_copy(deep=True)
                stored_profile.canonical_name = canonical
                stored_profile.arabic_name = arabic
                stored_profile.gender_info = GenderInfo(
                    gender=GenderEnum(str(gender or "UNKNOWN")),
                    confidence=conf_f,
                    source=str(source),
                )
            else:
                stored_profile = CharacterProfile(
                    canonical_name=canonical or "Unknown",
                    arabic_name=arabic,
                    gender_info=GenderInfo(
                        gender=GenderEnum(str(gender or "UNKNOWN")),
                        confidence=conf_f,
                        source=str(source),
                    ),
                )

            if japanese is not None:
                stored_profile.native_name = str(japanese)
            if aliases is not None:
                stored_profile.aliases = [str(a).strip() for a in aliases if str(a).strip()]
            if style is not None:
                stored_profile.speech_style = str(style)
            if notes is not None:
                stored_profile.translation_notes = str(notes)
            stored_profile.is_user_override = True

            item_can = QTableWidgetItem(canonical)
            item_can.setData(
                Qt.UserRole,
                {"conf": str(conf), "source": str(source), "profile": stored_profile},
            )
            item_ar = QTableWidgetItem(arabic)
            item_gen = QTableWidgetItem(gender)
            item_gen.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            self.table.setItem(row, 0, item_can)
            self.table.setItem(row, 1, item_ar)
            self.table.setItem(row, 2, item_gen)

    def get_characters(self):
        from app.models.character import CharacterProfile, GenderInfo, GenderEnum
        chars = []
        for row in range(self.table.rowCount()):
            item_can = self.table.item(row, 0)
            canonical = item_can.text() if item_can else ""
            arabic = self.table.item(row, 1).text() if self.table.item(row, 1) else ""
            gender_str = self.table.item(row, 2).text() if self.table.item(row, 2) else ""
            meta = item_can.data(Qt.UserRole) if item_can else {}

            conf_str = meta.get("conf", "1.0") if isinstance(meta, dict) else "1.0"
            src_str = meta.get("source", "Direct") if isinstance(meta, dict) else "Direct"
            stored_prof = meta.get("profile") if isinstance(meta, dict) else None

            gender_enum = GenderEnum(str(gender_str or "UNKNOWN"))
            try:
                conf = float(conf_str)
            except (TypeError, ValueError):
                conf = 1.0

            if stored_prof is not None and isinstance(stored_prof, CharacterProfile):
                prof = stored_prof.model_copy(deep=True)
                prof.canonical_name = canonical
                prof.arabic_name = arabic
                prof.gender_info = GenderInfo(gender=gender_enum, confidence=conf, source=src_str)
                chars.append(prof)
            else:
                chars.append(CharacterProfile(
                    canonical_name=canonical,
                    arabic_name=arabic,
                    gender_info=GenderInfo(gender=gender_enum, confidence=conf, source=src_str)
                ))
        return chars
