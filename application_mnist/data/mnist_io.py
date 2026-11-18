"""Download and parse the official MNIST IDX files; no TensorFlow dependency."""
from __future__ import annotations

import gzip
import struct
import urllib.error
import urllib.request
from pathlib import Path

import numpy as np

MNIST_BASE_URL = "https://storage.googleapis.com/cvdf-datasets/mnist/"
FILES = {
    "train_images": "train-images-idx3-ubyte.gz",
    "train_labels": "train-labels-idx1-ubyte.gz",
    "test_images": "t10k-images-idx3-ubyte.gz",
    "test_labels": "t10k-labels-idx1-ubyte.gz",
}
EXPECTED_LENGTHS = {"train": 60_000, "test": 10_000}


def default_raw_dir():
    return Path(__file__).resolve().parent / "raw"


def download_mnist(destination= None):
    root = Path(destination) if destination is not None else default_raw_dir()
    root.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {}
    for key, filename in FILES.items():
        target = root / filename
        if not target.is_file() or target.stat().st_size == 0:
            temporary = target.with_name(target.name + ".part")
            try:
                print(f"Downloading {MNIST_BASE_URL}{filename} ...", flush=True)
                urllib.request.urlretrieve(MNIST_BASE_URL + filename, temporary)
                with gzip.open(temporary, "rb") as f:
                    f.read(16)
                temporary.replace(target)
            except (OSError, urllib.error.URLError, EOFError) as exc:
                temporary.unlink(missing_ok=True)
                raise RuntimeError(
                    f"Could not download {filename}"
                ) from exc
        paths[key] = target
    return paths


def read_idx_images(path):
    """Read IDX image matrix; returns uint8 (N, 28, 28)."""
    with gzip.open(path, "rb") as handle:
        header = handle.read(16)
        if len(header) != 16:
            raise ValueError(f"Truncated IDX image header: {path}")
        magic, n, height, width = struct.unpack(">IIII", header)
        if magic != 2051 or (height, width) != (28, 28):
            raise ValueError(f"Invalid MNIST image header in {path}: {(magic, n, height, width)}")
        data = handle.read()
    if len(data) != n * height * width:
        raise ValueError(f"Image data length mismatch in {path}")
    return np.frombuffer(data, dtype=np.uint8).reshape(n, height, width).copy()


def read_idx_labels(path):
    """Read IDX label vector; returns uint8 (N,)."""
    with gzip.open(path, "rb") as handle:
        header = handle.read(8)
        if len(header) != 8:
            raise ValueError(f"Truncated IDX label header: {path}")
        magic, n = struct.unpack(">II", header)
        if magic != 2049:
            raise ValueError(f"Invalid MNIST label header in {path}: {magic}")
        data = handle.read()
    if len(data) != n:
        raise ValueError(f"Label data length mismatch in {path}")
    labels = np.frombuffer(data, dtype=np.uint8).copy()
    if np.any(labels > 9):
        raise ValueError("A label outside 0..9 was encountered")
    return labels


def load_mnist(destination= None):
    """Load MNIST with original 60k train / 10k test split."""
    paths = download_mnist(destination)
    result = {
        "train_images": read_idx_images(paths["train_images"]),
        "train_labels": read_idx_labels(paths["train_labels"]),
        "test_images": read_idx_images(paths["test_images"]),
        "test_labels": read_idx_labels(paths["test_labels"]),
    }
    for split, expected in EXPECTED_LENGTHS.items():
        images, labels = result[f"{split}_images"], result[f"{split}_labels"]
        if len(images) != expected or len(labels) != expected:
            raise ValueError(f"Expected {expected} {split} samples, got {len(images)} images and {len(labels)} labels")
    return result
