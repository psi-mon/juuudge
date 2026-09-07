from dataclasses import dataclass, field
from typing import Any, List, Optional
import re
import urllib.parse

@dataclass
class CardRuling:
    date: str
    text: str

@dataclass
class Card:
    name: str
    mana_cost: str = ""
    type_line: str = ""
    oracle_text: str = ""
    power: Optional[str] = None
    toughness: Optional[str] = None
    loyalty: Optional[str] = None
    defense: Optional[str] = None
    keywords: List[str] = field(default_factory=list)
    rulings: List[dict] = field(default_factory=list)
    scryfall_uri: str = ""

    @property
    def scryfall_search_url(self) -> str:
        encoded = urllib.parse.quote(f'!\"{self.name}\"')
        return f"https://scryfall.com/search?q={encoded}"

@dataclass
class Rule:
    rule_id: str
    chapter: str
    section: str
    parent_rule: str
    text: str
    examples: List[str] = field(default_factory=list)

    @property
    def yawgatog_url(self) -> str:
        # e.g., 613.1d -> #R6131d
        cleaned = re.sub(r'[^0-9a-zA-Z]', '', self.rule_id)
        return f"https://yawgatog.com/resources/magic-rules/#R{cleaned}"

@dataclass
class GlossaryTerm:
    term: str
    definition: str

@dataclass
class ToolCallRequest:
    tool_id: str
    name: str
    arguments: dict[str, Any]

@dataclass
class LLMChunk:
    text: str = ""
    tool_calls: List[ToolCallRequest] = field(default_factory=list)
    is_done: bool = False

@dataclass
class JudgeVerdict:
    verdict_text: str
    cards_referenced: List[Card] = field(default_factory=list)
    rules_referenced: List[Rule] = field(default_factory=list)
