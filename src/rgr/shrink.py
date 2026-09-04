"""Darwiche-Hirth greedy shrink: a model -> a prime implicant of `node`"""
from .sdd_utils import is_implicant

def greedy_shrink(model, node, mgr, order=None):

    term = dict(model)
    # the loop goes through each variable, in order if given, otherwise just the model's own key order
    for v in (order or list(model.keys())):
        if v not in term:
            continue
        trial = {k: val for k, val in term.items() if k != v} # make a candidate term that's the current one minus this variable
        if is_implicant(trial, node, mgr): # check "does this shorter term still imply the classifier?" if yes keep the change
            term = trial
    return term

def disagreement(term, omega):
    # counts the literals in term whose value differs from ω's value for that variable
    # Used to check that the reason the pipeline finds actually achieves the minimum disagreement, and to compare reasons against each other
    return sum(1 for v, val in term.items() if omega[v] != val)
