"""
Menu-extension experiment: three tiers of tie-reason recovery, plus the cost of the extension measured at two levels.

Tiers (recovery of minimal reasons on TIE cases):
  Tier 1  single-path menu       : original bounded menu (one nearest model + gap-0 on the winning path only).
  Tier 2  all nearest + complete : enumerate ALL nearest models (the gap-0 walk), and from each recover EVERY reachable prime implicant (complete shrinking, not sampled orders).
  ground truth                    : all prime implicants at minimum disagreement.


Two cost measures for Tier 2:
  - nearest_count            : number of nearest models (cheap, via rgr.count).
  - reachable_pi_per_model   : number of prime implicants reachable from a nearest model by complete shrinking.

Run:  python experiments/menu_extension/run_menu_extension.py

"""
import sys, os, csv, statistics
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from itertools import product, combinations
from rgr.suite import load_suite, build_classifier
from rgr.reasons import all_prime_implicants, disagreement
from rgr.reconstruct import nearest_model
from rgr.shrink import greedy_shrink
from rgr.alternatives import alternatives
from rgr.count import nearest_count
from rgr.nearest_all import all_nearest_models
from rgr.sdd_utils import term_to_sdd, is_implicant

OUT = os.path.join(os.path.dirname(__file__), "outputs")
os.makedirs(OUT, exist_ok=True)

def _minimal(pis, omega): # returns the subset of prime implicants that are minimal w.r.t. disagreement with omega, and the minimum disagreement value
    if not pis:
        return set()
    mind = min(disagreement(p, omega) for p in pis)
    return set(tuple(sorted(p.items())) for p in pis if disagreement(p, omega) == mind)

def tier1(delta, omega, nv, mgr):
    """single-path menu: one nearest model + gap-0 alternatives on the winning path."""
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

def reachable_pis_from_model(model, node, mgr, nv):
    """ALL prime implicants that are subsets of `model` (complete shrinking).
    Returns a set of reason-keys.
    """
    out = set()
    items = [(v, model[v]) for v in range(1, nv + 1)] # list of (var, value) pairs in the model

    for size in range(0, nv + 1): # for each size of subset of the model
        for combo in combinations(items, size): # for each combination of that size
            term = dict(combo)
            if not is_implicant(term, node, mgr): # if term is not an implicant, skip it
                continue
            if any(is_implicant({k: v for k, v in term.items() if k != x}, node, mgr) # if any smaller subset of term is an implicant, skip it
                   for x in term):
                continue
            out.add(tuple(sorted(term.items()))) # add the prime implicant
    return out

def tier2_and_cost(delta, omega, nv, mgr):
    """Complete Tier 2: union of reachable PIs over all nearest models.
    Returns (recovered_reason_set, max_reachable_pi_per_model, total_reachable)
    """
    all_rec = set()
    per_model_counts = []

    for w0 in all_nearest_models(delta, omega, nv): # for each nearest model, compute the reachable prime implicants
        rp = reachable_pis_from_model(w0, delta, mgr, nv) # complete shrinking from this nearest model
        per_model_counts.append(len(rp)) # add the count of reachable PIs from this model
        all_rec |= rp # union with the overall recovered set

    max_per = max(per_model_counts) if per_model_counts else 0 # maximum number of reachable PIs from any single nearest model
    return all_rec, max_per, len(all_rec)

def main():
    suite = load_suite("standard")
    pi_cache = {}
    rows = []

    for entry in suite["classifiers"]:
        nv = entry["nvars"]; cid = entry["id"]
        mgr, sdd = build_classifier(entry, vtree_type="right")
        if cid not in pi_cache:
            pi_cache[cid] = [dict(p) for p in all_prime_implicants(sdd, nv, mgr)]
        pis = pi_cache[cid]

        for bits in product([False, True], repeat=nv): # for each possible rejected instance (omega)
            om = {i + 1: bits[i] for i in range(nv)}
            if not (term_to_sdd(om, mgr) & sdd).is_false(): # if omega is accepted, skip it
                continue
            mset = _minimal(pis, om)
            if len(mset) < 2:
                continue  # tie cases only

            _, ncount = nearest_count(sdd, om)
            r1 = len(tier1(sdd, om, nv, mgr) & mset) / len(mset) # fraction of minimal reasons recovered by the single-path menu
            rec2, max_per_model, total_reach = tier2_and_cost(sdd, om, nv, mgr)
            r2 = len(rec2 & mset) / len(mset) # fraction of minimal reasons recovered by the complete Tier 2 
            
            rows.append({
                "nvars": nv, "density": entry["density"],
                "num_minimal": len(mset),
                "nearest_count": ncount,
                "max_reachable_pi_per_model": max_per_model,
                "total_reachable_pi": total_reach,
                "tier1_recovery": round(r1, 4),
                "tier2_recovery": round(r2, 4),
                "tier2_complete": int(r2 >= 1.0),
            })

    # CSV
    csv_path = os.path.join(OUT, "menu_extension_results.csv")
    with open(csv_path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)

    def mean(key, subset=rows):
        return statistics.mean(r[key] for r in subset)

    L = ["Menu-extension experiment summary", "=" * 55, ""]
    L.append(f"tie cases: {len(rows)}")
    L.append("")
    L.append("RECOVERY (mean fraction of minimal reasons on ties):")
    L.append(f"  Tier 1 (single-path menu)          : {mean('tier1_recovery'):.3f}")
    L.append(f"  Tier 2 (all nearest + complete)    : {mean('tier2_recovery'):.3f}")
    L.append(f"  gain from extension                : +{mean('tier2_recovery')-mean('tier1_recovery'):.3f}")
    L.append("")
    comp = mean('tier2_complete') * 100
    L.append(f"TIER 2 COMPLETENESS: {comp:.1f}% of tie cases fully recovered")
    resid = [r for r in rows if not r['tier2_complete']]
    if resid:
        L.append(f"  residual: {len(resid)} cases ({100*len(resid)/len(rows):.2f}%)")
    else:
        L.append("  NO residual: every minimal reason is reachable from a nearest model")
        L.append("  (each minimal reason sits at the minimum distance, so it has a nearest")
        L.append("   model that shrinks to it - completeness is structural).")
    L.append("")
    L.append("COST 1 - number of nearest models to enumerate (rgr.count):")
    L.append(f"  mean={mean('nearest_count'):.2f}  median={statistics.median(r['nearest_count'] for r in rows)}  "
             f"max={max(r['nearest_count'] for r in rows)}")
    L.append("")
    L.append("COST 2 - prime implicants reachable per nearest model (the real driver of")
    L.append("          Tier 2's completeness; complete shrinking must enumerate these):")
    L.append(f"  max per model : mean={mean('max_reachable_pi_per_model'):.2f}  "
             f"median={statistics.median(r['max_reachable_pi_per_model'] for r in rows)}  "
             f"max={max(r['max_reachable_pi_per_model'] for r in rows)}")
    L.append(f"  total reachable across nearest models: mean={mean('total_reachable_pi'):.2f}  "
             f"max={max(r['total_reachable_pi'] for r in rows)}")
    L.append("")
    L.append("by density (T1 -> T2 recovery, mean nearest-count, mean max-reachable-PI):")
    for d in sorted(set(r["density"] for r in rows)):
        sub = [r for r in rows if r["density"] == d]
        L.append(f"  density={d:<5}  T1={mean('tier1_recovery',sub):.3f}  T2={mean('tier2_recovery',sub):.3f}  "
                 f"nearest={mean('nearest_count',sub):.1f}  reach_pi={mean('max_reachable_pi_per_model',sub):.1f}")

    text = "\n".join(L)
    with open(os.path.join(OUT, "menu_extension_summary.txt"), "w") as fh:
        fh.write(text + "\n")
    print(text)
    print(f"\nwrote {csv_path}")
    print(f"wrote {os.path.join(OUT, 'menu_extension_summary.txt')}")

if __name__ == "__main__":
    main()
