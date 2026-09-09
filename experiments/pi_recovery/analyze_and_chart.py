"""
Analyse the harness-produced PI-recovery results and generate a chart.

Input CSV (from the harness): columns
    id, vtree, nvars, density, num_minimal, is_tie, recovery

Summary: for every category (overall, by nvars, by density, by vtree), reports mean / median / min / max of num_minimal, is_tie, recovery, 
plus the missed-reasons metrics on that category's tie cases:
    avg_missed  = mean fraction of tied reasons not recovered (1 - recovery)
    incomplete  = fraction of tie cases missing at least one reason (recovery < 1)

Chart: mean recovery on tie cases vs density and vs problem size, one line per vtree.

Run:  python experiments/pi_recovery/analyze_and_chart.py
"""
import csv, os, statistics

HERE = os.path.dirname(__file__)
OUT = os.path.join(HERE, "outputs")
CSV = os.path.join(OUT, "pi_recovery_results.csv") 

METRICS = ["num_minimal", "is_tie", "recovery"]

# LOADING
def load():
    rows = []
    with open(CSV) as fh:
        for r in csv.DictReader(fh):
            rows.append({
                "vtree": r["vtree"],
                "nvars": int(r["nvars"]),
                "density": float(r["density"]),
                "num_minimal": float(r["num_minimal"]),
                "is_tie": float(r["is_tie"]),
                "recovery": float(r["recovery"]),
            })
    return rows


# SUMMARY TEXT

def dist(vals): # returns a string summarising the distribution of the given numeric values (mean, median, min, max)
    if not vals:
        return "     -"
    return (f"mean={statistics.mean(vals):5.3f} med={statistics.median(vals):5.3f} "
            f"min={min(vals):5.3f} max={max(vals):5.3f}")

def missed(subset): # returns a string summarising the missed-reasons metrics on the tie cases in the given subset of rows
    ties = [r for r in subset if r["is_tie"] == 1]
    if not ties:
        return "avg_missed=  -    incomplete=  -"
    am = statistics.mean(1 - r["recovery"] for r in ties) * 100
    inc = statistics.mean(1 if r["recovery"] < 1.0 else 0 for r in ties) * 100
    return f"avg_missed={am:5.1f}%  incomplete={inc:5.1f}%"

def block(subset, label, lines): # writes a block of summary lines for a subset of rows, appending to the given list of lines
    if not subset:
        lines.append(f"  {label}: (no cases)"); lines.append(""); return
    lines.append(f"  {label}")
    for m in METRICS:
        lines.append(f"      {m:12s}  {dist([r[m] for r in subset])}")
    lines.append(f"      {'missed(ties)':12s}  {missed(subset)}")
    lines.append("")

def summarise(rows):
    # HEADER
    L = ["PI-recovery summary (augmented)", "=" * 60, ""]
    ties = [r for r in rows if r["is_tie"] == 1]
    L.append(f"total rows: {len(rows)}")
    L.append(f"tie cases (>=2 minimal reasons): {len(ties)} "
             f"({100*len(ties)/len(rows):.1f}%)")
    L += ["",
          "Each block reports mean/median/min/max for num_minimal, is_tie and",
          "recovery, plus missed-reasons metrics on that category's tie cases:",
          "  avg_missed  = mean fraction of tied reasons not recovered",
          "  incomplete  = fraction of tie cases missing at least one reason", ""]

    # BLOCKS
    L.append("OVERALL"); L.append("-" * 60)
    block(rows, "all", L)
    L.append("BY NVARS"); L.append("-" * 60)
    for n in sorted(set(r["nvars"] for r in rows)):
        block([r for r in rows if r["nvars"] == n], f"nvars={n}", L)
    L.append("BY DENSITY"); L.append("-" * 60)
    for d in sorted(set(r["density"] for r in rows)):
        block([r for r in rows if r["density"] == d], f"density={d}", L)
    L.append("BY VTREE"); L.append("-" * 60)
    for vt in sorted(set(r["vtree"] for r in rows)):
        block([r for r in rows if r["vtree"] == vt], f"vtree={vt}", L)
    return "\n".join(L)



# CHART

def chart(rows):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    ties = [r for r in rows if r["is_tie"] == 1]
    vtrees = sorted(set(r["vtree"] for r in rows))
    densities = sorted(set(r["density"] for r in ties))
    nvarss = sorted(set(r["nvars"] for r in ties))
    colors = {"right": "#D85A30", "left": "#534AB7", "balanced": "#3C8D6E"}

    def mean_rec(subset): # returns the mean recovery on the given subset of rows
        return statistics.mean([r["recovery"] for r in subset]) if subset else None

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))

    for vt in vtrees: # plot mean recovery on tie cases vs density, one line per vtree
        ys = [mean_rec([r for r in ties if r["vtree"] == vt and r["density"] == d]) for d in densities]
        ax1.plot(densities, ys, marker="o", color=colors.get(vt, "#888"), label=vt)
    ax1.axvline(4.26, ls="--", color="#B4B2A9", lw=1)
    ax1.text(4.26, ax1.get_ylim()[0], " phase\n transition", fontsize=8, color="#888")
    ax1.set_xlabel("clause/variable density"); ax1.set_ylabel("mean recovery (tie cases)")
    ax1.set_title("Recovery vs density"); ax1.legend(frameon=False, fontsize=9)

    for vt in vtrees: # plot mean recovery on tie cases vs problem size, one line per vtree
        
        ys = [mean_rec([r for r in ties if r["vtree"] == vt and r["nvars"] == n]) for n in nvarss]
        ax2.plot(nvarss, ys, marker="s", color=colors.get(vt, "#888"), label=vt)
    ax2.set_xlabel("number of variables"); ax2.set_ylabel("mean recovery (tie cases)")
    ax2.set_title("Recovery vs problem size"); ax2.legend(frameon=False, fontsize=9)
    ax2.set_xticks(nvarss)

    fig.suptitle("Menu recovery of tied minimal reasons", fontsize=13)
    fig.tight_layout()
    png = os.path.join(OUT, "pi_recovery_chart.png")
    fig.savefig(png, dpi=130)
    return png

# ---------------------------------------------------------------- main
def main():
    rows = load()
    text = summarise(rows)
    path = os.path.join(OUT, "pi_recovery_summary.txt")
    with open(path, "w") as fh:
        fh.write(text + "\n")
    print(text)
    print(f"\nwrote {path}")
    try:
        print(f"wrote {chart(rows)}")
    except Exception as e:
        print(f"(chart skipped: {e})")

if __name__ == "__main__":
    main()