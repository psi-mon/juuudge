"""Centralized constants configuration for juuudge."""

# ==============================================================================
# Network & URLs
# ==============================================================================
# NOTE: The WOTC CR URL is the latest version of the Comprehensive Rules - need to be updated periodically
WOTC_CR_URL = "https://media.wizards.com/2026/downloads/MagicCompRules%2020260819.txt"
SCRYFALL_BULK_API_URL = "https://api.scryfall.com/bulk-data"
SCRYFALL_SEARCH_URL_BASE = "https://scryfall.com/search?q="
YAWGATOG_RULES_URL_BASE = "https://yawgatog.com/resources/magic-rules/#R"
USER_AGENT = "juuudge/0.1.0 (https://github.com/psi-mon/juuudge)"
HTTP_DEFAULT_TIMEOUT = 180.0
OLLAMA_DEFAULT_TIMEOUT = 120.0

# ==============================================================================
# Files & Directories
# ==============================================================================
DEFAULT_DB_FILENAME = "juuudge.db"
DEFAULT_LANCEDB_DIRNAME = "lancedb"
DEFAULT_CACHE_DIRNAME = "cache"
DEFAULT_CONFIG_FILENAME = "config.toml"
CR_FILENAME = "MagicCompRules.txt"
CARDS_FILENAME = "default-cards.json"
RULINGS_FILENAME = "rulings.json"

# ==============================================================================
# LLM Defaults & Configuration
# ==============================================================================
DEFAULT_LLM_PROVIDER = "anthropic"
DEFAULT_ANTHROPIC_MODEL = "claude-3-7-sonnet"
DEFAULT_OLLAMA_MODEL = "llama3.3"
DEFAULT_OLLAMA_HOST = "http://localhost:11434"
DEFAULT_TEMPERATURE = 0.0
DEFAULT_MAX_TOOL_ROUNDS = 3
DEFAULT_MAX_TOKENS = 4096

# ==============================================================================
# RAG & Embeddings Defaults
# ==============================================================================
DEFAULT_EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"
DEFAULT_RULES_VEC_TABLE = "cr_rules_vec"
DEFAULT_GLOSSARY_VEC_TABLE = "glossary_vec"
DEFAULT_TOP_K_RULES = 5
DEFAULT_TOP_K_GLOSSARY = 2
DEFAULT_EXPAND_HIERARCHICAL_RULES = True

# ==============================================================================
# Stopwords / Filtering for Card Extraction
# ==============================================================================
COMMON_STOPWORDS = {
    "turn", "kill", "down", "life", "deal", "play", "draw", "land", 
    "pass", "target", "hand", "spell", "hero", "cost", "type", 
    "fast", "slow", "time", "game", "deck", "side", "rule", "card"
}

# ==============================================================================
# Agent Prompt & Tool Schemas
# ==============================================================================
JUDGE_SYSTEM_PROMPT = """You are juuudge, an elite certified Level 3 Magic: The Gathering Rules Judge.
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

# ==============================================================================
# TUI Styles & Layout
# ==============================================================================
TUI_CSS = """
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
    text-style: bold;
    color: #00B37E;
    margin-bottom: 1;
}
"""
