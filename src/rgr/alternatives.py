
from .distance import node_dist, INF

def _winning_path(node, omega, memo, acc):
    """This walks down the SDD following the cheapest branch, but instead of collecting variable assignments, 
       it collects the decision nodes themselves along the winning path, recording what happened at each.
    """
    if node.is_true() or node.is_false() or node.is_literal():
        return acc
    els = list(node.elements())
    bi, bc, be = None, INF, None
    for i, (p, s) in enumerate(els): # loop over the branches, find the cheapest one
        c = node_dist(p, omega, memo) + node_dist(s, omega, memo)
        if c < bc:
            bc, bi, be = c, i, (p, s)
    acc.append((node, bi, bc, els)) # record a tuple: this node, which branch won (bi), the winning cost (bc), and all its branches (els)
    #recurse into both halves of the winning branch
    _winning_path(be[0], omega, memo, acc)
    _winning_path(be[1], omega, memo, acc)
    return acc # the list of every decision node the winning route passed through

def _recon_override(node, omega, memo, oid, oidx):
    """Like _recon, but if we hit the decision node with id oid, we take the branch oidx instead of the winning branch."""

    if node.is_true():
        return {}
    if node.is_literal():
        lit = node.literal
        return {abs(lit): lit > 0}
    els = list(node.elements())
    if node.id == oid: # branch override: if this is the decision node we want to override, take the branch oidx instead of the winning branch
        p, s = els[oidx]
    else:
        p, s, bc = None, None, INF
        for pp, ss in els:
            c = node_dist(pp, omega, memo) + node_dist(ss, omega, memo)
            if c < bc:
                bc, p, s = c, pp, ss
    a = dict(_recon_override(p, omega, memo, oid, oidx))
    a.update(_recon_override(s, omega, memo, oid, oidx))
    return a

def alternatives(node, omega, nvars):
    """This ties them together and produces the list of alternatives.
    Return (d, [ {gap, instance, instance_distance}, ... ]). """
    # run the distance pass, get the optimal distance d, populate the cache.
    memo = {}
    d = node_dist(node, omega, memo)

    out = []
    for dec, wi, wc, els in _winning_path(node, omega, memo, []): # Loop over every decision node on the winning path, unpacking its recorded info
        for i, (p, s) in enumerate(els): # For each node, loop over its branches
            if i == wi: # skip the winning branch
                continue
            c = node_dist(p, omega, memo) + node_dist(s, omega, memo) # losing branch's cost
            if c == INF:
                continue
            partial = _recon_override(node, omega, memo, dec.id, i) # reconstruct the instance you'd get by overriding this node to this losing branch
            full = {v: partial.get(v, omega[v]) for v in range(1, nvars + 1)} # fill in the rest of the variables from omega (zero cost)
            out.append({
                "gap": c - wc, # how much more this branch costs than the winner at this node (local gap)
                "instance": full,
                "instance_distance": sum(1 for v in full if full[v] != omega[v]), # the Hamming distance from omega to this alternative instance
            })
    return d, out
