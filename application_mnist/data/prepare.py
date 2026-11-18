"""CLI: python -m application_mnist.data.prepare --help"""
from __future__ import annotations

import argparse
from pathlib import Path

from .features import FeatureSpec
from .mnist_io import default_raw_dir, load_mnist
from .pipeline import BinaryTask, prepare_dataset, save_prepared


def build_parser():
    parser = argparse.ArgumentParser(description="Build a binary MNIST task with Boolean features")
    parser.add_argument("--task", required=True, choices=["parity", "digit", "pair"])
    parser.add_argument("--positive-digit", type=int, help="Target digit for digit/pair task")
    parser.add_argument("--negative-digit", type=int, help="Other digit for pair task")
    parser.add_argument("--positive-parity", choices=["odd", "even"], default="odd")
    parser.add_argument("--digits", help="Optional comma-separated digit subset (parity or digit task)")
    parser.add_argument("--grid-size", type=int, default=7, help="Divisor of 28 (e.g. 4,7,14)")
    parser.add_argument("--threshold", type=float, default=0.20,
                        help="Boolean feature true when average region ink / 255 exceeds this value")
    parser.add_argument("--train-limit", type=int, default=4000,
                        help="Max original training examples BEFORE validation split; use 0 for all")
    parser.add_argument("--test-limit", type=int, default=1000,
                        help="Max original test examples; use 0 for all")
    parser.add_argument("--val-fraction", type=float, default=0.20)
    parser.add_argument("--seed", type=int, default=10)
    parser.add_argument("--balance", action="store_true",
                        help="Sample equal numbers from both classes; changes class prevalence")
    parser.add_argument("--raw-dir", type=Path, default=default_raw_dir())
    parser.add_argument("--output", type=Path, help="Custom path to output .npz")
    return parser


def main(argv = None):
    args = build_parser().parse_args(argv)
    digits = tuple(int(s) for s in args.digits.split(",")) if args.digits else None
    task = BinaryTask(kind=args.task, positive_digit=args.positive_digit,
                      negative_digit=args.negative_digit,
                      positive_parity=args.positive_parity, digits=digits)
    spec = FeatureSpec(grid_size=args.grid_size, threshold=args.threshold)
    raw = load_mnist(args.raw_dir)
    prepared = prepare_dataset(raw, task=task, features=spec,
                               train_limit=None if args.train_limit == 0 else args.train_limit,
                               test_limit=None if args.test_limit == 0 else args.test_limit,
                               val_fraction=args.val_fraction, seed=args.seed, balance=args.balance)
    tag = f"{task.name}_g{spec.grid_size}_t{int(round(spec.threshold*100)):02d}_seed{args.seed}"
    default_output = Path(__file__).resolve().parent / "processed" / f"{tag}.npz"
    path = save_prepared(prepared, args.output or default_output)
    print(f"Saved: {path}")
    for name, info in prepared["metadata"]["splits"].items():
        print(f"  {name:5} {info['total']:6} examples | positive={info['positive']:5}, negative={info['negative']:5}")
    print(f"Boolean features: {spec.n_features}; task: {task.name}")


if __name__ == "__main__":
    main()
