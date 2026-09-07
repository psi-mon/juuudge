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

    # Card search with punctuation/apostrophe safety
    results = test_db.search_cards("Urza's")
    assert len(results) >= 1
    assert results[0].name == "Urza's Saga"

    results_swat = test_db.search_cards("Swat")
    assert len(results_swat) >= 1
    assert results_swat[0].name == "Deflecting Swat"

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

def test_glossary_insert_and_lookup(test_db):
    terms = [
        GlossaryTerm(term="Priority", definition="A player who has priority may cast spells..."),
        GlossaryTerm(term="Continuous Effect", definition="An effect that modifies characteristics over time.")
    ]
    test_db.insert_glossary(terms)

    g = test_db.get_glossary_term("Priority")
    assert g is not None
    assert "cast spells" in g.definition

    fts_g = test_db.search_glossary_fts("modifies characteristics")
    assert len(fts_g) >= 1
    assert fts_g[0].term == "Continuous Effect"
