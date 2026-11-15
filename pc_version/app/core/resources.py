import sys
import os
import shutil
import tempfile
from pathlib import Path
from typing import Optional


def _is_dir_writable(path: Path) -> bool:
    """Probes whether a directory can actually be created and written to."""
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".write_probe.tmp"
        with open(probe, "w", encoding="utf-8") as f:
            f.write("ok")
        probe.unlink(missing_ok=True)
        return True
    except Exception:
        return False


def get_app_data_dir() -> Path:
    """
    Returns a guaranteed writable directory for persistent user config, SQLite DB, logs, and crash reports.
    Uses portable mode if 'portable.flag' exists next to the executable / project root;
    otherwise tries %APPDATA%\\SubNovaStudio (or ~/.local/share/SubNovaStudio) and verifies write access,
    falling back cleanly to <app_root>/user_data or system temp if AppData is restricted.
    """
    if getattr(sys, "frozen", False):
        app_root = Path(sys.executable).resolve().parent
    else:
        app_root = Path(__file__).resolve().parent.parent.parent

    if os.name == "nt":
        base = Path(os.environ.get("APPDATA") or (Path.home() / "AppData" / "Roaming"))
    else:
        base = Path(os.environ.get("XDG_DATA_HOME") or (Path.home() / ".local" / "share"))
    appdata_target = base / "SubNovaStudio"

    if (app_root / "portable.flag").exists():
        candidates = [app_root, app_root / "user_data", appdata_target]
    else:
        candidates = [appdata_target, app_root / "user_data", Path(tempfile.gettempdir()) / "SubNovaStudio"]

    for target in candidates:
        if _is_dir_writable(target):
            return target

    return Path(tempfile.gettempdir()) / "SubNovaStudio"


def resource_path(relative_path: str) -> str:
    """
    Resolves dynamic resource paths both in development and inside PyInstaller bundle (_MEIPASS).
    Compatible with Windows, Linux, and Android environments.
    """
    base_path = getattr(sys, '_MEIPASS', None)
    if not base_path:
        # Walk up from this file's location to the project root
        base_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    target = os.path.join(base_path, relative_path)
    if os.path.exists(target):
        return target
        
    # Secondary fallback to current working directory
    cwd_candidate = os.path.join(os.path.abspath("."), relative_path)
    if os.path.exists(cwd_candidate):
        return cwd_candidate

    return target

def find_binary(binary_name: str) -> str:
    """
    Locates an external executable (e.g. ffmpeg, ffprobe) checking:
    1. Bundled inside PyInstaller _MEIPASS / app directory
    2. Local directory or bin/ folder next to executable
    3. System PATH via shutil.which
    """
    exe_name = f"{binary_name}.exe" if sys.platform == "win32" and not binary_name.endswith(".exe") else binary_name
    
    # 1. Check PyInstaller _MEIPASS bundle
    bundled = resource_path(exe_name)
    if os.path.isfile(bundled) and os.access(bundled, os.X_OK):
        return bundled
    
    # Check bin/ subdirectory inside bundle
    bundled_bin = resource_path(os.path.join("bin", exe_name))
    if os.path.isfile(bundled_bin) and os.access(bundled_bin, os.X_OK):
        return bundled_bin

    # 2. Check next to sys.executable (when frozen) or project root
    if getattr(sys, "frozen", False):
        exe_dir = os.path.dirname(sys.executable)
        local_cand = os.path.join(exe_dir, exe_name)
        if os.path.isfile(local_cand):
            return local_cand
        local_bin = os.path.join(exe_dir, "bin", exe_name)
        if os.path.isfile(local_bin):
            return local_bin

    # 3. Check system PATH
    found = shutil.which(binary_name)
    if found:
        return found

    return binary_name
