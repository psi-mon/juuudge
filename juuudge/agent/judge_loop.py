from typing import AsyncIterator, Dict, Any, List
import re
from juuudge.storage.db import Database
from juuudge.storage.vector import VectorStore
from juuudge.retrieval.card_extractor import CardExtractor
from juuudge.retrieval.rule_retriever import RuleRetriever
from juuudge.agent.providers.base import LLMProvider
from juuudge.agent.tools import create_judge_tools, execute_tool
from juuudge.models import Card, Rule

SYSTEM_PROMPT = """You are juuudge, an elite certified Level 3 Magic: The Gathering Rules Judge.
Your mission is to provide 100% accurate, authoritative, and crystal-clear rulings on MTG mechanics, priority, stack resolution, continuous effects (layers), replacement effects, and state-based actions.

RULES OF ENGAGEMENT:
1. Always format output with:
   - **VERDICT:** Immediate, direct 1-sentence answer to the player's core question.
   - **STEP-BY-STEP RESOLUTION:** Clean chronological mechanics breakdown.
   - **OFFICIAL CITATIONS:** Exact CR rule citations (e.g. `[CR 613.1d](https://yawgatog.com/resources/magic-rules/#R6131d)`).
2. Whenever mentioning an MTG card name, format it as a markdown search link: `[Card Name](https://scryfall.com/search?q=%21"Card+Name")`.
3. Whenever citing a Comprehensive Rule, link it using Yawgatog anchor: `[CR 613.1d](https://yawgatog.com/resources/magic-rules/#R6131d)`.
4. If crucial card text, rule details, or glossary terms are missing from the injected context, use your available tools to look them up before issuing the verdict.
"""

class JudgeAgent:
    def __init__(
        self,
        db: Database,
        vec_store: VectorStore,
        provider: LLMProvider,
        max_rounds: int = 3
    ):
        self.db = db
        self.vec_store = vec_store
        self.provider = provider
        self.max_rounds = max_rounds
        self.card_extractor = CardExtractor(db)
        self.rule_retriever = RuleRetriever(db, vec_store)

    async def ask_stream(self, question: str) -> AsyncIterator[Dict[str, Any]]:
        # 1. Deterministic Pre-Retrieval
        cards = self.card_extractor.extract(question)
        grounded_context = self.rule_retriever.retrieve(question)

        # Emit initial cards and rules to UI
        yield {"type": "cards_found", "cards": cards}
        yield {"type": "rules_found", "rules": grounded_context.rules}

        # Build initial grounded prompt
        cards_context = "\n\n".join([
            f"CARD: {c.name} {c.mana_cost}\nTYPE: {c.type_line}\nORACLE:\n{c.oracle_text}\n"
            f"RULINGS:\n" + "\n".join([f"- ({r['date']}) {r['text']}" for r in c.rulings])
            for c in cards
        ]) or "None identified from query."

        rules_context = "\n\n".join([
            f"[{r.rule_id}] ({r.section})\n{r.text}\n" + ("\n".join(r.examples) if r.examples else "")
            for r in grounded_context.rules
        ]) or "None pre-retrieved."

        glossary_context = "\n".join([
            f"[{g.term}]: {g.definition}" for g in grounded_context.glossary
        ]) or "None."

        user_content = (
            f"PLAYER QUESTION:\n{question}\n\n"
            f"GROUNDED CARDS CONTEXT:\n{cards_context}\n\n"
            f"GROUNDED RULES CONTEXT:\n{rules_context}\n\n"
            f"GROUNDED GLOSSARY CONTEXT:\n{glossary_context}\n"
        )

        messages: List[Dict[str, Any]] = [{"role": "user", "content": user_content}]
        tools = create_judge_tools()

        # Bounded Tool Loop (Max N rounds)
        for round_idx in range(self.max_rounds):
            tool_calls_to_execute = []
            
            async for chunk in self.provider.stream_completion(
                messages=messages,
                system_prompt=SYSTEM_PROMPT,
                tools=tools if round_idx < self.max_rounds - 1 else None
            ):
                if chunk.text:
                    yield {"type": "token", "text": chunk.text}
                if chunk.tool_calls:
                    tool_calls_to_execute.extend(chunk.tool_calls)

            if not tool_calls_to_execute:
                # Finished without tool calls
                break

            # Execute tool calls
            tool_use_blocks = []
            tool_result_blocks = []
            for tc in tool_calls_to_execute:
                yield {"type": "tool_call_start", "name": tc.name, "args": tc.arguments}
                tool_result = execute_tool(tc.name, tc.arguments, self.db, self.vec_store)
                yield {"type": "tool_call_result", "name": tc.name, "result": tool_result}

                tool_use_blocks.append({
                    "type": "tool_use",
                    "id": tc.tool_id,
                    "name": tc.name,
                    "input": tc.arguments
                })
                tool_result_blocks.append({
                    "type": "tool_result",
                    "tool_use_id": tc.tool_id,
                    "content": tool_result
                })

            messages.append({"role": "assistant", "content": tool_use_blocks})
            messages.append({"role": "user", "content": tool_result_blocks})

        yield {"type": "done"}
