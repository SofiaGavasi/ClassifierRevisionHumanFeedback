"""Question-driven plots for the enum_from_model experiment.

Truncated runs are treated as censored outcomes: they are used for resource-
outcome plots, never as ordinary runtimes. Baseline runtime comparisons are
paired and include only rows where both methods completed without truncation.

Outputs PDF/PNG figures plus exactness_summary.csv and
hardness_correlations.csv in the figures directory.
"""
from __future__ import annotations

import argparse
import csv
import math
from collections import defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


PALETTE = ["#0072B2", "#D55E00", "#009E73", "#CC79A7",
           "#E69F00", "#56B4E9", "#000000", "#999999"]
LABEL = {
    "full": "Full pipeline", "no_conditioning": "No conditioning",
    "no_support": "No support red.", "no_core": "No core",
    "no_cegar": "No CEGAR", "baseline": "Exhaustive baseline",
}
ABLATIONS = ["full", "no_conditioning", "no_support", "no_core", "no_cegar"]


def apply_style():
    plt.rcParams.update({
        "font.family": "serif", "font.size": 9, "axes.labelsize": 9,
        "axes.titlesize": 10, "legend.fontsize": 8, "xtick.labelsize": 8,
        "ytick.labelsize": 8, "axes.spines.top": False,
        "axes.spines.right": False, "figure.dpi": 150,
        "savefig.dpi": 300, "savefig.bbox": "tight",
    })


def load_csv(path):
    rows = []
    with path.open(newline="", encoding="utf-8") as f:
        for raw in csv.DictReader(f):
            row = {}
            for key, value in raw.items():
                if value in (None, ""):
                    row[key] = None
                    continue
                try:
                    row[key] = int(value)
                except (TypeError, ValueError):
                    try:
                        row[key] = float(value)
                    except (TypeError, ValueError):
                        row[key] = value
            rows.append(row)
    return rows


def methods(rows, baseline=False):
    choices = ABLATIONS + (["baseline"] if baseline else [])
    return [m for m in choices if any(f"{m}_complete" in r for r in rows)]


def finished(row, method):
    return (row.get(f"{method}_complete") == 1 and
            row.get(f"{method}_truncated") == 0)


def measured_time(row, method, suffix="time_total_s"):
    if not finished(row, method):
        return None
    value = row.get(f"{method}_{suffix}")
    if isinstance(value, (int, float)) and value > 0 and math.isfinite(value):
        return float(value)
    return None


def paired(rows, first="full", second="baseline", suffix="time_total_s"):
    return [r for r in rows if measured_time(r, first, suffix) is not None
            and measured_time(r, second, suffix) is not None]


def figsize(cols=1, aspect=.72):
    width = 3.3 if cols == 1 else 6.9
    return width, width * aspect


def save(fig, stem):
    fig.tight_layout(pad=.5)
    fig.savefig(stem.with_suffix(".pdf"))
    fig.savefig(stem.with_suffix(".png"))
    plt.close(fig)
    print(f"  wrote {stem.with_suffix('.pdf').name}")


def quartiles(rows, field, getter):
    groups = defaultdict(list)
    for row in rows:
        x, y = row.get(field), getter(row)
        if x is not None and y is not None and np.isfinite(y):
            groups[x].append(float(y))
    xs = np.array(sorted(groups), dtype=float)
    if not len(xs):
        z = np.array([], dtype=float)
        return z, z, z, z
    return (xs, np.array([np.median(groups[x]) for x in xs]),
            np.array([np.percentile(groups[x], 25) for x in xs]),
            np.array([np.percentile(groups[x], 75) for x in xs]))


def median_iqr(ax, series, label, color):
    xs, med, q1, q3 = series
    if len(xs):
        ax.plot(xs, med, "o-", color=color, label=label, lw=1.3)
        ax.fill_between(xs, q1, q3, color=color, alpha=.16, linewidth=0)


def rankdata(values):
    x = np.asarray(values, dtype=float)
    order, ranks = np.argsort(x, kind="mergesort"), np.empty(len(x))
    start = 0
    while start < len(x):
        end = start + 1
        while end < len(x) and x[order[end]] == x[order[start]]:
            end += 1
        ranks[order[start:end]] = (start + end - 1) / 2 + 1
        start = end
    return ranks


def spearman(xs, ys):
    if len(xs) < 3:
        return float("nan")
    rx, ry = rankdata(xs), rankdata(ys)
    if np.std(rx) == 0 or np.std(ry) == 0:
        return float("nan")
    return float(np.corrcoef(rx, ry)[0, 1])


# RQ1: exactness -------------------------------------------------------

def exactness_rows(rows):
    output = []
    for method in methods(rows):
        available = [r for r in rows if r.get(f"{method}_complete") is not None]
        output.append({
            "method": method,
            "total_rows": len(available),
            "exact_completed": sum(finished(r, method) for r in available),
            "truncated": sum(r.get(f"{method}_truncated") == 1 for r in available),
            "nontruncated_mismatch": sum(
                r.get(f"{method}_truncated") == 0 and
                r.get(f"{method}_complete") == 0 for r in available),
        })
    return output


def exactness_summary(rows, path):
    fields = ["method", "total_rows", "exact_completed", "truncated",
              "nontruncated_mismatch"]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader(); writer.writerows(exactness_rows(rows))
    print(f"  wrote {path.name}")


def fig_exactness(rows, stem):
    data = exactness_rows(rows)
    exact = np.array([r["exact_completed"] for r in data], float)
    mismatch = np.array([r["nontruncated_mismatch"] for r in data], float)
    trunc = np.array([r["truncated"] for r in data], float)
    total = np.maximum(exact + mismatch + trunc, 1)
    x = np.arange(len(data)); fig, ax = plt.subplots(figsize=figsize(1, .82))
    ax.bar(x, 100*exact/total, color=PALETTE[2], label="Exact, completed")
    ax.bar(x, 100*mismatch/total, bottom=100*exact/total,
           color=PALETTE[1], label="Mismatch, not truncated")
    ax.bar(x, 100*trunc/total, bottom=100*(exact+mismatch)/total,
           color=PALETTE[7], label="Truncated")
    ax.set(ylim=(0, 100), ylabel="Rows (%)")
    ax.set_xticks(x); ax.set_xticklabels([LABEL[r["method"]] for r in data],
                                         rotation=27, ha="right")
    ax.legend(frameon=False, loc="lower left"); ax.grid(axis="y", ls=":", alpha=.4)
    save(fig, stem)


# RQ2: scalability -----------------------------------------------------

def fig_scalability(rows, stem):
    use = paired(rows)
    fig, ax = plt.subplots(figsize=figsize())
    for method, color in [("full", PALETTE[0]), ("baseline", PALETTE[1])]:
        median_iqr(ax, quartiles(use, "nvars",
                   lambda r, m=method: measured_time(r, m)), LABEL[method], color)
    ax.set_yscale("log"); ax.set_xlabel("Number of variables $n$")
    ax.set_ylabel("Total wall time (s), median [IQR]")
    ax.legend(frameon=False); ax.grid(axis="y", which="both", ls=":", alpha=.4)
    if not use:
        ax.text(.5, .5, "No paired completed rows", transform=ax.transAxes,
                ha="center", va="center")
    save(fig, stem)


def fig_first_result(rows, stem):
    use = paired(rows, suffix="time_first_pi_s")
    fig, ax = plt.subplots(figsize=figsize())
    for method, color in [("full", PALETTE[0]), ("baseline", PALETTE[1])]:
        median_iqr(ax, quartiles(use, "nvars", lambda r, m=method:
                   measured_time(r, m, "time_first_pi_s")), LABEL[method], color)
    ax.set_yscale("log"); ax.set_xlabel("Number of variables $n$")
    ax.set_ylabel("Time to first reason (s), median [IQR]")
    ax.legend(frameon=False); ax.grid(axis="y", which="both", ls=":", alpha=.4)
    save(fig, stem)


def fig_budget_success(rows, stem):
    # Baseline omitted: old CSVs encode intentional skips exactly like timeouts.
    fig, ax = plt.subplots(figsize=figsize(2, .45))
    for i, method in enumerate(methods(rows)):
        groups = defaultdict(list)
        for row in rows:
            if row.get("nvars") is not None and row.get(f"{method}_complete") is not None:
                groups[row["nvars"]].append(int(finished(row, method)))
        xs = sorted(groups); ys = [100*np.mean(groups[x]) for x in xs]
        ax.plot(xs, ys, "o-", lw=1.2, color=PALETTE[i], label=LABEL[method])
    ax.set(ylim=(-3, 103), xlabel="Number of variables $n$",
           ylabel="Completed within budget (%)")
    ax.legend(frameon=False, ncol=3, loc="lower left")
    ax.grid(axis="y", ls=":", alpha=.4); save(fig, stem)


def fig_sddsize(rows, stem):
    use = paired(rows)
    fig, ax = plt.subplots(figsize=figsize())
    for method, color in [("full", PALETTE[0]), ("baseline", PALETTE[1])]:
        xy = [(r.get("sdd_size"), measured_time(r, method)) for r in use]
        xy = [(x, y) for x, y in xy if isinstance(x, (int, float)) and x > 0 and y]
        ax.scatter([x for x, _ in xy], [y for _, y in xy], s=10,
                   color=color, alpha=.55, edgecolors="none", label=LABEL[method])
    ax.set_xscale("log"); ax.set_yscale("log")
    ax.set(xlabel=r"Compiled classifier size $|D|$", ylabel="Total wall time (s)")
    ax.legend(frameon=False); ax.grid(which="both", ls=":", alpha=.4); save(fig, stem)


# RQ3: output-sensitive behaviour -------------------------------------

def fig_output_sensitivity(rows, stem):
    use = paired(rows)
    fig, axes = plt.subplots(1, 2, figsize=figsize(2, .48))
    for method, color, marker in [("full", PALETTE[0], "o"),
                                  ("baseline", PALETTE[1], "s")]:
        xy = [(r.get("n_pis_minimal_gt"), measured_time(r, method)) for r in use]
        xy = [(x, y) for x, y in xy if isinstance(x, (int, float)) and x > 0 and y]
        axes[0].scatter([x for x, _ in xy], [y for _, y in xy], s=10,
                        marker=marker, color=color, alpha=.5, edgecolors="none",
                        label=LABEL[method])
    axes[0].set(xscale="log", yscale="log",
                xlabel="Number of minimum-disagreement reasons",
                ylabel="Total wall time (s)")
    axes[0].legend(frameon=False); axes[0].grid(which="both", ls=":", alpha=.4)
    xy = [(r.get("n_pis_minimal_gt"), measured_time(r, "full", "delay_avg_s"))
          for r in rows]
    xy = [(x, y) for x, y in xy if isinstance(x, (int, float)) and x > 0 and y]
    axes[1].scatter([x for x, _ in xy], [y for _, y in xy], s=10,
                    color=PALETTE[2], alpha=.55, edgecolors="none")
    axes[1].set(xscale="log", yscale="log",
                xlabel="Number of minimum-disagreement reasons",
                ylabel="Average inter-output delay (s), full")
    axes[1].grid(which="both", ls=":", alpha=.4); save(fig, stem)


def fig_speedup(rows, stem):
    xy = []
    for row in paired(rows):
        count, full, base = (row.get("n_pis_minimal_gt"),
                             measured_time(row, "full"), measured_time(row, "baseline"))
        if isinstance(count, (int, float)) and count > 0:
            xy.append((count, base/full))
    fig, ax = plt.subplots(figsize=figsize())
    ax.scatter([x for x, _ in xy], [y for _, y in xy], s=10,
               color=PALETTE[0], alpha=.6, edgecolors="none")
    ax.axhline(1, color=PALETTE[7], ls="--", lw=.9)
    ax.set(xscale="log", yscale="log",
           xlabel="Number of minimum-disagreement reasons",
           ylabel="Paired speedup: baseline / full")
    ax.grid(which="both", ls=":", alpha=.4); save(fig, stem)


# RQ4: ablations and mechanism ----------------------------------------

def fig_ablations(rows, stem):
    variants = [m for m in methods(rows) if m != "full"]
    ratios, rates, counts = [], [], []
    for method in variants:
        use = paired(rows, "full", method)
        vals = [measured_time(r, method)/measured_time(r, "full") for r in use]
        ratios.append(vals); counts.append(len(vals))
        available = [r for r in rows if r.get(f"{method}_truncated") is not None]
        rates.append(100*np.mean([r.get(f"{method}_truncated") == 1 for r in available]))
    x = np.arange(len(variants)); fig, axes = plt.subplots(1, 2, figsize=figsize(2, .5))
    if variants:
        bp = axes[0].boxplot(ratios, positions=x, widths=.6, patch_artist=True,
                             showfliers=True,
                             flierprops={"markersize": 2.5, "alpha": .35})
        for i, patch in enumerate(bp["boxes"]):
            patch.set_facecolor(PALETTE[i+1]); patch.set_alpha(.62)
    axes[0].axhline(1, color=PALETTE[7], ls="--", lw=.9)
    axes[0].set_yscale("log"); axes[0].set_ylabel("Paired slowdown: ablation / full")
    axes[0].set_xticks(x); axes[0].set_xticklabels(
        [f"{LABEL[m]}\n($N={n}$)" for m, n in zip(variants, counts)],
        rotation=22, ha="right")
    axes[0].grid(axis="y", which="both", ls=":", alpha=.4)
    axes[1].bar(x, rates, color=[PALETTE[i+1] for i in range(len(variants))])
    axes[1].set_ylabel("Truncated rows (%)"); axes[1].set_xticks(x)
    axes[1].set_xticklabels([LABEL[m] for m in variants], rotation=22, ha="right")
    axes[1].grid(axis="y", ls=":", alpha=.4); save(fig, stem)


def fig_reductions(rows, stem):
    search, residual = defaultdict(list), defaultdict(list)
    for row in rows:
        n, d, rmu = row.get("nvars"), row.get("d_star"), row.get("full_r_mu")
        size, res = row.get("sdd_size"), row.get("full_residual_sdd_size")
        if not finished(row, "full") or n is None:
            continue
        denominator = n-d if isinstance(d, (int, float)) else None
        if denominator and denominator > 0 and isinstance(rmu, (int, float)):
            search[int(n)].append(1-rmu/denominator)
        if isinstance(size, (int, float)) and size > 0 and isinstance(res, (int, float)):
            residual[int(n)].append(res/size)
    fig, axes = plt.subplots(1, 2, figsize=figsize(2, .48))
    specs = [(search, r"Search-dimension reduction $1-r_\mu/(n-d^*)$", PALETTE[2], 0),
             (residual, r"Residual fraction $|D_\mu|/|D|$", PALETTE[3], 1)]
    for ax, groups, ylabel, color, reference in zip(axes,
            [s[0] for s in specs], [s[1] for s in specs],
            [s[2] for s in specs], [s[3] for s in specs]):
        ns = sorted(groups); data = [groups[n] for n in ns]
        if data:
            bp = ax.boxplot(data, positions=np.arange(len(ns)), widths=.6,
                            patch_artist=True, showfliers=False)
            for patch in bp["boxes"]: patch.set_facecolor(color); patch.set_alpha(.62)
            ax.set_xticks(np.arange(len(ns))); ax.set_xticklabels(ns)
        ax.axhline(reference, color=PALETTE[7], ls="--", lw=.8)
        ax.set(xlabel="Number of variables $n$", ylabel=ylabel)
        ax.grid(axis="y", ls=":", alpha=.4)
    save(fig, stem)


def fig_operations(rows, stem):
    ms = methods(rows); metrics = [("entailment_checks", "Entailment checks"),
                                   ("countermodel_calls", "Countermodel calls"),
                                   ("conflicts_added", "Conflicts added")]
    fig, axes = plt.subplots(1, 3, figsize=figsize(2, .42)); x = np.arange(len(ms))
    for ax, (suffix, ylabel) in zip(axes, metrics):
        data = [[r.get(f"{m}_{suffix}") for r in rows if finished(r, m)
                 and isinstance(r.get(f"{m}_{suffix}"), (int, float))
                 and r.get(f"{m}_{suffix}") > 0] for m in ms]
        if any(data):
            bp = ax.boxplot(data, positions=x, widths=.58, patch_artist=True,
                            showfliers=False)
            for i, patch in enumerate(bp["boxes"]):
                patch.set_facecolor(PALETTE[i]); patch.set_alpha(.62)
        ax.set_yscale("log"); ax.set_ylabel(ylabel); ax.set_xticks(x)
        ax.set_xticklabels([LABEL[m] for m in ms], rotation=30, ha="right")
        ax.grid(axis="y", which="both", ls=":", alpha=.4)
    save(fig, stem)


# Hardness -------------------------------------------------------------

def sorted_unique(values):
    values = list(set(values))
    try: return sorted(values, key=float)
    except (TypeError, ValueError): return sorted(values, key=str)


def fig_heatmaps(rows, stem):
    ns = sorted_unique(r["nvars"] for r in rows if r.get("nvars") is not None)
    ds = sorted_unique(r["density"] for r in rows if r.get("density") is not None)
    ni, di = {v:i for i,v in enumerate(ns)}, {v:i for i,v in enumerate(ds)}
    times, successes = defaultdict(list), defaultdict(list)
    for row in rows:
        key = (row.get("nvars"), row.get("density"))
        if key[0] not in ni or key[1] not in di: continue
        successes[key].append(int(finished(row, "full")))
        time = measured_time(row, "full")
        if time is not None: times[key].append(time)
    tg = np.full((len(ns), len(ds)), np.nan); sg = np.full_like(tg, np.nan)
    for key, vals in times.items(): tg[ni[key[0]], di[key[1]]] = np.median(vals)
    for key, vals in successes.items(): sg[ni[key[0]], di[key[1]]] = 100*np.mean(vals)
    fig, axes = plt.subplots(1, 2, figsize=figsize(2, .48))
    im = axes[0].imshow(np.where(tg > 0, np.log10(tg), np.nan), origin="lower",
                        aspect="auto", cmap="viridis")
    fig.colorbar(im, ax=axes[0], fraction=.047, pad=.03).set_label(
        r"$\log_{10}$ median runtime (s)")
    im = axes[1].imshow(sg, origin="lower", aspect="auto", cmap="magma", vmin=0, vmax=100)
    fig.colorbar(im, ax=axes[1], fraction=.047, pad=.03).set_label(
        "Completed within budget (%)")
    for ax in axes:
        ax.set_xticks(np.arange(len(ds))); ax.set_xticklabels(ds, rotation=45, ha="right")
        ax.set_yticks(np.arange(len(ns))); ax.set_yticklabels(ns)
        ax.set(xlabel="Clause/variable density", ylabel="Number of variables $n$")
    axes[0].set_title("Completed runs only"); axes[1].set_title("All full-method runs")
    save(fig, stem)


PREDICTORS = [("nvars", "$n$"), ("sdd_size", "$|D|$"), ("d_star", "$d^*$"),
              ("n_nearest_models", "Nearest models"),
              ("n_pis_minimal_gt", "Minimum reasons"),
              ("full_r_mu", "$r_\\mu$"), ("full_core_size", "Core size"),
              ("full_residual_sdd_size", "$|D_\\mu|$")]


def correlation_rows(rows):
    output = []
    for field, label in PREDICTORS:
        pairs = [(r.get(field), measured_time(r, "full")) for r in rows]
        pairs = [(x, y) for x, y in pairs if isinstance(x, (int, float)) and y is not None]
        output.append({"field": field, "label": label,
                       "spearman_rho": spearman([x for x,_ in pairs], [y for _,y in pairs]),
                       "n": len(pairs)})
    return output


def correlation_summary(rows, path):
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["field", "spearman_rho", "n"])
        writer.writeheader()
        for row in correlation_rows(rows):
            writer.writerow({k: row[k] for k in writer.fieldnames})
    print(f"  wrote {path.name}")


def fig_correlations(rows, stem):
    data = [r for r in correlation_rows(rows) if np.isfinite(r["spearman_rho"])]
    data.sort(key=lambda r: abs(r["spearman_rho"])); y = np.arange(len(data))
    vals = [r["spearman_rho"] for r in data]
    fig, ax = plt.subplots(figsize=figsize(2, .9))
    ax.barh(y, vals, color=[PALETTE[0] if v >= 0 else PALETTE[1] for v in vals], alpha=.8)
    ax.axvline(0, color=PALETTE[6], lw=.8); ax.set_xlim(-1, 1)
    ax.set_yticks(y); ax.set_yticklabels([f"{r['label']} ($N={r['n']}$)" for r in data])
    ax.set_xlabel("Spearman correlation with full runtime")
    ax.grid(axis="x", ls=":", alpha=.4); save(fig, stem)


def main():
    parser = argparse.ArgumentParser()
    default = Path(__file__).resolve().parent / "outputs" / "enum_from_model_results.csv"
    parser.add_argument("--csv", type=Path, default=default)
    parser.add_argument("--out-dir", type=Path, default=None)
    args = parser.parse_args()
    if not args.csv.exists(): raise SystemExit(f"CSV not found: {args.csv}")
    rows = load_csv(args.csv)
    required = {"nvars", "density", "sdd_size", "d_star", "n_nearest_models",
                "n_pis_minimal_gt", "full_complete", "full_truncated",
                "full_time_total_s"}
    present = set().union(*(r.keys() for r in rows)) if rows else set()
    if missing := sorted(required-present):
        raise SystemExit("CSV is missing required columns: " + ", ".join(missing))
    out = args.out_dir or args.csv.parent / "figures"; out.mkdir(parents=True, exist_ok=True)
    apply_style(); print(f"plotting {len(rows)} rows -> {out}")
    exactness_summary(rows, out/"exactness_summary.csv")
    correlation_summary(rows, out/"hardness_correlations.csv")
    """
    fig_exactness(rows, out/"fig1_exactness_outcomes")
    fig_scalability(rows, out/"fig2_scalability_total")
    fig_first_result(rows, out/"fig3_time_to_first")
    fig_budget_success(rows, out/"fig4_budget_success")
    fig_output_sensitivity(rows, out/"fig5_output_sensitivity")
    fig_speedup(rows, out/"fig6_speedup_vs_pis")
    fig_ablations(rows, out/"fig7_ablation_effects")
    fig_reductions(rows, out/"fig8_structural_reduction")
    fig_heatmaps(rows, out/"fig9_hardness_heatmaps")
    """
    fig_correlations(rows, out/"fig10_hardness_correlations")
    fig_sddsize(rows, out/"fig11_time_vs_sddsize")
    fig_operations(rows, out/"fig12_operation_counts")


if __name__ == "__main__":
    main()
