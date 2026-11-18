"""Notebook-oriented figures for a binary Boolean MNIST decision tree."""
from __future__ import annotations

import numpy as np
import matplotlib.pyplot as plt
from sklearn.metrics import ConfusionMatrixDisplay, confusion_matrix
from sklearn.tree import DecisionTreeClassifier, plot_tree


def plot_validation_grid(rows, metric = "balanced_accuracy"):
    """Show validation score by requested max depth, grouped by min leaf size."""
    fig, ax = plt.subplots(figsize=(9, 4.5))
    for leaf in sorted({r["min_samples_leaf"] for r in rows}):
        group = [r for r in rows if r["min_samples_leaf"] == leaf and r["ccp_alpha"] == 0.0]
        group.sort(key=lambda r: (float("inf") if r["max_depth"] is None else r["max_depth"]))
        labels = ["None" if r["max_depth"] is None else str(r["max_depth"]) for r in group]
        ax.plot(range(len(group)), [r[metric] for r in group], marker="o", label=f"leaf≥{leaf}")
        ax.set_xticks(range(len(group)), labels)
    ax.set(xlabel="max_depth (None = unbounded)", ylabel=f"Validation {metric}",
           title="Tree complexity versus validation performance")
    ax.legend()
    fig.tight_layout()
    return fig


def plot_tree_diagram(model, feature_names, *, max_depth = 3):
    """Truncate the drawn tree, not the fitted predictor."""
    fig, ax = plt.subplots(figsize=(min(24, 3.5 * 2**min(max_depth, 3)), 7))
    plot_tree(model, feature_names=feature_names, class_names=["no", "yes"],
              filled=True, rounded=True, proportion=True, impurity=False,
              max_depth=max_depth, fontsize=8, ax=ax)
    ax.set_title(f"Trained decision tree (display depth ≤ {max_depth})")
    fig.tight_layout()
    return fig


def plot_confusion(model, data, split= "val"):
    if split not in ("train", "val", "test"):
        raise ValueError("Invalid split")
    y = data[f"{split}_labels"]
    predicted = model.predict(data[f"{split}_features"])
    mat = confusion_matrix(y, predicted, labels=[0, 1])
    fig, ax = plt.subplots(figsize=(5, 4))
    ConfusionMatrixDisplay(mat, display_labels=["No (0)", "Yes (1)"]).plot(ax=ax, cmap="Blues", colorbar=False)
    ax.set_title(f"{split.title()} confusion matrix")
    fig.tight_layout()
    return fig


def plot_used_regions(model, data):
    g = int(data["metadata"]["feature_spec"]["grid_size"])
    importance = model.feature_importances_.reshape(g, g)
    fig, ax = plt.subplots(figsize=(6, 5))
    im = ax.imshow(importance, cmap="viridis", interpolation="nearest")
    for r in range(g):
        for c in range(g):
            if importance[r, c] > 0:
                ax.text(c, r, "×", ha="center", va="center", color="white", fontsize=10)
    ax.set(xlabel="Grid column", ylabel="Grid row", title="Tree feature importance (× = used split)")
    fig.colorbar(im, ax=ax, label="Gini / entropy impurity reduction")
    fig.tight_layout()
    return fig


def explain_tree_path(model, x, feature_names):
    """Path through this specific tree; NOT guaranteed a prime implicant."""
    x = np.asarray(x).reshape(1, -1)
    if x.shape[1] != len(feature_names):
        raise ValueError("Feature-name mismatch")
    path = model.decision_path(x)
    leaf_id = int(model.apply(x)[0])
    splits = []
    for node in path.indices[path.indptr[0]:path.indptr[1]]:
        feature_index = int(model.tree_.feature[node])
        if feature_index >= 0:
            value = int(x[0, feature_index])
            splits.append({"node": int(node), "feature_index": feature_index,
                           "feature": feature_names[feature_index], "value": value,
                           "condition": f"{feature_names[feature_index]} = {value}"})
    return {"predicted": int(model.predict(x)[0]), "leaf": leaf_id,
            "confidence": float(model.predict_proba(x).max()), "splits": splits}


def plot_example(model, data, *, split= "val", index= 0):
    """Compare original 28x28 image, Boolean encoding, and selected tree path."""
    if split not in ("train", "val", "test"):
        raise ValueError("Invalid split")
    x = data[f"{split}_features"]
    if not 0 <= index < len(x):
        raise IndexError(f"Choose index from 0 to {len(x)-1}")
    names = [str(n) for n in data["feature_names"]]
    path = explain_tree_path(model, x[index], names)
    g = int(data["metadata"]["feature_spec"]["grid_size"])
    bits = x[index].reshape(g, g)
    mask = np.zeros_like(bits, dtype=bool)
    for split_info in path["splits"]:
        mask.flat[split_info["feature_index"]] = True
    fig, axes = plt.subplots(1, 3, figsize=(12, 4))
    axes[0].imshow(data[f"{split}_images"][index], cmap="gray", vmin=0, vmax=255)
    axes[0].set_title(f"Original digit: {int(data[f'{split}_digit_labels'][index])}")
    axes[1].imshow(bits, cmap="gray", vmin=0, vmax=1)
    axes[1].set_title(f"{g}×{g} Boolean encoding")
    axes[2].imshow(bits, cmap="gray", vmin=0, vmax=1)
    axes[2].set_title(f"Features tested on path ({int(mask.sum())})")
    for row, col in np.argwhere(mask):
        axes[2].add_patch(plt.Rectangle((col-.5, row-.5), 1, 1,
                                        fill=False, lw=2.0, edgecolor="orange"))
    for ax in axes:
        ax.axis("off")
    fig.suptitle(f"True binary class: {int(data[f'{split}_labels'][index])} | "
                 f"Predicted: {path['predicted']} | leaf: {path['leaf']}")
    fig.tight_layout()
    return fig, path


def plot_validation_errors(model, data, *, count: int = 10, seed: int = 10):
    x, y = data["val_features"], data["val_labels"]
    wrong = np.flatnonzero(model.predict(x) != y)
    if len(wrong) == 0:
        return None, np.array([], dtype=int)
    rng = np.random.default_rng(seed)
    selection = rng.choice(wrong, min(count, len(wrong)), replace=False)
    fig, axes = plt.subplots(1, len(selection), figsize=(2.1*len(selection), 2.7))
    for index, ax in zip(selection, np.atleast_1d(axes)):
        ax.imshow(data["val_images"][index], cmap="gray", vmin=0, vmax=255)
        ax.set_title(f"true={int(y[index])}, pred={int(model.predict(x[index:index+1])[0])}")
        ax.axis("off")
    fig.suptitle("Validation mistakes (not test cases)")
    fig.tight_layout()
    return fig, selection
