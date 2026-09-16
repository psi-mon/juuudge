import pytest
from juuudge.agent.tool_schemas import JUDGE_TOOLS_SCHEMA
from juuudge.agent.tools import create_judge_tools

def test_tool_schemas_defined_and_valid():
    assert isinstance(JUDGE_TOOLS_SCHEMA, list)
    assert len(JUDGE_TOOLS_SCHEMA) == 4

    tool_names = [t["name"] for t in JUDGE_TOOLS_SCHEMA]
    assert "lookup_card" in tool_names
    assert "lookup_rule" in tool_names
    assert "lookup_glossary" in tool_names
    assert "search_rules" in tool_names

    for tool in JUDGE_TOOLS_SCHEMA:
        assert "name" in tool
        assert "description" in tool
        assert "input_schema" in tool
        schema = tool["input_schema"]
        assert schema["type"] == "object"
        assert "properties" in schema
        assert "required" in schema
        assert isinstance(schema["required"], list)

def test_create_judge_tools_returns_schema():
    tools = create_judge_tools()
    assert tools == JUDGE_TOOLS_SCHEMA
