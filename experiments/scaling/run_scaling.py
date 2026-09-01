"""Scaling experiment: the pipeline vs naive prime-implicant enumeration.

Answers the feasibility objection. Times the full edit pipeline against the naive
"enumerate all reasons, compare each to omega" approach on identical classifiers,
across three regimes:
  - worst_case_naive (parity): small SDD, exponentially many reasons  -> pipeline wins
  - worst_case_pipeline (HWB): no small SDD                           -> both inherit |SDD|
  - random: general satisfiable classifiers of increasing size

Writes a CSV and a summary table to outputs/.
Run:  python experiments/scaling/run_scaling.py
"""
import time, csv, os
from rgr.dataset import load_examples, build_example
from rgr.edit import edit
from rgr.reasons import all_prime_implicants

OUT = os.path.join(os.path.dirname(__file__), "outputs")
os.makedirs(OUT, exist_ok=True)

REPS = 200   
ENUM_CAP_VARS = 12  

def time_pipeline(sdd, omega, mgr, nv):
    t0 = time.time()
    for _ in range(REPS):
        edit(sdd, omega, mgr, nv)
    return (time.time() - t0) / REPS

def time_enumeration(sdd, nv, mgr):
    if nv > ENUM_CAP_VARS:
        return None, None
    t0 = time.time()
    pis = all_prime_implicants(sdd, nv, mgr)
    return time.time() - t0, len(pis)

def main():
    rows = []
    for ex in load_examples():
        if ex["family"] not in ("worst_case_naive", "worst_case_pipeline", "random"):
            continue
        mgr, sdd, ex = build_example(ex)
        nv = ex["nvars"]
        omega = ex["test_instances"][0]
        t_pipe = time_pipeline(sdd, omega, mgr, nv)
        t_enum, npi = time_enumeration(sdd, nv, mgr)
        rows.append({
            "id": ex["id"], "family": ex["family"], "nvars": nv,
            "sdd_size": sdd.size(),
            "num_reasons": npi if npi is not None else "",
            "enum_s": f"{t_enum:.5f}" if t_enum is not None else "skipped",
            "pipeline_s": f"{t_pipe:.6f}",
            "speedup": (f"{t_enum/t_pipe:.0f}x" if (t_enum and t_pipe) else ""),
        })

    # CSV
    csv_path = os.path.join(OUT, "scaling_results.csv")
    with open(csv_path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)

    # human-readable table
    txt_path = os.path.join(OUT, "scaling_table.txt")
    header = f"{'id':14s} {'family':22s} {'nv':>3} {'|SDD|':>6} {'#reasons':>9} {'enum(s)':>10} {'pipe(s)':>11} {'speedup':>8}"
    lines = [header, "-" * len(header)]
    for r in rows:
        lines.append(f"{r['id']:14s} {r['family']:22s} {r['nvars']:>3} {r['sdd_size']:>6} "
                     f"{str(r['num_reasons']):>9} {r['enum_s']:>10} {r['pipeline_s']:>11} {r['speedup']:>8}")
    table = "\n".join(lines)
    with open(txt_path, "w") as fh:
        fh.write(table + "\n")
    print(table)
    print(f"\nwrote {csv_path}\nwrote {txt_path}")

if __name__ == "__main__":
    main()
