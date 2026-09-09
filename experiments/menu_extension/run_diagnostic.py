"""
Standalone counting diagnostic: for each tie case, count the number of nearest models (cheaply, via rgr.count.nearest_count), and relate that count to whether the bounded single-path menu is incomplete. 
Answers: "is full enumeration cheap exactly where the bounded menu fails?"

Run:  python experiments/menu_extension/run_diagnostic.py
"""
import sys, os, statistics
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from itertools import product
from rgr.suite import load_suite, build_classifier
from rgr.reasons import all_prime_implicants, disagreement
from rgr.reconstruct import nearest_model
from rgr.shrink import greedy_shrink
from rgr.alternatives import alternatives
from rgr.count import nearest_count
from rgr.sdd_utils import term_to_sdd


def minimal(pis, omega): # returns the subset of prime implicants that are minimal w.r.t. disagreement with omega, and the minimum disagreement value
    m = min(disagreement(p, omega) for p in pis)
    return set(tuple(sorted(p.items())) for p in pis if disagreement(p, omega) == m)

def bounded_menu(delta, omega, nv, mgr):
    # returns the set of reasons (as tuples) that are returned by the bounded single-path menu for the given disagreement delta and rejected instance omega
    # The returned reasons are shrunk to minimal size
    rec = set()
    w0, _ = nearest_model(delta, omega, nv)
    if w0 is None:
        return rec
    rec.add(tuple(sorted(greedy_shrink(w0, delta, mgr).items())))
    _, alts = alternatives(delta, omega, nv)
    for a in alts:
        if a["gap"] == 0:
            rec.add(tuple(sorted(greedy_shrink(a["instance"], delta, mgr).items())))
    return rec

def main():
    suite = load_suite("standard")
    pic = {}
    counts_all, counts_incomplete = [], []
    tie_cases = incomplete = 0

    for entry in suite["classifiers"]:
        nv = entry["nvars"]; cid = entry["id"]
        mgr, sdd = build_classifier(entry, vtree_type="right")

        if cid not in pic:# we only enumerate the PI once and cache them
            pic[cid] = [dict(p) for p in all_prime_implicants(sdd, nv, mgr)]
        pis = pic[cid]

        for bits in product([False, True], repeat=nv): # for each possible rejected instance (omega)
            om = {i + 1: bits[i] for i in range(nv)} 
            if not (term_to_sdd(om, mgr) & sdd).is_false(): # if omega is accepted, skip it
                continue

            mset = minimal(pis, om) # subset of prime implicants that are minimal w.r.t. disagreement with omega
            if len(mset) < 2: # if there is no tie, skip it
                continue

            tie_cases += 1
            _, ncount = nearest_count(sdd, om)     # THE CHEAP COUNT (no enumeration)
            counts_all.append(ncount)
            
            bm = bounded_menu(sdd, om, nv, mgr) & mset # the set of minimal reasons that are recovered by the bounded single-path menu
            if bm != mset:                          # bounded menu incomplete here
                incomplete += 1
                counts_incomplete.append(ncount)

    def stats(xs):
        return f"mean={statistics.mean(xs):.2f} median={statistics.median(xs)} max={max(xs)}" if xs else "n/a"

    print("Counting diagnostic (nearest-model count per tie case)")
    print("=" * 55)
    print(f"tie cases: {tie_cases}")
    print(f"bounded menu incomplete in: {incomplete} ({100*incomplete/tie_cases:.1f}% of ties)")
    print()
    print(f"nearest-model count, ALL tie cases      : {stats(counts_all)}")
    print(f"nearest-model count, INCOMPLETE cases   : {stats(counts_incomplete)}")
    print()
    for thr in [4, 8, 16, 32]:
        cheap = sum(1 for c in counts_incomplete if c <= thr)
        print(f"  incomplete cases with count <= {thr:2d}: "
              f"{cheap}/{len(counts_incomplete)} ({100*cheap/max(1,len(counts_incomplete)):.0f}%)")
    print()

if __name__ == "__main__":
    main()