from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, Iterable


class InternalDataset(ABC):
    """Abstract interface for internal datasets."""

    @abstractmethod
    def exists(self, paper_id: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def add_many(self, papers: Iterable[Dict]) -> None:
        raise NotImplementedError
