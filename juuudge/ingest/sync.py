from pathlib import Path
from typing import Callable, Optional, List, Dict, Any
import json
import gzip
import httpx
from juuudge.storage.db import Database
from juuudge.storage.vector import VectorStore
from juuudge.ingest.cr_parser import parse_comprehensive_rules
from juuudge.ingest.card_parser import parse_scryfall_cards
from juuudge.logger import get_logger
from juuudge.constants import (
    WOTC_CR_URL,
    SCRYFALL_BULK_API_URL,
    USER_AGENT,
    HTTP_DEFAULT_TIMEOUT,
    CR_FILENAME,
    CARDS_FILENAME,
    RULINGS_FILENAME,
)

logger = get_logger("sync")
SCRYFALL_BULK_API = SCRYFALL_BULK_API_URL

async def download_file(url: str, on_progress: Optional[Callable[[str], None]] = None) -> bytes:
    logger.debug(f"Downloading from {url}")
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json, text/plain, */*"
    }
    async with httpx.AsyncClient(timeout=HTTP_DEFAULT_TIMEOUT, follow_redirects=True, headers=headers) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        logger.debug(f"Downloaded {len(resp.content)} bytes from {url}")
        return resp.content

def parse_downloaded_data(data_bytes: bytes) -> List[Dict[str, Any]]:
    """Parse downloaded bytes that may be gzipped, JSON array, or JSON Lines (jsonl)."""
    if data_bytes.startswith(b"\x1f\x8b"):
        data_bytes = gzip.decompress(data_bytes)

    text = data_bytes.decode("utf-8", errors="ignore").strip()
    if not text:
        return []

    # Try parsing as standard JSON array or object
    if text.startswith("["):
        try:
            parsed = json.loads(text)
            if isinstance(parsed, list):
                return parsed
        except json.JSONDecodeError:
            pass
    elif text.startswith("{"):
        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict) and "data" in parsed and isinstance(parsed["data"], list):
                return parsed["data"]
            elif isinstance(parsed, dict) and not text.count("\n"):
                return [parsed]
        except json.JSONDecodeError:
            pass

    # Try parsing as JSON Lines (jsonl: one JSON object per line)
    records: List[Dict[str, Any]] = []
    for line in text.splitlines():
        line = line.strip()
        if line:
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return records

async def sync_all_data(
    db: Database,
    vec_store: VectorStore,
    cache_dir: Path,
    on_progress: Optional[Callable[[str], None]] = None
):
    logger.info("Starting sync_all_data workflow")
    cache_dir.mkdir(parents=True, exist_ok=True)

    if on_progress:
        on_progress("Downloading Comprehensive Rules from Wizards of the Coast...")
    cr_bytes = await download_file(WOTC_CR_URL, on_progress)
    (cache_dir / CR_FILENAME).write_bytes(cr_bytes)
    cr_text = cr_bytes.decode("utf-8", errors="ignore")

    if on_progress:
        on_progress("Parsing Comprehensive Rules & Glossary...")
    rules, glossary = parse_comprehensive_rules(cr_text)
    logger.info(f"Parsed {len(rules)} rules and {len(glossary)} glossary terms from CR")
    db.insert_rules(rules)
    db.insert_glossary(glossary)

    if on_progress:
        on_progress("Generating Vector Embeddings for Comprehensive Rules...")
    vec_store.index_rules(rules)
    vec_store.index_glossary(glossary)

    if on_progress:
        on_progress("Fetching Scryfall bulk cards export metadata...")
    bulk_meta_bytes = await download_file(SCRYFALL_BULK_API_URL)
    bulk_meta = json.loads(bulk_meta_bytes)
    bulk_data_list = bulk_meta.get("data", []) if isinstance(bulk_meta, dict) else []

    # Resolve card export URL (prefer default_cards, fallback to oracle_cards or all_cards)
    cards_entry = next(
        (item for item in bulk_data_list if item.get("type") == "default_cards"),
        next(
            (item for item in bulk_data_list if item.get("type") == "oracle_cards"),
            next(
                (item for item in bulk_data_list if item.get("type") == "all_cards"),
                None
            )
        )
    )
    if not cards_entry:
        logger.error("No valid card export found in Scryfall bulk metadata")
        raise ValueError("No valid card export found in Scryfall bulk metadata")

    cards_url = cards_entry.get("download_uri") or cards_entry.get("jsonl_download_uri") or cards_entry.get("uri")
    if not cards_url:
        logger.error(f"No download URL found for card export: {cards_entry}")
        raise ValueError(f"No download URL found for card export: {cards_entry}")

    # Resolve rulings export URL
    rulings_entry = next(
        (item for item in bulk_data_list if item.get("type") == "rulings"),
        None
    )
    rulings_url = (
        rulings_entry.get("download_uri") or rulings_entry.get("jsonl_download_uri") or rulings_entry.get("uri")
        if rulings_entry else None
    )

    if on_progress:
        on_progress("Downloading Scryfall bulk cards data...")
    cards_bytes = await download_file(cards_url, on_progress)
    (cache_dir / CARDS_FILENAME).write_bytes(cards_bytes)
    cards_data = parse_downloaded_data(cards_bytes)
    logger.info(f"Downloaded and parsed {len(cards_data)} card objects")

    rulings_data = []
    if rulings_url:
        if on_progress:
            on_progress("Downloading Scryfall Gatherer rulings data...")
        rulings_bytes = await download_file(rulings_url, on_progress)
        (cache_dir / RULINGS_FILENAME).write_bytes(rulings_bytes)
        rulings_data = parse_downloaded_data(rulings_bytes)
        logger.info(f"Downloaded and parsed {len(rulings_data)} rulings objects")

    if on_progress:
        on_progress("Indexing cards and rulings in local SQLite...")
    cards = parse_scryfall_cards(cards_data, rulings_data)
    logger.info(f"Parsed {len(cards)} unique cards with associated rulings")
    db.insert_cards(cards)

    if on_progress:
        on_progress("Sync completed successfully!")
    logger.info("sync_all_data finished successfully")
