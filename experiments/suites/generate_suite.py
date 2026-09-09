"""
Generates a standard benchmark suite of random classifiers, saved as JSON.

Methodology:
  - Random 3-CNF across a density grid (clause/variable ratio) straddling the 3-SAT phase transition (~4.26). Only satisfiable, non-trivial classifiers are kept.
  - Fixed variable order (natural 1..n). Fixed seeds for full reproducibility.

Each suite entry stores the CNF as an explicit clause list, so any loader rebuilds the exact same function under any vtree.

Run:  python experiments/suites/generate_suite.py
Output: data/suites/<name>.json
"""
import os, json, random

OUT = os.path.join(os.path.dirname(__file__), "..", "..", "data", "suites")
os.makedirs(OUT, exist_ok=True)

# suite definition 
SUITE_NAME  = "standard"
NVARS_RANGE = [3, 4, 5, 6, 7, 8, 9, 10]
DENSITIES   = [2.0, 3.0, 3.8, 4.0, 4.2, 4.26, 4.4, 4.6, 5.0, 6.0] 
PER_CELL    = 25
SEED        = 100


def random_3cnf_clauses(nvars, nclauses, rng):
    """Return a list of clauses. each clause is a list of signed var indices (e.g. [1,-3,4])."""
    clauses = []
    for _ in range(nclauses):
        vs = rng.sample(range(1, nvars + 1), min(3, nvars)) # we keep 3 out of nvars
        clause = [v if rng.random() < 0.5 else -v for v in vs]
        clauses.append(clause)
    return clauses

def clauses_to_sdd(clauses, mgr): # builds an SDD from a list of clauses
    f = mgr.true()
    for clause in clauses:
        c = mgr.false()
        for lit in clause:
            c = c | mgr.literal(lit)
        f = f & c
    return f

def main():
    from rgr.sdd_utils import build
    rng = random.Random(SEED)
    entries = []
    idx = 0
    for nvars in NVARS_RANGE:
        for density in DENSITIES:
            nclauses = max(1, round(density * nvars)) # the number of clauses is given by the density * nvars
            kept, attempts = 0, 0
            while kept < PER_CELL and attempts < PER_CELL * 30: # keeps trying until it finds enough classifiers to keep, or gives up after 30x attempts
                attempts += 1
                clauses = random_3cnf_clauses(nvars, nclauses, rng)
                # check satisfiable & non-trivial on a throwaway build
                mgr, _ = build(nvars, vtree_type="right")
                sdd = clauses_to_sdd(clauses, mgr)
                if sdd.is_false() or sdd.is_true(): 
                    continue
                mc = sdd.global_model_count()
                if mc == 0 or mc == 2 ** nvars: # checks for triviality (all true or all false)
                    continue
                kept += 1
                entries.append({
                    "id": f"c{idx}", "nvars": nvars, "density": density,
                    "nclauses": nclauses, "clauses": clauses,
                })
                idx += 1

    suite = {"name": SUITE_NAME, "seed": SEED,
             "nvars_range": NVARS_RANGE, "densities": DENSITIES,
             "per_cell": PER_CELL, "classifiers": entries}
    path = os.path.join(OUT, f"{SUITE_NAME}.json")
    with open(path, "w") as fh:
        json.dump(suite, fh, indent=1)
    print(f"wrote {len(entries)} classifiers to {path}")
    
    from collections import Counter
    by = Counter((e["nvars"], e["density"]) for e in entries)
    for k in sorted(by):
        print(f"  n={k[0]}, density={k[1]}: {by[k]} classifiers")

if __name__ == "__main__":
    main()
