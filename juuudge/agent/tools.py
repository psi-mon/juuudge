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
