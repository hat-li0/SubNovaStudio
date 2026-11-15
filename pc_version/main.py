import sys
import os
import traceback

# Ensure current working directory is application directory when frozen
if getattr(sys, "frozen", False):
    exe_dir = os.path.dirname(os.path.abspath(sys.executable))
    os.chdir(exe_dir)
    if sys.platform == "win32":
        # Ensure Windows DLL loader finds PySide6, shiboken6, and internal DLLs
        base_dir = getattr(sys, "_MEIPASS", exe_dir)
        for sub in ["", "_internal", os.path.join("_internal", "PySide6"), os.path.join("_internal", "shiboken6"), "PySide6", "shiboken6"]:
            candidate = os.path.abspath(os.path.join(base_dir, sub))
            if os.path.isdir(candidate):
                try:
                    os.add_dll_directory(candidate)
                except Exception:
                    pass
                os.environ["PATH"] = candidate + os.pathsep + os.environ.get("PATH", "")

# Add project directory to Python path if needed
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def log_fatal_crash(exc_type, exc_val, tb, show_dialog: bool = True) -> None:
    """Logs fatal crashes to crash.log (writable exe dir / portable / AppData fallback) and alerts the user."""
    from datetime import datetime
    from app.core.resources import get_app_data_dir

    local_dir = os.path.dirname(os.path.abspath(sys.executable if getattr(sys, "frozen", False) else __file__))
    local_crash_file = os.path.join(local_dir, "crash.log")
    fallback_crash_file = str(get_app_data_dir() / "crash.log")
    err_msg = "".join(traceback.format_exception(exc_type, exc_val, tb))
    payload = (
        f"\n{'='*60}\n"
        f"FATAL APPLICATION CRASH: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"{'='*60}\n"
        f"{err_msg}"
    )

    crash_file = fallback_crash_file
    if getattr(sys, "frozen", False):
        if os.path.exists(os.path.join(local_dir, "portable.flag")) or os.environ.get("PYTEST_CURRENT_TEST"):
            candidate_order = (local_crash_file, fallback_crash_file)
        else:
            candidate_order = (fallback_crash_file, local_crash_file)
    else:
        candidate_order = (fallback_crash_file, local_crash_file)

    for candidate in candidate_order:
        try:
            with open(candidate, "a", encoding="utf-8") as f:
                f.write(payload)
            crash_file = candidate
            break
        except Exception:
            continue

    # Native Windows alert dialog if running windowed and requested
    if show_dialog and sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(
                0,
                f"حدث خطأ غير متوقع أدى لتوقف التطبيق.\nتم تسجيل التفاصيل في ملف:\n{crash_file}\n\nالخطأ: {exc_val}",
                "SubNova Studio — خطأ غير متوقع",
                0x10  # MB_ICONERROR
            )
        except Exception:
            pass

def main() -> None:
    """Main entry point for SubNova Studio GUI wrapped in top-level crash handler."""
    try:
        from app.ui.app import run_app
        run_app()
    except Exception:
        exc_type, exc_val, tb = sys.exc_info()
        log_fatal_crash(exc_type, exc_val, tb)
        sys.exit(1)

if __name__ == "__main__":
    main()
