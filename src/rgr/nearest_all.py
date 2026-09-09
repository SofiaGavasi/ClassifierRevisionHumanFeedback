"""
Enumerate ALL minimum-distance models of an SDD to a target instance, by walking the sub-DAG of minimum-cost branches (the 'gap-0' paths). 
This is the bounded menu extension: instead of one nearest model, recover every nearest model.

Cost is proportional to the number of nearest models (see rgr.count.nearest_count for a cheap upper bound on that number before committing to enumeration).
"""

from .distance import node_dist, INF

def all_nearest_models(node, omega, nvars, weights=None):
    """Return a list of complete assignments, each a nearest model of `node` to omega.
    Free variables (unmentioned along a winning path) are filled from omega.
    """
    memo = {}
    d = node_dist(node, omega, memo, weights) # compute the minimum distance to omega, and memoize the distances of all nodes along the way
    if d == INF:
        return []
    partials = _walk(node, omega, memo, weights) # returns a list of partial assignments, one per minimum-cost path through node
    full = []
    seen = set()
    # fill in the free variables from omega, and deduplicate
    for part in partials:
        inst = {v: part.get(v, omega[v]) for v in range(1, nvars + 1)}
        key = tuple(sorted(inst.items()))
        if key not in seen:
            seen.add(key)
            full.append(inst)
    return full

def _walk(node, omega, memo, weights):
    """Return a list of partial assignments, one per minimum-cost path through node."""

    # base cases: true/false/literal
    if node.is_true():
        return [{}]
    if node.is_literal():
        lit = node.literal
        return [{abs(lit): lit > 0}]
    
    # find the minimum branch cost
    best = INF
    for p, s in node.elements(): # for each prime-sub branch, compute the distance to omega
        c = node_dist(p, omega, memo, weights) + node_dist(s, omega, memo, weights)
        best = min(best, c)

    # collect all branches achieving it, and cross-product their partial assignments
    out = []
    for p, s in node.elements():
        c = node_dist(p, omega, memo, weights) + node_dist(s, omega, memo, weights)
        if c != best:
            continue
        for pa in _walk(p, omega, memo, weights):
            for sa in _walk(s, omega, memo, weights):
                merged = dict(pa); merged.update(sa) # merge the two partial assignments into one
                out.append(merged)
    return out
