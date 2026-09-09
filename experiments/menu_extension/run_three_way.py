"""
Three-way comparison on the same task: recover the tied minimal reasons for a rejected instance. 
Each reports both its TIME and its RECOVERY fraction (against brute-force ground truth)

Methods:
  bounded   : original single-path menu (fast, but incomplete).
  extension : all nearest models + complete shrinking (complete by construction).
  enum      : enumerate ALL prime implicants, then filter to the minimal ones (the naive complete baseline; enumeration dominates its cost).

Only tie cases are timed (where the three can differ). Timing uses perf_counter, averaged.

Run:  python experiments/menu_extension/run_three_way.py
Outputs: outputs/three_way_results.csv, outputs/three_way_summary.txt
"""
import sys, os, csv, time, statistics
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from itertools import product, combinations
from rgr.suite import load_suite, build_classifier
from rgr.reasons import all_prime_implicants, disagreement
from rgr.reconstruct import nearest_model
from rgr.shrink import greedy_shrink
from rgr.alternatives import alternatives
from rgr.nearest_all import all_nearest_models
from rgr.sdd_utils import term_to_sdd, is_implicant

OUT = os.path.join(os.path.dirname(__file__), "outputs")
os.makedirs(OUT, exist_ok=True)
clock = time.perf_counter
REPS = 10  # average each timed method over this many runs

def avg_time(fn, reps=REPS):
    t0 = clock()
    for _ in range(reps):
        fn()
    return (clock() - t0) / reps


#___________________________________________________________________________
# THREE METHODS

def method_bounded(delta, omega, nv, mgr):
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

def _reachable_pis(model, node, mgr, nv):
    out = set()
    items = [(v, model[v]) for v in range(1, nv + 1)]
    for size in range(0, nv + 1):
        for combo in combinations(items, size):
            term = dict(combo)
            if not is_implicant(term, node, mgr):
                continue
            if any(is_implicant({k: v for k, v in term.items() if k != x}, node, mgr)
                   for x in term):
                continue
            out.add(tuple(sorted(term.items())))
    return out

def method_extension(delta, omega, nv, mgr):
    rec = set()
    for w0 in all_nearest_models(delta, omega, nv):
        rec |= _reachable_pis(w0, delta, mgr, nv)
    return rec

def method_enum(delta, omega, nv, mgr):
    pis = all_prime_implicants(delta, nv, mgr)
    if not pis:
        return set()
    mind = min(disagreement(p, omega) for p in pis)
    return set(tuple(sorted(p.items())) for p in pis if disagreement(p, omega) == mind)

#_______________________________________________________________________________________________

def main():
    suite = load_suite("standard")
    pic = {}
    rows = []

    def process(mgr, sdd, pis, nv, om, group, ident, density):
        """timing all three methods on one tie case"""
        mind = min(disagreement(p, om) for p in pis) # the disagreement value of the minimal reasons
        mset = set(tuple(sorted(p.items())) for p in pis if disagreement(p, om) == mind) # the set of minimal reasons (as tuples)
        if len(mset) < 2:
            return None  # tie cases only
        out_b = method_bounded(sdd, om, nv, mgr)
        out_e = method_extension(sdd, om, nv, mgr)
        out_n = method_enum(sdd, om, nv, mgr)
        t_b = avg_time(lambda: method_bounded(sdd, om, nv, mgr))
        t_e = avg_time(lambda: method_extension(sdd, om, nv, mgr))
        t_n = avg_time(lambda: method_enum(sdd, om, nv, mgr))
        return {
            "id": ident, "group": group, "nvars": nv, "density": density,
            "num_minimal": len(mset),
            "bounded_us": round(t_b * 1e6, 2),
            "extension_us": round(t_e * 1e6, 2),
            "enum_us": round(t_n * 1e6, 2),
            "bounded_recovery": round(len(out_b & mset) / len(mset), 4),
            "extension_recovery": round(len(out_e & mset) / len(mset), 4),
            "enum_recovery": round(len(out_n & mset) / len(mset), 4),
        }

    # suite
    for entry in suite["classifiers"]:
        nv = entry["nvars"]; cid = entry["id"]
        mgr, sdd = build_classifier(entry, vtree_type="right")
        if cid not in pic:
            pic[cid] = [dict(p) for p in all_prime_implicants(sdd, nv, mgr)]
        pis = pic[cid]
        for bits in product([False, True], repeat=nv):
            om = {i + 1: bits[i] for i in range(nv)}
            if not (term_to_sdd(om, mgr) & sdd).is_false():
                continue
            r = process(mgr, sdd, pis, nv, om, "random", cid, entry["density"])
            if r:
                rows.append(r)

    # handcrafted worst-cases (labelled group), capped where brute-force PI is feasible 
    from rgr.dataset import load_examples, build_example
    for ex in load_examples():
        fam = ex["family"]
        if not fam.startswith("worst_case"):
            continue
        if ex["nvars"] > 10:  
            continue
        group = "worst_case_naive" if fam == "worst_case_naive" else "worst_case_pipeline"
        mgr, sdd, exb = build_example(ex)
        nv = exb["nvars"]
        pis = [dict(p) for p in all_prime_implicants(sdd, nv, mgr)]
        # time every rejected TIE instance of this example
        for bits in product([False, True], repeat=nv):
            om = {i + 1: bits[i] for i in range(nv)}
            if not (term_to_sdd(om, mgr) & sdd).is_false():
                continue
            r = process(mgr, sdd, pis, nv, om, group, exb["id"], -1)
            if r:
                rows.append(r)


    # CSV
    csv_path = os.path.join(OUT, "three_way_results.csv")
    with open(csv_path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)

    def mean(k, sub=rows):
        return statistics.mean(r[k] for r in sub)

    L = ["Three-way comparison: recover tied minimal reasons", "=" * 55, ""]
    L.append(f"tie cases timed: {len(rows)}")
    L.append("")
    L.append("MEAN TIME (microseconds) and MEAN RECOVERY:")
    L.append(f"  bounded menu    : time={mean('bounded_us'):9.1f} us   recovery={mean('bounded_recovery'):.3f}")
    L.append(f"  extension       : time={mean('extension_us'):9.1f} us   recovery={mean('extension_recovery'):.3f}")
    L.append(f"  PI enumeration  : time={mean('enum_us'):9.1f} us   recovery={mean('enum_recovery'):.3f}")
    L.append("")
    L.append(f"  extension speedup over enumeration : {mean('enum_us')/mean('extension_us'):.1f}x")
    L.append(f"  bounded speedup over extension     : {mean('extension_us')/mean('bounded_us'):.1f}x  (but incomplete)")
    L.append("")
    L.append("by group (time us: bounded / extension / enum ; recovery bnd / ext):")
    for g in ["random", "worst_case_naive", "worst_case_pipeline"]:
        s = [r for r in rows if r["group"] == g]
        if not s:
            continue
        L.append(f"  {g:20s}:  {mean('bounded_us',s):8.1f} / {mean('extension_us',s):8.1f} / {mean('enum_us',s):9.1f}   "
                 f"rec {mean('bounded_recovery',s):.3f} / {mean('extension_recovery',s):.3f}   ({len(s)} cases)")
    L.append("")
    L.append("worst-case examples individually (id: bounded/extension/enum us, #minimal):")
    wc = [r for r in rows if r["group"] != "random"]
    seen_ids = {}
    for r in wc:
        seen_ids.setdefault(r["id"], []).append(r)
    for ident, rs in sorted(seen_ids.items()):
        L.append(f"  {ident:10s}:  {mean('bounded_us',rs):8.1f} / {mean('extension_us',rs):8.1f} / {mean('enum_us',rs):9.1f}   "
                 f"#minimal~{mean('num_minimal',rs):.1f}  ({len(rs)} tie instances)")
    L.append("")
    L.append("by nvars (random suite only):")
    for n in sorted(set(r["nvars"] for r in rows if r["group"] == "random")):
        s = [r for r in rows if r["nvars"] == n and r["group"] == "random"]
        L.append(f"  n={n}:  {mean('bounded_us',s):8.1f} / {mean('extension_us',s):8.1f} / {mean('enum_us',s):9.1f}   "
                 f"rec {mean('bounded_recovery',s):.3f} / {mean('extension_recovery',s):.3f}")
    L.append("")
    L.append("by density (random suite only):")
    for d in sorted(set(r["density"] for r in rows if r["group"] == "random")):
        s = [r for r in rows if r["density"] == d and r["group"] == "random"]
        L.append(f"  density={d:<5}:  {mean('bounded_us',s):8.1f} / {mean('extension_us',s):8.1f} / {mean('enum_us',s):9.1f}   "
                 f"rec {mean('bounded_recovery',s):.3f} / {mean('extension_recovery',s):.3f}")

    text = "\n".join(L)
    with open(os.path.join(OUT, "three_way_summary.txt"), "w") as fh:
        fh.write(text + "\n")
    print(text)
    print(f"\nwrote {csv_path}")

if __name__ == "__main__":
    main()
