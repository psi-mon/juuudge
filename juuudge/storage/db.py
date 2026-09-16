import sqlite3
import json
from pathlib import Path
from typing import List, Optional
from juuudge.models import Card, Rule, GlossaryTerm
from juuudge.logger import get_logger

logger = get_logger("db")

class Database:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._conn: Optional[sqlite3.Connection] = None

    def get_connection(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def init_schema(self):
        logger.debug(f"Initializing SQLite schema at {self.db_path}")
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

            # Key-Value Settings Table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT
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
        clean_query = "".join(c if c.isalnum() or c.isspace() else " " for c in query).strip()
        if not clean_query:
            return []
        cur = conn.execute("""
            SELECT c.* FROM cards c
            JOIN cards_fts f ON c.rowid = f.rowid
            WHERE cards_fts MATCH ?
            ORDER BY bm25(cards_fts)
            LIMIT ?
        """, (f'"{clean_query}"*', limit))
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

    # =========================================================================
    # Settings & Provider Configuration
    # =========================================================================

    def get_setting(self, key: str, default: Optional[str] = None) -> Optional[str]:
        conn = self.get_connection()
        cur = conn.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = cur.fetchone()
        if row is None:
            return default
        return row["value"]

    def set_setting(self, key: str, value: str):
        conn = self.get_connection()
        with conn:
            conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))

    def delete_setting(self, key: str):
        conn = self.get_connection()
        with conn:
            conn.execute("DELETE FROM settings WHERE key = ?", (key,))

    def save_provider_config(
        self,
        provider: str,
        api_key: str = "",
        model: str = "",
        host: str = ""
    ):
        from juuudge.crypto import encrypt_secret
        self.set_setting("provider", provider)
        if api_key:
            self.set_setting("anthropic_api_key", encrypt_secret(api_key))
        if model:
            self.set_setting("model", model)
        if host:
            self.set_setting("ollama_host", host)
        self.set_setting("setup_completed", "true")

    def get_provider_config(self) -> dict:
        from juuudge.crypto import decrypt_secret
        provider = self.get_setting("provider", "")
        enc_api_key = self.get_setting("anthropic_api_key", "")
        api_key = decrypt_secret(enc_api_key) if enc_api_key else ""
        model = self.get_setting("model", "")
        ollama_host = self.get_setting("ollama_host", "")
        setup_completed = self.get_setting("setup_completed", "false").lower() == "true"

        return {
            "provider": provider,
            "api_key": api_key,
            "model": model,
            "ollama_host": ollama_host,
            "setup_completed": setup_completed,
        }

    def is_provider_configured(self) -> bool:
        cfg = self.get_provider_config()
        if not cfg["setup_completed"]:
            return False
        provider = cfg["provider"].lower()
        if provider == "anthropic":
            return bool(cfg["api_key"])
        elif provider in ("ollama", "llama"):
            return True
        return False
