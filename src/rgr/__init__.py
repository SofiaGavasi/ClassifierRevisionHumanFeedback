"""rgr: reason-guided revision engine.

Core pipeline:
    from rgr.edit import edit

Files:
    rgr.distance      - bottom-up nearest-instance distance (weighted-capable)
    rgr.reconstruct   - nearest instance via backpointers
    rgr.shrink        - greedy shrink
    rgr.alternatives  - bounded menu of alternatives
    rgr.reasons       - prime-implicant enumeration (ground truth), weakening helpers
    rgr.compile       - decision tree -> SDD
    rgr.compare       - set-min vs cardinality 
    rgr.display       - human-readable term/instance/SDD display
    rgr.sdd_utils     - SDD construction and small wrappers
"""
from .edit import edit
from .distance import node_dist, INF
from .reconstruct import nearest_model
from .shrink import greedy_shrink, disagreement
from .alternatives import alternatives
from .sdd_utils import build, term_to_sdd, is_implicant

__all__ = [
    "edit", "node_dist", "INF", "nearest_model", "greedy_shrink",
    "disagreement", "alternatives", "build", "term_to_sdd", "is_implicant",
]
