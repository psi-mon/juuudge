import re
import pytest
from pathlib import Path
from juuudge.logger import get_logger, log_event, get_recent_logs, reset_logger, add_log_listener, remove_log_listener

def test_logger_file_creation_and_format(tmp_path, monkeypatch):
    monkeypatch.setenv("JUUUDGE_DIR", str(tmp_path))
    reset_logger()

    logger = get_logger("test_module")
    logger.debug("Debug level log message")
    logger.info("Info level log message")
    logger.warning("Warning level log message")
    logger.error("Error level log message")

    log_file = tmp_path / "log.txt"
    assert log_file.exists(), f"Log file expected at {log_file}"
    content = log_file.read_text(encoding="utf-8")
    lines = [line for line in content.splitlines() if line.strip()]

    assert len(lines) == 4
    # Check severity markers
    assert "[LOG]" in lines[0]
    assert "[INFO]" in lines[1]
    assert "[WARN]" in lines[2]
    assert "[ERROR]" in lines[3]

    # Check format: YYYY-MM-DD HH:MM:SS [SEVERITY] [file.py:line] message
    pattern = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} \[(LOG|INFO|WARN|ERROR)\] \[[a-zA-Z0-9_\-\.]+:\d+\] .+$")
    for line in lines:
        assert pattern.match(line), f"Line did not match expected format: {line}"

    assert "Debug level log message" in lines[0]
    assert "Info level log message" in lines[1]
    assert "Warning level log message" in lines[2]
    assert "Error level log message" in lines[3]

def test_logger_ring_buffer_last_10_entries(tmp_path, monkeypatch):
    monkeypatch.setenv("JUUUDGE_DIR", str(tmp_path))
    reset_logger()

    logger = get_logger("buffer_test")
    for i in range(15):
        logger.info(f"Iteration message {i}")

    recent = get_recent_logs()
    assert len(recent) == 10
    # Must contain the latest 10 (5 to 14)
    assert "Iteration message 5" in recent[0].message or "Iteration message 5" in str(recent[0])
    assert "Iteration message 14" in recent[-1].message or "Iteration message 14" in str(recent[-1])
    assert not any("Iteration message 0" in (r.message if hasattr(r, "message") else str(r)) for r in recent)

def test_logger_subscriber_callback(tmp_path, monkeypatch):
    monkeypatch.setenv("JUUUDGE_DIR", str(tmp_path))
    reset_logger()

    events = []
    def listener(entry):
        events.append(entry)

    add_log_listener(listener)
    try:
        logger = get_logger("subscriber_test")
        logger.info("Realtime notification event")

        assert len(events) == 1
        assert "Realtime notification event" in (events[0].message if hasattr(events[0], "message") else str(events[0]))
    finally:
        remove_log_listener(listener)
