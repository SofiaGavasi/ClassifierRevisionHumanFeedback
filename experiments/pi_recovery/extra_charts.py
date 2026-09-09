"""
Deeper PI-recovery charts (beyond the recovery-vs-density line). 

  (1) histogram of recovery on tie cases  - shows the "usually perfect, sometimes partial" shape the mean hides
  (2) recovery vs number of tied reasons  - recovery degrades as the tie grows  
  (3) avg_missed vs cases_incomplete, per density - the gap between "how much we miss" and "how often we miss anything"
  (4) tie frequency vs density - ties are overwhelmingly a low-density phenomenon, which explains where low recovery lives

Run:  python experiments/pi_recovery/extra_charts.py

"""
import csv, os, statistics

HERE = os.path.dirname(__file__)
OUT = os.path.join(HERE, "outputs")
CSV = os.path.join(OUT, "pi_recovery_results.csv")  

def load():
    rows = []
    with open(CSV) as fh:
        for r in csv.DictReader(fh):
            rows.append({"density": float(r["density"]),
                         "num_minimal": int(float(r["num_minimal"])),
                         "is_tie": int(float(r["is_tie"])),
                         "recovery": float(r["recovery"])})
    return rows

def main():
    import matplotlib; matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    rows = load()
    ties = [r for r in rows if r["is_tie"] == 1]
    dens = sorted(set(r["density"] for r in rows))

    fig, ax = plt.subplots(2, 2, figsize=(13, 9))

    # (1) recovery distribution on ties
    a = ax[0][0]
    a.hist([r["recovery"] for r in ties], bins=20, color="#534AB7", edgecolor="white")
    a.set_xlabel("recovery fraction (tie cases)"); a.set_ylabel("count")
    a.set_title("(1) Distribution of recovery on ties\n(spike at 1.0 = fully recovered)")

    # (2) recovery vs number of tied reasons
    a = ax[0][1]
    nms = sorted(set(r["num_minimal"] for r in ties))
    means = [statistics.mean([r["recovery"] for r in ties if r["num_minimal"] == k]) for k in nms]
    counts = [sum(1 for r in ties if r["num_minimal"] == k) for k in nms]
    a.plot(nms, means, marker="o", color="#D85A30")
    a.set_xlabel("number of tied minimal reasons"); a.set_ylabel("mean recovery")
    a.set_title("(2) Recovery degrades as ties grow")
    for k, m, c in zip(nms, means, counts):
        a.annotate(f"n={c}", (k, m), fontsize=6, color="#888", xytext=(0, 5), textcoords="offset points", ha="center")

    # (3) missed metrics vs density
    a = ax[1][0]
    am = [statistics.mean([1 - r["recovery"] for r in ties if r["density"] == d]) * 100 for d in dens]
    inc = [statistics.mean([1 if r["recovery"] < 1 else 0 for r in ties if r["density"] == d]) * 100 for d in dens]
    a.plot(dens, am, marker="o", label="avg reasons missed %", color="#D85A30")
    a.plot(dens, inc, marker="s", label="cases incomplete %", color="#534AB7")
    a.axvline(4.26, ls="--", color="#B4B2A9", lw=1)
    a.set_xlabel("density"); a.set_ylabel("percent")
    a.set_title("(3) Missed-reasons metrics vs density"); a.legend(frameon=False, fontsize=9)

    # (4) tie frequency vs density
    a = ax[1][1]
    tr = [statistics.mean([r["is_tie"] for r in rows if r["density"] == d]) * 100 for d in dens]
    a.bar([str(d) for d in dens], tr, color="#3C8D6E")
    a.set_xlabel("density"); a.set_ylabel("% of cases with a tie")
    a.set_title("(4) Ties are a low-density phenomenon")

    fig.suptitle("PI-recovery: deeper views", fontsize=14)
    fig.tight_layout()
    png = os.path.join(OUT, "pi_recovery_extra_charts.png")
    fig.savefig(png, dpi=120)
    print(f"wrote {png}")

if __name__ == "__main__":
    main()