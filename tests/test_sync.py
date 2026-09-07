import pytest
import json
from unittest.mock import patch, AsyncMock
from juuudge.storage.db import Database
from juuudge.storage.vector import VectorStore
from juuudge.ingest.sync import sync_all_data

MOCK_CR = """
1. Game Concepts
100. General
100.1. General rule text.
Glossary
Priority
Right to act.
"""

MOCK_BULK_INDEX = {
    "data": [
        {"type": "default_cards", "download_uri": "https://api.scryfall.com/bulk-data/default-cards.json"},
        {"type": "rulings", "download_uri": "https://api.scryfall.com/bulk-data/rulings.json"}
    ]
}

MOCK_CARDS_JSON = [
    {"name": "Lightning Bolt", "mana_cost": "{R}", "type_line": "Instant", "oracle_text": "Deal 3 damage."}
]

@pytest.mark.asyncio
async def test_sync_orchestrator(tmp_path):
    db = Database(tmp_path / "test.db")
    db.init_schema()
    vec_store = VectorStore(tmp_path / "lancedb")

    with patch("juuudge.ingest.sync.download_file") as mock_dl:
        mock_dl.side_effect = [
            MOCK_CR.encode("utf-8"),                     # CR text
            json.dumps(MOCK_BULK_INDEX).encode("utf-8"), # Scryfall bulk metadata
            json.dumps(MOCK_CARDS_JSON).encode("utf-8"), # Default cards JSON
            json.dumps([]).encode("utf-8")               # Rulings JSON
        ]
        
        await sync_all_data(db, vec_store, cache_dir=tmp_path / "cache")

        bolt = db.get_card_by_name("Lightning Bolt")
        assert bolt is not None
        assert bolt.mana_cost == "{R}"

        r100 = db.get_rule_by_id("100.1")
        assert r100 is not None
