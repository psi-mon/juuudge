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
        assert pilot.app.query_one("#card-pane") is not None
        assert pilot.app.query_one("#rule-pane") is not None
