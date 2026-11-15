from abc import ABC, abstractmethod
from pathlib import Path
from typing import Union
from app.models.subtitle import SubtitleDocument

class SubtitleWriter(ABC):
    """Abstract base class for subtitle writers."""
    
    def write(self, document: SubtitleDocument, file_path: Union[str, Path]) -> None:
        """Write a subtitle document to a file."""
        import os
        import stat
        target_path = Path(file_path)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        if target_path.exists():
            try:
                os.chmod(target_path, stat.S_IWRITE | stat.S_IREAD)
            except Exception:
                pass
        content = self.write_text(document)
        with open(target_path, "w", encoding="utf-8-sig") as f:
            f.write(content)
            
    @abstractmethod
    def write_text(self, document: SubtitleDocument) -> str:
        """Convert a subtitle document to string representation."""
        pass
