from __future__ import annotations

from typing import Dict, Iterable

from pymongo import MongoClient

from .base import InternalDataset


class MongoDataset(InternalDataset):
    def __init__(self, uri: str, db: str, collection: str) -> None:
        self.client = MongoClient(uri)
        self.collection = self.client[db][collection]
        self.collection.create_index("paper_id", unique=True)

    def exists(self, paper_id: str) -> bool:
        return self.collection.count_documents({"paper_id": str(paper_id)}, limit=1) > 0

    def add_many(self, papers: Iterable[Dict]) -> None:
        docs = []
        for paper in papers:
            paper_id = paper.get("paper_id")
            if not paper_id:
                continue
            doc = dict(paper)
            doc["paper_id"] = str(paper_id)
            docs.append(doc)
        if not docs:
            return
        try:
            self.collection.insert_many(docs, ordered=False)
        except Exception:
            # Ignore duplicates or other insert errors per document
            pass
