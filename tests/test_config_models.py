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
