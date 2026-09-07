import re
from dataclasses import dataclass, field
from typing import List, Dict, Set
from juuudge.storage.db import Database
from juuudge.storage.vector import VectorStore
from juuudge.models import Rule, GlossaryTerm

RULE_ID_REGEX = re.compile(r'\b(\d{3}\.\d+[a-z]?|\d{3}\.\d+|\d{3})\b')

@dataclass
class GroundedContext:
    rules: List[Rule] = field(default_factory=list)
    glossary: List[GlossaryTerm] = field(default_factory=list)

class RuleRetriever:
    def __init__(self, db: Database, vec_store: VectorStore, expand_hierarchical: bool = True):
        self.db = db
        self.vec_store = vec_store
        self.expand_hierarchical = expand_hierarchical

    def retrieve(self, query: str, top_k: int = 5) -> GroundedContext:
        seen_rule_ids: Set[str] = set()
        matched_rules: List[Rule] = []
        matched_glossary: List[GlossaryTerm] = []

        # 1. Direct Rule-ID Fast Path (Bypass BM25 / Vectors)
        rule_id_matches = RULE_ID_REGEX.findall(query)
        for rid in rule_id_matches:
            rule = self.db.get_rule_by_id(rid)
            if rule and rule.rule_id not in seen_rule_ids:
                matched_rules.append(rule)
                seen_rule_ids.add(rule.rule_id)

                if self.expand_hierarchical:
                    # Full expansion for direct Rule-ID lookups
                    parent_rule = rule.parent_rule
                    siblings = self.db.get_sibling_rules(parent_rule)
                    for sib in siblings:
                        if sib.rule_id not in seen_rule_ids:
                            matched_rules.append(sib)
                            seen_rule_ids.add(sib.rule_id)

        # 2. FTS5 Lexical Search
        fts_rules = self.db.search_rules_fts(query, limit=top_k)
        for r in fts_rules:
            if r.rule_id not in seen_rule_ids:
                matched_rules.append(r)
                seen_rule_ids.add(r.rule_id)
                if self.expand_hierarchical:
                    # Bounded expansion (top 3 siblings) on broad FTS search
                    for sib in self.db.get_sibling_rules(r.parent_rule)[:3]:
                        if sib.rule_id not in seen_rule_ids:
                            matched_rules.append(sib)
                            seen_rule_ids.add(sib.rule_id)

        # 3. Dense Vector Search (LanceDB)
        vec_rules = self.vec_store.search_rules(query, top_k=top_k)
        for vr in vec_rules:
            rid = vr["rule_id"]
            if rid not in seen_rule_ids:
                rule_obj = self.db.get_rule_by_id(rid)
                if rule_obj:
                    matched_rules.append(rule_obj)
                    seen_rule_ids.add(rid)

        # 4. Glossary Retrieval
        fts_glossary = self.db.search_glossary_fts(query, limit=2)
        matched_glossary.extend(fts_glossary)
        vec_glossary = self.vec_store.search_glossary(query, top_k=2)
        g_terms = {g.term for g in matched_glossary}
        for vg in vec_glossary:
            term = vg["term"]
            if term not in g_terms:
                matched_glossary.append(GlossaryTerm(term=term, definition=vg["definition"]))
                g_terms.add(term)

        return GroundedContext(rules=matched_rules, glossary=matched_glossary)
