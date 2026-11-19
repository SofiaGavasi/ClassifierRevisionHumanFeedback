from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import numpy as np

from application_mnist.decision_tree.boolean_formula import BooleanDNF
from application_mnist.data.pipeline import load_prepared
from .robdd import ROBDD


@dataclass
class Experiment:
    output_dir: Path
    dataset_path: Path
    data: dict[str, Any]
    bdd: ROBDD
    root: int
    positive_dnf: BooleanDNF
    negative_dnf: BooleanDNF | None
    feature_names: tuple[str, ...]


def read_formula(path):
    import json
    return BooleanDNF.from_dict(json.loads(Path(path).read_text(encoding='utf-8')))


def load_experiment(output_dir, *, dataset_path= None, max_nodes= 150_000, verify_negative = True):
    output = Path(output_dir).resolve()
    positive_file = output / 'positive_formula.json'
    if not positive_file.exists():
        raise FileNotFoundError(f'No positive formula at {positive_file}.')
    yes = read_formula(positive_file)
    no_file = output / 'negative_formula.json'
    no = read_formula(no_file) if no_file.exists() else None
    if dataset_path is None:
        candidate = output.parents[2] / 'data' / 'processed' / (output.name + '.npz')
        if not candidate.exists():
            candidate = Path(__file__).resolve().parents[1] / 'data' / 'processed' / (output.name + '.npz')
        dataset_path = candidate
    prepared = Path(dataset_path).resolve()
    if not prepared.exists():
        raise FileNotFoundError(f'Prepared dataset missing: {prepared}')
    data = load_prepared(prepared)
    names = tuple(map(str, data['feature_names']))
    if names != yes.feature_names:
        raise ValueError('Dataset feature names/order differ from exported positive formula')
    if no is not None and no.feature_names != names:
        raise ValueError('Negative formula feature schema mismatch')
    active = sorted(set(yes.used_indices) | (set(no.used_indices) if no is not None and verify_negative else set()))
    bdd = ROBDD(len(names), max_nodes=max_nodes, active_indices=active)
    root = bdd.dnf(yes.terms)
    if no is not None and verify_negative and bdd.apply('or', root, bdd.dnf(no.terms)) != 1:
        raise ValueError('Positive and negative exported formulas do not cover all assignments')
    if no is not None and verify_negative and bdd.apply('and', root, bdd.dnf(no.terms)) != 0:
        raise ValueError('Positive and negative exported formulas overlap')
    return Experiment(output, prepared, data, bdd, root, yes, no, names)


def label_name(data, label):
    task = data['metadata']['task']
    if task['kind'] == 'pair':
        return str(task['positive_digit'] if label else task['negative_digit'])
    if task['kind'] == 'digit':
        return f"{task['positive_digit']}" if label else f"not {task['positive_digit']}"
    parity = task.get('positive_parity', 'odd')
    return parity if label else ('even' if parity == 'odd' else 'odd')
