"""Prime-implicant enumeration and disagreement helpers.

Brute-force PI enumeration is EXPONENTIAL and provided only as ground truth /
for the set-vs-cardinality comparison, never inside the tractable pipeline.
"""
from itertools import product
from .sdd_utils import is_implicant

def disagreement(term, omega):
    """Number of literals in term that conflict with omega."""
    return sum(1 for v, val in term.items() if omega[v] != val)

def all_prime_implicants(node, nvars, mgr):
    """Every prime implicant of node (brute force, 3^n). Ground truth only."""
    out, seen = [], set()
    for vals in product([None, True, False], repeat=nvars):
        term = {i + 1: vals[i] for i in range(nvars) if vals[i] is not None}
        if not term and not node.is_true():
            continue
        if not is_implicant(term, node, mgr):
            continue
        if any(is_implicant({k: x for k, x in term.items() if k != v}, node, mgr)
               for v in term):
            continue
        key = tuple(sorted(term.items()))
        if key not in seen:
            seen.add(key)
            out.append(term)
    return out

def weaken(term, omega):
    """Definition-6 weakening: drop literals of term that disagree with omega."""
    return {v: val for v, val in term.items() if omega[v] == val}

def minimal_reasons(node, omega, nvars, mgr):
    """min(S, <=dis_omega): the prime implicants with fewest disagreements."""
    S = all_prime_implicants(node, nvars, mgr)
    if not S:
        return [], None
    mind = min(disagreement(t, omega) for t in S)
    return [t for t in S if disagreement(t, omega) == mind], mind
