import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from juuudge.agent.providers.base import LLMProvider
from juuudge.agent.providers.anthropic_provider import AnthropicProvider
from juuudge.models import LLMChunk, ToolCallRequest

@pytest.mark.asyncio
async def test_anthropic_provider_mock_stream():
    provider = AnthropicProvider(api_key="mock-key", model="claude-3-7-sonnet")

    mock_events = [
        MagicMock(type="content_block_delta", delta=MagicMock(type="text_delta", text="Yes, ")),
        MagicMock(type="content_block_delta", delta=MagicMock(type="text_delta", text="it dies.")),
        MagicMock(type="message_stop")
    ]

    mock_client = MagicMock()
    mock_stream = MagicMock()
    mock_stream.__aiter__.return_value = mock_events
    mock_client.messages.create = AsyncMock(return_value=mock_stream)

    provider.client = mock_client

    chunks = []
    async for chunk in provider.stream_completion(
        messages=[{"role": "user", "content": "Does Urza's Saga die?"}],
        system_prompt="You are a judge."
    ):
        chunks.append(chunk.text)

    assert "".join(chunks) == "Yes, it dies."
    assert provider.model == "claude-3-7-sonnet-20250219"
    assert mock_client.messages.create.call_args.kwargs["model"] == "claude-3-7-sonnet-20250219"
