import os
import sys
import logging
from pathlib import Path
from logging.handlers import RotatingFileHandler
from app.core.resources import get_app_data_dir

LOGS_DIR = get_app_data_dir() / "logs"
try:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
except Exception:
    pass


class SafeRotatingFileHandler(RotatingFileHandler):
    """Windows-safe rotating file handler that never crashes the application on permission or lock errors."""
    def _open(self):
        try:
            return super()._open()
        except (PermissionError, OSError):
            # In case the primary log file is locked by another running instance or antivirus,
            # gracefully fall back to a PID-tagged file or an in-memory stream
            try:
                p = Path(self.baseFilename)
                fallback = p.parent / f"{p.stem}_{os.getpid()}{p.suffix}"
                self.baseFilename = str(fallback)
                return super()._open()
            except Exception:
                import io
                return io.StringIO()

    def emit(self, record):
        try:
            super().emit(record)
        except (PermissionError, OSError):
            # Suppress file-lock / sharing violations on Windows during writes
            pass

    def doRollover(self):
        try:
            super().doRollover()
        except (PermissionError, OSError):
            # Suppress rollover lock conflicts when antivirus or another process touches the file
            pass


class EventBusLogHandler(logging.Handler):
    """Routes WARNING and ERROR logs safely to the frontend EventBus across threads."""
    def emit(self, record):
        try:
            from app.ui.bus import EventBus
            msg = record.getMessage()
            prefix = ""
            if record.levelno >= logging.ERROR:
                prefix = "[ERROR] "
            elif record.levelno >= logging.WARNING:
                prefix = "[WARN] "
            EventBus.emit_log_safe(f"{prefix}{msg}")
        except Exception:
            pass


def setup_root_logging(level: int = logging.INFO) -> None:
    """Configures the root logger with resilient file and EventBus handlers once."""
    root = logging.getLogger()
    if root.level == logging.NOTSET or root.level > level:
        root.setLevel(level)

    if not any(isinstance(h, EventBusLogHandler) for h in root.handlers):
        eb_handler = EventBusLogHandler()
        eb_handler.setLevel(logging.WARNING)
        root.addHandler(eb_handler)

    if not any(isinstance(h, RotatingFileHandler) for h in root.handlers):
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        created_handler = False

        # Attempt 1: Standard shared app.log with delay=True
        target_candidates = [
            LOGS_DIR / "app.log",
            LOGS_DIR / f"app_{os.getpid()}.log",
        ]

        for log_target in target_candidates:
            try:
                fh = SafeRotatingFileHandler(
                    log_target,
                    maxBytes=10 * 1024 * 1024,
                    backupCount=5,
                    encoding="utf-8",
                    delay=True,
                )
                fh.setLevel(logging.DEBUG)
                fh.setFormatter(formatter)
                root.addHandler(fh)
                created_handler = True
                break
            except Exception:
                continue

        # Fallback: stdout/stderr if file permissions prevent logging anywhere
        if not created_handler:
            try:
                sh = logging.StreamHandler(sys.stdout)
                sh.setLevel(logging.DEBUG)
                sh.setFormatter(formatter)
                root.addHandler(sh)
            except Exception:
                pass


def get_logger(name: str) -> logging.Logger:
    """Returns a named logger and ensures root file/EventBus handlers are configured once."""
    setup_root_logging()
    logger = logging.getLogger(name)
    if logger.level == logging.NOTSET:
        logger.setLevel(logging.DEBUG)
    return logger
