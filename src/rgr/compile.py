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
    """Compile a nested-dict decision tree to an SDD using manager `mgr`
    lits: dict {var_index: literal_sdd}"""
    if tree is True:
        return mgr.true()
    if tree is False:
        return mgr.false()
    x = lits[tree["feature"]]
    hi = decision_tree_to_sdd(tree["true"], mgr, lits)
    lo = decision_tree_to_sdd(tree["false"], mgr, lits)
    return (x & hi) | (~x & lo)

def compile_tree(tree, nvars, vtree_type="right"):
    """Convenience: build a manager and compile the tree. Returns (mgr, sdd)"""
    mgr, lit_list = build(nvars, vtree_type=vtree_type)
    lits = {i + 1: lit_list[i] for i in range(nvars)}
    return mgr, decision_tree_to_sdd(tree, mgr, lits)

def tree_predict(tree, assignment):
    """Evaluate the tree directly (ground truth for the compilation)"""
    if tree is True:
        return True
    if tree is False:
        return False
    branch = "true" if assignment[tree["feature"]] else "false"
    return tree_predict(tree[branch], assignment)
