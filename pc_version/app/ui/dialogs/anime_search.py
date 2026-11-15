from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton,
    QListWidget, QListWidgetItem, QLabel, QComboBox
)
from PySide6.QtCore import Qt
import asyncio
from typing import Optional, List
from app.models.anime import MediaInfo, CharacterProfile

class MediaSearchDialog(QDialog):
    """Dialog for searching movies, TV series, and anime."""
    
    def __init__(self, parent=None, metadata_service=None):
        super().__init__(parent)
        self.metadata_service = metadata_service
        self.selected_media: Optional[MediaInfo] = None
        self.selected_anime: Optional[MediaInfo] = None  # alias
        self.selected_characters: List[CharacterProfile] = []
        
        self.results: List[MediaInfo] = []
        
        self.setWindowTitle("Search Media (Movies, Series & Anime) / بحث عن عمل")
        self.setMinimumSize(680, 520)
        
        self.layout = QVBoxLayout(self)
        
        search_layout = QHBoxLayout()
        self.le_search = QLineEdit()
        self.le_search.setPlaceholderText("Enter title (Movie, Series, Anime) / ابحث عن اسم العمل...")
        
        self.cb_filter = QComboBox()
        self.cb_filter.addItems(["All / الكل", "TV Series / مسلسلات", "Movies / أفلام", "Anime / أنمي"])
        self.cb_filter.setFixedWidth(140)
        
        self.btn_search = QPushButton("🔍 Search / بحث")
        search_layout.addWidget(self.le_search)
        search_layout.addWidget(self.cb_filter)
        search_layout.addWidget(self.btn_search)
        self.layout.addLayout(search_layout)
        
        # Content layout
        content_layout = QHBoxLayout()
        
        self.list_results = QListWidget()
        self.list_results.setFixedWidth(300)
        
        details_layout = QVBoxLayout()
        self.lbl_details = QLabel("Select a title to view details / اختر عملاً لعرض تفاصيله.")
        self.lbl_details.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.lbl_details.setWordWrap(True)
        details_layout.addWidget(self.lbl_details)
        
        content_layout.addWidget(self.list_results)
        content_layout.addLayout(details_layout)
        
        self.layout.addLayout(content_layout)
        
        self.btn_select = QPushButton("Select Title / اختيار العمل")
        self.btn_select.setEnabled(False)
        self.layout.addWidget(self.btn_select)
        
        self.list_results.itemSelectionChanged.connect(self._on_select)
        self.btn_select.clicked.connect(self._on_accept_clicked)
        self.btn_search.clicked.connect(self._on_search_clicked)
        self.le_search.returnPressed.connect(self._on_search_clicked)
        
    def _on_search_clicked(self):
        title = self.le_search.text().strip()
        if not title or not self.metadata_service:
            return
            
        self.btn_search.setEnabled(False)
        self.list_results.clear()
        self.results = []
        self.lbl_details.setText("Searching across databases...")
        self.list_results.addItem("Searching...")
        
        filter_text = self.cb_filter.currentText()
        if "TV" in filter_text:
            filter_type = "tv"
        elif "Movie" in filter_text:
            filter_type = "movie"
        elif "Anime" in filter_text:
            filter_type = "anime"
        else:
            filter_type = "all"
        
        async def search():
            try:
                items = await self.metadata_service.search_multiple_media(title, filter_type=filter_type)
                self.list_results.clear()
                self.results = items
                if items:
                    for i, a in enumerate(items):
                        tag = "[TV]" if a.media_type == "tv" else ("[Movie]" if a.media_type == "movie" else "[Anime]")
                        year_str = f" ({a.year})" if a.year else ""
                        item = QListWidgetItem(f"{tag} {a.display_title}{year_str}")
                        item.setData(Qt.UserRole, i)
                        self.list_results.addItem(item)
                    self.lbl_details.setText(f"Found {len(items)} results. Select one to see cast.")
                else:
                    self.list_results.addItem("No results found.")
                    self.lbl_details.setText("No results found for this query.")
            except Exception as e:
                self.list_results.clear()
                self.list_results.addItem(f"Error: {e}")
                self.lbl_details.setText("")
            finally:
                self.btn_search.setEnabled(True)
                
        def run_coroutine(coro):
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(coro)
            except RuntimeError:
                import threading
                threading.Thread(target=lambda: asyncio.run(coro), daemon=True).start()

        run_coroutine(search())
        
    def _on_select(self):
        items = self.list_results.selectedItems()
        if not items:
            self.btn_select.setEnabled(False)
            return
            
        idx = items[0].data(Qt.UserRole)
        if idx is None or idx >= len(self.results):
            return
            
        media = self.results[idx]
        m_tag = "TV Series" if media.media_type == "tv" else ("Movie" if media.media_type == "movie" else "Anime")
        
        details = f"<h3 style='margin-bottom:4px;'>{media.display_title}</h3>"
        details += f"<b>Type:</b> {m_tag} | <b>Format:</b> {media.format or 'N/A'}<br>"
        if media.year:
            details += f"<b>Year:</b> {media.year}<br>"
        if media.status:
            details += f"<b>Status:</b> {media.status}<br>"
        if media.source_name:
            details += f"<b>Source:</b> {media.source_name}<br>"
        if media.genres:
            details += f"<b>Genres:</b> {', '.join(media.genres)}<br>"
        if media.overview:
            details += f"<br><b>Overview:</b><br><p>{media.overview[:300]}...</p>"
        
        self.lbl_details.setText(details)
        self.btn_select.setEnabled(True)
        
    def _on_accept_clicked(self):
        items = self.list_results.selectedItems()
        if not items:
            return
        idx = items[0].data(Qt.UserRole)
        if idx is None or idx >= len(self.results):
            return
            
        self.selected_media = self.results[idx]
        self.selected_anime = self.selected_media  # alias
        self.btn_select.setEnabled(False)
        self.btn_select.setText("Fetching Characters & Cast...")
        
        async def fetch_chars():
            try:
                self.selected_characters = await self.metadata_service.get_characters_for_media(self.selected_media)
                self.accept()
            except Exception as e:
                self.lbl_details.setText(f"Error fetching characters: {e}")
                self.btn_select.setEnabled(True)
                self.btn_select.setText("Select Title / اختيار العمل")
        
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(fetch_chars())
        except RuntimeError:
            import threading
            threading.Thread(target=lambda: asyncio.run(fetch_chars()), daemon=True).start()

# Backward compatibility alias
AnimeSearchDialog = MediaSearchDialog
