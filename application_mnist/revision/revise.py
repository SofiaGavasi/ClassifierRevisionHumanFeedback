
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import numpy as np

from .robdd import ROBDD
from .reasons import Term, is_prime_implicant


@dataclass(frozen=True)
class RevisionOutcome:
    old_root: int
    new_root: int
    target_label_before: int
    target_label_after: int
    desired_label: int
    original_reason: Term
    weakened_reason: Term
    removed_literals: Term
    preserved_old_target_class: bool


def apply_minimal_weakening(bdd: ROBDD, original_root, target, source, *, desired_label, require_minimum_disagreement = None):
    from rgr.reasons import weaken
    from rgr.sdd_utils import term_to_sdd

    if desired_label not in (0, 1):
        raise ValueError('desired_label must be 0 or 1')
    x = np.asarray(target, dtype=np.uint8)
    previous = int(bdd.evaluate(original_root, x))
    if previous == desired_label:
        raise ValueError('Target already has desired label (vacuity: no edit)')
    desired = original_root if desired_label == 1 else bdd.negate(original_root)
    if not is_prime_implicant(bdd, desired, source):
        raise ValueError('Selected source is not a prime implicant of desired class')
    dis = tuple((i, value) for i, value in source if bool(x[i]) != bool(value))
    if require_minimum_disagreement is not None and len(dis) != require_minimum_disagreement:
        raise ValueError('Selected reason does not have required minimum disagreement')
    if not dis:
        raise ValueError('Selected source already applies to target')

    original_term = bdd._mapped(source)
    rewritten_term = weaken(original_term, bdd._omega(x)) 
    weakened = tuple(sorted((bdd.sdd_to_original[v], value) for v, value in rewritten_term.items()))
    target_class_sdd = bdd.node(desired)
    revised_desired = target_class_sdd | term_to_sdd(rewritten_term, bdd.manager)
    new_sdd = revised_desired if desired_label == 1 else ~revised_desired
    new_root = bdd._store(new_sdd)
    after = int(bdd.evaluate(new_root, x))
    if after != desired_label:
        raise AssertionError('SDD revision did not change the target classification')
    preserved = (target_class_sdd & ~revised_desired).is_false()
    if not preserved:
        raise AssertionError('Revision failed to preserve the desired-class region')
    return RevisionOutcome(original_root, new_root, previous, after, desired_label, tuple(source), weakened, dis, True)


def compare_predictions(bdd, original_root, revised_root, X, y= None) :
    old = bdd.evaluate_batch(original_root, X)
    new = bdd.evaluate_batch(revised_root, X)
    result = {
        'n': int(len(old)),
        'changed': int(np.sum(old != new)),
        'changed_fraction': float(np.mean(old != new)) if len(old) else 0.0,
        'negative_to_positive': int(np.sum((old == 0) & (new == 1))),
        'positive_to_negative': int(np.sum((old == 1) & (new == 0))),
    }
    if y is not None:
        labels = np.asarray(y, dtype=np.uint8)
        result.update({
            'accuracy_before': float(np.mean(old == labels)),
            'accuracy_after': float(np.mean(new == labels)),
            'corrected_errors': int(np.sum((old != labels) & (new == labels))),
            'new_errors': int(np.sum((old == labels) & (new != labels))),
        })
    return result


def export_revision(bdd, outcome, path, feature_names):
    file = Path(path)
    file.parent.mkdir(parents=True, exist_ok=True)
    if outcome.old_root not in bdd._source_dnfs:
        raise ValueError('')
    payload = {
        'feature_names': list(map(str, feature_names)),
        'original_positive_dnf_terms': bdd._source_dnfs[outcome.old_root],
        'active_feature_indices': list(bdd.active_indices),
        'desired_label': outcome.desired_label,
        'source_reason': [[int(i), bool(v)] for i, v in outcome.original_reason],
        'weakened_reason': [[int(i), bool(v)] for i, v in outcome.weakened_reason],
        'removed_literals': [[int(i), bool(v)] for i, v in outcome.removed_literals],
    }
    file.write_text(json.dumps(payload, indent=2) + '\n', encoding='utf-8')
    return file


def load_revision(path):
    payload = json.loads(Path(path).read_text(encoding='utf-8'))
    bdd = ROBDD(len(payload['feature_names']), active_indices=payload['active_feature_indices'])
    original = bdd.dnf(payload['original_positive_dnf_terms'])
    weakened = tuple((int(i), bool(v)) for i, v in payload['weakened_reason'])
    desired_label = int(payload['desired_label'])
    if desired_label == 1:
        revised = bdd.apply('or', original, bdd.cube(weakened))
    elif desired_label == 0:
        revised = bdd.negate(bdd.apply('or', bdd.negate(original), bdd.cube(weakened)))
    else:
        raise ValueError('Invalid desired_label in saved revision')
    return bdd, revised, payload
