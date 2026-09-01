"""SDD construction and small wrappers shared across the engine."""
from pysdd.sdd import SddManager, Vtree

def build(nvars, var_order=None, vtree_type="right"):
    """Fresh manager + literal handles over nvars variables."""
    vt = Vtree(var_count=nvars,
               var_order=var_order or list(range(1, nvars + 1)),
               vtree_type=vtree_type)
    mgr = SddManager.from_vtree(vt)
    return mgr, [mgr.literal(i) for i in range(1, nvars + 1)]

def term_to_sdd(term, mgr):
    """dict {var: bool} -> conjunction SDD."""
    t = mgr.true()
    for v, val in term.items():
        t = t & (mgr.literal(v) if val else mgr.literal(-v))
    return t

def is_implicant(term, node, mgr):
    """Does `term` imply `node`?  (term & ~node unsatisfiable)."""
    return (term_to_sdd(term, mgr) & ~node).is_false()
