import pytest
import json
import gzip
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

# Real-world Scryfall bulk metadata format as returned by https://api.scryfall.com/bulk-data
MOCK_SCRYFALL_API_RESPONSE = {
    "object": "list",
    "has_more": False,
    "data": [
        {
            "object": "bulk_data",
            "id": "27bf3214-1271-490b-bdfe-c0be6c23d02e",
            "type": "oracle_cards",
            "jsonl_download_uri": "https://data.scryfall.io/oracle-cards/oracle-cards.jsonl.gz",
        },
        {
            "object": "bulk_data",
            "id": "e2ef41e3-5778-4bc2-af3f-78eca4dd9c23",
            "type": "default_cards",
            "jsonl_download_uri": "https://data.scryfall.io/default-cards/default-cards.jsonl.gz",
        },
        {
            "object": "bulk_data",
            "id": "06f54c0b-ab9c-452d-b35a-8297db5eb940",
            "type": "rulings",
            "jsonl_download_uri": "https://data.scryfall.io/rulings/rulings.jsonl.gz",
        }
    ]
}

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

@pytest.mark.asyncio
async def test_sync_with_scryfall_jsonl_gz_metadata(tmp_path):
    db = Database(tmp_path / "test.db")
    db.init_schema()
    vec_store = VectorStore(tmp_path / "lancedb")

    card_line_1 = json.dumps({"name": "Black Lotus", "mana_cost": "{0}", "type_line": "Artifact", "oracle_text": "{T}, Sacrifice Black Lotus: Add three mana of any one color."})
    card_line_2 = json.dumps({"name": "Counterspell", "mana_cost": "{U}{U}", "type_line": "Instant", "oracle_text": "Counter target spell."})
    cards_jsonl = f"{card_line_1}\n{card_line_2}\n"
    gzipped_cards = gzip.compress(cards_jsonl.encode("utf-8"))

    ruling_line = json.dumps({"oracle_id": "lotus-id", "published_at": "2020-01-01", "comment": "Mana ability ruling."})
    gzipped_rulings = gzip.compress(ruling_line.encode("utf-8"))

    with patch("juuudge.ingest.sync.download_file") as mock_dl:
        mock_dl.side_effect = [
            MOCK_CR.encode("utf-8"),                               # CR text
            json.dumps(MOCK_SCRYFALL_API_RESPONSE).encode("utf-8"), # Scryfall bulk metadata
            gzipped_cards,                                         # Gzipped JSONL cards
            gzipped_rulings                                        # Gzipped JSONL rulings
        ]
        
        await sync_all_data(db, vec_store, cache_dir=tmp_path / "cache")

        lotus = db.get_card_by_name("Black Lotus")
        assert lotus is not None
        assert lotus.mana_cost == "{0}"

        cs = db.get_card_by_name("Counterspell")
        assert cs is not None
        assert cs.mana_cost == "{U}{U}"
