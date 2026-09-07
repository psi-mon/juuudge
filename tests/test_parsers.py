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
        "id": "printing-bm-1",
        "oracle_id": "oracle-bm-1"
    },
    {
        "name": "Urza's Saga",
        "mana_cost": "",
        "type_line": "Enchantment Land — Urza's Saga",
        "oracle_text": "I, II, III chapters...",
        "keywords": ["Saga"],
        "scryfall_uri": "https://scryfall.com/card/mh2/259/urzas-saga",
        "id": "printing-us-2",
        "oracle_id": "oracle-us-2"
    }
]

SAMPLE_SCRYFALL_RULINGS = [
    {
        "oracle_id": "oracle-bm-1",
        "published_at": "2020-08-07",
        "comment": "Nonbasic lands lose all other abilities."
    }
]

def test_cr_parser():
    rules, glossary = parse_comprehensive_rules(SAMPLE_CR_TEXT)
    assert len(rules) >= 4
    assert len(glossary) == 2

    # Verify section header rule 613
    r613 = next(r for r in rules if r.rule_id == "613")
    assert "Interaction of Continuous Effects" in r613.text

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
