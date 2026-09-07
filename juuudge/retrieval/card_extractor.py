import re
from typing import List, Set
from rapidfuzz import process, fuzz
from juuudge.storage.db import Database
from juuudge.models import Card

BRACKET_PATTERN = re.compile(r'\[\[(.*?)\]\]')

# Common English words that are also MTG card names to avoid false positive matches in natural sentences
COMMON_STOPWORDS = {
    "turn", "kill", "down", "life", "deal", "play", "draw", "land", 
    "pass", "target", "hand", "spell", "hero", "cost", "type", 
    "fast", "slow", "time", "game", "deck", "side", "rule", "card"
}

class CardExtractor:
    def __init__(self, db: Database):
        self.db = db
        self._all_names: List[str] | None = None

    def _get_all_names(self) -> List[str]:
        if self._all_names is None:
            # Sort by length descending so longer specific card names match before substrings
            names = self.db.get_all_card_names()
            self._all_names = sorted(names, key=len, reverse=True)
        return self._all_names

    def extract(self, text: str) -> List[Card]:
        found_cards: List[Card] = []
        found_names: Set[str] = set()

        # 1. Highest Priority: Bracket syntax [[Card Name]]
        bracket_matches = BRACKET_PATTERN.findall(text)
        for match in bracket_matches:
            c = self.db.get_card_by_name(match.strip())
            if c and c.name not in found_names:
                found_cards.append(c)
                found_names.add(c.name)

        # 2. Word Boundary Regex Scan against known card names
        all_names = self._get_all_names()
        for name in all_names:
            if name.lower() in COMMON_STOPWORDS and len(name) <= 5:
                continue
            if len(name) < 3:
                continue

            # Check exact whole-word boundary
            pattern = re.compile(rf'\b{re.escape(name)}\b', re.IGNORECASE)
            if pattern.search(text):
                if name not in found_names:
                    c = self.db.get_card_by_name(name)
                    if c:
                        found_cards.append(c)
                        found_names.add(name)

        # 3. Fuzzy search for short typos if nothing found yet
        if not found_cards and len(text) > 3:
            fuzzy_matches = process.extract(
                text, all_names, scorer=fuzz.partial_ratio, limit=2, score_cutoff=85
            )
            for match_name, score, _ in fuzzy_matches:
                if match_name not in found_names and match_name.lower() not in COMMON_STOPWORDS:
                    c = self.db.get_card_by_name(match_name)
                    if c:
                        found_cards.append(c)
                        found_names.add(match_name)

        return found_cards
