import pytest
from juuudge import constants

def test_constants_defined_and_exported():
    assert constants.WOTC_CR_URL.startswith("https://")
    assert "MagicCompRules" in constants.WOTC_CR_URL
    assert constants.SCRYFALL_BULK_API_URL == "https://api.scryfall.com/bulk-data"
    assert constants.SCRYFALL_SEARCH_URL_BASE.startswith("https://scryfall.com/search")
    assert constants.YAWGATOG_RULES_URL_BASE.startswith("https://yawgatog.com/resources/magic-rules/")
    assert constants.DEFAULT_LLM_PROVIDER == "anthropic"
    assert constants.DEFAULT_ANTHROPIC_MODEL == "claude-3-7-sonnet-20250219"
    assert constants.resolve_anthropic_model("claude-3-7-sonnet") == "claude-3-7-sonnet-20250219"
    assert constants.resolve_anthropic_model("claude-3-5-sonnet") == "claude-3-5-sonnet-20241022"
    assert constants.DEFAULT_OLLAMA_MODEL == "llama3.3"
    assert constants.DEFAULT_OLLAMA_HOST == "http://localhost:11434"
    assert constants.DEFAULT_DB_FILENAME == "juuudge.db"
    assert constants.DEFAULT_LANCEDB_DIRNAME == "lancedb"
    assert constants.DEFAULT_CACHE_DIRNAME == "cache"
    assert constants.DEFAULT_CONFIG_FILENAME == "config.toml"
    assert isinstance(constants.COMMON_STOPWORDS, set)
    assert len(constants.COMMON_STOPWORDS) > 0
    assert len(constants.JUDGE_TOOLS_SCHEMA) == 4
    assert "lookup_card" in [t["name"] for t in constants.JUDGE_TOOLS_SCHEMA]
    assert "lookup_rule" in [t["name"] for t in constants.JUDGE_TOOLS_SCHEMA]
    assert "lookup_glossary" in [t["name"] for t in constants.JUDGE_TOOLS_SCHEMA]
    assert "search_rules" in [t["name"] for t in constants.JUDGE_TOOLS_SCHEMA]
