"""Generate reproducible plots and machine-readable reports for MNIST tasks.

    python -m application_mnist.eda.explore raw
    python -m application_mnist.eda.explore prepared --file application_mnist/data/processed/....npz
    python -m application_mnist.eda.explore compare --file application_mnist/data/processed/....npz
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # works on servers and without a GUI
import matplotlib.pyplot as plt
import numpy as np

from ..data.features import FeatureSpec, encode_boolean
from ..data.mnist_io import default_raw_dir, load_mnist
from ..data.pipeline import load_prepared


def _save_plot(path):
    plt.savefig(path, bbox_inches="tight", dpi=160)
    plt.close()


def raw_report(raw, out, seed =10):
    out.mkdir(parents=True, exist_ok=True)
    train_images, y = raw["train_images"], raw["train_labels"]
    test_images, yt = raw["test_images"], raw["test_labels"]
    train_counts = np.bincount(y, minlength=10)
    test_counts = np.bincount(yt, minlength=10)
    fig, ax = plt.subplots(figsize=(10, 4))
    positions = np.arange(10)
    ax.bar(positions - .19, train_counts, .38, label="Original training split")
    ax.bar(positions + .19, test_counts, .38, label="Original test split")
    ax.set(xticks=positions, xlabel="Digit", ylabel="Number of examples", title="MNIST: class counts")
    ax.legend()
    _save_plot(out / "digit_distribution.png")

    rng = np.random.default_rng(seed)
    fig, axes = plt.subplots(10, 5, figsize=(8, 14))
    for digit in range(10):
        positions = rng.choice(np.flatnonzero(y == digit), size=5, replace=False)
        for col, idx in enumerate(positions):
            ax = axes[digit, col]
            ax.imshow(train_images[idx], cmap="gray", vmin=0, vmax=255)
            ax.set_xticks([])
            ax.set_yticks([])
            if col == 0:
                ax.set_ylabel(str(digit), rotation=0, labelpad=15)
    fig.suptitle("Five original training examples per digit", y=1.005)
    fig.tight_layout()
    _save_plot(out / "digit_examples.png")

    fig, axes = plt.subplots(2, 5, figsize=(12, 5))
    for digit, ax in enumerate(axes.flat):
        ax.imshow(train_images[y == digit].mean(axis=0), cmap="inferno", vmin=0, vmax=255)
        ax.set_title(str(digit))
        ax.axis("off")
    fig.suptitle("Average image for each digit (training split)")
    fig.tight_layout()
    _save_plot(out / "digit_average_images.png")

    fig, ax = plt.subplots(figsize=(5, 5))
    ax.imshow(train_images.mean(axis=0), cmap="inferno", vmin=0, vmax=255)
    ax.set_title("Mean pixel intensity over training images")
    ax.set_xlabel("Pixel column")
    ax.set_ylabel("Pixel row")
    _save_plot(out / "global_mean_image.png")

    count_rows = [dict(digit=i, train=int(train_counts[i]), test=int(test_counts[i])) for i in range(10)]
    _write_csv(out / "class_counts.csv", count_rows)
    summary = {
        "train_size": len(train_images), "test_size": len(test_images),
        "image_shape": [28, 28], "dtype": str(train_images.dtype),
        "train_digit_counts": train_counts.tolist(), "test_digit_counts": test_counts.tolist(),
        "train_mean_pixel_intensity": round(float(train_images.mean()), 4),
        "train_fraction_nonzero_pixels": round(float(np.mean(train_images > 0)), 5),
        "test_fraction_nonzero_pixels": round(float(np.mean(test_images > 0)), 5),
    }
    _write_summary(out, summary, title="Original MNIST EDA")
    return summary


def _feature_stats(x: np.ndarray, y: np.ndarray):
    """Loss-of-information statistics without training a model."""
    x = np.asarray(x, dtype=np.uint8)
    y = np.asarray(y, dtype=np.uint8)
    if x.ndim != 2 or len(x) != len(y) or len(x) == 0:
        raise ValueError("Expected nonempty Boolean feature matrix and matching labels")
    if np.any((x != 0) & (x != 1)) or np.any((y != 0) & (y != 1)):
        raise ValueError("Features and target labels must be Boolean")
    packed = np.packbits(x, axis=1)
    _, index, frequency = np.unique(packed, axis=0, return_inverse=True, return_counts=True)
    per_pattern = np.bincount(index * 2 + y, minlength=2 * len(frequency)).reshape(-1, 2)
    unavoidable = int(np.minimum(per_pattern[:, 0], per_pattern[:, 1]).sum())
    collisions = int(np.sum(np.all(per_pattern > 0, axis=1)))
    rate = x.mean(axis=0)
    return {
        "n_examples": len(x), "n_features": x.shape[1],
        "unique_boolean_patterns": len(frequency),
        "repeated_examples": int(len(x) - len(frequency)),
        "conflicting_label_patterns": collisions,
        "min_in_sample_errors_from_collisions": unavoidable,
        "best_possible_in_sample_accuracy_given_features": float(1 - unavoidable / len(x)),
        "constant_features": int(np.sum((rate == 0) | (rate == 1))),
        "mean_active_features": float(x.sum(axis=1).mean()),
        "mean_active_fraction": float(rate.mean()),
    }


def _write_csv(path, rows):
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _write_summary(out, summary, title):
    (out / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    text = [f"# {title}", "", "Metrics calculated on provided data (not model predictions).", ""]
    text.extend(f"- **{k}**: {v}" for k, v in summary.items())
    (out / "summary.md").write_text("\n".join(text) + "\n", encoding="utf-8")


def prepared_report(data, out, seed = 100):
    out.mkdir(parents=True, exist_ok=True)
    spec = FeatureSpec(**data["metadata"]["feature_spec"])
    train_x = data["train_features"]
    train_y = data["train_labels"]
    y0, y1 = train_x[train_y == 0], train_x[train_y == 1]
    if not len(y0) or not len(y1):
        raise ValueError("Expected both classes in the training split")
    stats = _feature_stats(train_x, train_y)
    stats.update({
        "task": data["metadata"]["task_name"],
        "grid_size": spec.grid_size, "threshold": spec.threshold,
        "positive_count": int(len(y1)), "negative_count": int(len(y0)),
        "validation_count": int(len(data["val_labels"])),
        "test_count": int(len(data["test_labels"])),
        "mean_active_positive": float(y1.sum(axis=1).mean()),
        "mean_active_negative": float(y0.sum(axis=1).mean()),
    })
    _write_summary(out, stats, "Prepared binary MNIST EDA")

    fig, ax = plt.subplots(figsize=(7, 4))
    splits = ["train", "val", "test"]
    pos = [int(np.sum(data[f"{s}_labels"] == 1)) for s in splits]
    neg = [int(np.sum(data[f"{s}_labels"] == 0)) for s in splits]
    ax.bar(splits, neg, label="Negative (0)")
    ax.bar(splits, pos, bottom=neg, label="Positive (1)")
    ax.set(title="Binary class counts by split", ylabel="Examples")
    ax.legend()
    _save_plot(out / "class_balance.png")

    fig, axes = plt.subplots(1, 3, figsize=(12, 4))
    for ax, values, title in zip(axes, (y0.mean(axis=0), y1.mean(axis=0), y1.mean(axis=0) - y0.mean(axis=0)),
                                 ("Negative: fraction ON", "Positive: fraction ON", "Positive minus negative")):
        mat = values.reshape(spec.grid_size, spec.grid_size)
        im = ax.imshow(mat, cmap="coolwarm" if "minus" in title else "viridis",
                       vmin=-1 if "minus" in title else 0, vmax=1)
        ax.set_title(title)
        ax.set_xlabel("Feature grid column")
        ax.set_ylabel("Feature grid row")
        fig.colorbar(im, ax=ax, fraction=.048, pad=.03)
    fig.tight_layout()
    _save_plot(out / "feature_heatmaps.png")

    names = data["feature_names"]
    positive_rate = y1.mean(axis=0)
    negative_rate = y0.mean(axis=0)
    rows = [dict(feature=str(name), positive_rate=float(p), negative_rate=float(n),
                 absolute_difference=float(abs(p - n)))
            for name, p, n in zip(names, positive_rate, negative_rate)]
    rows.sort(key=lambda item: item["absolute_difference"], reverse=True)
    _write_csv(out / "feature_rates.csv", rows)
    top = rows[:min(20, len(rows))]
    fig, ax = plt.subplots(figsize=(9, max(4, .27 * len(top) + 1)))
    ax.barh([row["feature"] for row in top[::-1]], [row["absolute_difference"] for row in top[::-1]])
    ax.set(xlabel="Absolute difference in activation rate between classes",
           title="Most different Boolean regions (descriptive, not selected features)")
    _save_plot(out / "top_features.png")

    rng = np.random.default_rng(seed)
    fig, axes = plt.subplots(8, 2, figsize=(5, 15))
    for row in range(8):
        cls = row % 2
        index = int(rng.choice(np.flatnonzero(train_y == cls)))
        original_ax, boolean_ax = axes[row]
        original_ax.imshow(data["train_images"][index], cmap="gray", vmin=0, vmax=255)
        original_ax.set_title(f"Digit {data['train_digit_labels'][index]} | class {cls}")
        boolean_ax.imshow(train_x[index].reshape(spec.grid_size, spec.grid_size), cmap="gray", vmin=0, vmax=1)
        boolean_ax.set_title(f"Boolean {spec.grid_size}x{spec.grid_size} encoding")
        for ax in (original_ax, boolean_ax):
            ax.axis("off")
    fig.tight_layout()
    _save_plot(out / "original_vs_boolean.png")
    return stats


def compare_grids(data, out, grid_sizes= (4, 7, 14),thresholds = (.10, .20, .30)):
    """Compare feature encodings on TRAIN split only, never optimizing on test labels."""
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    images, labels = data["train_images"], data["train_labels"]
    for grid in grid_sizes:
        for threshold in thresholds:
            spec = FeatureSpec(grid, threshold)
            features = encode_boolean(images, spec)
            metrics = _feature_stats(features, labels)
            rows.append({"grid": grid, "threshold": threshold, **metrics})
    _write_csv(out / "grid_comparison.csv", rows)
    (out / "grid_comparison.json").write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    fig, ax = plt.subplots(figsize=(8, 5))
    for threshold in thresholds:
        these = sorted((r for r in rows if r["threshold"] == threshold), key=lambda r: r["n_features"])
        ax.plot([r["n_features"] for r in these],
                [r["min_in_sample_errors_from_collisions"] / r["n_examples"] for r in these],
                marker="o", label=f"threshold={threshold:g}")
    ax.set(xlabel="Number of Boolean features", ylabel="Min. unavoidable training error fraction",
           title="Representation collisions vs. feature count (train data only)")
    ax.legend()
    _save_plot(out / "collision_tradeoff.png")
    return rows


def main(argv = None):
    parser = argparse.ArgumentParser(description="Explore original MNIST or a prepared binary experiment")
    parser.add_argument("mode", choices=["raw", "prepared", "compare"])
    parser.add_argument("--file", type=Path, help="Prepared .npz (required for prepared/compare)")
    parser.add_argument("--out", type=Path, help="Output folder for plots/reports")
    parser.add_argument("--raw-dir", type=Path, default=default_raw_dir())
    parser.add_argument("--grid-sizes", default="4,7,14", help="Compare mode only")
    parser.add_argument("--thresholds", default="0.1,0.2,0.3", help="Compare mode only")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args(argv)
    if args.mode == "raw":
        out = args.out or Path(__file__).resolve().parent / "reports" / "raw"
        summary = raw_report(load_mnist(args.raw_dir), out, seed=args.seed)
        print(json.dumps(summary, indent=2))
    else:
        if args.file is None:
            parser.error("--file must point to a prepared .npz for this mode")
        dataset = load_prepared(args.file)
        out = args.out or Path(__file__).resolve().parent / "reports" / args.file.stem / args.mode
        if args.mode == "prepared":
            print(json.dumps(prepared_report(dataset, out, seed=args.seed), indent=2))
        else:
            sizes = tuple(int(s) for s in args.grid_sizes.split(","))
            thresholds = tuple(float(s) for s in args.thresholds.split(","))
            result = compare_grids(dataset, out, sizes, thresholds)
            print(json.dumps(result, indent=2))
    print(f"Saved plots/reports in {out}")


if __name__ == "__main__":
    main()
