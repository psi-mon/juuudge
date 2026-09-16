import os
import logging
import threading
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional, List

@dataclass
class LogEntry:
    timestamp: str
    severity: str
    source: str
    message: str

    def formatted(self) -> str:
        return f"{self.timestamp} [{self.severity}] [{self.source}] {self.message}"

    def __str__(self) -> str:
        return self.formatted()

class JuuudgeLogFormatter(logging.Formatter):
    SEVERITY_MAP = {
        "DEBUG": "LOG",
        "INFO": "INFO",
        "WARNING": "WARN",
        "ERROR": "ERROR",
        "CRITICAL": "ERROR",
    }

    def format(self, record: logging.LogRecord) -> str:
        timestamp = datetime.fromtimestamp(record.created).strftime("%Y-%m-%d %H:%M:%S")
        severity = self.SEVERITY_MAP.get(record.levelname, record.levelname)
        source = f"{record.filename}:{record.lineno}"
        message = record.getMessage()
        return f"{timestamp} [{severity}] [{source}] {message}"

class TUIRingBufferHandler(logging.Handler):
    SEVERITY_MAP = {
        "DEBUG": "LOG",
        "INFO": "INFO",
        "WARNING": "WARN",
        "ERROR": "ERROR",
        "CRITICAL": "ERROR",
    }

    def __init__(self, maxlen: int = 10):
        super().__init__()
        self.buffer: deque[LogEntry] = deque(maxlen=maxlen)
        self.listeners: List[Callable[[LogEntry], None]] = []
        self._lock = threading.Lock()

    def emit(self, record: logging.LogRecord):
        try:
            timestamp = datetime.fromtimestamp(record.created).strftime("%Y-%m-%d %H:%M:%S")
            severity = self.SEVERITY_MAP.get(record.levelname, record.levelname)
            source = f"{record.filename}:{record.lineno}"
            message = record.getMessage()
            entry = LogEntry(
                timestamp=timestamp,
                severity=severity,
                source=source,
                message=message,
            )
            with self._lock:
                self.buffer.append(entry)
                listeners = list(self.listeners)

            for listener in listeners:
                try:
                    listener(entry)
                except Exception:
                    pass
        except Exception:
            self.handleError(record)

    def get_recent(self) -> List[LogEntry]:
        with self._lock:
            return list(self.buffer)

    def add_listener(self, listener: Callable[[LogEntry], None]):
        with self._lock:
            if listener not in self.listeners:
                self.listeners.append(listener)

    def remove_listener(self, listener: Callable[[LogEntry], None]):
        with self._lock:
            if listener in self.listeners:
                self.listeners.remove(listener)

_tui_handler: Optional[TUIRingBufferHandler] = None
_file_handler: Optional[logging.FileHandler] = None
_initialized = False
_init_lock = threading.Lock()

def _get_log_file_path() -> Path:
    from juuudge.config import get_app_dir
    return get_app_dir() / "log.txt"

def setup_logging(log_file: Optional[Path] = None) -> None:
    global _tui_handler, _file_handler, _initialized

    with _init_lock:
        target_file = log_file or _get_log_file_path()
        target_file.parent.mkdir(parents=True, exist_ok=True)

        root_logger = logging.getLogger("juuudge")
        root_logger.setLevel(logging.DEBUG)

        # Clear existing handlers if already present
        for handler in list(root_logger.handlers):
            root_logger.removeHandler(handler)

        formatter = JuuudgeLogFormatter()

        # 1. File Handler
        _file_handler = logging.FileHandler(str(target_file), encoding="utf-8")
        _file_handler.setLevel(logging.DEBUG)
        _file_handler.setFormatter(formatter)
        root_logger.addHandler(_file_handler)

        # 2. Ring buffer handler for TUI
        if _tui_handler is None:
            _tui_handler = TUIRingBufferHandler(maxlen=10)
        _tui_handler.setLevel(logging.DEBUG)
        root_logger.addHandler(_tui_handler)

        _initialized = True

def get_logger(name: Optional[str] = None) -> logging.Logger:
    if not _initialized:
        setup_logging()
    if name:
        return logging.getLogger(f"juuudge.{name}")
    return logging.getLogger("juuudge")

def log_event(severity: str, message: str, name: str = "core"):
    logger = get_logger(name)
    sev = severity.upper()
    if sev == "LOG":
        logger.debug(message)
    elif sev == "INFO":
        logger.info(message)
    elif sev == "WARN":
        logger.warning(message)
    elif sev == "ERROR":
        logger.error(message)
    else:
        logger.info(message)

def get_recent_logs() -> List[LogEntry]:
    if not _initialized:
        setup_logging()
    if _tui_handler is not None:
        return _tui_handler.get_recent()
    return []

def add_log_listener(listener: Callable[[LogEntry], None]):
    if not _initialized:
        setup_logging()
    if _tui_handler is not None:
        _tui_handler.add_listener(listener)

def remove_log_listener(listener: Callable[[LogEntry], None]):
    if _tui_handler is not None:
        _tui_handler.remove_listener(listener)

def reset_logger():
    global _initialized, _tui_handler, _file_handler
    with _init_lock:
        root_logger = logging.getLogger("juuudge")
        for handler in list(root_logger.handlers):
            root_logger.removeHandler(handler)
            try:
                handler.close()
            except Exception:
                pass
        _tui_handler = None
        _file_handler = None
        _initialized = False
