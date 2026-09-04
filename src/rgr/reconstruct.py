"""recover the nearest instance itself via winning-branch backpointers,
filling variables unmentioned by winning branches from omega (zero cost)."""
from .distance import node_dist, INF

def _recon(node, omega, memo, weights): 
    """
      It walks the SDD and, at each decomposition node, follows the branch that achieved the minimum distance, 
      collecting the variable assignments along the way. 
      It returns a partial assignment (a dictionary of variable -> true/false)."""
    
    if node.is_true():
        return {}
    if node.is_literal(): # returns a dictionary with the variable and its value 
        lit = node.literal
        return {abs(lit): lit > 0}
    # if it's a decomposition, find the branch that achieved the minimum distance and recurse down that branch
    best, bc = None, INF
    for prime, sub in node.elements():
        c = node_dist(prime, omega, memo, weights) + node_dist(sub, omega, memo, weights)
        if c < bc:
            bc, best = c, (prime, sub)
    a = dict(_recon(best[0], omega, memo, weights))
    a.update(_recon(best[1], omega, memo, weights))
    return a

def nearest_model(node, omega, nvars, weights=None):
    # first run the distance pass, which both gives the distance and populates the memo cache that _recon will reuse
    memo = {}
    d = node_dist(node, omega, memo, weights)

    if d == INF: # if the classifier has no models at all (unsatisfiable), there's no nearest instance to find
        return None, INF
    
    partial = _recon(node, omega, memo, weights) # partial assignment from winning branches
    full = {v: partial.get(v, omega[v]) for v in range(1, nvars + 1)} # builds a complete assignment over all variables that are missing in partial by filling in from omega (zero cost)
    return full, d
