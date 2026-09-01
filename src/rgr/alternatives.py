
from .distance import node_dist, INF

def _winning_path(node, omega, memo, acc):
    if node.is_true() or node.is_false() or node.is_literal():
        return acc
    els = list(node.elements())
    bi, bc, be = None, INF, None
    for i, (p, s) in enumerate(els):
        c = node_dist(p, omega, memo) + node_dist(s, omega, memo)
        if c < bc:
            bc, bi, be = c, i, (p, s)
    acc.append((node, bi, bc, els))
    _winning_path(be[0], omega, memo, acc)
    _winning_path(be[1], omega, memo, acc)
    return acc

def _recon_override(node, omega, memo, oid, oidx):
    if node.is_true():
        return {}
    if node.is_literal():
        lit = node.literal
        return {abs(lit): lit > 0}
    els = list(node.elements())
    if node.id == oid:
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
    """Return (d, [ {gap, instance, instance_distance}, ... ])."""
    memo = {}
    d = node_dist(node, omega, memo)
    out = []
    for dec, wi, wc, els in _winning_path(node, omega, memo, []):
        for i, (p, s) in enumerate(els):
            if i == wi:
                continue
            c = node_dist(p, omega, memo) + node_dist(s, omega, memo)
            if c == INF:
                continue
            partial = _recon_override(node, omega, memo, dec.id, i)
            full = {v: partial.get(v, omega[v]) for v in range(1, nvars + 1)}
            out.append({
                "gap": c - wc,
                "instance": full,
                "instance_distance": sum(1 for v in full if full[v] != omega[v]),
            })
    return d, out
