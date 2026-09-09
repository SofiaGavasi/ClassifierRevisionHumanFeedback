"""
Counts the minimum-distance models of an SDD to a target instance, without enumerating them. 
One bottom-up pass like model counting, carrying (min_dist, count):
  literal: (0,1) if it matches omega, else (1,1)
  true:    (0,1)      false: (inf,0)
  decomposition: for each prime-sub branch, distance = dp+ds, count = cp*cs;
                 the node takes the minimum distance and sums the counts of the branches achieving that minimum.

This gives, for cheap, the number of nearest models.
"""
import math
INF = math.inf

def _dc(node, omega, memo, weights):
    k = node.id
    if k in memo:
        return memo[k]

    # if true/false/literal, we can compute the distance and count directly
    if node.is_false():
        r = (INF, 0)
    elif node.is_true():
        r = (0, 1)
    elif node.is_literal():
        lit = node.literal
        cost = weights[abs(lit)] if weights else 1
        r = (0, 1) if omega[abs(lit)] == (lit > 0) else (cost, 1)

    # decomposition: we need to combine the distances and counts of the prime-sub branches 
    else:
        best, cnt = INF, 0
        for p, s in node.elements():
            dp, cp = _dc(p, omega, memo, weights) # the distance and count of the prime branch
            ds, cs = _dc(s, omega, memo, weights) # the distance and count of the sub branch
            d, c = dp + ds, cp * cs # the distance and count of this branch
            if d < best: # new best distance
                best, cnt = d, c # update the best distance and count
            elif d == best:
                cnt += c # increase the count of nearest models if this branch is tied for best
        r = (best, cnt)
        
    memo[k] = r
    return r

def nearest_count(node, omega, weights=None):
    """Return (min_distance, number_of_models_at_that_distance)."""
    return _dc(node, omega, {}, weights)
