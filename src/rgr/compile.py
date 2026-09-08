"""
Compile structured inputs into SDDs.

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

    # base cases if leaf:
    if tree is True:
        return mgr.true()
    if tree is False:
        return mgr.false()
    
    x = lits[tree["feature"]] # two-step lookup: first find which feature this node tests (tree["feature"] -> 2), then fetch that feature's SDD literal (lits[2])

    hi = decision_tree_to_sdd(tree["true"], mgr, lits) # ecursively compiles the "if feature is true" subtree
    lo = decision_tree_to_sdd(tree["false"], mgr, lits) # ecursively compiles the "if feature is false" subtree

    return (x & hi) | (~x & lo) #"either (the feature is true AND whatever the true-branch decides) OR (the feature is false AND whatever the false-branch decides)"

 
def tree_var_order(tree):
    """Variable order induced by the tree's own structure: features in the order
    they are first tested in a root-first (pre-order) traversal."""
    order, seen = [], set()
    def walk(t):
        if t is True or t is False:
            return
        f = t["feature"]
        if f not in seen:
            seen.add(f)
            order.append(f)
        walk(t["true"])
        walk(t["false"])
    walk(tree)
    return order
 
def compile_tree(tree, nvars, vtree_type=None, var_order=None):
    """Convenience: build a manager and compile the tree. Returns (mgr, sdd).
 
    By default (vtree_type=None) the tree-INDUCED variable order is used with a
    right-linear vtree, which realises the linear-size compilation guarantee.
    Pass vtree_type explicitly (e.g. "right", "balanced") to override with a
    generic vtree over the natural order 1..nvars, or pass var_order directly."""
    if var_order is None and vtree_type is None:
        var_order = tree_var_order(tree)
        # append any features not tested in the tree so var_order is a full permutation
        for v in range(1, nvars + 1):
            if v not in var_order:
                var_order.append(v)
        vtree_type = "right"
    elif vtree_type is None:
        vtree_type = "right"
    mgr, lit_list = build(nvars, var_order=var_order, vtree_type=vtree_type)
    # build() returns literals indexed by position; map var index -> its literal
    lits = {i + 1: mgr.literal(i + 1) for i in range(nvars)}
    return mgr, decision_tree_to_sdd(tree, mgr, lits)
 
def tree_predict(tree, assignment):
    """Evaluate the tree directly (ground truth for the compilation)."""
    #base case leaf
    if tree is True:
        return True
    if tree is False:
        return False
    
    branch = "true" if assignment[tree["feature"]] else "false" # goes either down the "true" or "false" branch depending on whether the feature is set to True or False in the assignment

    return tree_predict(tree[branch], assignment) # recurses until it hits an accept/reject leaf
 

def hidden_weighted_bit(n, mgr, lits):
    """Compile the Hidden Weighted Bit function HWB_n as an SDD."""

    from itertools import product

    f = mgr.false() # we start from not accepting any inputs
    for bits in product([0, 1], repeat=n): # repeat n times, so we get all 2^n possible combinations of bits
        k = sum(bits)
        accept = (k > 0 and bits[k - 1] == 1) # we accept if kth bit is 1 (true)
        if accept:
            term = mgr.true()
            for i in range(n):
                term = term & (lits[i + 1] if bits[i] else ~lits[i + 1]) #turns a bit-tuple into its term by ANDing one literal per variable
            f = f | term # adding this as an accepted term
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
    # helpers for indexing into the lits list
    def R(i): return lits[i]
    def T(j): return lits[m + j]
    def S(i, j): return lits[2 * m + (i - 1) * m + j]

    f = mgr.false() # starting from false
    for i in range(1, m + 1): # we loop through every pair (i,j)
        for j in range(1, m + 1):
            f = f | (R(i) & S(i, j)) | (S(i, j) & T(j)) | (R(i) & T(j)) # adding this as an accepted term
    return f