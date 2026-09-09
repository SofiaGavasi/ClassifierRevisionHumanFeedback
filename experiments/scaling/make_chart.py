import csv, os, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

CSV = "experiments/scaling/outputs/scaling_results.csv"
OUT = "experiments/scaling/outputs"


def to_group(r):
    g = r.get("group") or r.get("family") or "random"
    if g.startswith("worst_case_pipeline"):
        return "worst_case_pipeline"
    if g == "worst_case_naive":
        return "worst_case_naive"
    return "random"

rows = []
with open(CSV) as f:
    for r in csv.DictReader(f):
        rows.append({
            "group": to_group(r),
            "nvars": int(r["nvars"]),
            "sdd_size": int(r["sdd_size"]),
            "num_reasons": int(r["num_reasons"]) if r["num_reasons"] not in ("", "-1") else None,
            "enum_us": float(r["enum_us"]) if r["enum_us"] not in ("", "skipped") else None,
            "pipeline_us": float(r["pipeline_us"]),
        })

colors = {"random": "#888780", "worst_case_naive": "#D85A30", "worst_case_pipeline": "#534AB7"}
labels = {"random": "random suite", "worst_case_naive": "parity (naive worst case)", "worst_case_pipeline": "HWB / Q_V (pipeline worst case)"}


# ============================================================
# CHART 1 (original): pipeline vs enumeration time, scatter plot, coloured by group
# shows the speedup gap between the two methods, and the different regimes of worst-case examples
# ============================================================
fig, ax = plt.subplots(figsize=(8, 5))
for g in colors:
    sub = [r for r in rows if r["group"] == g and r["enum_us"] is not None]
    if sub:
        ax.scatter([r["enum_us"] for r in sub], [r["pipeline_us"] for r in sub], s=28, c=colors[g], label=labels[g], alpha=0.7, edgecolors="none")
lo = min(r["pipeline_us"] for r in rows)
hi = max(r["enum_us"] for r in rows if r["enum_us"] is not None)
ax.plot([lo, hi], [lo, hi], "--", color="#B4B2A9", linewidth=1, label="equal time")
ax.set_xscale("log"); ax.set_yscale("log")
ax.set_xlabel("enumeration time (us, log)"); ax.set_ylabel("pipeline time (us, log)")
ax.set_title("Pipeline vs enumeration time")
ax.legend(frameon=False, fontsize=9)
fig.tight_layout()
fig.savefig(os.path.join(OUT, "scaling_chart.png"), dpi=130)
plt.close(fig)


# ============================================================
# CHART 2: time vs nvars, enum & pipeline, log-y (the widening gap)
# averages per (group, nvars) so worst-case series and random mean read cleanly
# ============================================================
import statistics
fig, ax = plt.subplots(figsize=(8, 5))
for g in colors:
    sub = [r for r in rows if r["group"] == g]
    if not sub:
        continue
    ns = sorted(set(r["nvars"] for r in sub))
    enum_y = []
    pipe_y = []
    for n in ns:
        cell = [r for r in sub if r["nvars"] == n]
        e = [r["enum_us"] for r in cell if r["enum_us"] is not None]
        enum_y.append(statistics.mean(e) if e else None)
        pipe_y.append(statistics.mean(r["pipeline_us"] for r in cell))
    # enumeration: solid; pipeline: dashed; same colour per group
    ex = [n for n, y in zip(ns, enum_y) if y is not None]
    ey = [y for y in enum_y if y is not None]
    ax.plot(ex, ey, "-o", color=colors[g], label=f"{labels[g]} : enum")
    ax.plot(ns, pipe_y, "--s", color=colors[g], alpha=0.7, label=f"{labels[g]} : pipeline")
ax.set_yscale("log")
ax.set_xlabel("number of variables")
ax.set_ylabel("time (us, log)")
ax.set_title("Time vs problem size\n(enum explodes, pipeline stays flat. gap = speedup)")
ax.legend(frameon=False, fontsize=7)
fig.tight_layout()
fig.savefig(os.path.join(OUT, "scaling_time_vs_nvars.png"), dpi=130)
plt.close(fig)


# ============================================================
# CHART 3: #PIs vs |SDD| scatter, coloured by group
# shows the two worst-case regimes occupy different regions
# ============================================================
fig, ax = plt.subplots(figsize=(8, 5))
for g in colors:
    sub = [r for r in rows if r["group"] == g and r["num_reasons"] is not None]
    if sub:
        ax.scatter([r["sdd_size"] for r in sub], [r["num_reasons"] for r in sub], s=30, c=colors[g], label=labels[g], alpha=0.7, edgecolors="none")
ax.set_xscale("log"); ax.set_yscale("log")
ax.set_xlabel("|SDD| (nodes, log)"); ax.set_ylabel("number of prime implicants (log)")
ax.set_title("Reasons vs compiled size\n(top-left = small SDD but many reasons: pipeline wins hardest)")
ax.legend(frameon=False, fontsize=9)
fig.tight_layout()
fig.savefig(os.path.join(OUT, "scaling_pis_vs_sdd.png"), dpi=130)
plt.close(fig)


# ============================================================
# CHART 4: cost-model validation , pipeline time vs |SDD|,
# and enum time vs #PIs, side by side
# ============================================================
fig, (axL, axR) = plt.subplots(1, 2, figsize=(13, 5))
for g in colors:
    sub = [r for r in rows if r["group"] == g]
    s1 = [r for r in sub if r["pipeline_us"] is not None]
    if s1:
        axL.scatter([r["sdd_size"] for r in s1], [r["pipeline_us"] for r in s1], s=26, c=colors[g], label=labels[g], alpha=0.7, edgecolors="none")
    s2 = [r for r in sub if r["enum_us"] is not None and r["num_reasons"] is not None]
    if s2:
        axR.scatter([r["num_reasons"] for r in s2], [r["enum_us"] for r in s2], s=26, c=colors[g], label=labels[g], alpha=0.7, edgecolors="none")
axL.set_xscale("log"); axL.set_yscale("log")
axL.set_xlabel("|SDD| (nodes, log)"); axL.set_ylabel("pipeline time (us, log)")
axL.set_title("Pipeline cost tracks |SDD|")
axL.legend(frameon=False, fontsize=8)
axR.set_xscale("log"); axR.set_yscale("log")
axR.set_xlabel("number of prime implicants (log)"); axR.set_ylabel("enum time (us, log)")
axR.set_title("Enumeration cost tracks #PIs")
axR.legend(frameon=False, fontsize=8)
fig.suptitle("Cost-model validation: each method's time tracks the quantity theory predicts", fontsize=12)
fig.tight_layout()
fig.savefig(os.path.join(OUT, "scaling_cost_model.png"), dpi=130)
plt.close(fig)

print("wrote 4 charts: scaling_chart.png, scaling_time_vs_nvars.png, " "scaling_pis_vs_sdd.png, scaling_cost_model.png")