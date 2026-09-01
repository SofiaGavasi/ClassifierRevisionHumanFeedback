"""Top-level engine entry point.

edit(delta, omega, mgr, nvars, weights=None) ->
    dict with keys: 'edited', 'reason', 'weakened', 'distance', 'alternatives'

Pipeline: nearest instance (R1+R2) -> greedy shrink (reason) ->
weaken by dropping disagreeing literals -> disjoin into delta (R-simplification).
"""
from .reconstruct import nearest_model
from .shrink import greedy_shrink
from .sdd_utils import term_to_sdd

def edit(delta, omega, mgr, nvars, weights=None):
    omega_is_model = not (term_to_sdd(omega, mgr) & delta).is_false()
    if omega_is_model:
        # omega already accepted: no-op
        return {"edited": delta, "reason": None, "weakened": None,
                "distance": 0, "alternatives": []}
    omega0, d = nearest_model(delta, omega, nvars, weights)
    reason = greedy_shrink(omega0, delta, mgr)
    weakened = {v: val for v, val in reason.items() if omega[v] == val}
    edited = delta | term_to_sdd(weakened, mgr)
    return {"edited": edited, "reason": reason, "weakened": weakened,
            "distance": d, "alternatives": []}
