"""Exact conversion of a learned 0/1 decision tree to a Boolean DNF.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
from typing import Iterable

import numpy as np
from sklearn.tree import DecisionTreeClassifier

Literal = tuple[int, bool]  # (feature_index, value required)
Term = tuple[Literal, ...]   # conjunction


def _clean_terms(terms):
    """Deduplicate, discard contradictory terms, and perform DNF absorption.
    Absorption removes a term that contains another term as a strict subset;
    it does NOT calculate all prime implicants or minimize the full DNF.
    """
    valid = set()
    for term in terms:
        assignments: dict[int, bool] = {}
        contradiction = False
        for i, v in term:
            if i in assignments and assignments[i] != v:
                contradiction = True
                break
            assignments[i] = bool(v)
        if not contradiction:
            valid.add(tuple(sorted(assignments.items())))
    ordered = sorted(valid, key=lambda t: (len(t), t))
    kept: list[Term] = []
    for term in ordered:
        s = set(term)
        if not any(set(existing).issubset(s) for existing in kept):
            kept.append(term)
    return tuple(kept)


@dataclass(frozen=True)
class BooleanDNF:
    feature_names: tuple[str, ...]
    terms: tuple[Term, ...]

    def __post_init__(self):
        n = len(self.feature_names)
        for term in self.terms:
            for i, _ in term:
                if not (0 <= i < n):
                    raise ValueError(f"Feature index {i} outside schema")

    @property
    def used_indices(self):
        return tuple(sorted({idx for term in self.terms for idx, _ in term}))

    @property
    def used_feature_names(self):
        return tuple(self.feature_names[i] for i in self.used_indices)

    def evaluate(self, X):
        """Evaluate exact DNF on full-length Boolean feature arrays."""
        arr = np.asarray(X)
        if arr.ndim == 1:
            arr = arr[None, :]
        if arr.ndim != 2 or arr.shape[1] != len(self.feature_names):
            raise ValueError(f"Expected (n, {len(self.feature_names)}) feature array")
        if not np.all((arr == 0) | (arr == 1)):
            raise ValueError("Features must be Boolean")
        result = np.zeros(arr.shape[0], dtype=bool)
        for term in self.terms:
            matching = np.ones(arr.shape[0], dtype=bool)
            for idx, value in term:
                matching &= (arr[:, idx] == value)
            result |= matching
        return result.astype(np.uint8)

    def text(self, *, max_terms= 25, unicode= True):
        if not self.terms:
            return "⊥" if unicode else "FALSE"
        if any(not t for t in self.terms):
            return "⊤" if unicode else "TRUE"
        join_and = " ∧ " if unicode else " & "
        join_or = " ∨ " if unicode else " | "
        neg = "¬" if unicode else "~"
        shown = self.terms if max_terms is None else self.terms[:max_terms]
        rendered = []
        for term in shown:
            lit = join_and.join(("" if value else neg) + self.feature_names[idx]
                               for idx, value in term)
            rendered.append(f"({lit})")
        s = join_or.join(rendered)
        if max_terms is not None and len(self.terms) > max_terms:
            s += f" ... [{len(self.terms) - max_terms} more terms]"
        return s

    def to_dict(self):
        return {
            "schema_version": 1,
            "representation": "dnf",
            "semantics": "disjunction of conjunctions; literal value true means ink is ON",
            "feature_names": list(self.feature_names),
            "used_feature_indices": list(self.used_indices),
            "terms": [
                [{"index": i, "name": self.feature_names[i], "value": bool(v)}
                 for i, v in term]
                for term in self.terms
            ],
            "warning": "Leaf-path terms are not necessarily prime implicants / sufficient reasons."
        }

    def save_json(self, path):
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(self.to_dict(), indent=2) + "\n", encoding="utf-8")
        return p

    @classmethod
    def from_dict(cls, payload):
        names = tuple(payload["feature_names"])
        terms = tuple(tuple((int(literal["index"]), bool(literal["value"]))
                            for literal in term) for term in payload["terms"])
        return cls(names, _clean_terms(terms))


def tree_to_dnf(
    model, feature_names, *, positive_class= 1):
    """Convert the learned *prediction function* to an exact DNF.
    Supported only for 0/1 inputs, with splits strictly between 0 and 1,
    including the normal scikit-learn threshold 0.5.
    This does not extract prime implicants.
    """
    names = tuple(str(name) for name in feature_names)
    if model.n_features_in_ != len(names):
        raise ValueError("The model and feature schema have different dimensions")
    if not set(model.classes_).issubset({0, 1}) or len(model.classes_) != 2:
        raise ValueError("Expected a fitted binary model with labels 0 and 1")
    tree = model.tree_
    for node_id, feat in enumerate(tree.feature):
        if feat >= 0 and not (0 < tree.threshold[node_id] < 1):
            raise ValueError("Tree contains a split incompatible with Boolean inputs")
    terms = []

    def walk(node, path):
        feat = int(tree.feature[node])
        if feat < 0:  # leaf
            class_index = int(np.argmax(tree.value[node].reshape(-1)))
            label = int(model.classes_[class_index])
            if label == positive_class:
                terms.append(path)
            return
        walk(int(tree.children_left[node]), path + ((feat, False),))
        walk(int(tree.children_right[node]), path + ((feat, True),))

    walk(0, ())
    return BooleanDNF(names, _clean_terms(terms))


def assert_equivalent(model, dnf, features):
    actual = model.predict(features).astype(np.uint8)
    derived = dnf.evaluate(features)
    if not np.array_equal(actual, derived):
        mismatch = np.flatnonzero(actual != derived)
        raise AssertionError(f"DNF does not match the tree at {len(mismatch)} rows")


def export_formulas(model, names, output_dir):
    """Save exact positive and negative prediction formulas (not prime form)."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    positive = tree_to_dnf(model, names, positive_class=1)
    negative = tree_to_dnf(model, names, positive_class=0)
    paths = {
        "positive_json": positive.save_json(out / "positive_formula.json"),
        "negative_json": negative.save_json(out / "negative_formula.json"),
        "positive_text": out / "positive_formula.txt",
        "negative_text": out / "negative_formula.txt",
    }
    paths["positive_text"].write_text(positive.text(max_terms=None) + "\n", encoding="utf-8")
    paths["negative_text"].write_text(negative.text(max_terms=None) + "\n", encoding="utf-8")
    return paths
