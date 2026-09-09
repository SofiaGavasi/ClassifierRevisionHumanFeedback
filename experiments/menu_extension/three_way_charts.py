"""
Charts for the three-way comparison (bounded / extension / enum).
Reads three_way_results.csv and writes a multi-panel figure.

Panels:
  (1) Time vs problem size (random suite): three lines, log-y. 
  (2) Speed vs completeness scatter: each method as a point cloud in (time, recovery) space
  (3) Time by group (bars): random vs parity vs HWB/Q_V, three methods each 
  (4) Extension speedup over enumeration vs number of tied reasons

Run:  python experiments/menu_extension/chart_three_way.py

"""
import csv, os, statistics

HERE = os.path.dirname(__file__)
OUT = os.path.join(HERE, "outputs")
CSV = os.path.join(OUT, "three_way_results.csv")

METHODS = ["bounded", "extension", "enum"]
MCOLORS = {"bounded": "#888780", "extension": "#534AB7", "enum": "#D85A30"}
MLABEL = {"bounded": "bounded menu", "extension": "extension", "enum": "PI enumeration"}

def load():
    rows = []
    with open(CSV) as fh:
        for r in csv.DictReader(fh):
            rows.append({
                "group": r["group"], "nvars": int(r["nvars"]),
                "num_minimal": int(r["num_minimal"]),
                "bounded_us": float(r["bounded_us"]),
                "extension_us": float(r["extension_us"]),
                "enum_us": float(r["enum_us"]),
                "bounded_recovery": float(r["bounded_recovery"]),
                "extension_recovery": float(r["extension_recovery"]),
            })
    return rows

def main():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    rows = load()
    rand = [r for r in rows if r["group"] == "random"]

    fig, ax = plt.subplots(2, 2, figsize=(13, 10))

    # (1) time vs nvars, random suite, three lines
    a = ax[0][0]
    ns = sorted(set(r["nvars"] for r in rand))
    for m in METHODS:
        ys = [statistics.mean([r[f"{m}_us"] for r in rand if r["nvars"] == n]) for n in ns]
        a.plot(ns, ys, marker="o", color=MCOLORS[m], label=MLABEL[m])
    a.set_yscale("log"); a.set_xlabel("number of variables"); a.set_ylabel("time (us, log)")
    a.set_xticks(ns)
    a.set_title("(1) Time vs problem size (random suite)")
    a.legend(frameon=False, fontsize=9)

    # (2) speed vs completeness: time (x) vs recovery (y), bounded & extension
    a = ax[0][1]
    a.scatter([r["bounded_us"] for r in rand], [r["bounded_recovery"] for r in rand],
              s=10, c=MCOLORS["bounded"], alpha=0.3, label="bounded", edgecolors="none")
    a.scatter([r["extension_us"] for r in rand], [r["extension_recovery"] for r in rand],
              s=10, c=MCOLORS["extension"], alpha=0.3, label="extension", edgecolors="none")
    a.set_xscale("log"); a.set_xlabel("time (us, log)"); a.set_ylabel("recovery fraction")
    a.set_title("(2) Speed vs completeness\n(extension: complete; bounded: cheaper but partial)")
    a.legend(frameon=False, fontsize=9)

    # (3) time by group, grouped bars
    a = ax[1][0]
    groups = [g for g in ["random", "worst_case_naive", "worst_case_pipeline"]
              if any(r["group"] == g for r in rows)]
    glabels = {"random": "random", "worst_case_naive": "parity", "worst_case_pipeline": "HWB / Q_V"}
    import numpy as np
    x = np.arange(len(groups)); w = 0.25
    for i, m in enumerate(METHODS):
        vals = [statistics.mean([r[f"{m}_us"] for r in rows if r["group"] == g]) for g in groups]
        a.bar(x + (i - 1) * w, vals, w, color=MCOLORS[m], label=MLABEL[m])
    a.set_yscale("log"); a.set_xticks(x); a.set_xticklabels([glabels[g] for g in groups])
    a.set_ylabel("mean time (us, log)")
    a.set_title("(3) Time by group\n(extension wins big on HWB/Q_V, narrows on parity)")
    a.legend(frameon=False, fontsize=9)

    # (4) extension speedup over enum vs number of tied reasons
    a = ax[1][1]
    nms = sorted(set(r["num_minimal"] for r in rows))
    sp = []
    for k in nms:
        sub = [r for r in rows if r["num_minimal"] == k]
        e = statistics.mean(r["enum_us"] for r in sub)
        x2 = statistics.mean(r["extension_us"] for r in sub)
        sp.append(e / x2 if x2 else None)
    a.plot(nms, sp, marker="o", color="#3C8D6E")
    a.axhline(1.0, ls="--", color="#B4B2A9", lw=1)
    a.set_xlabel("number of tied minimal reasons"); a.set_ylabel("extension speedup over enum")
    a.set_title("(4) Extension advantage shrinks as ties grow\n(dashed = parity; below it enum would win)")

    fig.suptitle("Three-way comparison: bounded menu vs extension vs PI enumeration", fontsize=14)
    fig.tight_layout()
    png = os.path.join(OUT, "three_way_charts.png")
    fig.savefig(png, dpi=120)
    print(f"wrote {png}")

if __name__ == "__main__":
    main()