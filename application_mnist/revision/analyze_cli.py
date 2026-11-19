"""Headless sufficient-reason example. Run from repository root.

python -m application_mnist.revision.analyze_cli --output-dir application_mnist/decision_tree/outputs/3_vs_8_g7_t20_seed42 --index 0
"""
from __future__ import annotations
import argparse
from pathlib import Path
from .model_io import load_experiment, label_name
from .reasons import sufficient_reasons, term_text, min_disagreement_reasons


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument('--output-dir', type=Path, required=True)
    p.add_argument('--dataset', type=Path)
    p.add_argument('--split', choices=['train', 'val', 'test'], default='val')
    p.add_argument('--index', type=int, default=0)
    p.add_argument('--max-reasons', type=int, default=20)
    p.add_argument('--max-queries', type=int, default=500)
    p.add_argument('--min-disagreement', action='store_true')
    a = p.parse_args(argv)
    ex = load_experiment(a.output_dir, dataset_path=a.dataset)
    x = ex.data[f'{a.split}_features'][a.index]
    predicted = int(ex.bdd.evaluate(ex.root, x))
    gold = int(ex.data[f'{a.split}_labels'][a.index])
    print('Model prediction:', label_name(ex.data, predicted), '| Actual:', label_name(ex.data, gold))
    result = sufficient_reasons(ex.bdd, ex.root, x, max_reasons=a.max_reasons, max_queries=a.max_queries)
    print('Found', len(result.reasons), '| complete:', result.complete, '| queries:', result.queries)
    for i, reason in enumerate(result.reasons):
        print(f'{i+1:02d}:', term_text(reason, ex.feature_names))
    if a.min_disagreement and predicted != gold:
        cand = min_disagreement_reasons(ex.bdd, ex.root, x, desired_label=gold, max_reasons=a.max_reasons)
        print('Nearest model distance:', cand.nearest_distance, '| complete:', cand.complete)
        for i, reason in enumerate(cand.reasons):
            print(f'candidate {i+1:02d}:', term_text(reason, ex.feature_names))


if __name__ == '__main__':
    main()
