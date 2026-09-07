import pytest
from unittest.mock import AsyncMock, MagicMock
from juuudge.storage.db import Database
from juuudge.storage.vector import VectorStore
from juuudge.agent.judge_loop import JudgeAgent
from juuudge.models import Card, Rule, LLMChunk

@pytest.fixture
def populated_judge(tmp_path):
    db = Database(tmp_path / "juuudge.db")
    db.init_schema()
    
    # Blood Moon & Urza's Saga scenario
    db.insert_cards([
        Card(name="Blood Moon", mana_cost="{2}{R}", type_line="Enchantment", oracle_text="Nonbasic lands are Mountains."),
        Card(name="Urza's Saga", mana_cost="", type_line="Enchantment Land — Urza's Saga", oracle_text="I, II, III chapters."),
        Card(name="Deflecting Swat", mana_cost="{2}{R}", type_line="Instant", oracle_text="You may choose new targets for target spell or ability."),
        Card(name="Counterspell", mana_cost="{U}{U}", type_line="Instant", oracle_text="Counter target spell.")
    ])

    db.insert_rules([
        Rule(rule_id="613.1d", chapter="6. Spells", section="613. Continuous Effects", parent_rule="613.1", text="Layer 4: Type-changing effects are applied."),
        Rule(rule_id="704.5s", chapter="7. SBAs", section="704. State-Based Actions", parent_rule="704.5", text="If a Saga has lore counters >= final chapter and isn't source of triggered ability, sacrifice it."),
        Rule(rule_id="115.7b", chapter="1. Game Concepts", section="115. Targets", parent_rule="115.7", text="A spell or ability that changes targets can't make a spell target itself.")
    ])

    vec_store = VectorStore(tmp_path / "lancedb")
    vec_store.index_rules([])
    vec_store.index_glossary([])

    return db, vec_store

@pytest.mark.asyncio
async def test_blood_moon_urzas_saga_scenario(populated_judge):
    db, vec_store = populated_judge
    
    mock_provider = MagicMock()
    async def mock_stream(*args, **kwargs):
        yield LLMChunk(text="**VERDICT:** Yes, Urza's Saga will be put into the graveyard as a state-based action under [CR 704.5s](https://yawgatog.com/resources/magic-rules/#R7045s).")
        yield LLMChunk(is_done=True)

    mock_provider.stream_completion = mock_stream
    agent = JudgeAgent(db, vec_store, mock_provider)

    events = []
    async for event in agent.ask_stream("What happens to Urza's Saga when Blood Moon is on the battlefield?"):
        events.append(event)

    card_event = next(e for e in events if e["type"] == "cards_found")
    card_names = {c.name for c in card_event["cards"]}
    assert "Blood Moon" in card_names
    assert "Urza's Saga" in card_names

    token_event = "".join([e["text"] for e in events if e["type"] == "token"])
    assert "put into the graveyard" in token_event

@pytest.mark.asyncio
async def test_deflecting_swat_target_self_scenario(populated_judge):
    db, vec_store = populated_judge

    mock_provider = MagicMock()
    async def mock_stream(*args, **kwargs):
        yield LLMChunk(text="**VERDICT:** No, a spell cannot target itself under [CR 115.7b](https://yawgatog.com/resources/magic-rules/#R1157b).")
        yield LLMChunk(is_done=True)

    mock_provider.stream_completion = mock_stream
    agent = JudgeAgent(db, vec_store, mock_provider)

    events = []
    async for event in agent.ask_stream("Can I use Deflecting Swat to make Counterspell target itself?"):
        events.append(event)

    card_event = next(e for e in events if e["type"] == "cards_found")
    card_names = {c.name for c in card_event["cards"]}
    assert "Deflecting Swat" in card_names
    assert "Counterspell" in card_names

    token_event = "".join([e["text"] for e in events if e["type"] == "token"])
    assert "cannot target itself" in token_event
