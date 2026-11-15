import json
import os
import time
from typing import Dict, Optional

class CheckpointManager:
    """Manages atomic checkpoint saves and resumes to prevent work loss during translation."""

    @staticmethod
    def get_checkpoint_path(source_file_path: str) -> str:
        base, _ = os.path.splitext(source_file_path)
        return f"{base}.checkpoint.json"

    @classmethod
    def save(
        cls,
        source_file_path: str,
        total_events: int,
        completed_translations: Dict[int, str],
        last_batch_index: int = 0
    ) -> None:
        """Saves current translation state to JSON checkpoint file atomically."""
        if not source_file_path:
            return
        checkpoint_path = cls.get_checkpoint_path(source_file_path)
        str_translations = {str(k): v for k, v in completed_translations.items()}
        data = {
            "source_file": source_file_path,
            "total_events": total_events,
            "completed_count": len(completed_translations),
            "completed_translations": str_translations,
            "last_batch_index": last_batch_index,
            "updated_at": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        temp_path = f"{checkpoint_path}.tmp"
        try:
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(temp_path, checkpoint_path)
        except Exception:
            pass

    @classmethod
    def load(cls, source_file_path: str) -> Optional[Dict[int, str]]:
        """Loads translations from checkpoint if available."""
        if not source_file_path:
            return None
        checkpoint_path = cls.get_checkpoint_path(source_file_path)
        if not os.path.exists(checkpoint_path):
            return None
        try:
            with open(checkpoint_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            raw_map = data.get("completed_translations", {})
            return {int(k): str(v) for k, v in raw_map.items()}
        except Exception:
            return None

    @classmethod
    def cleanup(cls, source_file_path: str) -> None:
        """Deletes checkpoint file once translation has completed successfully."""
        if not source_file_path:
            return
        checkpoint_path = cls.get_checkpoint_path(source_file_path)
        if os.path.exists(checkpoint_path):
            try:
                os.remove(checkpoint_path)
            except Exception:
                pass
