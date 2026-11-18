"""Train binary decision trees on prepared MNIST features without test leakage.

The original data preparation is reused from application_mnist.data.pipeline.
Hyperparameter selection uses *only* the validation split, not test labels.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from itertools import product
from pathlib import Path
import csv
import json

import numpy as np
from sklearn.metrics import (accuracy_score, balanced_accuracy_score,
                             confusion_matrix, f1_score, precision_score,
                             recall_score)
from sklearn.tree import DecisionTreeClassifier

from application_mnist.data.pipeline import load_prepared


@dataclass(frozen=True)
class TreeSettings:
    max_depth: int | None = 5
    min_samples_leaf: int = 5
    ccp_alpha: float = 0.0
    criterion: str = "gini"
    seed: int = 10

    def __post_init__(self):
        if self.max_depth is not None and self.max_depth < 1:
            raise ValueError("max_depth must be positive or None")
        if self.min_samples_leaf < 1:
            raise ValueError("min_samples_leaf must be >= 1")
        if self.ccp_alpha < 0:
            raise ValueError("ccp_alpha must be nonnegative")
        if self.criterion not in ("gini", "entropy"):
            raise ValueError("criterion must be 'gini' or 'entropy'")


def validate_prepared(data):
    """Ensure we train on the same 0/1 feature schema produced in stage 1."""
    names = data["feature_names"]
    if len(names) != len(set(map(str, names))):
        raise ValueError("Feature names must be unique")
    for split in ("train", "val", "test"):
        x, y = np.asarray(data[f"{split}_features"]), np.asarray(data[f"{split}_labels"])
        if x.ndim != 2 or x.shape[1] != len(names) or y.shape != (len(x),):
            raise ValueError(f"Invalid {split} shape or feature-name count")
        if not len(x):
            raise ValueError(f"{split} is empty")
        if not np.all((x == 0) | (x == 1)) or not np.all((y == 0) | (y == 1)):
            raise ValueError("Only Boolean features and binary labels (0/1) are allowed")
    if len(np.unique(data["train_labels"])) != 2:
        raise ValueError("Training data must contain both classes")


def fit_tree(data, settings = TreeSettings()):
    validate_prepared(data)
    model = DecisionTreeClassifier(
        criterion=settings.criterion,
        max_depth=settings.max_depth,
        min_samples_leaf=settings.min_samples_leaf,
        ccp_alpha=settings.ccp_alpha,
        random_state=settings.seed,
    )
    model.fit(data["train_features"], data["train_labels"])
    return model


def split_metrics(model, data, split = "val"):
    if split not in ("train", "val", "test"):
        raise ValueError("Split must be train, val, or test")
    x, y = data[f"{split}_features"], data[f"{split}_labels"]
    yp = model.predict(x)
    return {
        "split": split,
        "n": len(y),
        "accuracy": float(accuracy_score(y, yp)),
        "balanced_accuracy": float(balanced_accuracy_score(y, yp)),
        "precision_pos": float(precision_score(y, yp, pos_label=1, zero_division=0)),
        "recall_pos": float(recall_score(y, yp, pos_label=1, zero_division=0)),
        "f1_pos": float(f1_score(y, yp, pos_label=1, zero_division=0)),
        "confusion_matrix": confusion_matrix(y, yp, labels=[0, 1]).tolist(),
        "depth": int(model.get_depth()),
        "leaves": int(model.get_n_leaves()),
        "nodes": int(model.tree_.node_count),
        "used_variables": int(len(np.unique(model.tree_.feature[model.tree_.feature >= 0]))),
    }


def tune_trees(
    data,
    *,
    depths = (2, 3, 4, 5, 6, 8, None),
    min_leaf_sizes = (1, 5, 10, 20),
    ccp_alphas = (0.0,),
    criterion = "gini",
    seed= 10):
    """Select best validation balanced accuracy, breaking ties by smaller tree.
    Never consult test labels; a fresh model is fit on the training split only.
    """
    validate_prepared(data)
    candidates = []
    for depth, leaf, alpha in product(depths, min_leaf_sizes, ccp_alphas):
        config = TreeSettings(depth, leaf, alpha, criterion, seed)
        model = fit_tree(data, config)
        val = split_metrics(model, data, "val")
        row = {
            "max_depth": depth, "min_samples_leaf": leaf,
            "ccp_alpha": alpha, "criterion": criterion,
            "seed": seed, **{key: val[key] for key in
                           ("accuracy", "balanced_accuracy", "precision_pos", "recall_pos",
                            "f1_pos", "depth", "leaves", "nodes", "used_variables")}
        }
        candidates.append((model, config, row))
    if not candidates:
        raise ValueError("Provide at least one candidate configuration")
    # Deterministic preference: validation score, smaller tree, fewer variables,
    # shallower tree, then stable first-in-grid order.
    best = max(candidates, key=lambda entry: (
        entry[2]["balanced_accuracy"], -entry[2]["leaves"],
        -entry[2]["used_variables"], -entry[2]["depth"]
    ))
    rows = [entry[2] for entry in candidates]
    return best[0], best[1], rows


def save_tuning_table(rows, path) :
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if rows:
        with path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)
    return path


def save_model_bundle(
    model,
    settings,
    data,
    out_dir,
    *,
    test_results = None):
    """Persist a local sklearn model and readable metadata; local trusted files only.
    Pickled joblib models are not secure for loading from untrusted sources.
    For transferring the classifier to the revision step, use the JSON formula
    from decision_tree.boolean_formula instead of depending on joblib.
    """
    import joblib
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    model_path = out / "decision_tree.joblib"
    joblib.dump(model, model_path)
    summary = {
        "settings": asdict(settings),
        "task": data["metadata"].get("task_name", "unknown"),
        "encoding": data["metadata"].get("feature_spec", {}),
        "feature_names": [str(x) for x in data["feature_names"]],
        "train_metrics": split_metrics(model, data, "train"),
        "validation_metrics": split_metrics(model, data, "val"),
        "test_metrics": test_results,
    }
    metadata_path = out / "model_info.json"
    metadata_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return {"model": model_path, "metadata": metadata_path}
