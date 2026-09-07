from pathlib import Path
from typing import Callable, Optional
import json
import httpx
from juuudge.storage.db import Database
from juuudge.storage.vector import VectorStore
from juuudge.ingest.cr_parser import parse_comprehensive_rules
from juuudge.ingest.card_parser import parse_scryfall_cards

WOTC_CR_URL = "https://media.wizards.com/2024/downloads/MagicCompRules.txt"
SCRYFALL_BULK_API = "https://api.scryfall.com/bulk-data"

async def download_file(url: str, on_progress: Optional[Callable[[str], None]] = None) -> bytes:
    headers = {
        "User-Agent": "juuudge/0.1.0 (https://github.com/psi-mon/juuudge)",
        "Accept": "application/json, text/plain, */*"
    }
    async with httpx.AsyncClient(timeout=180.0, follow_redirects=True, headers=headers) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.content

async def sync_all_data(
    db: Database,
    vec_store: VectorStore,
    cache_dir: Path,
    on_progress: Optional[Callable[[str], None]] = None
):
    cache_dir.mkdir(parents=True, exist_ok=True)

    if on_progress:
        on_progress("Downloading Comprehensive Rules from Wizards of the Coast...")
    cr_bytes = await download_file(WOTC_CR_URL, on_progress)
    (cache_dir / "MagicCompRules.txt").write_bytes(cr_bytes)
    cr_text = cr_bytes.decode("utf-8", errors="ignore")

    if on_progress:
        on_progress("Parsing Comprehensive Rules & Glossary...")
    rules, glossary = parse_comprehensive_rules(cr_text)
    db.insert_rules(rules)
    db.insert_glossary(glossary)

    if on_progress:
        on_progress("Generating Vector Embeddings for Comprehensive Rules...")
    vec_store.index_rules(rules)
    vec_store.index_glossary(glossary)

    if on_progress:
        on_progress("Fetching Scryfall bulk cards export metadata...")
    bulk_meta_bytes = await download_file(SCRYFALL_BULK_API)
    bulk_meta = json.loads(bulk_meta_bytes)
    default_cards_url = next(
        item["download_uri"] for item in bulk_meta["data"] if item["type"] == "default_cards"
    )
    rulings_url = next(
        (item["download_uri"] for item in bulk_meta["data"] if item["type"] == "rulings"), None
    )

    if on_progress:
        on_progress("Downloading Scryfall bulk cards data...")
    cards_bytes = await download_file(default_cards_url)
    (cache_dir / "default-cards.json").write_bytes(cards_bytes)
    cards_data = json.loads(cards_bytes)

    rulings_data = []
    if rulings_url:
        if on_progress:
            on_progress("Downloading Scryfall Gatherer rulings data...")
        rulings_bytes = await download_file(rulings_url)
        (cache_dir / "rulings.json").write_bytes(rulings_bytes)
        rulings_data = json.loads(rulings_bytes)

    if on_progress:
        on_progress("Indexing cards and rulings in local SQLite...")
    cards = parse_scryfall_cards(cards_data, rulings_data)
    db.insert_cards(cards)

    if on_progress:
        on_progress("Sync completed successfully!")
