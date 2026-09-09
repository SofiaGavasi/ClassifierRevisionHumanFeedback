"""
Shared experiment harness. HAndles:
loading the frozen suite, iterating classifiers (and optionally rejected instances), collecting rows, aggregating, and writing CSV + summary. 
Each experiment supplies only a `measure` function that returns the metrics for one case.

Two granularities:
  per="classifier" : measure(mgr, sdd, entry) called once per classifier.
  per="instance"   : measure(mgr, sdd, entry, omega) called per REJECTED instance.

Timing convention: use harness.avg_time() with perf_counter; never raw time.time(), which rounds sub-ms durations to 0 on Windows.

Usage:
    from experiments.harness import run_experiment
    def measure(mgr, sdd, entry): return {"sdd_size": sdd.size()}
    run_experiment("standard", measure, per="classifier", out="my_exp",  group_keys=["nvars","density"])
"""
import os, csv, time, statistics
from itertools import product

from rgr.suite import load_suite, build_classifier
from rgr.sdd_utils import term_to_sdd

clock = time.perf_counter

def avg_time(fn, reps):
    """Average seconds over `reps` runs, using a high-resolution timer."""
    t0 = clock()
    for _ in range(reps):
        fn()
    return (clock() - t0) / reps

def _rejected_instances(sdd, mgr, nvars):
    """Yields all rejected instances for the given SDD."""
    for bits in product([False, True], repeat=nvars): # iterate all 2^nvars assignments
        omega = {i + 1: bits[i] for i in range(nvars)} # build a dict of var->bool
        if (term_to_sdd(omega, mgr) & sdd).is_false(): # rejected
            yield omega

def run_experiment(suite_name, measure, per="classifier", out="experiment", vtrees=("right",), group_keys=("nvars", "density"), out_dir=None, quiet=False):
    """
    suite_name : which suite to load.
    measure    : callback returning a dict of metrics for one case.
                 signature depends on `per`:
                   per="classifier": measure(mgr, sdd, entry) -> dict
                   per="instance"  : measure(mgr, sdd, entry, omega) -> dict
                 When multiple vtrees are given, measure also receives vtree via the entry-independent path: it is called once per (case, vtree), and the vtree name is added to the row automatically.
    per        : "classifier" or "instance".
    vtrees     : vtree types to build each classifier under.
    group_keys : entry fields to break the summary down by.
    out        : output basename
    """
    suite = load_suite(suite_name)
    rows = []
    for entry in suite["classifiers"]: # iterate classifiers
        nvars = entry["nvars"]
        for vt in vtrees:
            mgr, sdd = build_classifier(entry, vtree_type=vt)
            base = {"id": entry["id"], "vtree": vt, **{k: entry[k] for k in group_keys if k in entry}} # base row for this classifier (and vtree)
            if per == "classifier":
                m = measure(mgr, sdd, entry) # measure once per classifier
                rows.append({**base, **m})
            elif per == "instance":
                for omega in _rejected_instances(sdd, mgr, nvars): # measure once per rejected instance
                    m = measure(mgr, sdd, entry, omega)
                    rows.append({**base, **m})
            else:
                raise ValueError("per must be 'classifier' or 'instance'")

    out_dir = out_dir or os.path.join(os.path.dirname(__file__), out, "outputs")
    os.makedirs(out_dir, exist_ok=True)

    # CSV
    csv_path = os.path.join(out_dir, f"{out}_results.csv")
    fieldnames = list(rows[0].keys())
    with open(csv_path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fieldnames)
        w.writeheader(); w.writerows(rows)

    # summary: mean of every numeric metric, overall and per group key
    metric_keys = [k for k in fieldnames if k not in ("id", "vtree", *group_keys) and all(isinstance(r.get(k), (int, float)) for r in rows)] # numeric metrics only
    lines = [f"{out} summary", "=" * 50, "", f"total rows: {len(rows)}  (per={per}, vtrees={list(vtrees)})", ""] # header

    def block(subset, label): # writes a block of summary lines for a subset of rows
        if not subset:
            lines.append(f"  {label}: (no cases)"); return
        parts = [f"{k}={statistics.mean(r[k] for r in subset):.3f}" for k in metric_keys]
        lines.append(f"  {label:26s} " + "  ".join(parts))

    lines.append("overall:")
    block(rows, "all")
    for gk in group_keys: # writes a block of summary lines for each value of the group key (like nvars or density)
        lines.append(f"\nby {gk}:")
        for val in sorted(set(r[gk] for r in rows if gk in r)):
            block([r for r in rows if r.get(gk) == val], f"{gk}={val}")
    if len(vtrees) > 1:
        lines.append("\nby vtree:")
        for vt in vtrees:
            block([r for r in rows if r["vtree"] == vt], f"vtree={vt}")

    text = "\n".join(lines)
    txt_path = os.path.join(out_dir, f"{out}_summary.txt")
    with open(txt_path, "w") as fh:
        fh.write(text + "\n")
    if not quiet:
        print(text)
        print(f"\nwrote {csv_path}\nwrote {txt_path}")
    return rows
