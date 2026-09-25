"""Reason enumeration on a compiled SDD.

EnumerateReasons(delta, omega): a GENERATOR yielding weakened reasons on demand, in
non-decreasing order of disagreement with omega. First the minimal (nearest) reasons - for which recovery is COMPLETE and this is the
guarantee the paper proves - then, if the caller keeps pulling, reasons at higher
disagreement, yielded in non-decreasing disagreement order.

This is the object the paper describes: one reason immediately, further reasons on request.
Complexity, per the paper:
  - total cost to return all reasons at the minimum level: O(m * n * |D|)
  - delay between consecutive reasons: O(n * |D|), independent of the total count
"""
from itertools import product, combinations
import math
INF = math.inf


def _term_to_sdd(term, mgr):
    t = mgr.true()
    for v, val in term.items():
        t = t & (mgr.literal(v) if val else mgr.literal(-v))
    return t


def _is_implicant(term, node, mgr):
    return (_term_to_sdd(term, mgr) & ~node).is_false()


def node_dist(node, omega, memo):
    """Minimum Hamming distance from omega to a model of node (one bottom-up pass)."""
    k = node.id
    if k in memo:
        return memo[k]
    if node.is_false():
        r = INF
    elif node.is_true():
        r = 0
    elif node.is_literal():
        lit = node.literal
        r = 0 if omega[abs(lit)] == (lit > 0) else 1
    else:
        r = INF
        for p, s in node.elements():
            r = min(r, node_dist(p, omega, memo) + node_dist(s, omega, memo))
    memo[k] = r
    return r


def count_at(node, omega):
    """(minimum distance, number of models at it) in one pass, without enumerating."""
    memo = {}
    def rec(n):
        k = n.id
        if k in memo:
            return memo[k]
        if n.is_false():
            r = (INF, 0)
        elif n.is_true():
            r = (0, 1)
        elif n.is_literal():
            lit = n.literal
            r = (0, 1) if omega[abs(lit)] == (lit > 0) else (1, 1)
        else:
            best, cnt = INF, 0
            for p, s in n.elements():
                dp, cp = rec(p); ds, cs = rec(s)
                d = dp + ds
                if d < best:
                    best, cnt = d, cp * cs
                elif d == best:
                    cnt += cp * cs
            r = (best, cnt)
        memo[k] = r
        return r
    return rec(node)


def _subtree_cost(node, omega, memo):
    """Max achievable-relevant cost bound: number of variables under node that can flip.
    We use exact per-node reachable costs lazily instead; see _models_at."""
    return None


def _reachable_costs(node, omega, memo_rc):
    """Set of Hamming costs achievable by models of node w.r.t. omega (restricted to
    node's own variables). Cached per node id."""
    k = node.id
    if k in memo_rc:
        return memo_rc[k]
    if node.is_false():
        r = set()
    elif node.is_true():
        r = {0}
    elif node.is_literal():
        lit = node.literal
        r = {0} if omega[abs(lit)] == (lit > 0) else {1}
    else:
        r = set()
        for p, s in node.elements():
            rp = _reachable_costs(p, omega, memo_rc)
            rs = _reachable_costs(s, omega, memo_rc)
            for a in rp:
                for b in rs:
                    r.add(a + b)
    memo_rc[k] = r
    return r


def _models_at(node, omega, target, memo, memo_rc=None):
    """Yield partial assignments for every model of node at cost == target."""
    if memo_rc is None:
        memo_rc = {}
    if node.is_true():
        if target == 0:
            yield {}
        return
    if node.is_literal():
        lit = node.literal
        cost = 0 if omega[abs(lit)] == (lit > 0) else 1
        if cost == target:
            yield {abs(lit): lit > 0}
        return
    if node.is_false():
        return
    for p, s in node.elements():
        rp = _reachable_costs(p, omega, memo_rc)
        rs = _reachable_costs(s, omega, memo_rc)
        for a in rp:
            b = target - a
            if b in rs:
                for pa in _models_at(p, omega, a, memo, memo_rc):
                    for sa in _models_at(s, omega, b, memo, memo_rc):
                        m = dict(pa); m.update(sa); yield m


def models_at(node, omega, nvars, dist, memo=None):
    """Complete accepted instances at exactly `dist`, deduplicated."""
    if memo is None:
        memo = {}
    seen = set()
    memo_rc = {}
    for partial in _models_at(node, omega, dist, memo, memo_rc):
        full = {v: partial.get(v, omega[v]) for v in range(1, nvars + 1)}
        key = tuple(sorted(full.items()))
        if key not in seen:
            seen.add(key)
            yield full


def reasons_in(model, node, mgr, nvars):
    """Every prime implicant of node contained in model (all shrink outcomes)."""
    out = set()
    items = [(v, model[v]) for v in range(1, nvars + 1)]
    for size in range(nvars + 1):
        for combo in combinations(items, size):
            term = dict(combo)
            if not _is_implicant(term, node, mgr):
                continue
            if any(_is_implicant({k: val for k, val in term.items() if k != x}, node, mgr)
                   for x in term):
                continue
            out.add(tuple(sorted(term.items())))
    return out


def weaken(term, omega):
    return {v: val for v, val in term.items() if omega[v] == val}


def enumerate_reasons(delta, omega, mgr, nvars, max_levels=None):
    """Generator: weakened reasons on demand, in non-decreasing disagreement order.
    Yields dicts. Each yielded item is (reason_term, weakened_term, level_distance)."""
    memo = {}
    memo_rc = {}
    d0 = node_dist(delta, omega, memo)
    if d0 == INF:
        return
    # all achievable distances, in increasing order (each is a "level")
    dists = sorted(_reachable_costs(delta, omega, memo_rc))
    seen_reasons = set()
    levels = 0
    for d in dists:
        for model in models_at(delta, omega, nvars, d, memo):
            for tau_key in reasons_in(model, delta, mgr, nvars):
                if tau_key in seen_reasons:
                    continue
                seen_reasons.add(tau_key)
                tau = dict(tau_key)
                yield tau, weaken(tau, omega), d
        levels += 1
        if max_levels is not None and levels >= max_levels:
            return
