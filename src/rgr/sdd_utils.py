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
    #So for example {1: True, 2: False} comes out as the SDD representing x1 ∧ ¬x2
    t = mgr.true()
    for v, val in term.items():  #the loop goes through each variable in the dictionary
        t = t & (mgr.literal(v) if val else mgr.literal(-v)) #picks the right one depending on whether the dictionary said True or False. mgr.literal(v) is the SDD for "variable v is true"
    return t

def is_implicant(term, node, mgr):
    """Does `term` imply `node`?  (term & ~node unsatisfiable)."""
    #"A implies B" is the same as "A AND (not B) is impossible"
    # used by greedy shrink, "can I drop this literal and still have a valid reason?"
    return (term_to_sdd(term, mgr) & ~node).is_false()
