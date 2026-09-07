from pathlib import Path
from typing import List, Dict, Any
import lancedb
from fastembed import TextEmbedding
from juuudge.models import Rule, GlossaryTerm

class VectorStore:
    def __init__(self, db_dir: Path, model_name: str = "BAAI/bge-small-en-v1.5"):
        self.db_dir = db_dir
        self.db_dir.mkdir(parents=True, exist_ok=True)
        self.db = lancedb.connect(str(self.db_dir))
        self._embedder = TextEmbedding(model_name=model_name)

    def _embed(self, texts: List[str]) -> List[List[float]]:
        return [e.tolist() for e in self._embedder.embed(texts)]

    def _get_tables(self) -> List[str]:
        res = self.db.list_tables()
        if hasattr(res, "tables"):
            return res.tables
        return list(res)

    def index_rules(self, rules: List[Rule]):
        if not rules:
            return
        # Create contextualized text for dense embedding
        texts = [
            f"[{r.chapter} > {r.section} > {r.rule_id}] {r.text}"
            for r in rules
        ]
        vectors = self._embed(texts)
        data = []
        for r, vec, txt in zip(rules, vectors, texts):
            data.append({
                "rule_id": r.rule_id,
                "section": r.section,
                "text": r.text,
                "context_text": txt,
                "vector": vec
            })

        table_name = "cr_rules_vec"
        if table_name in self._get_tables():
            self.db.drop_table(table_name)
        self.db.create_table(table_name, data=data)

    def index_glossary(self, terms: List[GlossaryTerm]):
        if not terms:
            return
        texts = [f"[{g.term}] {g.definition}" for g in terms]
        vectors = self._embed(texts)
        data = []
        for g, vec, txt in zip(terms, vectors, texts):
            data.append({
                "term": g.term,
                "definition": g.definition,
                "context_text": txt,
                "vector": vec
            })

        table_name = "glossary_vec"
        if table_name in self._get_tables():
            self.db.drop_table(table_name)
        self.db.create_table(table_name, data=data)

    def search_rules(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        table_name = "cr_rules_vec"
        if table_name not in self._get_tables():
            return []
        tbl = self.db.open_table(table_name)
        query_vec = self._embed([query])[0]
        results = tbl.search(query_vec).limit(top_k).to_list()
        return results

    def search_glossary(self, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        table_name = "glossary_vec"
        if table_name not in self._get_tables():
            return []
        tbl = self.db.open_table(table_name)
        query_vec = self._embed([query])[0]
        results = tbl.search(query_vec).limit(top_k).to_list()
        return results
