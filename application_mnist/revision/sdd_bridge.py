from __future__ import annotations
from dataclasses import dataclass
from application_mnist.decision_tree.boolean_formula import BooleanDNF
from ._rgr import require_rgr


@dataclass
class SDDCompilation:
    manager: object
    root: object
    original_to_sdd: dict[int, int]
    sdd_to_original: dict[int, int]

    def assignment_for_sdd(self, original_values) -> dict[int, bool]:
        return {sdd: bool(original_values[old]) for old, sdd in self.original_to_sdd.items()}

    def term_from_sdd(self, term: list[int]) -> tuple[tuple[int, bool], ...]:
        return tuple(sorted((self.sdd_to_original[abs(literal)], literal > 0)
                            for literal in term))


def compile_dnf_to_sdd(dnf, *, compact= True):
    require_rgr()
    from rgr.sdd_utils import build, term_to_sdd

    indices = list(dnf.used_indices) if compact else list(range(len(dnf.feature_names)))
    mapping = {index: j + 1 for j, index in enumerate(indices)}
    manager, _ = build(max(1, len(indices)))
    root = manager.false()
    for term in dnf.terms:
        cube = {mapping[index]: bool(value) for index, value in term}
        root = root | term_to_sdd(cube, manager)
    return SDDCompilation(manager, root, mapping,
                          {v: k for k, v in mapping.items()})
