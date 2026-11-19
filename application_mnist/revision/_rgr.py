from __future__ import annotations

import importlib
import sys
from pathlib import Path


def require_rgr():
    try:
        return importlib.import_module('rgr')
    except ModuleNotFoundError as exc:
        if exc.name not in ('rgr', 'pysdd'):
            raise
        root = Path(__file__).resolve().parents[2]
        source = root / 'src'
        if (source / 'rgr' / '__init__.py').exists() and str(source) not in sys.path:
            sys.path.insert(0, str(source))
        try:
            return importlib.import_module('rgr')
        except ModuleNotFoundError as retry:
            if retry.name == 'pysdd':
                raise ImportError('') from retry
            raise ImportError('')from retry
