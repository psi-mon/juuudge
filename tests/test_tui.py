import pytest
from textual.pilot import Pilot
from juuudge.tui.app import JuuudgeApp
from juuudge.storage.db import Database
from juuudge.storage.vector import VectorStore

@pytest.mark.asyncio
async def test_tui_app_launch(tmp_path):
    db = Database(tmp_path / "test.db")
    db.init_schema()
    vec_store = VectorStore(tmp_path / "lancedb")

    app = JuuudgeApp(db=db, vec_store=vec_store)
    async with app.run_test() as pilot:
        assert pilot.app.is_running
        # Check panels exist
        assert pilot.app.query_one("#chat-pane") is not None
        assert pilot.app.query_one("#log-pane") is not None
        assert pilot.app.query_one("#card-pane") is not None
        assert pilot.app.query_one("#rule-pane") is not None

@pytest.mark.asyncio
async def test_tui_log_inspector_widget(tmp_path, monkeypatch):
    from juuudge.logger import get_logger, reset_logger
    from juuudge.tui.widgets import LogInspectorWidget

    monkeypatch.setenv("JUUUDGE_DIR", str(tmp_path))
    reset_logger()

    logger = get_logger("tui_test")
    logger.info("First UI log entry")
    logger.warning("Second UI log entry warning")

    db = Database(tmp_path / "test.db")
    db.init_schema()
    vec_store = VectorStore(tmp_path / "lancedb")

    app = JuuudgeApp(db=db, vec_store=vec_store)
    async with app.run_test() as pilot:
        log_widget = pilot.app.query_one("#log-pane", LogInspectorWidget)
        assert log_widget is not None
        text_content = log_widget.renderable
        assert "First UI log entry" in text_content
        assert "Second UI log entry warning" in text_content
        assert "INFO" in text_content
        assert "WARN" in text_content
