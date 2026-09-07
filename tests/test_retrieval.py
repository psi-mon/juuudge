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
