"""Task selection, reproducible subsampling, and leak-free train/val/test splits."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
from typing import Literal

import numpy as np

from .features import FeatureSpec, encode_boolean

TaskKind = Literal["parity", "digit", "pair"]


@dataclass(frozen=True)
class BinaryTask:
    kind: TaskKind
    positive_digit: int | None = None
    negative_digit: int | None = None
    positive_parity: Literal["odd", "even"] = "odd"
    digits: tuple[int, ...] | None = None

    def __post_init__(self):
        if self.kind not in ("parity", "digit", "pair"):
            raise ValueError(f"Unknown task: {self.kind}")
        for value in [self.positive_digit, self.negative_digit]:
            if value is not None and value not in range(10):
                raise ValueError("Digits must be 0..9")
        if self.digits is not None and (not self.digits or any(d not in range(10) for d in self.digits)):
            raise ValueError("The digit subset must contain values from 0..9")
        if self.kind == "parity":
            if self.positive_digit is not None or self.negative_digit is not None:
                raise ValueError("For parity, use positive_parity instead of explicit digits")
            if self.positive_parity not in ("even", "odd"):
                raise ValueError("positive_parity must be odd or even")
        elif self.kind == "digit":
            if self.positive_digit is None or self.negative_digit is not None:
                raise ValueError("Digit task requires positive_digit but not negative_digit")
            if self.digits is not None and (self.positive_digit not in self.digits or len(set(self.digits)) < 2):
                raise ValueError("For digit task, subset must contain target and at least one other digit")
        elif self.kind == "pair":
            if (self.positive_digit is None or self.negative_digit is None
                    or self.positive_digit == self.negative_digit):
                raise ValueError("Pair task requires two distinct digits")
            if self.digits is not None and set(self.digits) != {self.positive_digit, self.negative_digit}:
                raise ValueError("Pair task ignores subsets; omit digits or use exactly the two selected digits")

    @property
    def name(self):
        if self.kind == "parity":
            suffix = "_subset_" + "".join(str(d) for d in self.digits) if self.digits else ""
            return f"{self.positive_parity}_vs_other_parity{suffix}"
        if self.kind == "digit":
            suffix = "_subset_" + "".join(str(d) for d in self.digits) if self.digits else ""
            return f"is_{self.positive_digit}{suffix}"
        return f"{self.positive_digit}_vs_{self.negative_digit}"

    def select(self, images, original_labels):
        if len(images) != len(original_labels):
            raise ValueError("images and labels must have equal length")
        labels = np.asarray(original_labels, dtype=np.uint8)
        if self.kind == "pair":
            mask = np.isin(labels, [self.positive_digit, self.negative_digit])
            binary = (labels[mask] == self.positive_digit)
        elif self.kind == "digit":
            mask = np.ones(len(labels), dtype=bool) if self.digits is None else np.isin(labels, self.digits)
            binary = labels[mask] == self.positive_digit
        else:
            mask = np.ones(len(labels), dtype=bool) if self.digits is None else np.isin(labels, self.digits)
            parity = labels[mask] % 2 == 1
            binary = parity if self.positive_parity == "odd" else ~parity
        if len(binary) == 0 or len(np.unique(binary)) != 2:
            raise ValueError("Task selection must contain both positive and negative classes")
        return {
            "images": np.asarray(images)[mask],
            "labels": binary.astype(np.uint8),
            "digit_labels": labels[mask],
            "source_indices": np.flatnonzero(mask).astype(np.int32),
        }


def _stratified_limit(y, limit, *, rng, balance= False):
    """Select indices with deterministic seeded sampling, preserving or balancing classes."""
    y = np.asarray(y)
    classes, counts = np.unique(y, return_counts=True)
    if len(classes) != 2:
        raise ValueError("Expected both binary classes")
    if limit is not None and limit < 2:
        raise ValueError("Limit must be >=2 so both classes can be represented")
    if limit is None:
        if not balance:
            return np.arange(len(y))
        limit = 2 * int(min(counts))
    if not balance and limit >= len(y):
        return np.arange(len(y))
    limit = min(limit, len(y))
    if balance: # exact class balance
        per_class = min(limit // 2, int(counts.min()))
        allocation = [per_class, per_class]
    else:
        first = int(round(limit * counts[0] / len(y)))
        first = max(1, min(first, int(counts[0]), limit - 1))
        second = min(limit - first, int(counts[1]))
        first = min(limit - second, int(counts[0]))
        allocation = [first, second]
    choices = [rng.choice(np.flatnonzero(y == cls), size=int(n), replace=False)
               for cls, n in zip(classes, allocation)]
    selected = np.concatenate(choices)
    return np.sort(selected)


def _slice(dataset, idx):
    return {key: arr[idx] for key, arr in dataset.items()}


def _train_validation_indices(labels, fraction, seed):
    if not 0.0 < fraction < 0.5:
        raise ValueError("val_fraction must be strictly between 0 and 0.5")
    rng = np.random.default_rng(seed)
    train_parts, val_parts = [], []
    for cls in (0, 1):
        members = np.flatnonzero(labels == cls)
        if len(members) < 2:
            raise ValueError("Need at least two examples from each class for train/validation split")
        shuffled = rng.permutation(members)
        n_val = min(len(shuffled) - 1, max(1, round(len(shuffled) * fraction)))
        val_parts.append(shuffled[:n_val])
        train_parts.append(shuffled[n_val:])
    return np.sort(np.concatenate(train_parts)), np.sort(np.concatenate(val_parts))


def prepare_dataset(raw, *, task, features = FeatureSpec(), train_limit = 4000, test_limit= 1000, val_fraction= 0.20, seed= 10, balance= False):
    """Filter task, sample, and derive binary features with original images preserved.
    train_limit is the total pool from the original MNIST training split before carving
    out validation. Test is never part of feature selection or validation.
    """
    rng = np.random.default_rng(seed)
    train_pool = task.select(raw["train_images"], raw["train_labels"])
    test_pool = task.select(raw["test_images"], raw["test_labels"])
    idx_train = _stratified_limit(train_pool["labels"], train_limit, rng=rng, balance=balance)
    idx_test = _stratified_limit(test_pool["labels"], test_limit, rng=rng, balance=balance)
    pool = _slice(train_pool, idx_train)
    test = _slice(test_pool, idx_test)
    train_idx, val_idx = _train_validation_indices(pool["labels"], val_fraction, seed + 1)
    splits = {"train": _slice(pool, train_idx), "val": _slice(pool, val_idx), "test": test}
    metadata = {
        "source": "MNIST original IDX dataset via CVDF mirror",
        "task": asdict(task),
        "task_name": task.name,
        "feature_spec": asdict(features),
        "n_features": features.n_features,
        "seed": int(seed),
        "balance": bool(balance),
        "train_limit_before_validation": train_limit,
        "test_limit": test_limit,
        "val_fraction": val_fraction,
        "splits": {name: {"total": len(data["labels"]),
                          "positive": int(np.sum(data["labels"] == 1)),
                          "negative": int(np.sum(data["labels"] == 0))}
                   for name, data in splits.items()},
    }
    result: dict[str, np.ndarray | dict] = {"metadata": metadata, "feature_names": np.asarray(features.feature_names(), dtype=str)}
    for name, data in splits.items():
        for key, arr in data.items():
            result[f"{name}_{key}"] = arr
        result[f"{name}_features"] = encode_boolean(data["images"], features).astype(np.uint8)
    return result


def save_prepared(dataset, path):
    """Store a portable .npz file; metadata is JSON, never a pickle object."""
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    metadata = json.dumps(dataset["metadata"], sort_keys=True)
    arrays = {key: value for key, value in dataset.items() if key != "metadata"}
    arrays["metadata_json"] = np.asarray(metadata)
    with output.open("wb") as f:
        np.savez_compressed(f, **arrays)
    return output


def load_prepared(path):
    """Load train_features, val_features, test_features and matching metadata/images."""
    with np.load(path, allow_pickle=False) as payload:
        result = {key: payload[key] for key in payload.files if key != "metadata_json"}
        result["metadata"] = json.loads(str(payload["metadata_json"].item()))
    return result
