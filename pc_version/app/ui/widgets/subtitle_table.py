from PySide6.QtWidgets import QTableView, QStyledItemDelegate, QStyleOptionViewItem, QHeaderView
from PySide6.QtCore import Qt, QRect
from PySide6.QtGui import QPainter, QColor, QPen

class StatusBadgeDelegate(QStyledItemDelegate):
    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index):
        if index.column() == 6:
            status = str(index.data(Qt.ItemDataRole.DisplayRole) or "Pending")
            painter.save()
            
            # Select colors based on status
            bg_color = QColor(63, 63, 70)
            text_color = QColor(228, 228, 231)
            
            if status in ("Translating", "Improving"):
                bg_color = QColor(2, 132, 199)
                text_color = QColor(255, 255, 255)
            elif status == "Done":
                bg_color = QColor(22, 163, 74)
                text_color = QColor(255, 255, 255)
            elif status in ("مؤثرات (FX)", "FX / مؤثرات", "FX"):
                bg_color = QColor(99, 102, 241) # Elegant Indigo/Purple for Visual Effects
                text_color = QColor(255, 255, 255)
            elif status == "Error":
                bg_color = QColor(220, 38, 38)
                text_color = QColor(255, 255, 255)
            elif status == "Warning":
                bg_color = QColor(217, 119, 6)
                text_color = QColor(0, 0, 0)
                
            rect = option.rect
            margin_y = 5
            margin_x = 6
            badge_rect = QRect(rect.left() + margin_x, rect.top() + margin_y, rect.width() - 2*margin_x, rect.height() - 2*margin_y)
            
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(bg_color)
            painter.drawRoundedRect(badge_rect, 5, 5)
            
            painter.setPen(QPen(text_color))
            painter.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter, status)
            
            painter.restore()
        else:
            super().paint(painter, option, index)

class SubtitleTableView(QTableView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.setEditTriggers(
            QTableView.EditTrigger.DoubleClicked |
            QTableView.EditTrigger.EditKeyPressed |
            QTableView.EditTrigger.AnyKeyPressed
        )
        self.verticalHeader().hide()
        self.verticalHeader().setDefaultSectionSize(32)
        
        # Apply delegate for status badge
        self.setItemDelegateForColumn(6, StatusBadgeDelegate(self))
        
    def setModel(self, model):
        super().setModel(model)
        header = self.horizontalHeader()
        header.setStretchLastSection(False)
        
        # Fixed size metadata columns
        self.setColumnWidth(0, 48)  # ID
        self.setColumnWidth(1, 85)  # Start
        self.setColumnWidth(2, 85)  # End
        self.setColumnWidth(3, 95)  # Speaker
        self.setColumnWidth(6, 95)  # Status
        
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)  # Original text
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)  # Translated Arabic
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Fixed)
