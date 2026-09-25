"""Mandatory-core detection: literals ℓ such that T_μ\\{ℓ} ⊭ Δ."""
from __future__ import annotations
from typing import Callable, Iterable, Set


def find_mandatory_core(
    optional_candidates: Set[int],
    entails_residual: Callable[[Set[int]], bool],
) -> Set[int]:
    """Return C_μ ⊆ optional_candidates. |candidates| entailment checks."""
    core: Set[int] = set()
    full = set(optional_candidates)
    for lit in optional_candidates:
        if not entails_residual(full - {lit}):
            core.add(lit)
    return core