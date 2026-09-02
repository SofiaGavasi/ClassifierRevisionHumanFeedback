"""Compile structured inputs into SDDs.

A decision tree is represented as a nested dict:
    {"feature": v, "true": <subtree>, "false": <subtree>}   internal node
    True | False                                            leaf (accept/reject)

The function is the OR of accepting root-to-leaf paths. The recursive encoding
  leaf        -> true / false
  node on x   -> (x AND enc(true-child)) OR (NOT x AND enc(false-child))
yields a deterministic, decomposable circuit of size linear in the tree.
"""
from .sdd_utils import build

def decision_tree_to_sdd(tree, mgr, lits):
    """Compile a nested-dict decision tree to an SDD using manager `mgr`.
    lits: dict {var_index: literal_sdd}."""
    if tree is True:
        return mgr.true()
    if tree is False:
        return mgr.false()
    x = lits[tree["feature"]]
    hi = decision_tree_to_sdd(tree["true"], mgr, lits)
    lo = decision_tree_to_sdd(tree["false"], mgr, lits)
    return (x & hi) | (~x & lo)

def compile_tree(tree, nvars, vtree_type="right"):
    """Convenience: build a manager and compile the tree. Returns (mgr, sdd)."""
    mgr, lit_list = build(nvars, vtree_type=vtree_type)
    lits = {i + 1: lit_list[i] for i in range(nvars)}
    return mgr, decision_tree_to_sdd(tree, mgr, lits)

def tree_predict(tree, assignment):
    """Evaluate the tree directly (ground truth for the compilation)."""
    if tree is True:
        return True
    if tree is False:
        return False
    branch = "true" if assignment[tree["feature"]] else "false"
    return tree_predict(tree[branch], assignment)


def hidden_weighted_bit(n, mgr, lits):
    """Compile the Hidden Weighted Bit function HWB_n as an SDD.

    HWB_n(x_1..x_n) = x_k where k = (number of x_i set to 1); output is False if k=0.
    """
    from itertools import product
    f = mgr.false()
    for bits in product([0, 1], repeat=n):
        k = sum(bits)
        accept = (k > 0 and bits[k - 1] == 1)
        if accept:
            term = mgr.true()
            for i in range(n):
                term = term & (lits[i + 1] if bits[i] else ~lits[i + 1])
            f = f | term
    return f

def q_v(m, mgr, lits):
    """Compile the database-query lineage Q_V for parameter m as an SDD.

    Variables (1-based indices into `lits`):
        R_i   for i in 1..m       -> index i
        T_j   for j in 1..m       -> index m + j
        S_ij  for i,j in 1..m     -> index 2m + (i-1)*m + j
    total m*m + 2m variables.

        Q_V = OR over i,j of ( (R_i & S_ij) | (S_ij & T_j) | (R_i & T_j) )

    """
    def R(i): return lits[i]
    def T(j): return lits[m + j]
    def S(i, j): return lits[2 * m + (i - 1) * m + j]
    f = mgr.false()
    for i in range(1, m + 1):
        for j in range(1, m + 1):
            f = f | (R(i) & S(i, j)) | (S(i, j) & T(j)) | (R(i) & T(j))
    return f