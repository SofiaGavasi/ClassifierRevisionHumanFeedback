"""
Regenerate the scaling summary table from the existing results CSV.
No re-run of the timing experiment; just reads scaling_results.csv and rewrites scaling_table.txt.

Run:  python experiments/scaling/rerun_summary.py
"""
import csv, os, statistics

OUT = os.path.join(os.path.dirname(__file__), "outputs")
CSV = os.path.join(OUT, "scaling_results.csv")   

def load():
    rows = []
    with open(CSV) as fh:
        for r in csv.DictReader(fh):
            rows.append({
                "id": r["id"],
                "group": r["group"],
                "nvars": int(r["nvars"]),
                "sdd_size": int(r["sdd_size"]),
                "num_reasons": int(r["num_reasons"]),
                "enum_us": float(r["enum_us"]) if r["enum_us"] not in ("", "None") else None,
                "pipeline_us": float(r["pipeline_us"]),
                "speedup": float(r["speedup"]) if r["speedup"] not in ("", "None") else None,
            })
    return rows

def main():
    rows = load()

    def fmt(v, unit=""):
        return "skipped" if v is None else f"{v:.1f}{unit}"

    lines = ["Scaling: pipeline vs enumeration", "=" * 60, ""]
    header = (f"{'id':12s} {'group':20s} {'nv':>3} {'|SDD|':>6} {'#PIs':>6} "
              f"{'enum(us)':>10} {'pipe(us)':>10} {'speedup':>8}")
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
    with open(os.path.join(OUT, "scaling_table.txt"), "w") as fh:
        fh.write(table + "\n")
    print(table)
    print(f"\nwrote {os.path.join(OUT, 'scaling_table.txt')}")

if __name__ == "__main__":
    main()