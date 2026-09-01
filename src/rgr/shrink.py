"""Darwiche-Hirth greedy shrink: a model -> a prime implicant of `node`"""
from .sdd_utils import is_implicant

def greedy_shrink(model, node, mgr, order=None):
    term = dict(model)
    for v in (order or list(model.keys())):
        if v not in term:
            continue
        trial = {k: val for k, val in term.items() if k != v}
        if is_implicant(trial, node, mgr):
            term = trial
    return term

def disagreement(term, omega):
    return sum(1 for v, val in term.items() if omega[v] != val)
