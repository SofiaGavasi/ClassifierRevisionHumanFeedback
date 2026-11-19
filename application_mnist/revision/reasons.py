from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable
import time
import numpy as np

from .robdd import ROBDD

Literal = tuple[int, bool]
Term = tuple[Literal, ...]


@dataclass(frozen=True)
class ReasonResult:
    reasons: tuple[Term, ...]
    complete: bool
    queries: int
    predicted_label: int
    message: str = ''


@dataclass(frozen=True)
class CandidateResult:
    reasons: tuple[Term, ...]
    complete: bool
    nearest_distance: int | None
    nearest_models_seen: int
    message: str = ''


def _term_from_rgr(bdd, term):
    return tuple(sorted((bdd.sdd_to_original[int(v)], bool(value)) for v, value in term.items()))


def is_prime_implicant(bdd, desired, term):
    from rgr.sdd_utils import is_implicant
    mapped = bdd._mapped(term)
    node = bdd.node(desired)
    if not is_implicant(mapped, node, bdd.manager):
        return False
    return all(not is_implicant({v: value for v, value in mapped.items() if v != drop}, node, bdd.manager) for drop in mapped)


def _rgr_reasons_for_model(bdd, desired, mu, omega, *, max_reasons,max_queries):
    from rgr.reasons_from_model import (EnumerationStats, PipelineTimeout, reasons_from_model, )
    from rgr.enumeration.hitting_sets import MHSSearchLimitExceeded

    stats = EnumerationStats()
    deadline = time.perf_counter() + 30.0
    generator = reasons_from_model(
        bdd.node(desired), bdd._omega(mu), bdd._omega(omega),
        bdd.manager, bdd.n_sdd_variables,
        ablation='full', stats=stats, deadline=deadline,
    )
    found: list[Term] = []
    complete = True
    message = 'Complete'
    try:
        for term in generator:
            mapped = _term_from_rgr(bdd, term)
            if len(found) >= max_reasons:
                complete = False
                message = 'Reason limit reached; further reasons may exist'
                break
            if mapped not in found:
                found.append(mapped)
            if stats.entailment_checks >= max_queries:
                complete = False
                message = 'Query budget reached between reasons'
                break
        if stats.truncated:
            complete = False
            message = f'rgr reported truncation: {stats.truncation_reason}'
    except (PipelineTimeout, MHSSearchLimitExceeded) as exc:
        complete = False
        message = f'rgr search interrupted: {type(exc).__name__}: {exc}'
    finally:
        generator.close()
    return tuple(found), complete, stats.entailment_checks, message


def sufficient_reasons(bdd, root, instance,*, max_reasons = 30, max_queries = 1000):
    if max_reasons < 1 or max_queries < 1:
        raise ValueError('max_reasons and max_queries must be positive')
    x = np.asarray(instance, dtype=np.uint8)
    label = int(bdd.evaluate(root, x))
    desired = root if label == 1 else bdd.negate(root)
    reasons, complete, queries, message = _rgr_reasons_for_model(  bdd, desired, x, x, max_reasons=max_reasons, max_queries=max_queries, )
    return ReasonResult(reasons, complete, queries, label, message)


def min_disagreement_reasons(bdd, root, target, *, desired_label = 1, max_models= 48, max_reasons= 40, max_queries_per_model = 1000):
    if desired_label not in (0, 1):
        raise ValueError('desired_label must be 0 or 1')
    if max_models < 1 or max_reasons < 1 or max_queries_per_model < 1:
        raise ValueError('Limits must be positive')
    x = np.asarray(target, dtype=np.uint8)
    desired = root if desired_label == 1 else bdd.negate(root)
    distance = bdd.min_distance(desired, x)
    if distance is None:
        return CandidateResult((), True, None, 0, 'Desired class is logically impossible')
    if distance == 0:
        return CandidateResult((), True, 0, 0,' no revision necessary')
    models, models_truncated, reported_distance = bdd.nearest_models(desired, x, max_models=max_models,)
    if reported_distance != distance:
        raise AssertionError('rgr distance and nearest-model reconstruction disagree')
    output: set[Term] = set()
    complete = not models_truncated
    messages = []
    for mu in models:
        if len(output) >= max_reasons:
            complete = False
            messages.append('global reason limit reached')
            break
        reasons, done, _, why = _rgr_reasons_for_model(bdd, desired, mu, x, max_reasons=max_reasons - len(output), max_queries=max_queries_per_model, )
        complete = complete and done
        if not done:
            messages.append(why)
        for reason in reasons:
            disagreement = sum(bool(x[idx]) != value for idx, value in reason)
            if disagreement != distance:
                raise AssertionError('reason does not have expected disagreement with target')
            output.add(reason)
    if models_truncated:
        messages.insert(0, 'nearest-model limit reached')
    return CandidateResult( tuple(sorted(output, key=lambda t: (len(t), t))),
        complete, distance, len(models),'Complete' if complete else 'Truncated: ' + '; '.join(dict.fromkeys(messages)),)


def term_text(term, feature_names, max_literals= 20):
    names = tuple(feature_names)
    if not term:
        return 'T'
    selected = term if max_literals is None else term[:max_literals]
    text = ' ∧ '.join(('' if truth else '¬') + names[i] for i, truth in selected)
    if max_literals is not None and len(term) > max_literals:
        text += f' ... (+{len(term)-max_literals} more)'
    return text
