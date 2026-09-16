from typing import AsyncIterator, List, Dict, Any
import json
import anthropic
from juuudge.agent.providers.base import LLMProvider
from juuudge.models import LLMChunk, ToolCallRequest
from juuudge.logger import get_logger
from juuudge.constants import (
    DEFAULT_ANTHROPIC_MODEL,
    DEFAULT_TEMPERATURE,
    DEFAULT_MAX_TOKENS,
    resolve_anthropic_model,
)

logger = get_logger("anthropic")

class AnthropicProvider(LLMProvider):
    def __init__(
        self,
        api_key: str,
        model: str = DEFAULT_ANTHROPIC_MODEL,
        temperature: float = DEFAULT_TEMPERATURE,
    ):
        self.api_key = api_key
        self.model = resolve_anthropic_model(model)
        self.temperature = temperature
        self._client: anthropic.AsyncAnthropic | None = None

    @property
    def client(self) -> anthropic.AsyncAnthropic:
        if self._client is None:
            self._client = anthropic.AsyncAnthropic(api_key=self.api_key)
        return self._client

    @client.setter
    def client(self, val: anthropic.AsyncAnthropic):
        self._client = val

    @client.deleter
    def client(self):
        self._client = None

    async def stream_completion(
        self,
        messages: List[Dict[str, Any]],
        system_prompt: str,
        tools: List[Dict[str, Any]] | None = None
    ) -> AsyncIterator[LLMChunk]:
        logger.info(f"Connecting to Anthropic Messages stream (model: '{self.model}')")
        kwargs: Dict[str, Any] = {
            "model": self.model,
            "max_tokens": DEFAULT_MAX_TOKENS,
            "system": system_prompt,
            "messages": messages,
        }
        if tools:
            kwargs["tools"] = tools

        try:
            stream = await self.client.messages.create(**kwargs, stream=True)
        except Exception as e:
            logger.error(f"Anthropic API request error: {e}")
            raise
        current_tool_id = ""
        current_tool_name = ""
        current_tool_input_json = ""

        async for event in stream:
            event_type = getattr(event, "type", "")
            if event_type == "content_block_start":
                cb = getattr(event, "content_block", None)
                if cb and getattr(cb, "type", "") == "tool_use":
                    current_tool_id = getattr(cb, "id", "")
                    current_tool_name = getattr(cb, "name", "")
                    current_tool_input_json = ""
            elif event_type == "content_block_delta":
                delta = getattr(event, "delta", None)
                if delta:
                    delta_type = getattr(delta, "type", "")
                    if delta_type == "text_delta":
                        yield LLMChunk(text=getattr(delta, "text", ""))
                    elif delta_type == "input_json_delta":
                        current_tool_input_json += getattr(delta, "partial_json", "")
            elif event_type == "content_block_stop":
                if current_tool_name:
                    try:
                        args = json.loads(current_tool_input_json) if current_tool_input_json else {}
                    except json.JSONDecodeError:
                        args = {}
                    yield LLMChunk(
                        tool_calls=[ToolCallRequest(
                            tool_id=current_tool_id,
                            name=current_tool_name,
                            arguments=args
                        )]
                    )
                    current_tool_id = ""
                    current_tool_name = ""
                    current_tool_input_json = ""
            elif event_type == "message_stop":
                yield LLMChunk(is_done=True)
