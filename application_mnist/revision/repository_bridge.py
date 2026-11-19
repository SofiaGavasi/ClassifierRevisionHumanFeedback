"""Optional notebook cell: call the already-integrated `rgr` backend explicitly.

The ordinary notebook calls sufficient_reasons directly, which now delegates
to the same rgr.reasons_from_model algorithm. This wrapper also accepts the old
`package.module:function` adapter protocol for other external oracles, and
verifies their output using the original repository's SDD entailment oracle.
"""
from __future__ import annotations

import importlib
from pathlib import Path
import numpy as np
from .robdd import ROBDD
from .reasons import Term, is_prime_implicant, sufficient_reasons


def external_reasons(entrypoint: str, *, formula_json: str | Path,
                     bdd: ROBDD, root: int, instance: np.ndarray,
                     max_reasons: int = 30) -> tuple[Term, ...]:
    x = np.asarray(instance, dtype=np.uint8)
    if entrypoint in ('rgr', 'rgr.reasons_from_model'):
        return sufficient_reasons(bdd, root, x, max_reasons=max_reasons).reasons

    if ':' not in entrypoint:
        raise ValueError('Expected "rgr" or package.module:function')
    module, function = entrypoint.rsplit(':', 1)
    api = getattr(importlib.import_module(module), function)
    label = int(bdd.evaluate(root, x))
    received = api(positive_formula_json=str(formula_json),
                   instance=x.astype(int).tolist(),
                   predicted_label=label, max_reasons=max_reasons)
    desired = root if label else bdd.negate(root)
    results = []
    for term in received:
        converted = tuple(sorted((int(i), bool(v)) for i, v in term))
        if any(bool(x[i]) != v for i, v in converted):
            raise ValueError('External backend returned a reason not contained in instance')
        if len({i for i, _ in converted}) != len(converted):
            raise ValueError('External backend returned duplicate variables')
        if not is_prime_implicant(bdd, desired, converted):
            raise ValueError('External backend returned a non-prime reason')
        results.append(converted)
    if len(results) > max_reasons or len(set(results)) != len(results):
        raise ValueError('External backend violated result cap or returned duplicates')
    return tuple(results)
