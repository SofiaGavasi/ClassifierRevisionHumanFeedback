"""Conditioning an SDD on a literal set, and computing the support.

Signed-literal convention (internal only): +v = x_v=True, -v = x_v=False.
Interfaces at the module boundary use dict {var:int -> bool}, matching
the rest of `rgr`.
"""
from __future__ import annotations
from typing import Dict, Iterable, Set


def mu_to_literals(mu: Dict[int, bool]) -> Set[int]:
    """Full instance dict -> set of signed literals."""
    return {v if val else -v for v, val in mu.items()}


def literals_to_instance(lits: Iterable[int]) -> Dict[int, bool]:
    """Set of signed literals -> instance dict (partial)."""
    return {abs(l): (l > 0) for l in lits}


def flipped_literals(mu: Dict[int, bool], omega: Dict[int, bool]) -> Set[int]:
    """F_μ as signed literals of μ on the disagreeing variables."""
    return {(v if mu[v] else -v) for v in mu if mu[v] != omega[v]}


def condition_sdd(sdd, mgr, literals: Iterable[int]):
    """Condition the SDD on the given signed literals."""
    residual = sdd
    for lit in literals:
        residual = residual.condition(lit)
    return residual


def support_of(sdd) -> Set[int]:
    """Variables (1-indexed, unsigned) actually appearing in `sdd`."""
    if hasattr(sdd, "vars"):
        try:
            return {int(v) for v in sdd.vars}
        except (TypeError, ValueError):
            pass
    seen: Set[int] = set()
    variables: Set[int] = set()

    def walk(n):
        nid = id(n)
        if nid in seen:
            return
        seen.add(nid)
        if n.is_true() or n.is_false():
            return
        if n.is_literal():
            variables.add(abs(n.literal))
            return
        for prime, sub in n.elements():
            walk(prime)
            walk(sub)

    walk(sdd)
    return variables