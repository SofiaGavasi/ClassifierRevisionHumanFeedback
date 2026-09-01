"""
  - SET / all-minimal reading: weaken ALL minimal reasons (S_w = min(S,<=dis)).
  - SINGLE-REASON / cardinality reading: weaken ONE reason from a nearest instance
    (what the tractable pipeline computes).
 the set version enumerates PIs and is exponential.
"""
from .reasons import all_prime_implicants, disagreement, weaken, minimal_reasons
from .sdd_utils import term_to_sdd, is_implicant
from .edit import edit as pipeline_edit

def edit_all_minimal(delta, omega, nvars, mgr):
    """Definition 6 with S_w = all minimal reasons. Returns (edited_sdd, minimal_reasons, mind)"""
    S = all_prime_implicants(delta, nvars, mgr)
    if not S:
        return None, [], None
    mind = min(disagreement(t, omega) for t in S)
    Sw = [t for t in S if disagreement(t, omega) == mind]
    result = mgr.false()
    for t in S:
        if disagreement(t, omega) == mind:
            result = result | term_to_sdd(weaken(t, omega), mgr)
        else:
            result = result | term_to_sdd(t, mgr)
    return result, Sw, mind

def equivalent(a, b):
    return (a & ~b).is_false() and (b & ~a).is_false()

def compare_readings(delta, omega, nvars, mgr):
    """Run both readings and report whether they coincide, plus diagnostics"""
    # skip if omega already accepted
    if not (term_to_sdd(omega, mgr) & delta).is_false():
        return {"applicable": False, "reason": "omega already accepted"}
    e_all, Sw, mind = edit_all_minimal(delta, omega, nvars, mgr)
    res = pipeline_edit(delta, omega, mgr, nvars)
    e_single = res["edited"]
    same = equivalent(e_all, e_single)
    # is the pipeline's reason one of the minimal reasons?
    tau = res["reason"]
    tau_in_min = tau is not None and any(
        tuple(sorted(tau.items())) == tuple(sorted(t.items())) for t in Sw)
    return {
        "applicable": True,
        "coincide": same,
        "min_disagreement": mind,
        "pipeline_distance": res["distance"],
        "num_minimal_reasons": len(Sw),
        "pipeline_reason_is_minimal": tau_in_min,
        "models_all_minimal": e_all.global_model_count(),
        "models_single": e_single.global_model_count(),
    }
