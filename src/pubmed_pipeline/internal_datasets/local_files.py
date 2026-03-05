from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Iterable, Set

from .base import InternalDataset


class LocalJsonlDataset(InternalDataset):
    """Simple JSONL-backed dataset storing papers by id."""

    def __init__(self, path: str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._ids: Set[str] = set()
        if self.path.exists():
            with self.path.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    paper_id = record.get("paper_id")
                    if paper_id:
                        self._ids.add(str(paper_id))

    def exists(self, paper_id: str) -> bool:
        return str(paper_id) in self._ids

    def add_many(self, papers: Iterable[Dict]) -> None:
        to_write = []
        for paper in papers:
            paper_id = paper.get("paper_id")
            if not paper_id:
                continue
            paper_id = str(paper_id)
            if paper_id in self._ids:
                continue
            self._ids.add(paper_id)
            to_write.append(paper)

        if not to_write:
            return

        with self.path.open("a", encoding="utf-8") as f:
            for paper in to_write:
                f.write(json.dumps(paper, ensure_ascii=False) + "\n")
