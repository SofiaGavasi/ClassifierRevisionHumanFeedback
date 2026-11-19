
from __future__ import annotations

import re
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from .reasons import Term

_PATTERN = re.compile(r'^ink_r(\d+)_c(\d+)$')


def plot_instance_reason(data, *, split, index, term= None, title= 'Sufficient reason',  show_boolean= True):
    if split not in ('train', 'val', 'test'):
        raise ValueError('')
    image = np.asarray(data[f'{split}_images'][index])
    vector = np.asarray(data[f'{split}_features'][index])
    names = tuple(map(str, data['feature_names']))
    grid = data['metadata']['feature_spec']['grid_size']
    if image.shape != (28, 28) or len(names) != grid * grid:
        raise ValueError('')
    ax_count = 2 if show_boolean else 1
    fig, axes = plt.subplots(1, ax_count, figsize=(9 if show_boolean else 5, 4.5))
    if ax_count == 1:
        axes = [axes]
    axes[0].imshow(image, cmap='gray', vmin=0, vmax=255)
    axes[0].set_title('Original MNIST image')
    if show_boolean:
        axes[1].imshow(vector.reshape(grid, grid), cmap='gray', vmin=0, vmax=1)
        axes[1].set_title('Boolean grid and reason')
    step = 28 / grid
    for feature, truth in (term or ()):
        match = _PATTERN.fullmatch(names[feature])
        if not match:
            raise ValueError(f'')
        row, col = map(int, match.groups())
        if bool(vector[feature]) != bool(truth):
            raise ValueError(f'')
        color = '#3182CE' if truth else '#ED8936'
        axes[0].add_patch(Rectangle((col*step-.5, row*step-.5), step, step, linewidth=2.5, edgecolor=color, fill=False))
        if show_boolean:
            axes[1].add_patch(Rectangle((col-.5, row-.5), 1, 1, linewidth=2.5, edgecolor=color, fill=False))
    for ax in axes:
        ax.set_xticks([]); ax.set_yticks([])
    fig.suptitle(title + '  |  Blue: ink required,  Orange: ink absent required', fontsize=10)
    fig.tight_layout()
    return fig


def plot_reasons_grid(data, *, split, index, reasons, max_show= 4):
    count = min(max_show, len(reasons))
    if count == 0:
        return None
    fig, axes = plt.subplots(1, count, figsize=(3.4 * count, 3.6), squeeze=False)
    image = data[f'{split}_images'][index]
    names = tuple(map(str, data['feature_names']))
    grid = data['metadata']['feature_spec']['grid_size']
    for i, reason in enumerate(reasons[:count]):
        ax = axes[0][i]
        ax.imshow(image, cmap='gray', vmin=0, vmax=255)
        for feature, truth in reason:
            match = _PATTERN.fullmatch(names[feature])
            if match:
                r, c = map(int, match.groups())
                step = 28 / grid
                ax.add_patch(Rectangle((c*step-.5, r*step-.5), step, step, linewidth=2.5, edgecolor=('#3182CE' if truth else '#ED8936'), fill=False))
        ax.set_title(f'Reason {i+1}  -  {len(reason)} literals')
        ax.axis('off')
    fig.tight_layout()
    return fig

