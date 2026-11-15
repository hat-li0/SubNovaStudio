import sys
import os
import asyncio
import traceback
import ctypes
import qasync
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon
from app.ui.windows.main_window import MainWindow
from app.ui.theme import DARK_THEME_QSS
from app.ui.bus import EventBus
from app.core.logging import get_logger, setup_root_logging
from app.core.resources import resource_path, get_app_data_dir

logger = get_logger("app")

def run_app():
    setup_root_logging()
    
    # Set Windows AppUserModelID for proper taskbar icon and grouping
    if os.name == 'nt':
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("com.subnova.studio")
        except Exception:
            pass

    app = QApplication(sys.argv)
    app.setApplicationName("SubNova Studio")
    app.setApplicationDisplayName("SubNova Studio — استوديو سوب نوفا")
    app.setStyleSheet(DARK_THEME_QSS)

    # Set application icon with dynamic asset resolution
    icon_path = resource_path(os.path.join("app", "resources", "icons", "subnova_icon.ico"))
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))
    
    # Initialize EventBus
    bus = EventBus.instance()
    
    # Set up qasync event loop
    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)

    # 1. Capture unhandled async background errors and surface them to UI
    def async_exception_handler(current_loop, context):
        exc = context.get("exception")
        msg = context.get("message", "Unhandled async task exception")
        if isinstance(exc, (asyncio.CancelledError, ConnectionRefusedError)):
            return  # Benign task cancellation or offline local server probe
        if exc and "Cannot enter into task" in str(exc):
            return  # Benign loop re-entrance artifact
        if exc:
            err_text = f"[ASYNC ERROR] {type(exc).__name__}: {exc}"
        else:
            err_text = f"[ASYNC ERROR] {msg}"
        logger.error(err_text)
        bus.log_message.emit(err_text)

    loop.set_exception_handler(async_exception_handler)

    # 2. Capture unhandled synchronous exceptions and surface them to UI & crash.log
    def sys_exception_hook(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        full_tb = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        err_msg = "".join(traceback.format_exception_only(exc_type, exc_value)).strip()
        logger.critical(f"Unhandled Exception: {err_msg}\n{full_tb}")
        try:
            crash_path = get_app_data_dir() / "crash.log"
            with open(crash_path, "a", encoding="utf-8") as f:
                from datetime import datetime
                f.write(f"\n{'='*60}\nUNHANDLED EXCEPTION [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}]:\n{full_tb}\n{'='*60}\n")
        except Exception:
            pass
        EventBus.emit_log_safe(f"[FATAL ERROR] {err_msg}")

    sys.excepthook = sys_exception_hook
    
    window = MainWindow()
    window.show()
    
    with loop:
        sys.exit(loop.run_forever())
