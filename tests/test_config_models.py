import pytest
from pathlib import Path
from juuudge.config import Config, get_config, get_app_dir
from juuudge.models import Card, Rule, GlossaryTerm, JudgeVerdict, LLMChunk

def test_config_defaults(monkeypatch, tmp_path):
    monkeypatch.setenv("JUUUDGE_DIR", str(tmp_path))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-123")
    cfg = get_config()
    assert cfg.llm.provider == "anthropic"
    assert cfg.llm.model == "claude-3-7-sonnet-20250219"
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

def test_validate_provider_setup():
    from juuudge.config import validate_provider_setup, Config, LLMConfig
    
    # Anthropic missing key
    cfg1 = Config(llm=LLMConfig(provider="anthropic", api_key=""))
    valid, msg = validate_provider_setup(cfg1)
    assert not valid
    assert "juuudge setup" in msg

    # Anthropic with key
    cfg2 = Config(llm=LLMConfig(provider="anthropic", api_key="sk-ant-test"))
    valid, msg = validate_provider_setup(cfg2)
    assert valid
    assert msg == ""

    # Ollama valid
    cfg3 = Config(llm=LLMConfig(provider="ollama", ollama_host="http://localhost:11434", model="llama3.3"))
    valid, msg = validate_provider_setup(cfg3)
    assert valid

def test_validate_provider_setup_decrypt_failed(tmp_path, monkeypatch):
    from juuudge.config import validate_provider_setup, Config, LLMConfig
    from juuudge.storage.db import Database

    monkeypatch.setenv("JUUUDGE_DIR", str(tmp_path))
    db = Database(tmp_path / "juuudge.db")
    db.init_schema()
    # Store an encrypted blob in DB, but decrypted in-memory key is empty (simulating decrypt failure)
    db.set_setting("anthropic_api_key", "enc_v1:0123456789abcdef:fedcba9876543210")

    cfg = Config(llm=LLMConfig(provider="anthropic", api_key=""))
    valid, msg = validate_provider_setup(cfg, db=db)
    assert not valid
    assert "decryption failed" in msg.lower()
    assert "re-enter" in msg.lower()
