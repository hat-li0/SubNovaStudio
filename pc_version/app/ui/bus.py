from PySide6.QtCore import QObject, Signal, Slot, Qt, QCoreApplication, QThread, QMetaObject, Q_ARG


class EventBus(QObject):
    """Singleton EventBus for global application events."""

    _instance = None

    file_selected = Signal(list)
    files_cleared = Signal()
    provider_changed = Signal(dict)
    model_selected = Signal(str)
    translation_started = Signal()
    improvement_started = Signal()
    translation_progress = Signal(int, int, str)  # current, total, status
    translation_finished = Signal(dict)
    translation_cancelled = Signal()
    character_updated = Signal(dict)
    log_message = Signal(str)
    live_preview_updated = Signal(str, str)  # orig, imp
    auto_detect_status = Signal(str, str)  # status, color

    @Slot(str)
    def _deliver_log(self, msg: str):
        self.log_message.emit(msg)

    @classmethod
    def emit_log_safe(cls, msg: str):
        """Thread-safe log emission onto the Qt main thread when called from background threads."""
        bus = cls.instance()
        app = QCoreApplication.instance()
        if app is not None:
            if bus.thread() != app.thread() and QThread.currentThread() == app.thread():
                bus.moveToThread(app.thread())
            if QThread.currentThread() != bus.thread():
                QMetaObject.invokeMethod(
                    bus,
                    "_deliver_log",
                    Qt.ConnectionType.QueuedConnection,
                    Q_ARG(str, msg),
                )
                return
        bus.log_message.emit(msg)

    @classmethod
    def instance(cls):
        if cls._instance is None:
            bus = EventBus()
            app = QCoreApplication.instance()
            if app is not None and bus.thread() != app.thread():
                bus.moveToThread(app.thread())
            cls._instance = bus
        return cls._instance
