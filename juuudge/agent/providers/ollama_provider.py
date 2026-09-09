from typing import AsyncIterator, List, Dict, Any
import json
import httpx
from juuudge.agent.providers.base import LLMProvider
from juuudge.models import LLMChunk, ToolCallRequest
from juuudge.constants import (
    DEFAULT_OLLAMA_HOST,
    DEFAULT_OLLAMA_MODEL,
    DEFAULT_TEMPERATURE,
    OLLAMA_DEFAULT_TIMEOUT,
)

class OllamaProvider(LLMProvider):
    def __init__(
        self,
        host: str = DEFAULT_OLLAMA_HOST,
        model: str = DEFAULT_OLLAMA_MODEL,
        temperature: float = DEFAULT_TEMPERATURE,
    ):
        self.host = host.rstrip("/")
        self.model = model
        self.temperature = temperature

    async def stream_completion(
        self,
        messages: List[Dict[str, Any]],
        system_prompt: str,
        tools: List[Dict[str, Any]] | None = None
    ) -> AsyncIterator[LLMChunk]:
        formatted_messages = [{"role": "system", "content": system_prompt}]
        for m in messages:
            role = m.get("role")
            content = m.get("content")
            if isinstance(content, list):
                parts = []
                for block in content:
                    if isinstance(block, dict):
                        if block.get("type") == "text":
                            parts.append(block.get("text", ""))
                        elif block.get("type") == "tool_use":
                            parts.append(f"[Tool Call: {block.get('name')}({json.dumps(block.get('input', {}))})]")
                        elif block.get("type") == "tool_result":
                            parts.append(f"[Tool Result for {block.get('tool_use_id')}]:\n{block.get('content')}")
                        else:
                            parts.append(str(block))
                    else:
                        parts.append(str(block))
                formatted_messages.append({"role": role, "content": "\n".join(parts)})
            else:
                formatted_messages.append({"role": role, "content": content or ""})

        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": formatted_messages,
            "stream": True,
            "options": {"temperature": self.temperature}
        }
        if tools:
            payload["tools"] = tools

        async with httpx.AsyncClient(timeout=OLLAMA_DEFAULT_TIMEOUT) as client:
            async with client.stream("POST", f"{self.host}/api/chat", json=payload) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line:
                        continue
                    data = json.loads(line)
                    msg = data.get("message", {})
                    content = msg.get("content", "")
                    tool_calls_raw = msg.get("tool_calls", [])
                    
                    tool_calls = []
                    for tc in tool_calls_raw:
                        fn = tc.get("function", {})
                        tool_calls.append(ToolCallRequest(
                            tool_id=tc.get("id", "call_1"),
                            name=fn.get("name", ""),
                            arguments=fn.get("arguments", {})
                        ))

                    if content:
                        yield LLMChunk(text=content)
                    if tool_calls:
                        yield LLMChunk(tool_calls=tool_calls)
                    if data.get("done", False):
                        yield LLMChunk(is_done=True)
