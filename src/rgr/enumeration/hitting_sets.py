"""Lazy best-first minimal hitting set enumerator.

Keeps a min-heap of candidate hitting sets ordered by size. On each
`next_candidate`:
- pop the smallest candidate;
- if it's a superset of a blocked PI, skip;
- if it hits every known conflict, return it (the CEGAR caller then tests
  entailment);
- otherwise branch: push cand ∪ {ℓ} for each ℓ in the first unhit conflict.

Two hooks let the CEGAR loop update the state after each check:

- `add_blocked_pi(cand)` after a successful yield, so strict supersets are
  never returned again.
- `add_conflict(conflict)` after a failed entailment check.

*IMPORTANT*: `add_conflict` alone is not enough for completeness. The
candidate that CEGAR just tested has already been popped from the heap.
If the new conflict is not hit by the queue's remaining candidates
(or those candidates are exhausted), the enumerator will terminate
without ever branching the failed candidate on the new conflict, and
miss any PI that would have been reached through it. So CEGAR must
also call `branch(failed_cand, new_conflict)` after `add_conflict`.
See `cegar.py` for the standard usage.
"""
from __future__ import annotations

import heapq
from typing import FrozenSet, Iterable, List, Optional, Set


class MHSSearchLimitExceeded(Exception):
    """Raised when the enumerator exceeds its iteration or queue budget."""


class MinimalHittingSetEnumerator:
    """Lazy best-first enumerator over minimal hitting sets of an
    incrementally growing conflict family, restricted to `universe`."""

    def __init__(
        self,
        universe: Iterable[int],
        max_iterations: int = 50_000,
        max_queue: int = 50_000,
    ) -> None:
        self.universe: Set[int] = set(universe)
        self.conflicts: List[FrozenSet[int]] = []
        self.blocked_pis: List[FrozenSet[int]] = []
        self.max_iterations = int(max_iterations)
        self.max_queue = int(max_queue)

        self._queue: list = []          # min-heap of (size, tie, cand)
        self._tie = 0
        self._visited: Set[FrozenSet[int]] = set()
        self._iterations = 0

        self._push(frozenset())

    # ------------------------------------------------------------------ state

    def add_blocked_pi(self, pi_optional_part: Iterable[int]) -> None:
        """Block strict supersets of `pi_optional_part` from being yielded."""
        b = frozenset(pi_optional_part) & self.universe
        self.blocked_pis.append(b)

    def add_conflict(self, conflict: Iterable[int]) -> None:
        """Record a new conflict that every future candidate must hit."""
        c = frozenset(conflict) & self.universe
        if not c:
            # A conflict disjoint from `universe` cannot be hit at all — the
            # search is over.
            self._queue.clear()
            return
        self.conflicts.append(c)

    def branch(self, cand: FrozenSet[int], conflict: Iterable[int]) -> None:
        """Push cand ∪ {ℓ} for each ℓ in `conflict` (restricted to universe).

        Called by CEGAR after a candidate that hit every prior conflict
        fails entailment: without this, the failed candidate is lost and
        the new conflict never drives any branching from it.
        """
        c = frozenset(conflict) & self.universe
        for lit in c:
            self._push(cand | {lit})

    # ----------------------------------------------------------- enumeration

    def next_candidate(self) -> Optional[FrozenSet[int]]:
        """Return the next minimal hitting set of the current conflict
        family, or None if none remain."""
        while self._queue:
            self._iterations += 1
            if self._iterations > self.max_iterations:
                raise MHSSearchLimitExceeded(
                    f"MHS enumerator exceeded {self.max_iterations} iterations"
                )
            _, _, cand = heapq.heappop(self._queue)

            # prune supersets of already-yielded PIs
            if any(b <= cand for b in self.blocked_pis):
                continue

            # find the first unhit conflict
            unhit: Optional[FrozenSet[int]] = None
            for c in self.conflicts:
                if not (cand & c):
                    unhit = c
                    break

            if unhit is None:
                return cand  # hits every known conflict → hand to CEGAR

            # branch on the unhit conflict
            for lit in unhit:
                self._push(cand | {lit})

        return None

    # -------------------------------------------------------------- internal

    def _push(self, cand: FrozenSet[int]) -> None:
        if cand in self._visited:
            return
        if len(cand) > len(self.universe):
            return
        if any(b <= cand for b in self.blocked_pis):
            return
        self._visited.add(cand)
        heapq.heappush(self._queue, (len(cand), self._tie, cand))
        self._tie += 1
        if len(self._queue) > self.max_queue:
            raise MHSSearchLimitExceeded(
                f"MHS enumerator queue exceeded {self.max_queue} entries"
            )