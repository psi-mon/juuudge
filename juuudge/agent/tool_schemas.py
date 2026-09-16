"""Tool schemas and function definitions for juuudge AI agent."""

from typing import List, Dict, Any

JUDGE_TOOLS_SCHEMA: List[Dict[str, Any]] = [
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
