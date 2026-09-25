"""Residual-SDD memoization cache (per-μ and cross-μ)."""
from __future__ import annotations
from typing import Dict, FrozenSet, List, Tuple

Key = Tuple[int, FrozenSet[int]]


class ResidualCache:
    def __init__(self) -> None:
        self._store: Dict[Key, List[FrozenSet[int]]] = {}
        self.hits: int = 0
        self.misses: int = 0

    def get(self, residual_id: int, fixed: FrozenSet[int]):
        val = self._store.get((residual_id, fixed))
        if val is None:
            self.misses += 1
            return None
        self.hits += 1
        return val

    def put(self, residual_id: int, fixed: FrozenSet[int],
            pis: List[FrozenSet[int]]) -> None:
        self._store[(residual_id, fixed)] = pis

    def stats(self) -> dict:
        total = self.hits + self.misses
        return {"hits": self.hits, "misses": self.misses,
                "hit_rate": self.hits / total if total else 0.0,
                "entries": len(self._store)}