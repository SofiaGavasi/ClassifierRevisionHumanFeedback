"""
Complexity & worst-case: pipeline stays polynomial in |SDD|; parity is the
worst case for naive enumeration (small SDD, exponentially many PIs)."""
import time, pytest
from rgr.dataset import get_example, build_example
from rgr.edit import edit
from rgr.reasons import all_prime_implicants

def test_parity_small_sdd_many_reasons():
    """Parity: SDD size linear, prime-implicant count 2^(n-1)"""
    for n in [3, 4, 5]:
        mgr, sdd, ex = build_example(get_example(f"parity_{n}"))
        pis = all_prime_implicants(sdd, n, mgr)
        assert sdd.size() <= 4 * n            # linear-ish in n
        assert len(pis) == 2 ** (n - 1)       # exponential reasons
        # pipeline still runs fine
        res = edit(sdd, ex["test_instances"][0], mgr, n)
        assert res["distance"] is not None

def test_hwb_is_pipeline_worst_case():
    """HWB's SDD grows faster than parity's for the same variable count:
    it is the pipeline's worst case (no small SDD), not the naive method's"""
    sizes_hwb, sizes_parity = {}, {}
    for n in [4, 5, 6]:
        mgr, sdd, ex = build_example(get_example(f"hwb_{n}"))
        sizes_hwb[n] = sdd.size()
    for n in [4, 5]:
        mgr, sdd, ex = build_example(get_example(f"parity_{n}"))
        sizes_parity[n] = sdd.size()
    # HWB size strictly increases with n 
    assert sizes_hwb[4] < sizes_hwb[5] < sizes_hwb[6]
    # and at n=5 HWB's SDD is already larger than parity's
    assert sizes_hwb[5] > sizes_parity[5]
    # the pipeline still runs correctly on HWB, just over a larger |SDD|
    mgr, sdd, ex = build_example(get_example("hwb_6"))
    res = edit(sdd, ex["test_instances"][0], mgr, 6)
    assert res["distance"] is not None

def test_pipeline_faster_than_enumeration():
    """On parity_5 the pipeline is far cheaper than enumerating reasons:
    the naive method's worst case, where |SDD| is small but reasons are exponential"""
    mgr, sdd, ex = build_example(get_example("parity_5"))
    omega = ex["test_instances"][0]
    t0 = time.time()
    for _ in range(50):
        edit(sdd, omega, mgr, 5)
    t_pipe = (time.time() - t0) / 50
    t0 = time.time()
    all_prime_implicants(sdd, 5, mgr)
    t_enum = time.time() - t0
    assert t_pipe < t_enum   # pipeline cheaper than a single full enumeration