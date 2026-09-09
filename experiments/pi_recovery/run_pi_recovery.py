"""
PI-recovery experiment.

Measures, per rejected instance, the fraction of minimal-disagreement reasons recovered by the gap-0 alternatives menu, under each vtree. 
Runs on the shared frozen suite so it uses the same classifiers as every other experiment.

Run:  python experiments/pi_recovery/run_pi_recovery.py
"""


import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from harness import run_experiment
from rgr.reasons import all_prime_implicants, disagreement
from rgr.reconstruct import nearest_model
from rgr.shrink import greedy_shrink
from rgr.alternatives import alternatives

def _minimal(pis, omega): # returns the subset of prime implicants that are minimal w.r.t. disagreement with omega, and the minimum disagreement value.
    if not pis: return set(), None
    mind = min(disagreement(p, omega) for p in pis)
    return set(tuple(sorted(p.items())) for p in pis
               if disagreement(p, omega) == mind), mind


def _menu_reasons(delta, omega, nvars, mgr): 
    # returns the set of reasons (as tuples) that are returned by the alternatives menu for the given disagreement delta and rejected instance omega. 
    # The returned reasons are shrunk to minimal size.
    rec = set()
    w0, _ = nearest_model(delta, omega, nvars) 
    if w0 is None: return rec
    rec.add(tuple(sorted(greedy_shrink(w0, delta, mgr).items())))  # we shrink the nearest model to a minimal reason before adding it to the recovered set
    _, alts = alternatives(delta, omega, nvars)# returns a list of alternative instances (and their disagreement values) that are returned by the alternatives menu
    for a in alts:
        if a["gap"] == 0:
            rec.add(tuple(sorted(greedy_shrink(a["instance"], delta, mgr).items()))) # we shrink the alternative instance to a minimal reason before adding it to the recovered set
    return rec


# PI cache: prime implicants depend only on the FUNCTION (the classifier id), not on the vtree or the instance, so compute them once per classifier
_PI_CACHE = {}

def measure(mgr, sdd, entry, omega): 
    """ Measures one rejected instance (omega) for the given classifier (mgr, sdd) 
         and returns a dict of metrics: number of minimal reasons, whether there is a tie, and the fraction of minimal reasons recovered by the alternatives menu.
    """
    nv = entry["nvars"]
    cid = entry["id"]
    if cid not in _PI_CACHE: # we only enumerate the PI once and cache them
        pis = all_prime_implicants(sdd, nv, mgr)
        _PI_CACHE[cid] = [dict(p) for p in pis]
    pis = _PI_CACHE[cid]

    minimal, _ = _minimal(pis, omega) # the set of minimal-disagreement reasons for this rejected instance

    if not minimal: # if there are no minimal reasons, we consider the recovery to be 100% (trivially recovered) and there is no tie
        return {"num_minimal": 0, "is_tie": 0, "recovery": 1.0}
    
    rec = _menu_reasons(sdd, omega, nv, mgr) & minimal # the set of minimal reasons that are recovered by the alternatives menu
    return {"num_minimal": len(minimal),
            "is_tie": int(len(minimal) > 1),
            "recovery": round(len(rec) / len(minimal), 4)}



if __name__ == "__main__":
    # we call the harness to run the experiment on the shared frozen suite, measuring per rejected instance, and saving the results to a CSV file.
    run_experiment("standard", measure, per="instance", vtrees=("right", "left", "balanced"), out="pi_recovery", group_keys=["nvars", "density"])
