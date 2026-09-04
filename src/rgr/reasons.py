"""Prime-implicant enumeration and disagreement helpers.

Brute-force PI enumeration is EXPONENTIAL and provided only as ground truth /
for the set-vs-cardinality comparison, never inside the tractable pipeline.
"""
from itertools import product
from .sdd_utils import is_implicant

def disagreement(term, omega):
    """Number of literals in term that conflict with omega, same as in shrink.py."""
    return sum(1 for v, val in term.items() if omega[v] != val)

def all_prime_implicants(node, nvars, mgr):
    """Every prime implicant of node (brute force, 3^n). Ground truth only."""
    out, seen = [], set()
    for vals in product([None, True, False], repeat=nvars): # this is the 3^n loop
        term = {i + 1: vals[i] for i in range(nvars) if vals[i] is not None}
        if not term and not node.is_true(): # skip the empty term unless the classifier is trivially true (an edge case)
            continue
        if not is_implicant(term, node, mgr): # skip if this term isn't even an implicant. Only implicants can be prime implicants.
            continue
        if any(is_implicant({k: x for k, x in term.items() if k != v}, node, mgr)  for v in term): # "can I drop any single literal and still have an implicant?"
            continue
        # deduplication, so the same prime implicant isn't listed twice
        key = tuple(sorted(term.items())) 
        if key not in seen:
            seen.add(key)
            out.append(term)
    return out # full list of prime implicants

def weaken(term, omega):
    # take a reason and loosen it by removing exactly the parts that clash with the instance you're trying to accept, so the weakened reason now covers ω
    return {v: val for v, val in term.items() if omega[v] == val}

def minimal_reasons(node, omega, nvars, mgr):
    """min(S, <=dis_omega): the set of prime implicants tied for the fewest disagreements with ω."""
    S = all_prime_implicants(node, nvars, mgr)
    if not S:
        return [], None
    mind = min(disagreement(t, omega) for t in S) # the smallest disagreement count across all of them
    return [t for t in S if disagreement(t, omega) == mind], mind
