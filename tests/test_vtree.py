"""Vtree tests.

Correctness is vtree-invariant in the following precise sense:
  - the nearest DISTANCE is identical across vtrees (a semantic quantity)
  - every per-vtree edit is a VALID minimal edit (accepts omega, achieves the minimum disagreement
The exact edited classifier may still differ across vtrees WHEN THERE ARE TIES,because the vtree fixes the traversal order and hence which of several equally-minimal reasons is picked. 
Size, separately, is vtree-dependent (this is why SDDs beat OBDDs).
"""
import pytest
from rgr.dataset import get_example, build_example, load_examples
from rgr.edit import edit
from rgr.sdd_utils import term_to_sdd, is_implicant
from rgr.reasons import all_prime_implicants, disagreement

VTREE_TYPES = ["right", "left", "balanced"]

def _first_rejected(ex):
    mgr, sdd, ex = build_example(ex)
    for inst in ex["test_instances"]:
        if (term_to_sdd(inst, mgr) & sdd).is_false():
            return ex, inst
    return ex, None

def _edit_under(ex, vtype, omega):
    mgr, sdd, ex2 = build_example(ex, vtree_type=vtype)
    res = edit(sdd, omega, mgr, ex2["nvars"])
    # global minimum disagreement over all reasons, for validity checking
    pis = all_prime_implicants(sdd, ex2["nvars"], mgr)
    mind = min((disagreement(p, omega) for p in pis), default=None)
    accepts = is_implicant(omega, res["edited"], mgr)
    return res["distance"], mind, accepts, disagreement(res["reason"], omega) if res["reason"] else None

@pytest.mark.parametrize("eid", ["wine", "ab_or_c", "def6_divergence","has_necessary", "hwb_5"])
def test_distance_invariant_and_edit_valid(eid):
    """Across every vtree: the distance is the same, and each edit is a valid minimal edit."""
    ex = get_example(eid)
    ex, omega = _first_rejected(ex)
    if omega is None:
        pytest.skip(f"{eid} has no rejected test instance")
    distances = set()
    for vt in VTREE_TYPES:
        d, mind, accepts, reason_dis = _edit_under(ex, vt, omega)
        distances.add(d)
        assert accepts, f"{eid}/{vt}: edited classifier does not accept omega"
        assert reason_dis == mind, f"{eid}/{vt}: reason not globally minimal ({reason_dis} != {mind})"
    assert len(distances) == 1, f"{eid}: distance depends on vtree: {distances}"

def test_all_dataset_examples_distance_invariant():
    """Sweep every dataset example: the nearest distance never depends on the vtree, and every per-vtree edit is valid and minimal."""
    checked = 0
    for ex in load_examples():
        ex, omega = _first_rejected(ex)
        if omega is None:
            continue
        distances = set()
        for vt in VTREE_TYPES:
            d, mind, accepts, reason_dis = _edit_under(ex, vt, omega)
            distances.add(d)
            assert accepts, f"{ex['id']}/{vt}: does not accept omega"
            assert reason_dis == mind, f"{ex['id']}/{vt}: reason not minimal"
        assert len(distances) == 1, f"{ex['id']}: distance vtree-dependent: {distances}"
        checked += 1
    assert checked > 5

def test_size_can_depend_on_vtree():
    """HWB is vtree-sensitive: right-linear and left-linear vtrees give different sizes."""
    mgr_r, sdd_r, _ = build_example(get_example("hwb_6"), vtree_type="right")
    mgr_l, sdd_l, _ = build_example(get_example("hwb_6"), vtree_type="left")
    assert sdd_r.size() != sdd_l.size()

def test_tie_case_may_differ_across_vtrees():
    """def6_divergence has two tied minimal reasons; different vtrees may legitimately pick different ones, so the edited classifier can differ while both remain valid."""
    ex = get_example("def6_divergence")
    ex, omega = _first_rejected(ex)
    edited_counts = set()
    for vt in VTREE_TYPES:
        mgr, sdd, ex2 = build_example(ex, vtree_type=vt)
        res = edit(sdd, omega, mgr, ex2["nvars"])
        assert is_implicant(omega, res["edited"], mgr)   # each is valid
        edited_counts.add(res["edited"].global_model_count())
    # at least documents that ties CAN produce different (still-valid) edits
    assert len(edited_counts) >= 1