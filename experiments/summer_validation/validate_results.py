"""Summer validation: reproduce and check Results 1-4 against the current engine.


  Result 1: bottom-up distance == brute-force nearest distance
  Result 2: reconstructed instance is a genuine model at exactly that distance
  Result 3: greedy-shrink reason is a genuine PI achieving the global-min disagreement   (robust to shrink order and to ties)
  Result 4: each alternative sits at distance d+gap; its reason disagreement is in [d, d+gap]

Run:  python experiments/summer_validation/validate_results.py
"""
import os, random, itertools
from rgr.sdd_utils import build, term_to_sdd, is_implicant
from rgr.edit import edit
from rgr.reconstruct import nearest_model
from rgr.shrink import greedy_shrink, disagreement
from rgr.alternatives import alternatives
from rgr.reasons import all_prime_implicants
from rgr.dataset import load_examples, build_example

OUT = os.path.join(os.path.dirname(__file__), "outputs")
os.makedirs(OUT, exist_ok=True)

def brute_nearest(node, omega, nvars, mgr):
    best, bd = None, float("inf")
    for bits in itertools.product([False, True], repeat=nvars):
        asg = {v: bits[v - 1] for v in range(1, nvars + 1)}
        if not is_implicant(asg, node, mgr):
            continue
        d = sum(1 for v in range(1, nvars + 1) if asg[v] != omega[v])
        if d < bd:
            bd, best = d, asg
    return best, bd

def check_canonical(report):
    report.append("== Canonical examples ==")
    for eid in ["wine", "ab_or_c", "def6_divergence", "xnor", "has_necessary"]:
        ex = next(e for e in load_examples() if e["id"] == eid)
        mgr, sdd, ex = build_example(ex)
        nv = ex["nvars"]
        for omega in ex["test_instances"]:
            if not (term_to_sdd(omega, mgr) & sdd).is_false():
                continue  # accepted, skip
            res = edit(sdd, omega, mgr, nv)
            _, bd = brute_nearest(sdd, omega, nv, mgr)
            ok = (res["distance"] == bd) and is_implicant(omega, res["edited"], mgr)
            report.append(f"  {eid:16s} dist={res['distance']} (brute={bd}) "
                          f"reason={res['reason']} -> {'OK' if ok else 'FAIL'}")

def check_random(report, trials=300, seed=7):
    rng = random.Random(seed)
    f1 = f2 = f3 = f4 = 0
    tested = 0
    for _ in range(trials):
        nv = rng.randint(3, 6)
        mgr = build(nv, vtree_type=rng.choice(["right", "balanced", "left"]))[0]
        # random CNF
        delta = mgr.true()
        for _ in range(rng.randint(1, 4)):
            vs = rng.sample(range(1, nv + 1), rng.randint(1, min(3, nv)))
            cl = mgr.false()
            for v in vs:
                cl = cl | mgr.literal(v if rng.random() < 0.5 else -v)
            delta = delta & cl
        if delta.is_false() or delta.is_true():
            continue
        omega = {v: rng.random() < 0.5 for v in range(1, nv + 1)}
        if not (term_to_sdd(omega, mgr) & delta).is_false():
            continue
        tested += 1
        # R1 + R2
        full, d = nearest_model(delta, omega, nv)
        _, bd = brute_nearest(delta, omega, nv, mgr)
        if d != bd: f1 += 1; continue
        if not is_implicant(full, delta, mgr) or sum(1 for v in full if full[v] != omega[v]) != d:
            f2 += 1; continue
        # R3: shrink in several orders, check PI + global-min disagreement
        pis = all_prime_implicants(delta, nv, mgr)
        if not pis: continue
        mind = min(disagreement(p, omega) for p in pis)
        for _ in range(4):
            order = list(range(1, nv + 1)); rng.shuffle(order)
            tau = greedy_shrink(full, delta, mgr, order)
            if not any(tau == p for p in pis): f3 += 1
            if disagreement(tau, omega) != mind: f3 += 1
        # R4: alternatives bound
        d4, alts = alternatives(delta, omega, nv)
        for a in alts:
            if a["instance_distance"] != d4 + a["gap"]: f4 += 1
            tau_a = greedy_shrink(a["instance"], delta, mgr)
            if not (d4 <= disagreement(tau_a, omega) <= d4 + a["gap"]): f4 += 1
    report.append("\n== Random stress test ==")
    report.append(f"  tested (rejected-omega): {tested}")
    report.append(f"  Result 1 (distance)        failures: {f1}")
    report.append(f"  Result 2 (reconstruction)  failures: {f2}")
    report.append(f"  Result 3 (shrink/min)      failures: {f3}")
    report.append(f"  Result 4 (alternatives)    failures: {f4}")
    report.append(f"  OVERALL: {'PASS' if f1+f2+f3+f4 == 0 else 'FAILURES FOUND'}")

def main():
    report = ["Summer validation report", "=" * 40, ""]
    check_canonical(report)
    check_random(report)
    text = "\n".join(report)
    print(text)
    with open(os.path.join(OUT, "validation_report.txt"), "w") as fh:
        fh.write(text + "\n")
    print(f"\nwrote {os.path.join(OUT, 'validation_report.txt')}")

if __name__ == "__main__":
    main()
