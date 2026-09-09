"""
Scaling experiment (harness-based): pipeline vs naive prime-implicant enumeration.

Answers the feasibility objection. Runs on the shared frozen suite and on the handcrafted worst-case examples (parity, HWB, Q_V), shown as a labelled comparison group so the two stories sit side by side:
  - random suite    : general classifiers across densities
  - worst_case_naive (parity): small SDD, exponentially many reasons -> pipeline wins
  - worst_case_pipeline (HWB/Q_V): large SDD -> both inherit |SDD|


Run:  python experiments/scaling/run_scaling.py
"""
import sys, os, csv, statistics
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from harness import avg_time
from rgr.suite import load_suite, build_classifier
from rgr.dataset import load_examples, build_example
from rgr.edit import edit
from rgr.reasons import all_prime_implicants
from rgr.sdd_utils import term_to_sdd
from itertools import product

OUT = os.path.join(os.path.dirname(__file__), "outputs")
os.makedirs(OUT, exist_ok=True)

PIPE_REPS = 300 # number of repetitions for timing the pipeline (to reduce noise)
ENUM_CAP_VARS = 12 # maximum number of variables for which to run the naive enumeration (otherwise skipped, as it is exponential)

def _first_rejected(sdd, mgr, nv): 
    # returns one rejected instance (omega) for the given SDD, or None if none exist. Used to time the pipeline on a single rejected instance.
    for bits in product([False, True], repeat=nv):
        o = {i + 1: bits[i] for i in range(nv)}
        if (term_to_sdd(o, mgr) & sdd).is_false():
            return o
    return None

def _time_pipeline(sdd, omega, mgr, nv): 
    # returns the average time (seconds) to run the pipeline on the given SDD and rejected instance (omega). Repeats PIPE_REPS times to reduce noise.
    return avg_time(lambda: edit(sdd, omega, mgr, nv), PIPE_REPS)

def _time_enum(sdd, nv, mgr): 
    # returns the average time (seconds) to enumerate all prime implicants for the given SDD, and the number of prime implicants.
    if nv > ENUM_CAP_VARS:
        return None, None
    npi = len(all_prime_implicants(sdd, nv, mgr))
    reps = 20 if nv <= 8 else 3
    t = avg_time(lambda: all_prime_implicants(sdd, nv, mgr), reps)
    return t, npi

def _measure_one(mgr, sdd, nv, group, ident):
    # Measures one classifier (mgr, sdd) with nvars=nv, belonging to group=group, and with identifier ident. Returns a dict of metrics.
    omega = _first_rejected(sdd, mgr, nv)
    if omega is None:
        omega = {i + 1: True for i in range(nv)}
    t_pipe = _time_pipeline(sdd, omega, mgr, nv) # time the pipeline on one rejected instance
    t_enum, npi = _time_enum(sdd, nv, mgr) # time the naive enumeration of all prime implicants
    return {"id": ident, "group": group, "nvars": nv, "sdd_size": sdd.size(),
            "num_reasons": npi if npi is not None else -1,
            "enum_us": (t_enum * 1e6) if t_enum is not None else None,
            "pipeline_us": t_pipe * 1e6,
            "speedup": (t_enum / t_pipe) if (t_enum and t_pipe) else None}

def main():
    rows = []

    #  random suite (via the shared frozen benchmark)
    for entry in load_suite("standard")["classifiers"]:
        mgr, sdd = build_classifier(entry, vtree_type="right")
        rows.append(_measure_one(mgr, sdd, entry["nvars"], "random", entry["id"]))

    #  handcrafted worst-case examples, shown alongside
    for ex in load_examples():
        fam = ex["family"]
        if fam == "worst_case_naive":
            group = "worst_case_naive"
        elif fam.startswith("worst_case_pipeline"):
            group = "worst_case_pipeline"
        else:
            continue
        mgr, sdd, exb = build_example(ex)
        rows.append(_measure_one(mgr, sdd, exb["nvars"], group, exb["id"]))

    # CSV 
    csv_path = os.path.join(OUT, "scaling_results.csv")
    with open(csv_path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)

    # text table: worst-cases individually, random summarised by nvars 
    def fmt(v, unit=""):
        return "skipped" if v is None else f"{v:.1f}{unit}"
    lines = ["Scaling: pipeline vs enumeration", "=" * 60, ""]
    header = f"{'id':12s} {'group':20s} {'nv':>3} {'|SDD|':>6} {'#PIs':>6} {'enum(us)':>10} {'pipe(us)':>10} {'speedup':>8}"
    lines += [header, "-" * len(header)]
    # worst-case rows individually
    for r in rows:
        if r["group"] == "random":
            continue
        sp = "" if r["speedup"] is None else f"{r['speedup']:.0f}x"
        npi = "skipped" if r["num_reasons"] < 0 else str(r["num_reasons"])
        lines.append(f"{r['id']:12s} {r['group']:20s} {r['nvars']:>3} {r['sdd_size']:>6} "
                     f"{npi:>6} {fmt(r['enum_us']):>10} {fmt(r['pipeline_us']):>10} {sp:>8}")
        # random suite summarised by nvars (means)
    lines.append("-" * len(header))
    rand = [r for r in rows if r["group"] == "random"]
    for nv in sorted(set(r["nvars"] for r in rand)):
        sub = [r for r in rand if r["nvars"] == nv]
        me = statistics.mean(r["enum_us"] for r in sub if r["enum_us"] is not None)
        mp = statistics.mean(r["pipeline_us"] for r in sub)
        ms = statistics.mean(r["speedup"] for r in sub if r["speedup"] is not None)
        msz = statistics.mean(r["sdd_size"] for r in sub)
        mpi = statistics.mean(r["num_reasons"] for r in sub if r["num_reasons"] >= 0)
        lines.append(f"{'random(mean)':12s} {'random':20s} {nv:>3} {msz:>6.0f} "
                     f"{mpi:>6.0f} {me:>10.1f} {mp:>10.1f} {ms:>7.0f}x")
    table = "\n".join(lines)
    txt_path = os.path.join(OUT, "scaling_table.txt")
    with open(txt_path, "w") as fh:
        fh.write(table + "\n")
    print(table)

    #  chart: enum vs pipeline time, coloured by group 
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(8, 5))
        colors = {"random": "#888780", "worst_case_naive": "#D85A30",
                  "worst_case_pipeline": "#534AB7"}
        labels = {"random": "random suite", "worst_case_naive": "parity (naive worst case)",
                  "worst_case_pipeline": "HWB / Q_V (pipeline worst case)"}
        for group in ["random", "worst_case_naive", "worst_case_pipeline"]:
            sub = [r for r in rows if r["group"] == group and r["enum_us"] is not None]
            if not sub: continue
            ax.scatter([r["enum_us"] for r in sub], [r["pipeline_us"] for r in sub],
                       s=28, c=colors[group], label=labels[group], alpha=0.7,
                       edgecolors="none")
        lo = min(r["pipeline_us"] for r in rows)
        hi = max([r["enum_us"] for r in rows if r["enum_us"] is not None] + [lo])
        ax.plot([lo, hi], [lo, hi], "--", color="#B4B2A9", linewidth=1, label="equal time")
        ax.set_xscale("log"); ax.set_yscale("log")
        ax.set_xlabel("enumeration time (us, log)")
        ax.set_ylabel("pipeline time (us, log)")
        ax.set_title("Pipeline vs enumeration time (points below the line = pipeline faster)")
        ax.legend(frameon=False, fontsize=9)
        fig.tight_layout()
        png = os.path.join(OUT, "scaling_chart.png")
        fig.savefig(png, dpi=130)
        print(f"\nwrote {csv_path}\nwrote {txt_path}\nwrote {png}")
    except Exception as e:
        print(f"\n(chart skipped: {e})\nwrote {csv_path}\nwrote {txt_path}")

if __name__ == "__main__":
    main()
