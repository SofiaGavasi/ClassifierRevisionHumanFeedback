"""The two readings of Definition 6:
  - the pipeline's reason is always a minimal reason;
  - the pipeline edit equals Def 6 with S_w = that single reason;
  - the all-minimal reading can differ from the single-reason reading."""
import random
from rgr.dataset import get_example, build_example
from rgr.compare import compare_readings, edit_all_minimal, equivalent
from rgr.edit import edit
from rgr.sdd_utils import build, term_to_sdd, is_implicant
from rgr.reasons import all_prime_implicants, disagreement, weaken

def test_divergence_example_differs():
    """The crafted def6_divergence example: the two readings do NOT coincide"""
    mgr, sdd, ex = build_example(get_example("def6_divergence"))
    rep = compare_readings(sdd, ex["test_instances"][0], ex["nvars"], mgr)
    assert rep["applicable"]
    assert rep["coincide"] is False or rep["coincide"] == 0
    # all-minimal opens the classifier wider than single-reason
    assert rep["models_all_minimal"] > rep["models_single"]

def test_pipeline_reason_always_minimal_and_singleton_matches():
    """Across random classifiers: pipeline reason is minimal, and equals Def6 with S_w={tau}."""
    rng = random.Random(7)
    def rand(mgr, nv, nc):
        f = mgr.true()
        for _ in range(nc):
            vs = rng.sample(range(1,nv+1), rng.randint(1,min(3,nv)))
            cl = mgr.false()
            for v in vs: cl = cl | mgr.literal(v if rng.random()<0.5 else -v)
            f = f & cl
        return f
    checked = 0
    for _ in range(120):
        nv = rng.randint(3,5)
        mgr = build(nv, vtree_type=rng.choice(["right","balanced"]))[0]
        delta = rand(mgr, nv, rng.randint(1,4))
        if delta.is_false() or delta.is_true(): continue
        omega = {v: rng.random()<0.5 for v in range(1,nv+1)}
        if not (term_to_sdd(omega,mgr) & delta).is_false(): continue  # accepted
        S = all_prime_implicants(delta, nv, mgr)
        if not S: continue
        checked += 1
        res = edit(delta, omega, mgr, nv)
        tau = res["reason"]
        mind = min(disagreement(t,omega) for t in S)
        minimal = [t for t in S if disagreement(t,omega)==mind]
        # (1) tau is minimal
        assert any(tuple(sorted(tau.items()))==tuple(sorted(t.items())) for t in minimal)
        # (2) pipeline edit == Def6 with S_w = {tau}
        res_single = delta | term_to_sdd(weaken(tau,omega), mgr)
        assert equivalent(res["edited"], res_single)
    assert checked > 20
