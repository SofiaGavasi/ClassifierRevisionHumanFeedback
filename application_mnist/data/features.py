from __future__ import annotations

from dataclasses import dataclass
import numpy as np


@dataclass(frozen=True)
class FeatureSpec:
    grid_size: int = 7
    threshold: float = 0.20

    def __post_init__(self):
        if self.grid_size < 1 or 28 % self.grid_size != 0:
            raise ValueError("grid_size must be a positive divisor of 28 (recommended: 4, 7, 14)")
        if not 0.0 <= self.threshold <= 1.0:
            raise ValueError("threshold must be between 0 and 1")

    @property
    def n_features(self):
        return self.grid_size**2

    def feature_names(self):
        return [f"ink_r{r}_c{c}" for r in range(self.grid_size) for c in range(self.grid_size)]

    def pixel_box(self, row, col):
        """Return (top, bottom_exclusive, left, right_exclusive) in the original image"""
        if not (0 <= row < self.grid_size and 0 <= col < self.grid_size):
            raise IndexError("Grid cell is out of range")
        step = 28 // self.grid_size
        return row * step, (row + 1) * step, col * step, (col + 1) * step


def block_intensity(images, grid_size= 7):
    """Blockwise mean intensity normalized to [0,1], shape (N, g, g)"""
    arr = np.asarray(images)
    if arr.ndim == 2:
        arr = arr[None, ...]
    if arr.ndim != 3 or arr.shape[1:] != (28, 28):
        raise ValueError("images must have shape (N,28,28) or (28,28)")
    if not np.issubdtype(arr.dtype, np.number):
        raise ValueError("Expected numeric pixel intensities in [0,255]")
    if grid_size < 1 or 28 % grid_size != 0:
        raise ValueError("grid_size must divide 28")
    block = 28 // grid_size
    return (arr.astype(np.float32).reshape(-1, grid_size, block, grid_size, block).mean(axis=(2, 4)) / 255.0)


def encode_boolean(images, spec= FeatureSpec()):
    """Each Boolean feature says whether its block's mean ink > threshold.

    For one image returns (1, n_features); for N images returns (N, n_features).
    Feature i represents the same spatial block across all images and tasks.
    """
    blocks = block_intensity(images, spec.grid_size)
    return (blocks > spec.threshold).reshape(-1, spec.n_features)
