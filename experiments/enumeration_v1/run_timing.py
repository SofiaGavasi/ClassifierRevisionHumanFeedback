"""Enumeration timing on the shared suite (uses rgr.suite + the harness).

Metrics per rejected TIE instance: time to retrieve minimal-only reasons (stream),
time to retrieve all reasons (stream, worst case), naive PI-enumeration baseline,
and max/avg delay between consecutive reasons.

Run: python experiments/enumeration/run_timing.py
"""
import sys, os, time, statistics
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from itertools import product
from harness import run_experiment          # shared harness
from rgr.enumerate import enumerate_reasons, node_dist
from rgr.reasons import all_prime_implicants, disagreement
from rgr.sdd_utils import term_to_sdd

clock = time.perf_counter
REPS = 3

def _rejected_ties(mgr, sdd, nv, pis):
    for bits in product([False, True], repeat=nv):
        om = {i + 1: bits[i] for i in range(nv)}
        if not (term_to_sdd(om, mgr) & sdd).is_false():
            continue
        mind = min(disagreement(p, om) for p in pis)
        if sum(1 for p in pis if disagreement(p, om) == mind) >= 2:
            yield om, mind

def _time_min(sdd, om, mgr, nv, d0):
    def run():
        for _, _, dist in enumerate_reasons(sdd, om, mgr, nv):
            if dist > d0: break
    t = clock()
    for _ in range(REPS): run()
    return (clock() - t) / REPS

def _time_all(sdd, om, mgr, nv):
    ts = []; t0 = clock(); prev = t0; n = 0
    for _ in enumerate_reasons(sdd, om, mgr, nv):
        now = clock(); ts.append(now - prev); prev = now; n += 1
    total = clock() - t0
    dl = ts[1:] if len(ts) > 1 else ts
    return total, (max(dl) if dl else 0.0), (statistics.mean(dl) if dl else 0.0), n

def _time_naive(sdd, nv, mgr):
    t = clock()
    for _ in range(REPS): all_prime_implicants(sdd, nv, mgr)
    return (clock() - t) / REPS

def measure(mgr, sdd, entry):
    """Per-classifier: aggregate over its rejected tie instances (mean per classifier)."""
    nv = entry["nvars"]
    pis = all_prime_implicants(sdd, nv, mgr)
    rows = []
    for om, mind in _rejected_ties(mgr, sdd, nv, pis):
        d0 = node_dist(sdd, om, {})
        t_min = _time_min(sdd, om, mgr, nv, d0)
        t_all, mx, av, nall = _time_all(sdd, om, mgr, nv)
        t_nv = _time_naive(sdd, nv, mgr)
        rows.append((t_min, t_all, t_nv, mx, av))
    if not rows:
        return {"enum_minimal_us": 0.0, "enum_all_us": 0.0, "naive_all_us": 0.0,
                "max_delay_us": 0.0, "avg_delay_us": 0.0, "n_tie_instances": 0}
    agg = lambda i: statistics.mean(r[i] for r in rows)
    return {"enum_minimal_us": agg(0)*1e6, "enum_all_us": agg(1)*1e6,
            "naive_all_us": agg(2)*1e6, "max_delay_us": agg(3)*1e6,
            "avg_delay_us": agg(4)*1e6, "n_tie_instances": len(rows)}

if __name__ == "__main__":
    run_experiment("standard", measure, per="classifier", out="enumeration", group_keys=["nvars", "density"])