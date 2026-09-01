"""recover the nearest instance itself via winning-branch backpointers,
filling variables unmentioned by winning branches from omega (zero cost)."""
from .distance import node_dist, INF

def _recon(node, omega, memo, weights):
    if node.is_true():
        return {}
    if node.is_literal():
        lit = node.literal
        return {abs(lit): lit > 0}
    best, bc = None, INF
    for prime, sub in node.elements():
        c = node_dist(prime, omega, memo, weights) + node_dist(sub, omega, memo, weights)
        if c < bc:
            bc, best = c, (prime, sub)
    a = dict(_recon(best[0], omega, memo, weights))
    a.update(_recon(best[1], omega, memo, weights))
    return a

def nearest_model(node, omega, nvars, weights=None):
    memo = {}
    d = node_dist(node, omega, memo, weights)
    if d == INF:
        return None, INF
    partial = _recon(node, omega, memo, weights)
    full = {v: partial.get(v, omega[v]) for v in range(1, nvars + 1)}
    return full, d
