import pytest
from unittest.mock import AsyncMock, MagicMock
from juuudge.storage.db import Database
from juuudge.storage.vector import VectorStore
from juuudge.retrieval.card_extractor import CardExtractor
from juuudge.retrieval.rule_retriever import RuleRetriever
from juuudge.agent.tools import create_judge_tools, execute_tool
from juuudge.agent.judge_loop import JudgeAgent
from juuudge.models import Card, Rule, GlossaryTerm, LLMChunk, ToolCallRequest

@pytest.fixture
def judge_setup(tmp_path):
    db = Database(tmp_path / "test.db")
    db.init_schema()
    db.insert_cards([
        Card(name="Blood Moon", mana_cost="{2}{R}", type_line="Enchantment", oracle_text="Nonbasic lands are Mountains.")
    ])
    db.insert_rules([
        Rule(rule_id="613.1d", chapter="6. Spells", section="613. Continuous Effects", parent_rule="613.1", text="Layer 4: Type-changing effects.")
    ])
    db.insert_glossary([
        GlossaryTerm(term="Continuous Effect", definition="An effect that modifies characteristics over time.")
    ])
    vec_store = VectorStore(tmp_path / "lancedb")
    vec_store.index_rules([])
    vec_store.index_glossary([])

    return db, vec_store

def test_local_tools_execution(judge_setup):
    db, vec_store = judge_setup
    
    # Test lookup_card
    card_res = execute_tool("lookup_card", {"name": "Blood Moon"}, db, vec_store)
    assert "Nonbasic lands are Mountains" in card_res

    # Test lookup_rule
    rule_res = execute_tool("lookup_rule", {"rule_id": "613.1d"}, db, vec_store)
    assert "Layer 4: Type-changing" in rule_res

@pytest.mark.asyncio
async def test_judge_loop_verdict(judge_setup):
    db, vec_store = judge_setup
    mock_provider = MagicMock()

    # Stream returns final answer directly
    async def mock_stream(*args, **kwargs):
        yield LLMChunk(text="VERDICT: Blood Moon turns Urza's Saga into a Mountain. [CR 613.1d](https://yawgatog.com/resources/magic-rules/#R6131d)")
        yield LLMChunk(is_done=True)

    mock_provider.stream_completion = mock_stream

    agent = JudgeAgent(db=db, vec_store=vec_store, provider=mock_provider, max_rounds=2)
    stream = agent.ask_stream("Does Blood Moon affect nonbasics?")
    
    output = []
    async for event in stream:
        if event.get("type") == "token":
            output.append(event["text"])

    assert "VERDICT: Blood Moon" in "".join(output)
