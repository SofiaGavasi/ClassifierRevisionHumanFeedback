"""CEGAR loop that lazily enumerates minimal implicants of the residual
by refining a minimal-hitting-set search with countermodel-derived
conflicts.

The `branch` call after `add_conflict` is required for completeness:
the failed candidate has been popped from the heap, so without
re-branching it on the new conflict any PI reachable only through its
subtree would be missed once the queue empties.
"""
from __future__ import annotations

from itertools import combinations
from typing import Callable, Dict, FrozenSet, Iterator, Set

from .hitting_sets import MinimalHittingSetEnumerator


def _falsifies(lit: int, nu: Dict[int, bool]) -> bool:
    var = abs(lit)
    if var not in nu:
        return False
    val = nu[var]
    return (lit > 0 and val is False) or (lit < 0 and val is True)


def cegar_enumerate(
    optional: Set[int],
    entails_residual: Callable[[Set[int]], bool],
    countermodel_residual: Callable[[Set[int]], Dict[int, bool]],
    stats: "dict | None" = None,
) -> Iterator[FrozenSet[int]]:
    """Yield minimal A ⊆ optional such that `entails_residual(A)` is True."""
    stats = stats if stats is not None else {}

    def _incr(k: str) -> None:
        stats[k] = stats.get(k, 0) + 1

    mhs = MinimalHittingSetEnumerator(optional)

    while True:
        cand = mhs.next_candidate()
        if cand is None:
            return

        A = set(cand)
        _incr("entailment_checks")
        if entails_residual(A):
            _incr("pis_found")
            yield frozenset(A)
            mhs.add_blocked_pi(A)
            continue

        _incr("countermodel_calls")
        nu = countermodel_residual(A)
        conflict = {lit for lit in optional if _falsifies(lit, nu)}
        _incr("conflicts_added")
        mhs.add_conflict(conflict)
        mhs.branch(frozenset(A), conflict)


def blind_enumerate(
    optional: Set[int],
    entails_residual: Callable[[Set[int]], bool],
    stats: "dict | None" = None,
) -> Iterator[FrozenSet[int]]:
    """Ablation: enumerate all subsets by increasing size, keep minimal
    ones by superset-blocking, but WITHOUT CEGAR conflict propagation.
    """
    stats = stats if stats is not None else {}

    def _incr(k: str) -> None:
        stats[k] = stats.get(k, 0) + 1

    opt_list = sorted(optional, key=abs)
    found: list[FrozenSet[int]] = []
    for k in range(len(opt_list) + 1):
        for combo in combinations(opt_list, k):
            cand = frozenset(combo)
            if any(f <= cand for f in found):
                continue
            _incr("entailment_checks")
            if entails_residual(set(cand)):
                _incr("pis_found")
                found.append(cand)
                yield cand