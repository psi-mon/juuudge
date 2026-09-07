import pytest
from pathlib import Path
from juuudge.storage.vector import VectorStore
from juuudge.models import Rule, GlossaryTerm

@pytest.fixture
def vector_store(tmp_path):
    vec_dir = tmp_path / "lancedb"
    store = VectorStore(vec_dir)
    return store

def test_vector_store_index_and_search(vector_store):
    rules = [
        Rule(rule_id="613.1d", chapter="6. Spells, Abilities", section="613. Continuous Effects", parent_rule="613.1", text="Layer 4: Type-changing effects are applied.", examples=[]),
        Rule(rule_id="704.5s", chapter="7. Additional Rules", section="704. State-Based Actions", parent_rule="704.5", text="If a Saga has lore counters greater than or equal to final chapter, sacrifice it.", examples=[])
    ]
    glossary = [
        GlossaryTerm(term="State-Based Action", definition="A game event that occurs automatically when certain game conditions are met.")
    ]

    vector_store.index_rules(rules)
    vector_store.index_glossary(glossary)

    # Semantic search
    hits = vector_store.search_rules("When does a Saga die from lore counters?", top_k=1)
    assert len(hits) == 1
    assert hits[0]["rule_id"] == "704.5s"

    g_hits = vector_store.search_glossary("game events that happen automatically", top_k=1)
    assert len(g_hits) == 1
    assert g_hits[0]["term"] == "State-Based Action"
