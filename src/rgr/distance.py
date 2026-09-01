"""bottom-up nearest-instance distance over an SDD.

dist(node) = min Hamming distance from omega to a model of node.
Supports optional per-variable weights (weighted minimality).
Rules: literal -> 0/weight; true -> 0; false -> inf; decomposition -> min_i(prime+sub).
"""
import math
INF = math.inf

def node_dist(node, omega, memo, weights=None):
    key = node.id
    if key in memo:
        return memo[key]
    if node.is_false():
        r = INF
    elif node.is_true():
        r = 0
    elif node.is_literal():
        lit = node.literal
        v = abs(lit)
        cost = weights[v] if weights else 1
        r = 0 if omega[v] == (lit > 0) else cost
    else:
        r = INF
        for prime, sub in node.elements():
            r = min(r, node_dist(prime, omega, memo, weights)
                     + node_dist(sub, omega, memo, weights))
    memo[key] = r
    return r
