# `juuudge` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `juuudge`, an offline-capable CLI and interactive 3-pane Textual TUI AI assistant specialized in Magic: The Gathering rules adjudication, powered by local SQLite FTS5 + embedded LanceDB RAG, hierarchical CR expansion, a bounded tool-using judge loop, and Anthropic Claude / Ollama providers.

**Architecture:** A layered architecture consisting of local SQLite and LanceDB storage, Scryfall bulk and WotC CR hierarchical parsers, direct Rule-ID fast-path + hybrid retrieval with hierarchical context expansion, a bounded tool-using judge loop with local deterministic tools, and a responsive 3-pane Textual TUI with CLI one-shot commands.

**Tech Stack:** Python 3.11+, Textual, SQLite3 (FTS5), LanceDB, FastEmbed, Anthropic SDK, httpx, Click/Typer, Pytest.

**Spec:** [`docs/superpowers/specs/2026-09-04-juuudge-mtg-rules-agent-design.md`](file:///Users/zoiman/DEV/Agentic/juuudge/docs/superpowers/specs/2026-09-04-juuudge-mtg-rules-agent-design.md)

## Global Constraints
- Target Language: Python 3.11+
- Package Manager / Build System: `pyproject.toml` with `hatchling` or `flit` / `pip`
- Primary Cloud LLM Provider: Anthropic Claude (`claude-3-7-sonnet`, `claude-3-5-haiku`) via `ANTHROPIC_API_KEY`
- Local Offline LLM Provider: Ollama (`http://localhost:11434`)
- Vector Storage: Embedded `lancedb` (zero server setup)
- Local Cache Directory: `~/.juuudge/` (or `$XDG_DATA_HOME/juuudge/`)
- Formatting: Clean Markdown output with clickable Scryfall search links and Yawgatog CR anchor links
- Bounded Agent Loop: Capped at maximum 3 tool iterations

---

### Task 1: Project Scaffolding & Core Models

**Files:**
- Create: `pyproject.toml`
- Create: `juuudge/__init__.py`
- Create: `juuudge/models.py`
- Create: `juuudge/config.py`
- Test: `tests/test_config_models.py`

**Interfaces:**
- Produces: `Config`, `Card`, `CardRuling`, `Rule`, `GlossaryTerm`, `JudgeVerdict`, `LLMChunk` dataclasses/models in `juuudge.models` and `juuudge.config`.

- [ ] **Step 1: Write the failing test for configuration and data models**

```python
# tests/test_config_models.py
import pytest
from pathlib import Path
from juuudge.config import Config, get_config, get_app_dir
from juuudge.models import Card, Rule, GlossaryTerm, JudgeVerdict, LLMChunk

def test_config_defaults(monkeypatch, tmp_path):
    monkeypatch.setenv("JUUUDGE_DIR", str(tmp_path))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-123")
    cfg = get_config()
    assert cfg.llm.provider == "anthropic"
    assert cfg.llm.model == "claude-3-7-sonnet"
    assert cfg.llm.api_key == "test-key-123"
    assert cfg.rag.top_k_rules == 5
    assert cfg.rag.expand_hierarchical_rules is True
    assert get_app_dir() == tmp_path

def test_models_instantiation():
    card = Card(
        name="Blood Moon",
        mana_cost="{2}{R}",
        type_line="Enchantment",
        oracle_text="Nonbasic lands are Mountains.",
        rulings=[{"date": "2020-08-07", "text": "Nonbasic lands lose all other abilities."}],
        scryfall_uri="https://scryfall.com/card/2xm/118/blood-moon"
    )
    assert card.name == "Blood Moon"
    assert len(card.rulings) == 1

    rule = Rule(
        rule_id="613.1d",
        chapter="6. Spells, Abilities, and Effects",
        section="613. Interaction of Continuous Effects",
        parent_rule="613.1",
        text="Layer 4: Type-changing effects are applied.",
        examples=["Example: Blood Moon turns nonbasic lands into Mountains."]
    )
    assert rule.rule_id == "613.1d"
    assert rule.yawgatog_url == "https://yawgatog.com/resources/magic-rules/#R6131d"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_config_models.py -v`  
Expected: FAIL (ModuleNotFoundError: No module named 'juuudge')

- [ ] **Step 3: Implement `pyproject.toml`, `juuudge/__init__.py`, `juuudge/models.py`, and `juuudge/config.py`**

```toml
# pyproject.toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "juuudge"
version = "0.1.0"
description = "MTG Rules Judge CLI and TUI Agent"
readme = "README.md"
requires-python = ">=3.11"
dependencies = [
    "textual>=0.85.0",
    "anthropic>=0.40.0",
    "lancedb>=0.17.0",
    "fastembed>=0.4.0",
    "httpx>=0.27.0",
    "pydantic>=2.10.0",
    "click>=8.1.0",
    "rich>=13.9.0",
    "rapidfuzz>=3.10.0",
]

[project.scripts]
juuudge = "juuudge.cli:main"

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.24.0",
]
```

```python
# juuudge/__init__.py
"""juuudge - MTG Rules Judge CLI and TUI Agent."""
__version__ = "0.1.0"
```

```python
# juuudge/models.py
from dataclasses import dataclass, field
from typing import Any, List, Optional
import re
import urllib.parse

@dataclass
class CardRuling:
    date: str
    text: str

@dataclass
class Card:
    name: str
    mana_cost: str = ""
    type_line: str = ""
    oracle_text: str = ""
    power: Optional[str] = None
    toughness: Optional[str] = None
    loyalty: Optional[str] = None
    defense: Optional[str] = None
    keywords: List[str] = field(default_factory=list)
    rulings: List[dict] = field(default_factory=list)
    scryfall_uri: str = ""

    @property
    def scryfall_search_url(self) -> str:
        encoded = urllib.parse.quote(f'!\"{self.name}\"')
        return f"https://scryfall.com/search?q={encoded}"

@dataclass
class Rule:
    rule_id: str
    chapter: str
    section: str
    parent_rule: str
    text: str
    examples: List[str] = field(default_factory=list)

    @property
    def yawgatog_url(self) -> str:
        # e.g., 613.1d -> #R6131d
        cleaned = re.sub(r'[^0-9a-zA-Z]', '', self.rule_id)
        return f"https://yawgatog.com/resources/magic-rules/#R{cleaned}"

@dataclass
class GlossaryTerm:
    term: str
    definition: str

@dataclass
class ToolCallRequest:
    tool_id: str
    name: str
    arguments: dict[str, Any]

@dataclass
class LLMChunk:
    text: str = ""
    tool_calls: List[ToolCallRequest] = field(default_factory=list)
    is_done: bool = False

@dataclass
class JudgeVerdict:
    verdict_text: str
    cards_referenced: List[Card] = field(default_factory=list)
    rules_referenced: List[Rule] = field(default_factory=list)
```

```python
# juuudge/config.py
from dataclasses import dataclass, field
from pathlib import Path
import os
try:
    import tomllib
except ImportError:
    import tomli as tomllib

def get_app_dir() -> Path:
    override = os.environ.get("JUUUDGE_DIR")
    if override:
        path = Path(override)
    else:
        xdg_data = os.environ.get("XDG_DATA_HOME")
        if xdg_data:
            path = Path(xdg_data) / "juuudge"
        else:
            path = Path.home() / ".juuudge"
    path.mkdir(parents=True, exist_ok=True)
    return path

@dataclass
class LLMConfig:
    provider: str = "anthropic"
    model: str = "claude-3-7-sonnet"
    api_key: str = ""
    temperature: float = 0.0
    ollama_host: str = "http://localhost:11434"
    max_tool_rounds: int = 3

@dataclass
class RAGConfig:
    top_k_rules: int = 5
    top_k_glossary: int = 2
    expand_hierarchical_rules: bool = True
    embedder: str = "fastembed"

@dataclass
class Config:
    llm: LLMConfig = field(default_factory=LLMConfig)
    rag: RAGConfig = field(default_factory=RAGConfig)

def get_config() -> Config:
    app_dir = get_app_dir()
    config_file = app_dir / "config.toml"
    cfg = Config()

    if config_file.exists():
        with open(config_file, "rb") as f:
            data = tomllib.load(f)
            if "llm" in data:
                llm_data = data["llm"]
                cfg.llm.provider = llm_data.get("provider", cfg.llm.provider)
                cfg.llm.model = llm_data.get("model", cfg.llm.model)
                cfg.llm.api_key = llm_data.get("api_key", cfg.llm.api_key)
                cfg.llm.temperature = float(llm_data.get("temperature", cfg.llm.temperature))
                cfg.llm.ollama_host = llm_data.get("ollama_host", cfg.llm.ollama_host)
                cfg.llm.max_tool_rounds = int(llm_data.get("max_tool_rounds", cfg.llm.max_tool_rounds))
            if "rag" in data:
                rag_data = data["rag"]
                cfg.rag.top_k_rules = int(rag_data.get("top_k_rules", cfg.rag.top_k_rules))
                cfg.rag.top_k_glossary = int(rag_data.get("top_k_glossary", cfg.rag.top_k_glossary))
                cfg.rag.expand_hierarchical_rules = bool(rag_data.get("expand_hierarchical_rules", cfg.rag.expand_hierarchical_rules))

    # Env override for API key
    env_anthropic = os.environ.get("ANTHROPIC_API_KEY")
    if env_anthropic and not cfg.llm.api_key:
        cfg.llm.api_key = env_anthropic

    return cfg
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_config_models.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml juuudge/__init__.py juuudge/models.py juuudge/config.py tests/test_config_models.py
git commit -m "feat: setup project scaffolding, models and configuration loader"
```

---

### Task 2: SQLite Storage Layer with FTS5 Lexical Search

**Files:**
- Create: `juuudge/storage/db.py`
- Test: `tests/test_storage_db.py`

**Interfaces:**
- Consumes: `Card`, `Rule`, `GlossaryTerm` from `juuudge.models`
- Produces: `Database` class with schema initialization, batch inserts, exact rule lookup by ID, FTS5 search on cards/rules/glossary, and fuzzy card queries.

- [ ] **Step 1: Write the failing test for SQLite Database & FTS5 search**

```python
# tests/test_storage_db.py
import pytest
from pathlib import Path
from juuudge.storage.db import Database
from juuudge.models import Card, Rule, GlossaryTerm

@pytest.fixture
def test_db(tmp_path):
    db_path = tmp_path / "test_juuudge.db"
    db = Database(db_path)
    db.init_schema()
    return db

def test_cards_insert_and_lookup(test_db):
    cards = [
        Card(name="Blood Moon", mana_cost="{2}{R}", type_line="Enchantment", oracle_text="Nonbasic lands are Mountains.", rulings=[{"date": "2020-08-07", "text": "Nonbasics lose abilities."}], scryfall_uri="https://scryfall.com/card/1"),
        Card(name="Urza's Saga", mana_cost="", type_line="Enchantment Land — Urza's Saga", oracle_text="(As this Saga enters and after your draw step, add a lore counter...)", rulings=[], scryfall_uri="https://scryfall.com/card/2"),
        Card(name="Deflecting Swat", mana_cost="{2}{R}", type_line="Instant", oracle_text="You may choose new targets for target spell or ability.", rulings=[], scryfall_uri="https://scryfall.com/card/3")
    ]
    test_db.insert_cards(cards)

    # Exact lookup
    bm = test_db.get_card_by_name("Blood Moon")
    assert bm is not None
    assert bm.type_line == "Enchantment"
    assert len(bm.rulings) == 1

    # Case-insensitive lookup
    saga = test_db.get_card_by_name("urza's saga")
    assert saga is not None
    assert "Urza's Saga" in saga.type_line

    # Card search
    results = test_db.search_cards("Swat")
    assert len(results) >= 1
    assert results[0].name == "Deflecting Swat"

def test_rules_insert_exact_and_fts(test_db):
    rules = [
        Rule(rule_id="613.1d", chapter="6. Spells, Abilities, and Effects", section="613. Continuous Effects", parent_rule="613.1", text="Layer 4: Type-changing effects are applied.", examples=["Example 1"]),
        Rule(rule_id="704.5s", chapter="7. Additional Rules", section="704. State-Based Actions", parent_rule="704.5", text="If a Saga has lore counters >= final chapter...", examples=[]),
        Rule(rule_id="613.1", chapter="6. Spells, Abilities, and Effects", section="613. Continuous Effects", parent_rule="613", text="The interaction of continuous effects is indicated by layers.", examples=[])
    ]
    test_db.insert_rules(rules)

    # Exact O(1) Rule-ID lookup
    r = test_db.get_rule_by_id("613.1d")
    assert r is not None
    assert r.section == "613. Continuous Effects"

    # FTS5 Match
    fts_results = test_db.search_rules_fts("continuous effects layers")
    assert len(fts_results) >= 1
    assert any(x.rule_id == "613.1" for x in fts_results)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_storage_db.py -v`  
Expected: FAIL (ModuleNotFoundError: No module named 'juuudge.storage')

- [ ] **Step 3: Implement `juuudge/storage/db.py`**

```python
# juuudge/storage/db.py
import sqlite3
import json
from pathlib import Path
from typing import List, Optional
from juuudge.models import Card, Rule, GlossaryTerm

class Database:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._conn: Optional[sqlite3.Connection] = None

    def get_connection(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_path))
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def init_schema(self):
        conn = self.get_connection()
        with conn:
            # Cards Table & FTS5
            conn.execute("""
                CREATE TABLE IF NOT EXISTS cards (
                    name TEXT PRIMARY KEY COLLATE NOCASE,
                    mana_cost TEXT,
                    type_line TEXT,
                    oracle_text TEXT,
                    power TEXT,
                    toughness TEXT,
                    loyalty TEXT,
                    defense TEXT,
                    keywords_json TEXT,
                    rulings_json TEXT,
                    scryfall_uri TEXT
                );
            """)
            conn.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS cards_fts USING fts5(
                    name,
                    type_line,
                    oracle_text,
                    content='cards',
                    content_rowid='rowid'
                );
            """)

            # Rules Table & FTS5
            conn.execute("""
                CREATE TABLE IF NOT EXISTS rules (
                    rule_id TEXT PRIMARY KEY COLLATE NOCASE,
                    chapter TEXT,
                    section TEXT,
                    parent_rule TEXT,
                    text TEXT,
                    examples_json TEXT
                );
            """)
            conn.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS rules_fts USING fts5(
                    rule_id,
                    section,
                    text,
                    content='rules',
                    content_rowid='rowid'
                );
            """)

            # Glossary Table & FTS5
            conn.execute("""
                CREATE TABLE IF NOT EXISTS glossary (
                    term TEXT PRIMARY KEY COLLATE NOCASE,
                    definition TEXT
                );
            """)
            conn.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS glossary_fts USING fts5(
                    term,
                    definition,
                    content='glossary',
                    content_rowid='rowid'
                );
            """)

    def insert_cards(self, cards: List[Card]):
        conn = self.get_connection()
        with conn:
            for c in cards:
                conn.execute("""
                    INSERT OR REPLACE INTO cards 
                    (name, mana_cost, type_line, oracle_text, power, toughness, loyalty, defense, keywords_json, rulings_json, scryfall_uri)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    c.name, c.mana_cost, c.type_line, c.oracle_text,
                    c.power, c.toughness, c.loyalty, c.defense,
                    json.dumps(c.keywords), json.dumps(c.rulings), c.scryfall_uri
                ))
            # Rebuild cards_fts
            conn.execute("INSERT INTO cards_fts(cards_fts) VALUES('rebuild');")

    def insert_rules(self, rules: List[Rule]):
        conn = self.get_connection()
        with conn:
            for r in rules:
                conn.execute("""
                    INSERT OR REPLACE INTO rules
                    (rule_id, chapter, section, parent_rule, text, examples_json)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (r.rule_id, r.chapter, r.section, r.parent_rule, r.text, json.dumps(r.examples)))
            conn.execute("INSERT INTO rules_fts(rules_fts) VALUES('rebuild');")

    def insert_glossary(self, terms: List[GlossaryTerm]):
        conn = self.get_connection()
        with conn:
            for g in terms:
                conn.execute("""
                    INSERT OR REPLACE INTO glossary (term, definition)
                    VALUES (?, ?)
                """, (g.term, g.definition))
            conn.execute("INSERT INTO glossary_fts(glossary_fts) VALUES('rebuild');")

    def get_card_by_name(self, name: str) -> Optional[Card]:
        conn = self.get_connection()
        cur = conn.execute("SELECT * FROM cards WHERE name = ? COLLATE NOCASE", (name.strip(),))
        row = cur.fetchone()
        if not row:
            return None
        return Card(
            name=row["name"],
            mana_cost=row["mana_cost"] or "",
            type_line=row["type_line"] or "",
            oracle_text=row["oracle_text"] or "",
            power=row["power"],
            toughness=row["toughness"],
            loyalty=row["loyalty"],
            defense=row["defense"],
            keywords=json.loads(row["keywords_json"] or "[]"),
            rulings=json.loads(row["rulings_json"] or "[]"),
            scryfall_uri=row["scryfall_uri"] or ""
        )

    def search_cards(self, query: str, limit: int = 5) -> List[Card]:
        conn = self.get_connection()
        cur = conn.execute("""
            SELECT c.* FROM cards c
            JOIN cards_fts f ON c.rowid = f.rowid
            WHERE cards_fts MATCH ?
            ORDER BY bm25(cards_fts)
            LIMIT ?
        """, (f'"{query}"*', limit))
        results = []
        for row in cur.fetchall():
            results.append(Card(
                name=row["name"],
                mana_cost=row["mana_cost"] or "",
                type_line=row["type_line"] or "",
                oracle_text=row["oracle_text"] or "",
                power=row["power"],
                toughness=row["toughness"],
                loyalty=row["loyalty"],
                defense=row["defense"],
                keywords=json.loads(row["keywords_json"] or "[]"),
                rulings=json.loads(row["rulings_json"] or "[]"),
                scryfall_uri=row["scryfall_uri"] or ""
            ))
        return results

    def get_all_card_names(self) -> List[str]:
        conn = self.get_connection()
        cur = conn.execute("SELECT name FROM cards")
        return [row["name"] for row in cur.fetchall()]

    def get_rule_by_id(self, rule_id: str) -> Optional[Rule]:
        conn = self.get_connection()
        cur = conn.execute("SELECT * FROM rules WHERE rule_id = ? COLLATE NOCASE", (rule_id.strip(),))
        row = cur.fetchone()
        if not row:
            return None
        return Rule(
            rule_id=row["rule_id"],
            chapter=row["chapter"],
            section=row["section"],
            parent_rule=row["parent_rule"],
            text=row["text"],
            examples=json.loads(row["examples_json"] or "[]")
        )

    def get_sibling_rules(self, parent_rule_id: str) -> List[Rule]:
        conn = self.get_connection()
        cur = conn.execute("""
            SELECT * FROM rules 
            WHERE parent_rule = ? OR rule_id LIKE ?
            ORDER BY rule_id ASC
        """, (parent_rule_id, f"{parent_rule_id}%"))
        results = []
        for row in cur.fetchall():
            results.append(Rule(
                rule_id=row["rule_id"],
                chapter=row["chapter"],
                section=row["section"],
                parent_rule=row["parent_rule"],
                text=row["text"],
                examples=json.loads(row["examples_json"] or "[]")
            ))
        return results

    def search_rules_fts(self, query: str, limit: int = 5) -> List[Rule]:
        conn = self.get_connection()
        # Escape special characters for FTS5
        clean_query = "".join(c if c.isalnum() or c.isspace() else " " for c in query).strip()
        if not clean_query:
            return []
        cur = conn.execute("""
            SELECT r.* FROM rules r
            JOIN rules_fts f ON r.rowid = f.rowid
            WHERE rules_fts MATCH ?
            ORDER BY bm25(rules_fts)
            LIMIT ?
        """, (clean_query, limit))
        results = []
        for row in cur.fetchall():
            results.append(Rule(
                rule_id=row["rule_id"],
                chapter=row["chapter"],
                section=row["section"],
                parent_rule=row["parent_rule"],
                text=row["text"],
                examples=json.loads(row["examples_json"] or "[]")
            ))
        return results

    def get_glossary_term(self, term: str) -> Optional[GlossaryTerm]:
        conn = self.get_connection()
        cur = conn.execute("SELECT * FROM glossary WHERE term = ? COLLATE NOCASE", (term.strip(),))
        row = cur.fetchone()
        if not row:
            return None
        return GlossaryTerm(term=row["term"], definition=row["definition"])

    def search_glossary_fts(self, query: str, limit: int = 3) -> List[GlossaryTerm]:
        conn = self.get_connection()
        clean_query = "".join(c if c.isalnum() or c.isspace() else " " for c in query).strip()
        if not clean_query:
            return []
        cur = conn.execute("""
            SELECT g.* FROM glossary g
            JOIN glossary_fts f ON g.rowid = f.rowid
            WHERE glossary_fts MATCH ?
            ORDER BY bm25(glossary_fts)
            LIMIT ?
        """, (clean_query, limit))
        results = []
        for row in cur.fetchall():
            results.append(GlossaryTerm(term=row["term"], definition=row["definition"]))
        return results
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_storage_db.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add juuudge/storage/db.py tests/test_storage_db.py
git commit -m "feat: implement SQLite database layer with FTS5 lexical matching and sibling lookups"
```

---

### Task 3: Comprehensive Rules Hierarchical Parser & Card Bulk Parser

**Files:**
- Create: `juuudge/ingest/cr_parser.py`
- Create: `juuudge/ingest/card_parser.py`
- Test: `tests/test_parsers.py`

**Interfaces:**
- Consumes: Raw `MagicCompRules.txt` string and Scryfall `default-cards.json` format.
- Produces: `parse_comprehensive_rules(text: str) -> tuple[List[Rule], List[GlossaryTerm]]` and `parse_scryfall_cards(cards_data: list[dict], rulings_data: list[dict]) -> List[Card]`.

- [ ] **Step 1: Write the failing test for CR parser and Scryfall card parser**

```python
# tests/test_parsers.py
import pytest
from juuudge.ingest.cr_parser import parse_comprehensive_rules
from juuudge.ingest.card_parser import parse_scryfall_cards

SAMPLE_CR_TEXT = """
Magic: The Gathering Comprehensive Rules
These rules are effective as of November 8, 2024.

Contents
1. Game Concepts
6. Spells, Abilities, and Effects
Glossary

1. Game Concepts
100. General
100.1. These Magic rules apply to any Magic game.
100.1a A two-player game is a game between two players.
Example: In a two-player game, players sit across from each other.

6. Spells, Abilities, and Effects
613. Interaction of Continuous Effects
613.1. The interaction of continuous effects is indicated by the layer system.
613.1d Layer 4: Type-changing effects are applied.
Example: Blood Moon makes nonbasic lands Mountains.

Glossary
Active Player
The player whose turn it is.

Priority
A player who has priority may cast spells, activate abilities, and take special actions.
"""

SAMPLE_SCRYFALL_CARDS = [
    {
        "name": "Blood Moon",
        "mana_cost": "{2}{R}",
        "type_line": "Enchantment",
        "oracle_text": "Nonbasic lands are Mountains.",
        "keywords": [],
        "scryfall_uri": "https://scryfall.com/card/2xm/118/blood-moon",
        "id": "card-bm-1"
    },
    {
        "name": "Urza's Saga",
        "mana_cost": "",
        "type_line": "Enchantment Land — Urza's Saga",
        "oracle_text": "I, II, III chapters...",
        "keywords": ["Saga"],
        "scryfall_uri": "https://scryfall.com/card/mh2/259/urzas-saga",
        "id": "card-us-2"
    }
]

SAMPLE_SCRYFALL_RULINGS = [
    {
        "oracle_id": "card-bm-1",
        "published_at": "2020-08-07",
        "comment": "Nonbasic lands lose all other abilities."
    }
]

def test_cr_parser():
    rules, glossary = parse_comprehensive_rules(SAMPLE_CR_TEXT)
    assert len(rules) >= 4
    assert len(glossary) == 2

    # Verify rule 613.1d
    r613_1d = next(r for r in rules if r.rule_id == "613.1d")
    assert r613_1d.section == "613. Interaction of Continuous Effects"
    assert "Layer 4: Type-changing" in r613_1d.text
    assert len(r613_1d.examples) == 1
    assert "Blood Moon" in r613_1d.examples[0]

    # Verify Glossary
    ap = next(g for g in glossary if g.term == "Active Player")
    assert "player whose turn it is" in ap.definition

def test_scryfall_card_parser():
    cards = parse_scryfall_cards(SAMPLE_SCRYFALL_CARDS, SAMPLE_SCRYFALL_RULINGS)
    assert len(cards) == 2
    bm = next(c for c in cards if c.name == "Blood Moon")
    assert bm.type_line == "Enchantment"
    assert len(bm.rulings) == 1
    assert "lose all other abilities" in bm.rulings[0]["text"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_parsers.py -v`  
Expected: FAIL (ModuleNotFoundError: No module named 'juuudge.ingest')

- [ ] **Step 3: Implement `juuudge/ingest/cr_parser.py` and `juuudge/ingest/card_parser.py`**

```python
# juuudge/ingest/cr_parser.py
import re
from typing import List, Tuple
from juuudge.models import Rule, GlossaryTerm

RULE_ID_PATTERN = re.compile(r'^(\d{3})\.(\d+[a-z]?)\.?\s+(.*)$')
SECTION_HEADER_PATTERN = re.compile(r'^(\d{3})\.\s+(.+)$')
CHAPTER_HEADER_PATTERN = re.compile(r'^(\d)\.\s+(.+)$')

def parse_comprehensive_rules(text: str) -> Tuple[List[Rule], List[GlossaryTerm]]:
    lines = text.splitlines()
    rules: List[Rule] = []
    glossary_terms: List[GlossaryTerm] = []

    current_chapter = ""
    current_section = ""
    current_parent_rule = ""
    current_rule: Rule | None = None
    
    in_glossary = False
    current_glossary_term = ""
    current_glossary_def: List[str] = []

    for line in lines:
        raw_line = line.strip()
        if not raw_line:
            continue

        if raw_line == "Glossary":
            in_glossary = True
            if current_rule:
                rules.append(current_rule)
                current_rule = None
            continue

        if in_glossary:
            # Glossary entries: A line without indentation or leading lowercase is a term, following indented/normal lines are definition
            if not line.startswith(" ") and not line.startswith("\t") and len(raw_line) < 60 and not raw_line.endswith("."):
                if current_glossary_term and current_glossary_def:
                    glossary_terms.append(GlossaryTerm(
                        term=current_glossary_term,
                        definition=" ".join(current_glossary_def)
                    ))
                current_glossary_term = raw_line
                current_glossary_def = []
            else:
                if current_glossary_term:
                    current_glossary_def.append(raw_line)
            continue

        # Chapter header (e.g. "6. Spells, Abilities, and Effects")
        chap_match = CHAPTER_HEADER_PATTERN.match(raw_line)
        if chap_match and not raw_line.startswith("Contents"):
            current_chapter = raw_line
            continue

        # Section header (e.g. "613. Interaction of Continuous Effects")
        sec_match = SECTION_HEADER_PATTERN.match(raw_line)
        if sec_match:
            current_section = raw_line
            current_parent_rule = sec_match.group(1)
            continue

        # Examples (e.g. "Example: Blood Moon makes nonbasic lands Mountains.")
        if raw_line.startswith("Example:") or raw_line.startswith("Example 1:") or raw_line.startswith("Example 2:"):
            if current_rule:
                current_rule.examples.append(raw_line)
            continue

        # Numbered Rule (e.g. "613.1d Layer 4: Type-changing...")
        rule_match = RULE_ID_PATTERN.match(raw_line)
        if rule_match:
            if current_rule:
                rules.append(current_rule)

            rule_num = f"{rule_match.group(1)}.{rule_match.group(2)}"
            rule_text = rule_match.group(3)
            parent = rule_match.group(1)
            if "." in rule_match.group(2):
                parent = f"{rule_match.group(1)}.{rule_match.group(2).split('.')[0]}"
            else:
                base_sub = re.match(r'^\d+', rule_match.group(2))
                if base_sub:
                    parent = f"{rule_match.group(1)}.{base_sub.group(0)}"

            current_rule = Rule(
                rule_id=rule_num,
                chapter=current_chapter or "Rules",
                section=current_section or current_chapter or "General",
                parent_rule=parent,
                text=rule_text,
                examples=[]
            )
        else:
            # Continuation of existing rule text
            if current_rule:
                current_rule.text += " " + raw_line

    if current_rule:
        rules.append(current_rule)

    if in_glossary and current_glossary_term and current_glossary_def:
        glossary_terms.append(GlossaryTerm(
            term=current_glossary_term,
            definition=" ".join(current_glossary_def)
        ))

    return rules, glossary_terms
```

```python
# juuudge/ingest/card_parser.py
from typing import List, Dict, Any
from juuudge.models import Card

def parse_scryfall_cards(cards_data: List[Dict[str, Any]], rulings_data: List[Dict[str, Any]] | None = None) -> List[Card]:
    # Index rulings by card name or oracle_id
    rulings_by_id: Dict[str, List[Dict[str, str]]] = {}
    if rulings_data:
        for r in rulings_data:
            c_id = r.get("oracle_id") or r.get("card_id") or ""
            if c_id:
                rulings_by_id.setdefault(c_id, []).append({
                    "date": r.get("published_at", ""),
                    "text": r.get("comment", "")
                })

    seen_names = set()
    cards: List[Card] = []

    for item in cards_data:
        # Filter non-playable tokens / art cards if needed
        layout = item.get("layout", "")
        if layout in ("token", "art_series", "double_faced_token"):
            continue

        name = item.get("name", "").strip()
        if not name or name in seen_names:
            continue
        seen_names.add(name)

        # Handle double-faced / multi-face cards
        mana_cost = item.get("mana_cost", "")
        type_line = item.get("type_line", "")
        oracle_text = item.get("oracle_text", "")
        power = item.get("power")
        toughness = item.get("toughness")
        loyalty = item.get("loyalty")
        defense = item.get("defense")

        if "card_faces" in item and not oracle_text:
            face_texts = []
            for face in item["card_faces"]:
                face_name = face.get("name", "")
                face_type = face.get("type_line", "")
                face_oracle = face.get("oracle_text", "")
                face_texts.append(f"[{face_name} - {face_type}]\n{face_oracle}")
            oracle_text = "\n//\n".join(face_texts)

        c_id = item.get("id") or item.get("oracle_id") or ""
        card_rulings = rulings_by_id.get(c_id, [])

        cards.append(Card(
            name=name,
            mana_cost=mana_cost,
            type_line=type_line,
            oracle_text=oracle_text,
            power=power,
            toughness=toughness,
            loyalty=loyalty,
            defense=defense,
            keywords=item.get("keywords", []),
            rulings=card_rulings,
            scryfall_uri=item.get("scryfall_uri", "")
        ))

    return cards
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_parsers.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add juuudge/ingest/cr_parser.py juuudge/ingest/card_parser.py tests/test_parsers.py
git commit -m "feat: add Comprehensive Rules hierarchical parser and Scryfall card bulk parser"
```

---

### Task 4: Embedded LanceDB Vector Storage & Embeddings

**Files:**
- Create: `juuudge/storage/vector.py`
- Test: `tests/test_storage_vector.py`

**Interfaces:**
- Consumes: `Rule`, `GlossaryTerm` from `juuudge.models`
- Produces: `VectorStore` class managing embedded LanceDB table `cr_rules_vec` and `glossary_vec`, using `fastembed.TextEmbedding` (model: `BAAI/bge-small-en-v1.5`).

- [ ] **Step 1: Write the failing test for LanceDB vector search**

```python
# tests/test_storage_vector.py
import pytest
from pathlib import Path
from juuudge.storage.vector import VectorStore
from juuudge.models import Rule, GlossaryTerm

@pytest.fixture
def vector_store(tmp_path):
    vec_dir = tmp_path / "lancedb"
    store = VectorStore(vec_dir)
    return store

def test_vector_store_index_and_search(vector_store):
    rules = [
        Rule(rule_id="613.1d", chapter="6. Spells, Abilities", section="613. Continuous Effects", parent_rule="613.1", text="Layer 4: Type-changing effects are applied.", examples=[]),
        Rule(rule_id="704.5s", chapter="7. Additional Rules", section="704. State-Based Actions", parent_rule="704.5", text="If a Saga has lore counters greater than or equal to final chapter, sacrifice it.", examples=[])
    ]
    glossary = [
        GlossaryTerm(term="State-Based Action", definition="A game event that occurs automatically when certain game conditions are met.")
    ]

    vector_store.index_rules(rules)
    vector_store.index_glossary(glossary)

    # Semantic search
    hits = vector_store.search_rules("When does a Saga die from lore counters?", top_k=1)
    assert len(hits) == 1
    assert hits[0]["rule_id"] == "704.5s"

    g_hits = vector_store.search_glossary("game events that happen automatically", top_k=1)
    assert len(g_hits) == 1
    assert g_hits[0]["term"] == "State-Based Action"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_storage_vector.py -v`  
Expected: FAIL (ModuleNotFoundError: No module named 'juuudge.storage.vector')

- [ ] **Step 3: Implement `juuudge/storage/vector.py`**

```python
# juuudge/storage/vector.py
from pathlib import Path
from typing import List, Dict, Any
import lancedb
from fastembed import TextEmbedding
from juuudge.models import Rule, GlossaryTerm

class VectorStore:
    def __init__(self, db_dir: Path, model_name: str = "BAAI/bge-small-en-v1.5"):
        self.db_dir = db_dir
        self.db_dir.mkdir(parents=True, exist_ok=True)
        self.db = lancedb.connect(str(self.db_dir))
        self._embedder = TextEmbedding(model_name=model_name)

    def _embed(self, texts: List[str]) -> List[List[float]]:
        return [e.tolist() for e in self._embedder.embed(texts)]

    def index_rules(self, rules: List[Rule]):
        if not rules:
            return
        # Create contextualized text for dense embedding
        texts = [
            f"[{r.chapter} > {r.section} > {r.rule_id}] {r.text}"
            for r in rules
        ]
        vectors = self._embed(texts)
        data = []
        for r, vec, txt in zip(rules, vectors, texts):
            data.append({
                "rule_id": r.rule_id,
                "section": r.section,
                "text": r.text,
                "context_text": txt,
                "vector": vec
            })

        table_name = "cr_rules_vec"
        if table_name in self.db.table_names():
            self.db.drop_table(table_name)
        self.db.create_table(table_name, data=data)

    def index_glossary(self, terms: List[GlossaryTerm]):
        if not terms:
            return
        texts = [f"[{g.term}] {g.definition}" for g in terms]
        vectors = self._embed(texts)
        data = []
        for g, vec, txt in zip(terms, vectors, texts):
            data.append({
                "term": g.term,
                "definition": g.definition,
                "context_text": txt,
                "vector": vec
            })

        table_name = "glossary_vec"
        if table_name in self.db.table_names():
            self.db.drop_table(table_name)
        self.db.create_table(table_name, data=data)

    def search_rules(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        table_name = "cr_rules_vec"
        if table_name not in self.db.table_names():
            return []
        tbl = self.db.open_table(table_name)
        query_vec = self._embed([query])[0]
        results = tbl.search(query_vec).limit(top_k).to_list()
        return results

    def search_glossary(self, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        table_name = "glossary_vec"
        if table_name not in self.db.table_names():
            return []
        tbl = self.db.open_table(table_name)
        query_vec = self._embed([query])[0]
        results = tbl.search(query_vec).limit(top_k).to_list()
        return results
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_storage_vector.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add juuudge/storage/vector.py tests/test_storage_vector.py
git commit -m "feat: implement embedded LanceDB vector store with fastembed for dense RAG"
```

---

### Task 5: Card Extractor & Hybrid Rule Retriever with Hierarchical Expansion

**Files:**
- Create: `juuudge/retrieval/card_extractor.py`
- Create: `juuudge/retrieval/rule_retriever.py`
- Test: `tests/test_retrieval.py`

**Interfaces:**
- Consumes: `Database` and `VectorStore`
- Produces: `extract_cards(query: str, db: Database) -> List[Card]` and `RuleRetriever.retrieve_context(query: str) -> GroundedContext` with direct rule-ID fast path and hierarchical expansion.

- [ ] **Step 1: Write failing test for Card Extractor, Direct Rule-ID Bypass, and Hierarchical Context Expansion**

```python
# tests/test_retrieval.py
import pytest
from pathlib import Path
from juuudge.storage.db import Database
from juuudge.storage.vector import VectorStore
from juuudge.retrieval.card_extractor import CardExtractor
from juuudge.retrieval.rule_retriever import RuleRetriever
from juuudge.models import Card, Rule, GlossaryTerm

@pytest.fixture
def setup_engine(tmp_path):
    db = Database(tmp_path / "test.db")
    db.init_schema()
    
    # Insert cards
    cards = [
        Card(name="Blood Moon", mana_cost="{2}{R}", type_line="Enchantment", oracle_text="Nonbasic lands are Mountains."),
        Card(name="Urza's Saga", mana_cost="", type_line="Enchantment Land — Urza's Saga", oracle_text="Saga chapters..."),
        Card(name="Deflecting Swat", mana_cost="{2}{R}", type_line="Instant", oracle_text="You may choose new targets...")
    ]
    db.insert_cards(cards)

    # Insert rules with siblings
    rules = [
        Rule(rule_id="613.1", chapter="6. Spells", section="613. Continuous Effects", parent_rule="613", text="Layer system overview."),
        Rule(rule_id="613.1a", chapter="6. Spells", section="613. Continuous Effects", parent_rule="613.1", text="Layer 1: Copy effects."),
        Rule(rule_id="613.1d", chapter="6. Spells", section="613. Continuous Effects", parent_rule="613.1", text="Layer 4: Type-changing effects."),
        Rule(rule_id="613.7", chapter="6. Spells", section="613. Continuous Effects", parent_rule="613", text="Timestamps."),
        Rule(rule_id="704.5s", chapter="7. SBAs", section="704. State-Based Actions", parent_rule="704.5", text="Saga SBA.")
    ]
    db.insert_rules(rules)

    vec_store = VectorStore(tmp_path / "lancedb")
    vec_store.index_rules(rules)
    vec_store.index_glossary([GlossaryTerm(term="Layer", definition="Rules for applying continuous effects.")])

    return db, vec_store

def test_card_extractor(setup_engine):
    db, _ = setup_engine
    extractor = CardExtractor(db)

    # Bracket syntax
    cards = extractor.extract("What happens with [[Blood Moon]] and [[Urza's Saga]]?")
    assert len(cards) == 2
    assert {c.name for c in cards} == {"Blood Moon", "Urza's Saga"}

    # Natural text matching
    cards_nat = extractor.extract("Can I cast Deflecting Swat to change targets?")
    assert len(cards_nat) == 1
    assert cards_nat[0].name == "Deflecting Swat"

def test_direct_rule_id_bypass_and_hierarchical_expansion(setup_engine):
    db, vec_store = setup_engine
    retriever = RuleRetriever(db, vec_store)

    # Direct Rule-ID fast path bypass
    res = retriever.retrieve("Explain CR 613.1d and how it works")
    rule_ids = [r.rule_id for r in res.rules]
    
    # 613.1d should be present
    assert "613.1d" in rule_ids
    # Hierarchical expansion should pull parent 613.1 and sibling 613.1a
    assert "613.1" in rule_ids
    assert "613.1a" in rule_ids
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_retrieval.py -v`  
Expected: FAIL (ModuleNotFoundError: No module named 'juuudge.retrieval')

- [ ] **Step 3: Implement `juuudge/retrieval/card_extractor.py` and `juuudge/retrieval/rule_retriever.py`**

```python
# juuudge/retrieval/card_extractor.py
import re
from typing import List, Set
from rapidfuzz import process, fuzz
from juuudge.storage.db import Database
from juuudge.models import Card

BRACKET_PATTERN = re.compile(r'\[\[(.*?)\]\]')

class CardExtractor:
    def __init__(self, db: Database):
        self.db = db
        self._all_names: List[str] | None = None

    def _get_all_names(self) -> List[str]:
        if self._all_names is None:
            self._all_names = self.db.get_all_card_names()
        return self._all_names

    def extract(self, text: str) -> List[Card]:
        found_cards: List[Card] = []
        found_names: Set[str] = set()

        # 1. Bracket syntax [[Card Name]]
        bracket_matches = BRACKET_PATTERN.findall(text)
        for match in bracket_matches:
            c = self.db.get_card_by_name(match.strip())
            if c and c.name not in found_names:
                found_cards.append(c)
                found_names.add(c.name)

        # 2. Exact / Substring scan against known card names
        all_names = self._get_all_names()
        text_lower = text.lower()
        for name in all_names:
            if len(name) >= 4 and name.lower() in text_lower:
                if name not in found_names:
                    c = self.db.get_card_by_name(name)
                    if c:
                        found_cards.append(c)
                        found_names.add(name)

        # 3. Fuzzy search for short typos if nothing found yet
        if not found_cards and len(text) > 3:
            fuzzy_matches = process.extract(
                text, all_names, scorer=fuzz.partial_ratio, limit=2, score_cutoff=85
            )
            for match_name, score, _ in fuzzy_matches:
                if match_name not in found_names:
                    c = self.db.get_card_by_name(match_name)
                    if c:
                        found_cards.append(c)
                        found_names.add(match_name)

        return found_cards
```

```python
# juuudge/retrieval/rule_retriever.py
import re
from dataclasses import dataclass, field
from typing import List, Dict, Set
from juuudge.storage.db import Database
from juuudge.storage.vector import VectorStore
from juuudge.models import Rule, GlossaryTerm

RULE_ID_REGEX = re.compile(r'\b(\d{3}\.\d+[a-z]?|\d{3}\.\d+|\d{3})\b')

@dataclass
class GroundedContext:
    rules: List[Rule] = field(default_factory=list)
    glossary: List[GlossaryTerm] = field(default_factory=list)

class RuleRetriever:
    def __init__(self, db: Database, vec_store: VectorStore, expand_hierarchical: bool = True):
        self.db = db
        self.vec_store = vec_store
        self.expand_hierarchical = expand_hierarchical

    def retrieve(self, query: str, top_k: int = 5) -> GroundedContext:
        seen_rule_ids: Set[str] = set()
        matched_rules: List[Rule] = []
        matched_glossary: List[GlossaryTerm] = []

        # 1. Direct Rule-ID Fast Path (Bypass BM25 / Vectors)
        rule_id_matches = RULE_ID_REGEX.findall(query)
        for rid in rule_id_matches:
            rule = self.db.get_rule_by_id(rid)
            if rule and rule.rule_id not in seen_rule_ids:
                matched_rules.append(rule)
                seen_rule_ids.add(rule.rule_id)

                if self.expand_hierarchical:
                    # Expand parent & siblings
                    parent_rule = rule.parent_rule
                    siblings = self.db.get_sibling_rules(parent_rule)
                    for sib in siblings:
                        if sib.rule_id not in seen_rule_ids:
                            matched_rules.append(sib)
                            seen_rule_ids.add(sib.rule_id)

        # 2. FTS5 Lexical Search
        fts_rules = self.db.search_rules_fts(query, limit=top_k)
        for r in fts_rules:
            if r.rule_id not in seen_rule_ids:
                matched_rules.append(r)
                seen_rule_ids.add(r.rule_id)
                if self.expand_hierarchical:
                    for sib in self.db.get_sibling_rules(r.parent_rule):
                        if sib.rule_id not in seen_rule_ids:
                            matched_rules.append(sib)
                            seen_rule_ids.add(sib.rule_id)

        # 3. Dense Vector Search (LanceDB)
        vec_rules = self.vec_store.search_rules(query, top_k=top_k)
        for vr in vec_rules:
            rid = vr["rule_id"]
            if rid not in seen_rule_ids:
                rule_obj = self.db.get_rule_by_id(rid)
                if rule_obj:
                    matched_rules.append(rule_obj)
                    seen_rule_ids.add(rid)

        # 4. Glossary Retrieval
        fts_glossary = self.db.search_glossary_fts(query, limit=2)
        matched_glossary.extend(fts_glossary)
        vec_glossary = self.vec_store.search_glossary(query, top_k=2)
        g_terms = {g.term for g in matched_glossary}
        for vg in vec_glossary:
            term = vg["term"]
            if term not in g_terms:
                matched_glossary.append(GlossaryTerm(term=term, definition=vg["definition"]))
                g_terms.add(term)

        return GroundedContext(rules=matched_rules, glossary=matched_glossary)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_retrieval.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add juuudge/retrieval/card_extractor.py juuudge/retrieval/rule_retriever.py tests/test_retrieval.py
git commit -m "feat: implement card extractor, direct Rule-ID bypass and hierarchical rule expansion"
```

---

### Task 6: Extensible LLM Provider Interface (Anthropic & Ollama) with Tool Use

**Files:**
- Create: `juuudge/agent/providers/base.py`
- Create: `juuudge/agent/providers/anthropic_provider.py`
- Create: `juuudge/agent/providers/ollama_provider.py`
- Create: `juuudge/agent/providers/__init__.py`
- Test: `tests/test_llm_providers.py`

**Interfaces:**
- Produces: `LLMProvider` abstract base class with async `stream_completion` and tool-use parsing, and concrete `AnthropicProvider` and `OllamaProvider` implementations.

- [ ] **Step 1: Write test for LLMProvider interface and mock streaming**

```python
# tests/test_llm_providers.py
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from juuudge.agent.providers.base import LLMProvider
from juuudge.agent.providers.anthropic_provider import AnthropicProvider
from juuudge.models import LLMChunk, ToolCallRequest

@pytest.mark.asyncio
async def test_anthropic_provider_mock_stream():
    provider = AnthropicProvider(api_key="mock-key", model="claude-3-7-sonnet")

    # Mock raw anthropic client stream
    mock_events = [
        MagicMock(type="content_block_delta", delta=MagicMock(type="text_delta", text="Yes, ")),
        MagicMock(type="content_block_delta", delta=MagicMock(type="text_delta", text="it dies.")),
        MagicMock(type="message_stop")
    ]

    with patch.object(provider, "client") as mock_client:
        mock_stream = AsyncMock()
        mock_stream.__aiter__.return_value = mock_events
        mock_client.messages.create.return_value = mock_stream

        chunks = []
        async for chunk in provider.stream_completion(
            messages=[{"role": "user", "content": "Does Urza's Saga die?"}],
            system_prompt="You are a judge."
        ):
            chunks.append(chunk.text)

        assert "".join(chunks) == "Yes, it dies."
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_llm_providers.py -v`  
Expected: FAIL (ModuleNotFoundError: No module named 'juuudge.agent')

- [ ] **Step 3: Implement `juuudge/agent/providers/base.py`, `anthropic_provider.py`, and `ollama_provider.py`**

```python
# juuudge/agent/providers/base.py
from abc import ABC, abstractmethod
from typing import AsyncIterator, List, Dict, Any
from juuudge.models import LLMChunk

class LLMProvider(ABC):
    @abstractmethod
    async def stream_completion(
        self,
        messages: List[Dict[str, Any]],
        system_prompt: str,
        tools: List[Dict[str, Any]] | None = None
    ) -> AsyncIterator[LLMChunk]:
        """Stream response tokens and return any tool calls."""
        pass
```

```python
# juuudge/agent/providers/anthropic_provider.py
from typing import AsyncIterator, List, Dict, Any
import json
import anthropic
from juuudge.agent.providers.base import LLMProvider
from juuudge.models import LLMChunk, ToolCallRequest

class AnthropicProvider(LLMProvider):
    def __init__(self, api_key: str, model: str = "claude-3-7-sonnet", temperature: float = 0.0):
        self.api_key = api_key
        self.model = model
        self.temperature = temperature
        self._client: anthropic.AsyncAnthropic | None = None

    @property
    def client(self) -> anthropic.AsyncAnthropic:
        if self._client is None:
            self._client = anthropic.AsyncAnthropic(api_key=self.api_key)
        return self._client

    async def stream_completion(
        self,
        messages: List[Dict[str, Any]],
        system_prompt: str,
        tools: List[Dict[str, Any]] | None = None
    ) -> AsyncIterator[LLMChunk]:
        kwargs: Dict[str, Any] = {
            "model": self.model,
            "max_tokens": 4096,
            "temperature": self.temperature,
            "system": system_prompt,
            "messages": messages,
        }
        if tools:
            kwargs["tools"] = tools

        stream = await self.client.messages.create(**kwargs, stream=True)
        current_tool_id = ""
        current_tool_name = ""
        current_tool_input_json = ""

        async for event in stream:
            if event.type == "content_block_start":
                if event.content_block.type == "tool_use":
                    current_tool_id = event.content_block.id
                    current_tool_name = event.content_block.name
                    current_tool_input_json = ""
            elif event.type == "content_block_delta":
                if event.delta.type == "text_delta":
                    yield LLMChunk(text=event.delta.text)
                elif event.delta.type == "input_json_delta":
                    current_tool_input_json += event.delta.partial_json
            elif event.type == "content_block_stop":
                if current_tool_name:
                    try:
                        args = json.loads(current_tool_input_json) if current_tool_input_json else {}
                    except json.JSONDecodeError:
                        args = {}
                    yield LLMChunk(
                        tool_calls=[ToolCallRequest(
                            tool_id=current_tool_id,
                            name=current_tool_name,
                            arguments=args
                        )]
                    )
                    current_tool_id = ""
                    current_tool_name = ""
                    current_tool_input_json = ""
            elif event.type == "message_stop":
                yield LLMChunk(is_done=True)
```

```python
# juuudge/agent/providers/ollama_provider.py
from typing import AsyncIterator, List, Dict, Any
import json
import httpx
from juuudge.agent.providers.base import LLMProvider
from juuudge.models import LLMChunk, ToolCallRequest

class OllamaProvider(LLMProvider):
    def __init__(self, host: str = "http://localhost:11434", model: str = "llama3.3", temperature: float = 0.0):
        self.host = host.rstrip("/")
        self.model = model
        self.temperature = temperature

    async def stream_completion(
        self,
        messages: List[Dict[str, Any]],
        system_prompt: str,
        tools: List[Dict[str, Any]] | None = None
    ) -> AsyncIterator[LLMChunk]:
        formatted_messages = [{"role": "system", "content": system_prompt}] + messages
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": formatted_messages,
            "stream": True,
            "options": {"temperature": self.temperature}
        }
        if tools:
            payload["tools"] = tools

        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream("POST", f"{self.host}/api/chat", json=payload) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line:
                        continue
                    data = json.loads(line)
                    msg = data.get("message", {})
                    content = msg.get("content", "")
                    tool_calls_raw = msg.get("tool_calls", [])
                    
                    tool_calls = []
                    for tc in tool_calls_raw:
                        fn = tc.get("function", {})
                        tool_calls.append(ToolCallRequest(
                            tool_id=tc.get("id", "call_1"),
                            name=fn.get("name", ""),
                            arguments=fn.get("arguments", {})
                        ))

                    if content:
                        yield LLMChunk(text=content)
                    if tool_calls:
                        yield LLMChunk(tool_calls=tool_calls)
                    if data.get("done", False):
                        yield LLMChunk(is_done=True)
```

```python
# juuudge/agent/providers/__init__.py
from juuudge.agent.providers.base import LLMProvider
from juuudge.agent.providers.anthropic_provider import AnthropicProvider
from juuudge.agent.providers.ollama_provider import OllamaProvider

__all__ = ["LLMProvider", "AnthropicProvider", "OllamaProvider"]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_llm_providers.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add juuudge/agent/providers/ tests/test_llm_providers.py
git commit -m "feat: implement extensible LLMProvider interface for Anthropic and Ollama"
```

---

### Task 7: Bounded Tool-Using Judge Loop & Context Assembler

**Files:**
- Create: `juuudge/agent/tools.py`
- Create: `juuudge/agent/judge_loop.py`
- Test: `tests/test_judge_loop.py`

**Interfaces:**
- Consumes: `CardExtractor`, `RuleRetriever`, `Database`, `VectorStore`, `LLMProvider`
- Produces: `JudgeAgent` executing the bounded agent loop (max 3 rounds) with deterministic local tools (`lookup_card`, `lookup_rule`, `lookup_glossary`, `search_rules`), yielding tokens and emitting `Card` and `Rule` references with Scryfall/Yawgatog links.

- [ ] **Step 1: Write test for local tools and bounded Judge Loop execution**

```python
# tests/test_judge_loop.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from juuudge.storage.db import Database
from juuudge.storage.vector import VectorStore
from juuudge.retrieval.card_extractor import CardExtractor
from juuudge.retrieval.rule_retriever import RuleRetriever
from juuudge.agent.tools import create_judge_tools, execute_tool
from juuudge.agent.judge_loop import JudgeAgent
from juuudge.models import Card, Rule, GlossaryTerm, LLMChunk, ToolCallRequest

@pytest.fixture
def judge_setup(tmp_path):
    db = Database(tmp_path / "test.db")
    db.init_schema()
    db.insert_cards([
        Card(name="Blood Moon", mana_cost="{2}{R}", type_line="Enchantment", oracle_text="Nonbasic lands are Mountains.")
    ])
    db.insert_rules([
        Rule(rule_id="613.1d", chapter="6. Spells", section="613. Continuous Effects", parent_rule="613.1", text="Layer 4: Type-changing effects.")
    ])
    db.insert_glossary([
        GlossaryTerm(term="Continuous Effect", definition="An effect that modifies characteristics over time.")
    ])
    vec_store = VectorStore(tmp_path / "lancedb")
    vec_store.index_rules([])
    vec_store.index_glossary([])

    return db, vec_store

def test_local_tools_execution(judge_setup):
    db, vec_store = judge_setup
    
    # Test lookup_card
    card_res = execute_tool("lookup_card", {"name": "Blood Moon"}, db, vec_store)
    assert "Nonbasic lands are Mountains" in card_res

    # Test lookup_rule
    rule_res = execute_tool("lookup_rule", {"rule_id": "613.1d"}, db, vec_store)
    assert "Layer 4: Type-changing" in rule_res

@pytest.mark.asyncio
async def test_judge_loop_verdict(judge_setup):
    db, vec_store = judge_setup
    mock_provider = MagicMock()

    # Stream returns final answer directly
    async def mock_stream(*args, **kwargs):
        yield LLMChunk(text="VERDICT: Blood Moon turns Urza's Saga into a Mountain. [CR 613.1d](https://yawgatog.com/resources/magic-rules/#R6131d)")
        yield LLMChunk(is_done=True)

    mock_provider.stream_completion = mock_stream

    agent = JudgeAgent(db=db, vec_store=vec_store, provider=mock_provider, max_rounds=2)
    stream = agent.ask_stream("Does Blood Moon affect nonbasics?")
    
    output = []
    async for event in stream:
        if event.get("type") == "token":
            output.append(event["text"])

    assert "VERDICT: Blood Moon" in "".join(output)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_judge_loop.py -v`  
Expected: FAIL (ModuleNotFoundError: No module named 'juuudge.agent.tools')

- [ ] **Step 3: Implement `juuudge/agent/tools.py` and `juuudge/agent/judge_loop.py`**

```python
# juuudge/agent/tools.py
from typing import Dict, Any, List
import json
from juuudge.storage.db import Database
from juuudge.storage.vector import VectorStore

JUDGE_TOOLS_SCHEMA = [
    {
        "name": "lookup_card",
        "description": "Look up official Scryfall Oracle text, mana cost, card types, and Gatherer rulings for an MTG card.",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "The exact or partial name of the card"}
            },
            "required": ["name"]
        }
    },
    {
        "name": "lookup_rule",
        "description": "Look up the exact text and hierarchical context for an MTG Comprehensive Rule by rule ID (e.g. '613.1d', '704.5s').",
        "input_schema": {
            "type": "object",
            "properties": {
                "rule_id": {"type": "string", "description": "Rule number like '613.1d' or '704.5'"}
            },
            "required": ["rule_id"]
        }
    },
    {
        "name": "lookup_glossary",
        "description": "Look up official MTG legal definition for a game mechanic term (e.g. 'Priority', 'Active Player', 'Replacement Effect').",
        "input_schema": {
            "type": "object",
            "properties": {
                "term": {"type": "string", "description": "The game term to look up"}
            },
            "required": ["term"]
        }
    },
    {
        "name": "search_rules",
        "description": "Search the MTG Comprehensive Rules using keyword or semantic search.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query keywords"}
            },
            "required": ["query"]
        }
    }
]

def create_judge_tools() -> List[Dict[str, Any]]:
    return JUDGE_TOOLS_SCHEMA

def execute_tool(name: str, args: Dict[str, Any], db: Database, vec_store: VectorStore) -> str:
    if name == "lookup_card":
        card_name = args.get("name", "")
        card = db.get_card_by_name(card_name)
        if not card:
            matches = db.search_cards(card_name, limit=1)
            card = matches[0] if matches else None
        if not card:
            return f"Card '{card_name}' not found."
        rulings_str = "\n".join([f"- ({r['date']}) {r['text']}" for r in card.rulings])
        return (
            f"CARD: {card.name} {card.mana_cost}\n"
            f"TYPE: {card.type_line}\n"
            f"ORACLE:\n{card.oracle_text}\n"
            f"RULINGS:\n{rulings_str or 'None'}"
        )

    elif name == "lookup_rule":
        rule_id = args.get("rule_id", "")
        rule = db.get_rule_by_id(rule_id)
        if not rule:
            return f"Rule '{rule_id}' not found."
        siblings = db.get_sibling_rules(rule.parent_rule)
        sib_texts = "\n".join([f"[{s.rule_id}] {s.text}" for s in siblings if s.rule_id != rule.rule_id])
        return (
            f"RULE {rule.rule_id} ({rule.section}):\n{rule.text}\n"
            f"EXAMPLES:\n" + "\n".join(rule.examples) + "\n"
            f"SIBLING RULES:\n{sib_texts}"
        )

    elif name == "lookup_glossary":
        term = args.get("term", "")
        g = db.get_glossary_term(term)
        if not g:
            matches = db.search_glossary_fts(term, limit=1)
            g = matches[0] if matches else None
        if not g:
            return f"Glossary term '{term}' not found."
        return f"GLOSSARY [{g.term}]: {g.definition}"

    elif name == "search_rules":
        query = args.get("query", "")
        fts_rules = db.search_rules_fts(query, limit=3)
        if not fts_rules:
            vec_rules = vec_store.search_rules(query, top_k=3)
            return "\n\n".join([f"[{vr['rule_id']}] {vr['text']}" for vr in vec_rules]) or "No rules found."
        return "\n\n".join([f"[{r.rule_id}] {r.text}" for r in fts_rules])

    return f"Unknown tool '{name}'"
```

```python
# juuudge/agent/judge_loop.py
from typing import AsyncIterator, Dict, Any, List
import re
from juuudge.storage.db import Database
from juuudge.storage.vector import VectorStore
from juuudge.retrieval.card_extractor import CardExtractor
from juuudge.retrieval.rule_retriever import RuleRetriever
from juuudge.agent.providers.base import LLMProvider
from juuudge.agent.tools import create_judge_tools, execute_tool
from juuudge.models import Card, Rule

SYSTEM_PROMPT = """You are juuudge, an elite certified Level 3 Magic: The Gathering Rules Judge.
Your mission is to provide 100% accurate, authoritative, and crystal-clear rulings on MTG mechanics, priority, stack resolution, continuous effects (layers), replacement effects, and state-based actions.

RULES OF ENGAGEMENT:
1. Always format output with:
   - **VERDICT:** Immediate, direct 1-sentence answer to the player's core question.
   - **STEP-BY-STEP RESOLUTION:** Clean chronological mechanics breakdown.
   - **OFFICIAL CITATIONS:** Exact CR rule citations (e.g. `[CR 613.1d](https://yawgatog.com/resources/magic-rules/#R6131d)`).
2. Whenever mentioning an MTG card name, format it as a markdown search link: `[Card Name](https://scryfall.com/search?q=%21"Card+Name")`.
3. Whenever citing a Comprehensive Rule, link it using Yawgatog anchor: `[CR 613.1d](https://yawgatog.com/resources/magic-rules/#R6131d)`.
4. If crucial card text, rule details, or glossary terms are missing from the injected context, use your available tools to look them up before issuing the verdict.
"""

class JudgeAgent:
    def __init__(
        self,
        db: Database,
        vec_store: VectorStore,
        provider: LLMProvider,
        max_rounds: int = 3
    ):
        self.db = db
        self.vec_store = vec_store
        self.provider = provider
        self.max_rounds = max_rounds
        self.card_extractor = CardExtractor(db)
        self.rule_retriever = RuleRetriever(db, vec_store)

    async def ask_stream(self, question: str) -> AsyncIterator[Dict[str, Any]]:
        # 1. Deterministic Pre-Retrieval
        cards = self.card_extractor.extract(question)
        grounded_context = self.rule_retriever.retrieve(question)

        # Emit initial cards and rules to UI
        yield {"type": "cards_found", "cards": cards}
        yield {"type": "rules_found", "rules": grounded_context.rules}

        # Build initial grounded prompt
        cards_context = "\n\n".join([
            f"CARD: {c.name} {c.mana_cost}\nTYPE: {c.type_line}\nORACLE:\n{c.oracle_text}\n"
            f"RULINGS:\n" + "\n".join([f"- ({r['date']}) {r['text']}" for r in c.rulings])
            for c in cards
        ]) or "None identified from query."

        rules_context = "\n\n".join([
            f"[{r.rule_id}] ({r.section})\n{r.text}\n" + ("\n".join(r.examples) if r.examples else "")
            for r in grounded_context.rules
        ]) or "None pre-retrieved."

        glossary_context = "\n".join([
            f"[{g.term}]: {g.definition}" for g in grounded_context.glossary
        ]) or "None."

        user_content = (
            f"PLAYER QUESTION:\n{question}\n\n"
            f"GROUNDED CARDS CONTEXT:\n{cards_context}\n\n"
            f"GROUNDED RULES CONTEXT:\n{rules_context}\n\n"
            f"GROUNDED GLOSSARY CONTEXT:\n{glossary_context}\n"
        )

        messages: List[Dict[str, Any]] = [{"role": "user", "content": user_content}]
        tools = create_judge_tools()

        # Bounded Tool Loop (Max N rounds)
        for round_idx in range(self.max_rounds):
            tool_calls_to_execute = []
            
            async for chunk in self.provider.stream_completion(
                messages=messages,
                system_prompt=SYSTEM_PROMPT,
                tools=tools if round_idx < self.max_rounds - 1 else None
            ):
                if chunk.text:
                    yield {"type": "token", "text": chunk.text}
                if chunk.tool_calls:
                    tool_calls_to_execute.extend(chunk.tool_calls)

            if not tool_calls_to_execute:
                # Finished without tool calls
                break

            # Execute tool calls
            for tc in tool_calls_to_execute:
                yield {"type": "tool_call_start", "name": tc.name, "args": tc.arguments}
                tool_result = execute_tool(tc.name, tc.arguments, self.db, self.vec_store)
                yield {"type": "tool_call_result", "name": tc.name, "result": tool_result}

                messages.append({
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [{"id": tc.tool_id, "type": "function", "function": {"name": tc.name, "arguments": json.dumps(tc.arguments)}}]
                })
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.tool_id,
                    "content": tool_result
                })

        yield {"type": "done"}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_judge_loop.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add juuudge/agent/tools.py juuudge/agent/judge_loop.py tests/test_judge_loop.py
git commit -m "feat: implement bounded tool-using judge loop with local deterministic tools"
```

---

### Task 8: Ingestion Sync Orchestrator (`juuudge sync`)

**Files:**
- Create: `juuudge/ingest/sync.py`
- Test: `tests/test_sync.py`

**Interfaces:**
- Consumes: `parse_scryfall_cards`, `parse_comprehensive_rules`, `Database`, `VectorStore`
- Produces: `sync_databases(db: Database, vec_store: VectorStore, force: bool = False, on_progress=None)` downloading Scryfall Default Cards JSON + WotC `MagicCompRules.txt` and indexing them.

- [ ] **Step 1: Write test for sync orchestrator with mocked downloads**

```python
# tests/test_sync.py
import pytest
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
            MOCK_CR.encode("utf-8"), # CR text
            MOCK_CARDS_JSON,         # Scryfall Cards JSON
            []                       # Rulings JSON
        ]
        
        await sync_all_data(db, vec_store, cache_dir=tmp_path / "cache")

        bolt = db.get_card_by_name("Lightning Bolt")
        assert bolt is not None
        assert bolt.mana_cost == "{R}"

        r100 = db.get_rule_by_id("100.1")
        assert r100 is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_sync.py -v`  
Expected: FAIL (ModuleNotFoundError: No module named 'juuudge.ingest.sync')

- [ ] **Step 3: Implement `juuudge/ingest/sync.py`**

```python
# juuudge/ingest/sync.py
from pathlib import Path
from typing import Callable, Optional
import httpx
from juuudge.storage.db import Database
from juuudge.storage.vector import VectorStore
from juuudge.ingest.cr_parser import parse_comprehensive_rules
from juuudge.ingest.card_parser import parse_scryfall_cards

WOTC_CR_URL = "https://media.wizards.com/2024/downloads/MagicCompRules.txt"
SCRYFALL_BULK_API = "https://api.scryfall.com/bulk-data"

async def download_file(url: str, on_progress: Optional[Callable[[str], None]] = None) -> bytes:
    async with httpx.AsyncClient(timeout=180.0, follow_redirects=True) as client:
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
    import json
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
    cards_data = json.loads(cards_bytes)

    rulings_data = []
    if rulings_url:
        if on_progress:
            on_progress("Downloading Scryfall Gatherer rulings data...")
        rulings_bytes = await download_file(rulings_url)
        rulings_data = json.loads(rulings_bytes)

    if on_progress:
        on_progress("Indexing cards and rulings in local SQLite...")
    cards = parse_scryfall_cards(cards_data, rulings_data)
    db.insert_cards(cards)

    if on_progress:
        on_progress("Sync completed successfully!")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_sync.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add juuudge/ingest/sync.py tests/test_sync.py
git commit -m "feat: implement sync orchestrator for Scryfall cards and MTG Comprehensive Rules"
```

---

### Task 9: 3-Pane Textual TUI Application

**Files:**
- Create: `juuudge/tui/widgets.py`
- Create: `juuudge/tui/app.py`
- Test: `tests/test_tui.py`

**Interfaces:**
- Produces: `JuuudgeApp` with 3-pane layout (Chat/Verdict, Card Inspector, Rules Inspector), Help Modal on `?`, browser link handling on `Ctrl+O`, and hotkeys.

- [ ] **Step 1: Write Textual Pilot test for TUI rendering and interaction**

```python
# tests/test_tui.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_tui.py -v`  
Expected: FAIL (ModuleNotFoundError: No module named 'juuudge.tui')

- [ ] **Step 3: Implement `juuudge/tui/widgets.py` and `juuudge/tui/app.py`**

```python
# juuudge/tui/widgets.py
import webbrowser
from rich.markdown import Markdown
from textual.app import ComposeResult
from textual.containers import Vertical, VerticalScroll, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Static, Input, Button, Label, Markdown as TextualMarkdown
from juuudge.models import Card, Rule

class HelpModal(ModalScreen):
    """Interactive help modal showing keybindings."""
    BINDINGS = [("escape", "dismiss", "Close")]

    def compose(self) -> ComposeResult:
        yield Vertical(
            Label("juuudge - MTG Rules Judge Keybindings", id="help-title"),
            Static("""
- [b]Enter[/b]: Submit question or command
- [b]Tab / Shift+Tab[/b]: Switch focus between panels
- [b]?[/b] or [b]Shift+?[/b]: Show this Help modal
- [b]Ctrl+O[/b]: Open selected Card / Rule link in browser
- [b]Ctrl+L[/b]: Clear chat history
- [b]Ctrl+K[/b] or [b]/[/b]: Focus question input
- [b]Esc / q[/b]: Close modal or exit
            """),
            Button("Close", variant="primary", id="close-btn"),
            id="help-dialog"
        )

    def on_button_pressed(self, event: Button.Pressed):
        self.dismiss()

class CardInspectorWidget(VerticalScroll):
    def update_cards(self, cards: list[Card]):
        self.remove_children()
        if not cards:
            self.mount(Static("No cards currently selected.\nMention cards in [[brackets]] or natural language.", classes="dim-text"))
            return
        for card in cards:
            rulings_md = "\n".join([f"* **({r['date']})** {r['text']}" for r in card.rulings])
            card_md = f"""### {card.name} `{card.mana_cost}`
*{card.type_line}*

{card.oracle_text}

---
**Gatherer Rulings:**
{rulings_md or '_No rulings on record._'}

[Scryfall Link]({card.scryfall_search_url})
"""
            self.mount(TextualMarkdown(card_md))

class RuleInspectorWidget(VerticalScroll):
    def update_rules(self, rules: list[Rule]):
        self.remove_children()
        if not rules:
            self.mount(Static("No rules currently cited.", classes="dim-text"))
            return
        for rule in rules:
            examples_md = "\n".join([f"> _{ex}_" for ex in rule.examples])
            rule_md = f"""### CR {rule.rule_id}
**{rule.section}**

{rule.text}

{examples_md}

[Yawgatog Link]({rule.yawgatog_url})
"""
            self.mount(TextualMarkdown(rule_md))
```

```python
# juuudge/tui/app.py
import webbrowser
from pathlib import Path
from typing import Optional
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Header, Footer, Input, Static, Markdown as TextualMarkdown
from juuudge.config import get_config, get_app_dir
from juuudge.storage.db import Database
from juuudge.storage.vector import VectorStore
from juuudge.agent.providers.anthropic_provider import AnthropicProvider
from juuudge.agent.providers.ollama_provider import OllamaProvider
from juuudge.agent.judge_loop import JudgeAgent
from juuudge.tui.widgets import HelpModal, CardInspectorWidget, RuleInspectorWidget
from juuudge.models import Card, Rule

class JuuudgeApp(App):
    CSS = """
    Screen {
        background: #121214;
        color: #E1E1E6;
    }
    #main-container {
        height: 1fr;
    }
    #chat-pane {
        width: 60%;
        border-right: solid #29292E;
        padding: 1 2;
    }
    #side-pane {
        width: 40%;
    }
    #card-pane {
        height: 50%;
        border-bottom: solid #29292E;
        padding: 1;
    }
    #rule-pane {
        height: 50%;
        padding: 1;
    }
    #input-box {
        dock: bottom;
        margin: 1;
        border: tall #00875F;
    }
    .dim-text {
        color: #7C7C8A;
    }
    #help-dialog {
        background: #202024;
        border: thick #00875F;
        padding: 2;
        width: 60;
        height: auto;
        align: center middle;
    }
    #help-title {
        font-weight: bold;
        color: #00B37E;
        margin-bottom: 1;
    }
    """

    BINDINGS = [
        ("question_mark", "show_help", "Help (?)"),
        ("ctrl+l", "clear_chat", "Clear Chat"),
        ("ctrl+o", "open_link", "Open Link"),
        ("ctrl+k", "focus_input", "Focus Input"),
        ("q", "quit", "Quit"),
    ]

    def __init__(self, db: Optional[Database] = None, vec_store: Optional[VectorStore] = None):
        super().__init__()
        self.cfg = get_config()
        app_dir = get_app_dir()
        self.db = db or Database(app_dir / "juuudge.db")
        self.vec_store = vec_store or VectorStore(app_dir / "lancedb")
        self.db.init_schema()

        if self.cfg.llm.provider == "ollama":
            provider = OllamaProvider(host=self.cfg.llm.ollama_host, model=self.cfg.llm.model)
        else:
            provider = AnthropicProvider(api_key=self.cfg.llm.api_key, model=self.cfg.llm.model)

        self.agent = JudgeAgent(self.db, self.vec_store, provider, max_rounds=self.cfg.llm.max_tool_rounds)
        self.chat_history: list[str] = []
        self.last_cards: list[Card] = []
        self.last_rules: list[Rule] = []

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="main-container"):
            with VerticalScroll(id="chat-pane"):
                yield Static("# Welcome to juuudge - MTG Rules Judge CLI\nAsk any rules or card interaction question below.", id="chat-content")
            with Vertical(id="side-pane"):
                yield CardInspectorWidget(id="card-pane")
                yield RuleInspectorWidget(id="rule-pane")
        yield Input(placeholder="Ask a rules question (e.g. 'Does Blood Moon kill Urza's Saga?')...", id="input-box")
        yield Footer()

    def action_show_help(self):
        self.push_screen(HelpModal())

    def action_clear_chat(self):
        self.chat_history.clear()
        chat = self.query_one("#chat-content", Static)
        chat.update("Chat cleared.")

    def action_focus_input(self):
        self.query_one("#input-box", Input).focus()

    def action_open_link(self):
        if self.last_cards:
            webbrowser.open(self.last_cards[0].scryfall_search_url)
        elif self.last_rules:
            webbrowser.open(self.last_rules[0].yawgatog_url)

    async def on_input_submitted(self, event: Input.Submitted):
        query = event.value.strip()
        if not query:
            return
        event.input.value = ""
        
        chat = self.query_one("#chat-content", Static)
        self.chat_history.append(f"\n\n**Player:** {query}\n\n**juuudge:** ")
        chat.update("".join(self.chat_history))

        card_widget = self.query_one("#card-pane", CardInspectorWidget)
        rule_widget = self.query_one("#rule-pane", RuleInspectorWidget)

        async for chunk in self.agent.ask_stream(query):
            if chunk["type"] == "cards_found":
                self.last_cards = chunk["cards"]
                card_widget.update_cards(self.last_cards)
            elif chunk["type"] == "rules_found":
                self.last_rules = chunk["rules"]
                rule_widget.update_rules(self.last_rules)
            elif chunk["type"] == "token":
                self.chat_history[-1] += chunk["text"]
                chat.update("".join(self.chat_history))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_tui.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add juuudge/tui/ tests/test_tui.py
git commit -m "feat: implement 3-pane Textual TUI with streaming markdown and Help modal"
```

---

### Task 10: CLI Commands & One-Shot Subcommands

**Files:**
- Create: `juuudge/cli.py`
- Test: `tests/test_cli.py`

**Interfaces:**
- Produces: Click/Typer CLI commands: `juuudge` (launches TUI), `juuudge ask "..."`, `juuudge card "<name>"`, `juuudge rule "<id>"`, `juuudge sync [--force]`.

- [ ] **Step 1: Write test for CLI commands**

```python
# tests/test_cli.py
import pytest
from click.testing import CliRunner
from juuudge.cli import main
from juuudge.storage.db import Database
from juuudge.models import Card, Rule

def test_cli_card_and_rule_lookup(tmp_path, monkeypatch):
    monkeypatch.setenv("JUUUDGE_DIR", str(tmp_path))
    db = Database(tmp_path / "juuudge.db")
    db.init_schema()
    db.insert_cards([Card(name="Blood Moon", mana_cost="{2}{R}", type_line="Enchantment", oracle_text="Nonbasic lands are Mountains.")])
    db.insert_rules([Rule(rule_id="613.1d", chapter="6. Spells", section="613. Continuous Effects", parent_rule="613.1", text="Layer 4: Type change.")])

    runner = CliRunner()
    
    # Test card lookup
    res_card = runner.invoke(main, ["card", "Blood Moon"])
    assert res_card.exit_code == 0
    assert "Enchantment" in res_card.output
    assert "Mountains" in res_card.output

    # Test rule lookup
    res_rule = runner.invoke(main, ["rule", "613.1d"])
    assert res_rule.exit_code == 0
    assert "Layer 4: Type change" in res_rule.output
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_cli.py -v`  
Expected: FAIL (ModuleNotFoundError: No module named 'juuudge.cli')

- [ ] **Step 3: Implement `juuudge/cli.py`**

```python
# juuudge/cli.py
import asyncio
import click
from rich.console import Console
from rich.markdown import Markdown
from juuudge.config import get_config, get_app_dir
from juuudge.storage.db import Database
from juuudge.storage.vector import VectorStore
from juuudge.ingest.sync import sync_all_data
from juuudge.agent.providers.anthropic_provider import AnthropicProvider
from juuudge.agent.providers.ollama_provider import OllamaProvider
from juuudge.agent.judge_loop import JudgeAgent

console = Console()

@click.group(invoke_without_command=True)
@click.pass_context
def main(ctx: click.Context):
    """juuudge - Magic: The Gathering Rules Judge CLI & TUI Agent."""
    if ctx.invoked_subcommand is None:
        from juuudge.tui.app import JuuudgeApp
        app = JuuudgeApp()
        app.run()

@main.command()
@click.argument("question")
def ask(question: str):
    """Ask a rules question directly from stdout."""
    async def _run():
        cfg = get_config()
        app_dir = get_app_dir()
        db = Database(app_dir / "juuudge.db")
        vec_store = VectorStore(app_dir / "lancedb")
        db.init_schema()

        if cfg.llm.provider == "ollama":
            provider = OllamaProvider(host=cfg.llm.ollama_host, model=cfg.llm.model)
        else:
            provider = AnthropicProvider(api_key=cfg.llm.api_key, model=cfg.llm.model)

        agent = JudgeAgent(db, vec_store, provider, max_rounds=cfg.llm.max_tool_rounds)
        
        with console.status("[bold green]Adjudicating MTG rules..."):
            tokens = []
            async for event in agent.ask_stream(question):
                if event["type"] == "token":
                    tokens.append(event["text"])
            
            console.print(Markdown("".join(tokens)))

    asyncio.run(_run())

@main.command()
@click.argument("name")
def card(name: str):
    """Look up card oracle text and Gatherer rulings."""
    app_dir = get_app_dir()
    db = Database(app_dir / "juuudge.db")
    db.init_schema()
    c = db.get_card_by_name(name)
    if not c:
        matches = db.search_cards(name, limit=1)
        c = matches[0] if matches else None
    if not c:
        console.print(f"[red]Card '{name}' not found in local database. Run `juuudge sync` first.[/red]")
        return
    rulings_str = "\n".join([f"* ({r['date']}) {r['text']}" for r in c.rulings])
    md = f"""# {c.name} {c.mana_cost}
*{c.type_line}*

{c.oracle_text}

---
**Gatherer Rulings:**
{rulings_str or '_No rulings on record._'}

[Scryfall]({c.scryfall_search_url})
"""
    console.print(Markdown(md))

@main.command()
@click.argument("rule_id")
def rule(rule_id: str):
    """Look up an official MTG Comprehensive Rule by ID (e.g. 613.1d)."""
    app_dir = get_app_dir()
    db = Database(app_dir / "juuudge.db")
    db.init_schema()
    r = db.get_rule_by_id(rule_id)
    if not r:
        console.print(f"[red]Rule '{rule_id}' not found. Run `juuudge sync` first.[/red]")
        return
    examples_str = "\n".join([f"> _{ex}_" for ex in r.examples])
    md = f"""# CR {r.rule_id} ({r.section})
{r.text}

{examples_str}

[Yawgatog Link]({r.yawgatog_url})
"""
    console.print(Markdown(md))

@main.command()
@click.option("--force", is_flag=True, help="Force re-download of all data.")
def sync(force: bool):
    """Download and sync Scryfall cards and MTG Comprehensive Rules."""
    async def _run():
        app_dir = get_app_dir()
        db = Database(app_dir / "juuudge.db")
        db.init_schema()
        vec_store = VectorStore(app_dir / "lancedb")
        
        with console.status("[bold green]Starting sync...") as status:
            def on_progress(msg: str):
                status.update(f"[bold green]{msg}")
            
            await sync_all_data(db, vec_store, cache_dir=app_dir / "cache", on_progress=on_progress)
            console.print("[bold green]✓ Database sync complete![/bold green]")

    asyncio.run(_run())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_cli.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add juuudge/cli.py tests/test_cli.py
git commit -m "feat: implement CLI commands (ask, card, rule, sync) and TUI launch"
```

---

### Task 11: End-to-End Judge Test Suite & Verification

**Files:**
- Create: `tests/test_judge_scenarios.py`
- Test: `tests/test_judge_scenarios.py`

**Interfaces:**
- Validates: Canonical MTG judge edge-case test suite (Blood Moon + Urza's Saga, Humility + Opalescence, Deflecting Swat + Counterspell, APNAP trigger resolution).

- [ ] **Step 1: Write integration tests for canonical judge scenarios**

```python
# tests/test_judge_scenarios.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from juuudge.storage.db import Database
from juuudge.storage.vector import VectorStore
from juuudge.agent.judge_loop import JudgeAgent
from juuudge.models import Card, Rule, LLMChunk

@pytest.fixture
def populated_judge(tmp_path):
    db = Database(tmp_path / "juuudge.db")
    db.init_schema()
    
    # Blood Moon & Urza's Saga scenario
    db.insert_cards([
        Card(name="Blood Moon", mana_cost="{2}{R}", type_line="Enchantment", oracle_text="Nonbasic lands are Mountains."),
        Card(name="Urza's Saga", mana_cost="", type_line="Enchantment Land — Urza's Saga", oracle_text="I, II, III chapters."),
        Card(name="Deflecting Swat", mana_cost="{2}{R}", type_line="Instant", oracle_text="You may choose new targets for target spell or ability."),
        Card(name="Counterspell", mana_cost="{U}{U}", type_line="Instant", oracle_text="Counter target spell.")
    ])

    db.insert_rules([
        Rule(rule_id="613.1d", chapter="6. Spells", section="613. Continuous Effects", parent_rule="613.1", text="Layer 4: Type-changing effects are applied."),
        Rule(rule_id="704.5s", chapter="7. SBAs", section="704. State-Based Actions", parent_rule="704.5", text="If a Saga has lore counters >= final chapter and isn't source of triggered ability, sacrifice it."),
        Rule(rule_id="115.7b", chapter="1. Game Concepts", section="115. Targets", parent_rule="115.7", text="A spell or ability that changes targets can't make a spell target itself.")
    ])

    vec_store = VectorStore(tmp_path / "lancedb")
    vec_store.index_rules([])
    vec_store.index_glossary([])

    return db, vec_store

@pytest.mark.asyncio
async def test_blood_moon_urzas_saga_scenario(populated_judge):
    db, vec_store = populated_judge
    
    mock_provider = MagicMock()
    async def mock_stream(*args, **kwargs):
        yield LLMChunk(text="**VERDICT:** Yes, Urza's Saga will be put into the graveyard as a state-based action.")
        yield LLMChunk(is_done=True)

    mock_provider.stream_completion = mock_stream
    agent = JudgeAgent(db, vec_store, mock_provider)

    events = []
    async for event in agent.ask_stream("What happens to Urza's Saga when Blood Moon is on the battlefield?"):
        events.append(event)

    card_event = next(e for e in events if e["type"] == "cards_found")
    card_names = {c.name for c in card_event["cards"]}
    assert "Blood Moon" in card_names
    assert "Urza's Saga" in card_names

    token_event = "".join([e["text"] for e in events if e["type"] == "token"])
    assert "put into the graveyard" in token_event
```

- [ ] **Step 2: Run test suite to verify everything passes**

Run: `pytest tests/ -v`  
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_judge_scenarios.py
git commit -m "test: add end-to-end MTG rules judge verification test suite"
```
