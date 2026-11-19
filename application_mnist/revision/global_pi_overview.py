
from __future__ import annotations

from dataclasses import dataclass
from itertools import product
from math import isfinite
from time import perf_counter
from typing import Iterator

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Patch, Rectangle

from .reasons import Term, term_text
from .model_io import label_name


@dataclass(frozen=True)
class GlobalPIResult:
    reasons: tuple[Term, ...]
    class_label: int
    complete: bool
    method: str
    models_examined: int
    n_sdd_variables: int
    message: str


def _mapped_to_term(bdd, reason):
    return tuple(sorted((bdd.sdd_to_original[int(i)], bool(val)) for i, val in reason.items()))


def _complete_sdd_models(node, nvars):
    for partial in node.models():
        partial = dict(partial)
        fixed = {}
        for key, val in partial.items():
            v = int(key)
            if not 1 <= v <= nvars:
                continue
            if val is not None:
                if val not in (0, 1, False, True):
                    raise ValueError(f'Unexpected PySDD model value {val!r} for {v}')
                fixed[v] = bool(val)
        free = [v for v in range(1, nvars + 1) if v not in fixed]
        for bits in product((False, True), repeat=len(free)):
            whole = dict(fixed)
            whole.update(zip(free, bits))
            yield whole


def enumerate_global_prime_implicants(
    bdd,
    root,
    *,
    class_label,
    method = 'auto',
    exact_nvars_limit = 9,
    max_models = 100,
    max_reasons = 500,
    max_seconds = 40.0,
    verbose= True,):
    if class_label not in (0, 1):
        raise ValueError('class_label must be 0 (negative) or 1 (positive)')
    if method not in ('auto', 'brute', 'models'):
        raise ValueError('method must be auto, brute, or models')
    if exact_nvars_limit < 0 or max_models < 1 or max_reasons < 1:
        raise ValueError('Caps must be positive and exact_nvars_limit nonnegative')
    if max_seconds <= 0 or not isfinite(max_seconds):
        raise ValueError('max_seconds must be a positive finite number')

    formula_handle = root if class_label else bdd.negate(root)
    node = bdd.node(formula_handle)
    nvars = int(bdd.n_sdd_variables)
    if method == 'auto':
        method = 'brute' if nvars <= exact_nvars_limit else 'models'
    if method == 'brute' and nvars > exact_nvars_limit:
        raise ValueError(
            f'Brute-force 3^{nvars} search disabled above {exact_nvars_limit} variables. '
            'Use method="models" with explicit caps, or raise exact_nvars_limit deliberately.'
        )

    found: set[Term] = set()
    examined = 0
    complete = True
    message = 'Complete: all global prime implicants recovered'

    if node.is_false():
        return GlobalPIResult((), class_label, True, method, 0, nvars, 'Class formula is unsatisfiable')
    if node.is_true():
        return GlobalPIResult(((),), class_label, True, method, 0, nvars,'T')

    if method == 'brute':
        from rgr.reasons import all_prime_implicants
        all_reasons = {_mapped_to_term(bdd, d)
                       for d in all_prime_implicants(node, nvars, bdd.manager)}
        ordered = tuple(sorted(all_reasons, key=lambda t: (len(t), t)))
        if len(ordered) > max_reasons:
            complete = False
            message = f'Partial: {max_reasons} of {len(ordered)} global PIs (reason cap)'
            ordered = ordered[:max_reasons]
        result = GlobalPIResult(ordered, class_label, complete, method, 0,
                                nvars, message)
    else:
        from rgr.reasons_from_model import ( EnumerationStats, reasons_from_model, PipelineTimeout, )
        from rgr.enumeration.hitting_sets import MHSSearchLimitExceeded

        deadline = perf_counter() + max_seconds
        seen_models = set()
        models = _complete_sdd_models(node, nvars)
        try:
            for mu in models:
                if perf_counter() >= deadline:
                    complete = False
                    message = 'Partial: elapsed-time limit reached'
                    break
                model_key = tuple(mu[i] for i in range(1, nvars + 1))
                if model_key in seen_models:
                    continue
                if examined >= max_models:
                    complete = False
                    message = f'Partial: SDD-model cap ({max_models}) reached'
                    break
                seen_models.add(model_key)
                examined += 1
                stats = EnumerationStats()
                generator = reasons_from_model( node, mu, mu, bdd.manager, nvars, ablation='full', stats=stats, deadline=deadline, )
                try:
                    for d in generator:
                        found.add(_mapped_to_term(bdd, d))
                        if len(found) >= max_reasons:
                            complete = False
                            message = f'Partial: global-reason cap ({max_reasons}) reached'
                            break
                finally:
                    generator.close()
                if not complete:
                    break
                if stats.truncated:
                    complete = False
                    message = f'Partial: rgr per-model search truncated: {stats.truncation_reason}'
                    break
        except (PipelineTimeout, MHSSearchLimitExceeded) as exc:
            complete = False
            message = f'Partial: rgr interrupted ({type(exc).__name__}: {exc})'
        result = GlobalPIResult(
            tuple(sorted(found, key=lambda t: (len(t), t))),
            class_label, complete, method, examined, nvars, message,
        )

    if verbose:
        print(f"{'PI(Delta)' if class_label else 'PI(not Delta)'}: "
              f'{len(result.reasons)} reasons; '
              f'method={result.method}; SDD variables={nvars}; '
              f'complete={result.complete}')
        print(result.message)
    return result


def prepare_global_pi_overview(
    data,
    bdd,
    root,
    *,
    split = 'train',
    class_label = 1,
    pi_result= None,
    **enumeration_options,
):
    if split not in ('train', 'val', 'test'):
        raise ValueError('split must be train, val, or test')
    if class_label not in (0, 1):
        raise ValueError('class_label must be 0 or 1')
    if pi_result is None:
        pi_result = enumerate_global_prime_implicants(bdd, root, class_label=class_label, **enumeration_options )
    elif pi_result.class_label != class_label:
        raise ValueError('pi_result class_label does not match requested class')

    X = np.asarray(data[f'{split}_features'])
    images = np.asarray(data[f'{split}_images'])
    names = tuple(map(str, data['feature_names']))
    grid = int(data['metadata']['feature_spec']['grid_size'])
    if X.ndim != 2 or X.shape[1] != len(names) or len(names) != grid**2:
        raise ValueError('Expected a full regular Boolean feature grid')
    if images.shape != (len(X), 28, 28):
        raise ValueError('Expected one 28x28 image per Boolean feature row')
    predicted = bdd.evaluate_batch(root, X)
    indices = np.flatnonzero(predicted == class_label)
    if len(indices) == 0:
        raise ValueError(f'No images predicted as class {class_label} in {split}')

    present = np.zeros((grid, grid), dtype=float)
    absent = np.zeros((grid, grid), dtype=float)
    for reason in pi_result.reasons:
        for feature_idx, polarity in reason:
            if not 0 <= feature_idx < len(names):
                raise ValueError('Reason index outside feature schema')
            expected = f'ink_r{feature_idx // grid}_c{feature_idx % grid}'
            if names[feature_idx] != expected:
                raise ValueError(f'Non-row-major grid feature {names[feature_idx]!r}')
            r, c = divmod(feature_idx, grid)
            (present if polarity else absent)[r, c] += 1
    denom = max(1, len(pi_result.reasons))
    return {
        'split': split,
        'class_label': class_label,
        'n_predicted_examples': len(indices),
        'avg_28': images[indices].mean(axis=0),
        'avg_grid': X[indices].mean(axis=0).reshape(grid, grid),
        'present_freq': present / denom,
        'absent_freq': absent / denom,
        'reasons': pi_result.reasons,
        'pi_result': pi_result,
        'grid': grid,
    }


def list_global_pi_reasons(summary, feature_names, *, top_k= 30):
    results = summary['pi_result']
    print(f"{'PI(Delta)' if results.class_label else 'PI(not Delta)'}: "
          f'{len(results.reasons)} distinct reasons - '
          f"{'COMPLETE' if results.complete else 'PARTIAL'}")
    if not results.complete:
        print('WARNING: enumeration truncated; missing global reasons are possible.')
    print(results.message)
    reasons = results.reasons
    if top_k is None:
        bound = len(reasons)
    elif top_k < 0:
        raise ValueError('top_k cannot be negative')
    else:
        bound = min(top_k, len(reasons))
    for index, reason in enumerate(reasons[:bound]):
        print(f'{index:3d} | len={len(reason):2d} | '
              f'{term_text(reason, feature_names, max_literals=None)}')
    if bound < len(reasons):
        print(f'... plus {len(reasons) - bound} more (top_k=None to list all)')
    return reasons


def _draw_literal_outlines(ax, grid, n_pixels, pos, neg,*, selected= None):
    step = n_pixels / grid
    if selected is not None:
        for idx, truth in selected:
            r, c = divmod(idx, grid)
            ax.add_patch(Rectangle((c * step - .5, r * step - .5), step, step,fill=False, linewidth=2.5,edgecolor='#3182CE' if truth else '#ED8936'))
        return
    strength = float(max(pos.max(), neg.max(), 1e-10))
    for r in range(grid):
        for c in range(grid):
            for truth, frequency in ((True, pos[r, c]), (False, neg[r, c])):
                if frequency <= 0:
                    continue
                scale = frequency / strength
                inset = step * (0 if truth else .13)
                ax.add_patch(Rectangle((c*step - .5 + inset, r*step - .5 + inset), step - 2*inset, step - 2*inset, fill=False, linewidth=.65+3*scale, alpha=.25+.75*scale,  edgecolor='#3182CE' if truth else '#ED8936'))


def plot_global_pi_overview(summary, data, *,reason_index= None,figsize= (10, 10)):
    grid = int(summary['grid'])
    label = label_name(data, summary['class_label'])
    selected = None
    if reason_index is not None:
        if not 0 <= reason_index < len(summary['reasons']):
            raise IndexError(f'Reason must be between 0 and {len(summary["reasons"])-1}')
        selected = summary['reasons'][reason_index]
    fig, axes = plt.subplots(2, 2, figsize=figsize)
    images = [(summary['avg_28'], 28, 255, '28x28'),
              (summary['avg_grid'], grid, 1, f'{grid}x{grid}')]
    for col, (img, resolution, vmax, title) in enumerate(images):
        ax = axes[0, col]
        ax.imshow(img, cmap='gray', vmin=0, vmax=vmax, interpolation='nearest')
        _draw_literal_outlines(ax, grid, resolution, summary['present_freq'], summary['absent_freq'])
        ax.set_title(f'Aggregate: {title} class mean')
        ax.axis('off')
        if selected is not None:
            ax = axes[1, col]
            ax.imshow(img, cmap='gray', vmin=0, vmax=vmax, interpolation='nearest')
            _draw_literal_outlines(ax, grid, resolution, summary['present_freq'], summary['absent_freq'], selected=selected)
            ax.set_title(f'Reason #{reason_index} ({len(selected)} literals): {title}')
            ax.axis('off')
    if selected is None:
        for ax, value, title, cmap in (
            (axes[1, 0], summary['present_freq'], 'Ink required across PIs', 'Blues'),
            (axes[1, 1], summary['absent_freq'], 'No ink required across PIs', 'Oranges'), ):
            im = ax.imshow(value, cmap=cmap, vmin=0, vmax=1, interpolation='nearest')
            ax.set_title(title)
            ax.set_xticks(range(grid)); ax.set_yticks(range(grid))
            fig.colorbar(im, ax=ax, fraction=.046, pad=.04)
    fig.legend(handles=[Patch(facecolor='none', edgecolor='#3182CE', label='Ink required'),
                        Patch(facecolor='none', edgecolor='#ED8936', label='No ink required')], loc='lower center', ncol=2)
    pi = summary['pi_result']
    completeness = 'ALL PIs' if pi.complete else 'PARTIAL PI LIST'
    fig.suptitle(
        f"Predicted {label} | {completeness} of "
        f"{'Δ' if summary['class_label'] else '¬Δ'} | "
        f"{len(pi.reasons)} distinct reasons | "
        f"{summary['n_predicted_examples']} class-average images",
        fontsize=11,
    )
    fig.tight_layout(rect=[0, .035, 1, .945])
    return fig



def plot_single_global_pi_reason(
    summary,
    data,
    reason_index,
    figsize=(10, 5),
):
    grid = int(summary["grid"])
    reasons = summary["reasons"]

    if not 0 <= reason_index < len(reasons):
        raise IndexError("Invalid reason index")

    selected = reasons[reason_index]
    label = label_name(data, summary["class_label"])

    fig, axes = plt.subplots(1, 2, figsize=figsize)

    images = [
        (summary["avg_28"], 28, 255, "Original 28×28"),
        (summary["avg_grid"], grid, 1, f"Boolean {grid}×{grid}"),
    ]

    for ax, (img, resolution, vmax, title) in zip(axes, images):
        ax.imshow(
            img,
            cmap="gray",
            vmin=0,
            vmax=vmax,
            interpolation="nearest",
        )

        _draw_literal_outlines(
            ax,
            grid,
            resolution,
            summary["present_freq"],
            summary["absent_freq"],
            selected=selected,
        )

        ax.set_title(title)
        ax.axis("off")

    fig.legend(
        handles=[
            Patch(facecolor="none", edgecolor="#3182CE",
                  label="Ink required"),
            Patch(facecolor="none", edgecolor="#ED8936",
                  label="No ink required"),
        ],
        loc="lower center",
        ncol=2,
    )

    fig.suptitle(
        f"Predicted {label} | Prime Implicant #{reason_index} "
        f"| {len(selected)} literals",
        fontsize=12,
    )

    fig.tight_layout(rect=[0, 0.06, 1, 0.92])

    return fig