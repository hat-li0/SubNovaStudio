DARK_THEME_QSS = """
/* Modern Dark UI Palette */
QMainWindow, QDialog {
    background-color: #121214;
    color: #e4e4e7;
}

QWidget {
    background-color: #121214;
    color: #e4e4e7;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, "Noto Sans Arabic", sans-serif;
    font-size: 10pt;
}

/* Group Boxes / Panels */
QGroupBox {
    background-color: #18181b;
    border: 1px solid #27272a;
    border-radius: 8px;
    margin-top: 16px;
    padding: 14px 10px 10px 10px;
    font-weight: 600;
    color: #a1a1aa;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 8px;
    color: #38bdf8;
    background-color: #18181b;
}

/* Tabs */
QTabWidget::pane {
    border: 1px solid #27272a;
    background-color: #18181b;
    border-radius: 6px;
    top: -1px;
}

QTabBar::tab {
    background-color: #1c1c20;
    color: #a1a1aa;
    border: 1px solid #27272a;
    border-bottom: none;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    padding: 6px 12px;
    margin-right: 2px;
    font-weight: 600;
    font-size: 9pt;
}

QTabBar::tab:selected {
    background-color: #18181b;
    color: #38bdf8;
    border-bottom: 2px solid #38bdf8;
}

QTabBar::tab:hover:!selected {
    background-color: #27272a;
    color: #f4f4f5;
}

/* Buttons */
QPushButton {
    background-color: #27272a;
    border: 1px solid #3f3f46;
    border-radius: 6px;
    padding: 6px 12px;
    color: #f4f4f5;
    font-weight: 500;
    min-height: 20px;
}

QPushButton:hover {
    background-color: #3f3f46;
    border-color: #52525b;
}

QPushButton:pressed {
    background-color: #18181b;
}

QPushButton:disabled {
    background-color: #18181b;
    border-color: #27272a;
    color: #52525b;
}

/* Primary Action Buttons */
QPushButton#primary_action {
    background-color: #2563eb;
    border: 1px solid #3b82f6;
    color: #ffffff;
    font-weight: 600;
}

QPushButton#primary_action:hover {
    background-color: #1d4ed8;
}

QPushButton#primary_action:pressed {
    background-color: #1e40af;
}

/* Inputs & Dropdowns */
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
    background-color: #1c1c20;
    border: 1px solid #323238;
    border-radius: 6px;
    padding: 5px 8px;
    color: #fafafa;
    selection-background-color: #2563eb;
    min-height: 24px;
}

QLineEdit:hover, QComboBox:hover, QSpinBox:hover, QDoubleSpinBox:hover {
    border-color: #4b4b52;
}

QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {
    border: 1px solid #38bdf8;
    background-color: #202026;
}

QSpinBox, QDoubleSpinBox {
    padding-right: 22px;
}

QSpinBox::up-button, QDoubleSpinBox::up-button {
    subcontrol-origin: border;
    subcontrol-position: top right;
    width: 20px;
    border-left: 1px solid #323238;
    border-bottom: 1px solid #323238;
    background-color: #27272a;
    border-top-right-radius: 5px;
}

QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover {
    background-color: #38bdf8;
}

QSpinBox::down-button, QDoubleSpinBox::down-button {
    subcontrol-origin: border;
    subcontrol-position: bottom right;
    width: 20px;
    border-left: 1px solid #323238;
    background-color: #27272a;
    border-bottom-right-radius: 5px;
}

QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {
    background-color: #38bdf8;
}

QComboBox {
    padding-right: 24px;
}

QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 22px;
    border-left: none;
}

QComboBox QAbstractItemView {
    background-color: #1c1c20;
    border: 1px solid #323238;
    border-radius: 6px;
    padding: 4px;
    color: #fafafa;
    selection-background-color: #2563eb;
    selection-color: #ffffff;
}

/* Checkboxes */
QCheckBox {
    spacing: 8px;
    color: #e4e4e7;
    font-size: 9.5pt;
}

QCheckBox::indicator {
    width: 17px;
    height: 17px;
    border-radius: 4px;
    border: 1px solid #3f3f46;
    background-color: #1c1c20;
}

QCheckBox::indicator:hover {
    border-color: #38bdf8;
}

QCheckBox::indicator:checked {
    background-color: #0284c7;
    border-color: #38bdf8;
}

/* Table View */
QTableView, QTableWidget {
    background-color: #18181b;
    alternate-background-color: #1f1f23;
    color: #f4f4f5;
    gridline-color: #27272a;
    border: 1px solid #27272a;
    border-radius: 6px;
    selection-background-color: #1e3a8a;
    selection-color: #ffffff;
}

QHeaderView::section {
    background-color: #202024;
    color: #a1a1aa;
    padding: 6px 10px;
    border: none;
    border-right: 1px solid #27272a;
    border-bottom: 1px solid #27272a;
    font-weight: 600;
    font-size: 9pt;
}

/* Progress Bar */
QProgressBar {
    background-color: #202024;
    border: 1px solid #27272a;
    border-radius: 6px;
    text-align: center;
    color: #f4f4f5;
    font-weight: 600;
    height: 18px;
}

QProgressBar::chunk {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #2563eb, stop:1 #38bdf8);
    border-radius: 5px;
}

/* Splitter */
QSplitter::handle {
    background-color: #27272a;
}

QSplitter::handle:horizontal {
    width: 8px;
    background-color: #27272a;
    border-left: 1px solid #18181b;
    border-right: 1px solid #18181b;
    margin: 0px 2px;
}

QSplitter::handle:horizontal:hover {
    background-color: #38bdf8;
}

QSplitter::handle:vertical {
    height: 8px;
    background-color: #27272a;
    border-top: 1px solid #18181b;
    border-bottom: 1px solid #18181b;
    margin: 2px 0px;
}

QSplitter::handle:vertical:hover {
    background-color: #38bdf8;
}

/* Log & Text Edit */
QTextEdit {
    background-color: #141416;
    border: 1px solid #27272a;
    border-radius: 6px;
    color: #e4e4e7;
    font-family: Consolas, "Cascadia Code", Monaco, "Courier New", monospace;
    font-size: 9.5pt;
    padding: 6px;
}

/* ScrollBars */
QScrollBar:vertical {
    background-color: #141416;
    width: 10px;
    margin: 0;
}

QScrollBar::handle:vertical {
    background-color: #323238;
    border-radius: 5px;
    min-height: 20px;
}

QScrollBar::handle:vertical:hover {
    background-color: #4b4b52;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

QScrollBar:horizontal {
    background-color: #141416;
    height: 10px;
    margin: 0;
}

QScrollBar::handle:horizontal {
    background-color: #323238;
    border-radius: 5px;
    min-width: 20px;
}

QScrollBar::handle:horizontal:hover {
    background-color: #4b4b52;
}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0px;
}

/* Menu Bar */
QMenuBar {
    background-color: #141416;
    color: #e4e4e7;
    border-bottom: 1px solid #27272a;
}

QMenuBar::item:selected {
    background-color: #27272a;
    border-radius: 4px;
}

QMenu {
    background-color: #1c1c20;
    color: #e4e4e7;
    border: 1px solid #323238;
    border-radius: 6px;
    padding: 4px;
}

QMenu::item {
    padding: 6px 20px 6px 12px;
    border-radius: 4px;
}

QMenu::item:selected {
    background-color: #2563eb;
    color: #ffffff;
}
"""
