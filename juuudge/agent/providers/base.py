from abc import ABC, abstractmethod
from typing import AsyncIterator, List, Dict, Any
from juuudge.models import LLMChunk

class LLMProvider(ABC):
    @abstractmethod
    async def stream_completion(
        self,
        messages: List[Dict[str, Any]],
        system_prompt: str,
        tools: List[Dict[str, Any]] | None = None
    ) -> AsyncIterator[LLMChunk]:
        """Stream response tokens and return any tool calls."""
        pass
