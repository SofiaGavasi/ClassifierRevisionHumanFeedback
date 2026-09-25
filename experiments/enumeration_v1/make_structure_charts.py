"""Paper-style structural charts for the enumeration experiments.

Recomputes structural quantities from the same sources used by the timing
experiments and writes four line plots:

  1. number of variables -> SDD size
  2. density -> SDD size
  3. number of variables -> number of PIs / minimal reasons
  4. density -> number of PIs / minimal reasons

The variable-based plots compare:
  - random suite
  - parity worst cases
  - HWB/Q_V worst cases

The handcrafted worst-case examples do not have a density value, so the
density-based plots contain the random suite only.

Run:
    python experiments/enumeration/make_structure_charts.py
"""

import os
import sys
import statistics
from itertools import product

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import rcParams

HERE = os.path.dirname(__file__)
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from rgr.suite import load_suite, build_classifier
from rgr.dataset import load_examples, build_example
from rgr.enumerate import enumerate_reasons, node_dist
from rgr.reasons import all_prime_implicants, disagreement
from rgr.sdd_utils import term_to_sdd

rcParams.update({
    "font.family": "serif",
    "font.size": 11,
    "axes.linewidth": 0.8,
    "xtick.direction": "in",
    "ytick.direction": "in",
    "legend.frameon": False,
})

OUT = os.path.join(HERE, "outputs")
os.makedirs(OUT, exist_ok=True)

C = {
    "random": "#4C6EF5",
    "parity": "#E8590C",
    "hwb_qv": "#7048E8",
}

MARKERS = {
    "random": "o",
    "parity": "s",
    "hwb_qv": "^",
}

LABELS = {
    "random": "random",
    "parity": "parity",
    "hwb_qv": "HWB/Q_V",
}

MAX_NV = 10


def mean(values):
    return statistics.mean(values) if values else 0.0


def structural_metrics(mgr, sdd, nvars):
    """Return classifier-level structural metrics.

    avg_n_minimal_reasons is the mean number of reasons in the minimal
    disagreement layer, averaged over rejected tie instances, matching the
    instance selection used in the timing experiments.
    """
    pis = all_prime_implicants(sdd, nvars, mgr)
    minimal_counts = []

    for bits in product([False, True], repeat=nvars):
        omega = {i + 1: bits[i] for i in range(nvars)}

        if not (term_to_sdd(omega, mgr) & sdd).is_false():
            continue

        mind = min(disagreement(p, omega) for p in pis)

        if sum(1 for p in pis if disagreement(p, omega) == mind) < 2:
            continue

        d0 = node_dist(sdd, omega, {})

        n_minimal = 0
        for _, _, dist in enumerate_reasons(sdd, omega, mgr, nvars):
            if dist > d0:
                break
            n_minimal += 1

        minimal_counts.append(n_minimal)

    return {
        "sdd_size": sdd.size(),
        "n_pis": len(pis),
        "avg_n_minimal_reasons": mean(minimal_counts),
        "n_tie_instances": len(minimal_counts),
    }


def load_random_rows():
    suite = load_suite("standard")
    rows = []

    for entry in suite["classifiers"]:
        mgr, sdd = build_classifier(entry, vtree_type="right")
        metrics = structural_metrics(mgr, sdd, entry["nvars"])

        rows.append({
            "id": entry["id"],
            "group": "random",
            "nvars": entry["nvars"],
            "density": entry["density"],
            **metrics,
        })

    return rows


def load_worstcase_rows():
    rows = []

    for ex in load_examples():
        family = ex["family"]

        if not family.startswith("worst_case"):
            continue
        if ex["nvars"] > MAX_NV:
            continue

        group = "parity" if family == "worst_case_naive" else "hwb_qv"

        mgr, sdd, exb = build_example(ex)
        nvars = exb["nvars"]
        metrics = structural_metrics(mgr, sdd, nvars)

        rows.append({
            "id": exb["id"],
            "group": group,
            "nvars": nvars,
            **metrics,
        })

    return rows


def grouped_mean(rows, xkey, ykey):
    xs = sorted(set(r[xkey] for r in rows))
    ys = [
        statistics.mean(r[ykey] for r in rows if r[xkey] == x)
        for x in xs
    ]
    return xs, ys


def plot_variables_vs_sdd(random_rows, worst_rows):
    fig, ax = plt.subplots(figsize=(4.8, 3.2))

    groups = [
        ("random", random_rows),
        ("parity", [r for r in worst_rows if r["group"] == "parity"]),
        ("hwb_qv", [r for r in worst_rows if r["group"] == "hwb_qv"]),
    ]

    for group, rows in groups:
        if not rows:
            continue

        xs, ys = grouped_mean(rows, "nvars", "sdd_size")
        ax.plot(
            xs, ys, MARKERS[group] + "-",
            color=C[group], ms=4, lw=1.4,
            label=LABELS[group],
        )

    ax.set_xlabel("number of features $n$")
    ax.set_ylabel("SDD size $|D|$")
    ax.legend(fontsize=8.5, loc="upper left")
    fig.tight_layout()

    fig.savefig(os.path.join(OUT, "fig_sdd_size_vs_n.png"), dpi=200)
    plt.close(fig)


def plot_density_vs_sdd(random_rows):
    fig, ax = plt.subplots(figsize=(4.8, 3.2))

    xs, ys = grouped_mean(random_rows, "density", "sdd_size")

    ax.plot(
        xs, ys, "o-",
        color=C["random"], ms=4, lw=1.4,
        label=LABELS["random"],
    )

    ax.set_xlabel("clause/variable density")
    ax.set_ylabel("SDD size $|D|$")
    ax.set_xticks(xs)
    ax.legend(fontsize=8.5, loc="upper left")
    fig.tight_layout()

    fig.savefig(os.path.join(OUT, "fig_sdd_size_vs_density.png"), dpi=200)
    plt.close(fig)


def plot_variables_vs_reason_counts(random_rows, worst_rows):
    fig, ax = plt.subplots(figsize=(5.2, 3.4))

    groups = [
        ("random", random_rows),
        ("parity", [r for r in worst_rows if r["group"] == "parity"]),
        ("hwb_qv", [r for r in worst_rows if r["group"] == "hwb_qv"]),
    ]

    for group, rows in groups:
        if not rows:
            continue

        xs, y_pi = grouped_mean(rows, "nvars", "n_pis")
        _, y_min = grouped_mean(rows, "nvars", "avg_n_minimal_reasons")

        ax.plot(
            xs, y_pi, MARKERS[group] + "-",
            color=C[group], ms=4, lw=1.4,
            label=f"{LABELS[group]}: PIs",
        )

        ax.plot(
            xs, y_min, MARKERS[group] + "--",
            color=C[group], ms=4, lw=1.2, alpha=0.75,
            label=f"{LABELS[group]}: minimal reasons",
        )

    ax.set_xlabel("number of features $n$")
    ax.set_ylabel("number of reasons")
    ax.legend(fontsize=7.8, loc="upper left", ncol=2)
    fig.tight_layout()

    fig.savefig(os.path.join(OUT, "fig_reason_counts_vs_n.png"), dpi=200)
    plt.close(fig)


def plot_density_vs_reason_counts(random_rows):
    fig, ax = plt.subplots(figsize=(4.8, 3.2))

    xs, y_pi = grouped_mean(random_rows, "density", "n_pis")
    _, y_min = grouped_mean(random_rows, "density", "avg_n_minimal_reasons")

    ax.plot(
        xs, y_pi, "o-",
        color=C["random"], ms=4, lw=1.4,
        label="PIs",
    )

    ax.plot(
        xs, y_min, "o--",
        color=C["random"], ms=4, lw=1.2, alpha=0.75,
        label="minimal reasons",
    )

    ax.set_xlabel("clause/variable density")
    ax.set_ylabel("number of reasons")
    ax.set_xticks(xs)
    ax.legend(fontsize=8.5, loc="upper left")
    fig.tight_layout()

    fig.savefig(os.path.join(OUT, "fig_reason_counts_vs_density.png"), dpi=200)
    plt.close(fig)


def main():
    print("RUNNING STRUCTURE CHARTS")
    print("Output directory:", OUT)
    random_rows = load_random_rows()
    worst_rows = load_worstcase_rows()

    plot_variables_vs_sdd(random_rows, worst_rows)
    plot_density_vs_sdd(random_rows)
    plot_variables_vs_reason_counts(random_rows, worst_rows)
    plot_density_vs_reason_counts(random_rows)

    print("wrote structural charts:")
    print("  fig_sdd_size_vs_n.png")
    print("  fig_sdd_size_vs_density.png")
    print("  fig_reason_counts_vs_n.png")
    print("  fig_reason_counts_vs_density.png")


if __name__ == "__main__":
    main()
