from PySide6.QtWidgets import QDialog, QFormLayout, QLineEdit, QComboBox, QTextEdit, QDialogButtonBox, QVBoxLayout
from app.ui.bus import EventBus
from typing import Optional, Dict, Any

class CharacterEditorDialog(QDialog):
    def __init__(self, parent=None, initial_data: Optional[Dict[str, Any]] = None):
        super().__init__(parent)
        self.setWindowTitle("Edit Character / تعديل بيانات الشخصية")
        self.setMinimumWidth(440)
        self.initial_data = initial_data or {}
        
        self.layout = QVBoxLayout(self)
        form_layout = QFormLayout()
        
        self.le_canonical = QLineEdit()
        self.le_japanese = QLineEdit()
        self.le_arabic = QLineEdit()
        
        self.cb_gender = QComboBox()
        self.cb_gender.addItems(["Unknown", "Male", "Female", "Non-Binary"])
        
        self.le_aliases = QLineEdit()
        self.le_style = QLineEdit()
        
        self.te_notes = QTextEdit()
        self.te_notes.setMaximumHeight(100)
        
        form_layout.addRow("Canonical Name (الاسم الإنجليزي/الشائع):", self.le_canonical)
        form_layout.addRow("Original / Native Name (الاسم الأصلي):", self.le_japanese)
        form_layout.addRow("Arabic Name (الاسم المعرب):", self.le_arabic)
        form_layout.addRow("Gender (الجنس):", self.cb_gender)
        form_layout.addRow("Aliases (الأسماء المستعارة/الممثل):", self.le_aliases)
        form_layout.addRow("Speech Style (أسلوب الكلام):", self.le_style)
        form_layout.addRow("Translation Notes (ملاحظات الترجمة):", self.te_notes)
        
        self.layout.addLayout(form_layout)
        
        self.button_box = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self.save)
        self.button_box.rejected.connect(self.reject)
        self.layout.addWidget(self.button_box)
        
        # Populate if initial data provided
        if self.initial_data:
            self.le_canonical.setText(self.initial_data.get("canonical", ""))
            self.le_japanese.setText(self.initial_data.get("japanese", ""))
            self.le_arabic.setText(self.initial_data.get("arabic", ""))
            
            gender_val = str(self.initial_data.get("gender", "")).capitalize()
            idx = self.cb_gender.findText(gender_val)
            if idx >= 0:
                self.cb_gender.setCurrentIndex(idx)
                
            aliases = self.initial_data.get("aliases", [])
            if isinstance(aliases, list):
                self.le_aliases.setText(", ".join(aliases))
            elif isinstance(aliases, str):
                self.le_aliases.setText(aliases)
                
            self.le_style.setText(self.initial_data.get("style", ""))
            self.te_notes.setPlainText(self.initial_data.get("notes", ""))
        
    def save(self):
        data = {
            "row": self.initial_data.get("row"),
            "canonical": self.le_canonical.text().strip(),
            "japanese": self.le_japanese.text().strip(),
            "arabic": self.le_arabic.text().strip(),
            "gender": self.cb_gender.currentText(),
            "aliases": [x.strip() for x in self.le_aliases.text().split(",") if x.strip()],
            "style": self.le_style.text().strip(),
            "notes": self.te_notes.toPlainText().strip()
        }
        EventBus.instance().character_updated.emit(data)
        self.accept()
