"""
Charts for the three-way comparison (bounded / extension / enum).
Reads three_way_results.csv and writes a multi-panel figure.

Panels:
  (1) Time vs problem size (random suite): three lines, log-y. 
  (2) Speed vs completeness scatter: each method as a point cloud in (time, recovery) space
  (3) Time by group (bars): random vs parity vs HWB/Q_V, three methods each 
  (4) Extension speedup over enumeration vs number of tied reasons

Run:  python experiments/menu_extension/three_way_charts.py

"""
import csv, os, statistics

HERE = os.path.dirname(__file__)
OUT = os.path.join(HERE, "outputs")
CSV = os.path.join(OUT, "three_way_results.csv")

METHODS = ["bounded", "extension", "enum"]
MCOLORS = {"bounded": "#888780", "extension": "#534AB7", "enum": "#D85A30"}
MLABEL = {"bounded": "single-path", "extension": "extension", "enum": "PI enumeration"}

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

    fig1, a = plt.subplots(figsize=(7, 5))

    # (1) time vs nvars, random suite, three lines
    ns = sorted(set(r["nvars"] for r in rand))
    for m in METHODS:
        ys = [statistics.mean([r[f"{m}_us"] for r in rand if r["nvars"] == n]) for n in ns]
        a.plot(ns, ys, marker="o", color=MCOLORS[m], label=MLABEL[m])
    a.set_yscale("log"); a.set_xlabel("number of variables"); a.set_ylabel("time (us, log)")
    a.set_xticks(ns)
    a.set_title("Time vs problem size (random suite)")
    a.legend(frameon=False, fontsize=9)

    fig2, a = plt.subplots(figsize=(13, 10))

    # (2) speed vs completeness: time (x) vs recovery (y), bounded & extension
    a.scatter([r["bounded_us"] for r in rand], [r["bounded_recovery"] for r in rand],
              s=10, c=MCOLORS["bounded"], alpha=0.3, label="bounded", edgecolors="none")
    a.scatter([r["extension_us"] for r in rand], [r["extension_recovery"] for r in rand],
              s=10, c=MCOLORS["extension"], alpha=0.3, label="extension", edgecolors="none")
    a.set_xscale("log"); a.set_xlabel("time (us, log)"); a.set_ylabel("recovery fraction")
    a.set_title("Speed vs completeness\n(extension: complete; bounded: cheaper but partial)")
    a.legend(frameon=False, fontsize=9)

    fig3, a = plt.subplots(figsize=(13, 10))

    # (3) time by group, grouped bars
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
    a.set_title("Time by group")
    a.legend(frameon=False, fontsize=9)

    fig4, a = plt.subplots(figsize=(13, 10))

        # (4) extension speedup over enum vs number of tied reasons, one line per group
    GCOLORS = {"random": "#888780", "worst_case_naive": "#D85A30", "worst_case_pipeline": "#534AB7"}
    GLABEL = {"random": "random", "worst_case_naive": "parity", "worst_case_pipeline": "HWB / Q_V"}
    for g in ["random", "worst_case_naive", "worst_case_pipeline"]:
        sub_g = [r for r in rows if r["group"] == g]
        if not sub_g:
            continue
        nms = sorted(set(r["num_minimal"] for r in sub_g))
        xs, ys = [], []
        for k in nms:
            cell = [r for r in sub_g if r["num_minimal"] == k]
            x2 = statistics.mean(r["extension_us"] for r in cell)
            if x2:
                xs.append(k)
                ys.append(statistics.mean(r["enum_us"] for r in cell) / x2)
        a.plot(xs, ys, marker="o", markersize=4, color=GCOLORS[g], label=GLABEL[g])
    a.axhline(1.0, ls="--", color="#B4B2A9", lw=1)
    a.set_xlabel("number of tied minimal reasons"); a.set_ylabel("extension speedup over enum")
    a.set_title("(4) Extension advantage shrinks as ties grow\n(dashed = no speedup; below it enum would win)")
    a.legend(frameon=False, fontsize=9)


        # (5) time vs nvars for all function groups, three methods each
    fig5, a = plt.subplots(figsize=(7, 5))

    GROUP_STYLES = {
        "random": "-",
        "worst_case_naive": "--",
        "worst_case_pipeline": ":",
    }

    GROUP_COLORS = {
        "bounded": {
            "random": "#888780",
            "worst_case_naive": "#6F6E68",
            "worst_case_pipeline": "#AAA9A3",
        },
        "extension": {
            "random": "#534AB7",
            "worst_case_naive": "#3F3799",
            "worst_case_pipeline": "#746DCC",
        },
        "enum": {
            "random": "#D85A30",
            "worst_case_naive": "#B84420",
            "worst_case_pipeline": "#E77C58",
        },
    }
    GROUP_LABELS = {
        "random": "random",
        "worst_case_naive": "parity",
        "worst_case_pipeline": "HWB / Q_V",
    }

    for g in ["random", "worst_case_naive", "worst_case_pipeline"]:
        sub_g = [r for r in rows if r["group"] == g and 4 <= r["nvars"] <= 8]
        ns = sorted(set(r["nvars"] for r in sub_g))

        for m in METHODS:
            ys = [
                statistics.mean(
                    [r[f"{m}_us"] for r in sub_g if r["nvars"] == n]
                )
                for n in ns
            ]
            a.plot(
                ns,
                ys,
                marker="o",
                color=GROUP_COLORS[m][g],
                linestyle=GROUP_STYLES[g],
                label=f"{GROUP_LABELS[g]} - {MLABEL[m]}",
            )

    a.set_yscale("log")
    a.set_xlabel("number of variables")
    a.set_ylabel("time (us, log)")
    a.set_xticks(range(4, 9))
    a.set_title("(Time vs problem size across function types")
    a.legend(frameon=False, fontsize=8)

    figs = [fig1, fig2, fig3, fig4, fig5]
    for i, fig in enumerate(figs, start=1):
        fig.suptitle("Three-way comparison", fontsize=14)
        fig.tight_layout()
        png = os.path.join(OUT, f"three_way_chart_{i}.png")
        fig.savefig(png, dpi=120)
        print(f"wrote {png}")

if __name__ == "__main__":
    main()