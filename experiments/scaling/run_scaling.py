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

PIPE_REPS = 500      # average the pipeline over repeats (single runs hit the timer floor)
ENUM_REPS = 20       # also repeat enumeration; fast cases otherwise round to 0 on Windows
ENUM_CAP_VARS = 14   # skip enumeration above this many variables
clock = time.perf_counter   # high-resolution timer (works well on Windows)

def _avg_time(fn, reps):
    """Run fn reps times, return mean seconds. Uses perf_counter for resolution."""
    t0 = clock()
    for _ in range(reps):
        fn()
    return (clock() - t0) / reps

def time_pipeline(sdd, omega, mgr, nv):
    return _avg_time(lambda: edit(sdd, omega, mgr, nv), PIPE_REPS)

def time_enumeration(sdd, nv, mgr):
    if nv > ENUM_CAP_VARS:
        return None, None
    npi = len(all_prime_implicants(sdd, nv, mgr))   # one call for the count
    # fewer repeats for expensive enumerations, more for cheap ones
    reps = ENUM_REPS if nv <= 8 else 3
    t = _avg_time(lambda: all_prime_implicants(sdd, nv, mgr), reps)
    return t, npi

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
            "enum_us": f"{t_enum*1e6:.1f}" if t_enum is not None else "skipped",
            "pipeline_us": f"{t_pipe*1e6:.1f}",
            "speedup": (f"{t_enum/t_pipe:.0f}x" if (t_enum and t_pipe) else ""),
        })

    # CSV
    csv_path = os.path.join(OUT, "scaling_results.csv")
    with open(csv_path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)

    # human-readable table (times in microseconds so small values stay visible)
    txt_path = os.path.join(OUT, "scaling_table.txt")
    header = f"{'id':14s} {'family':22s} {'nv':>3} {'|SDD|':>6} {'#reasons':>9} {'enum(us)':>11} {'pipe(us)':>11} {'speedup':>8}"
    lines = [header, "-" * len(header)]
    for r in rows:
        lines.append(f"{r['id']:14s} {r['family']:22s} {r['nvars']:>3} {r['sdd_size']:>6} "
                     f"{str(r['num_reasons']):>9} {r['enum_us']:>11} {r['pipeline_us']:>11} {r['speedup']:>8}")
    table = "\n".join(lines)
    with open(txt_path, "w") as fh:
        fh.write(table + "\n")
    print(table)
    print(f"\nwrote {csv_path}\nwrote {txt_path}")

if __name__ == "__main__":
    main()