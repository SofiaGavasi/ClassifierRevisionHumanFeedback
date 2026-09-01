"""Load example classifiers from the JSON dataset and rebuild them as SDDs.

Usage:
    from rgr.dataset import load_examples, build_example
    exs = load_examples()               # list of dicts
    mgr, sdd, ex = build_example(exs[0])   # rebuild one into an SDD
"""
import json, os
from .sdd_utils import build
from .compile import decision_tree_to_sdd

_DEFAULT = os.path.join(os.path.dirname(__file__), "..", "..",
                        "data", "examples", "examples.json")

def load_examples(path=None):
    with open(path or _DEFAULT) as fh:
        return json.load(fh)

def get_example(id, path=None):
    for e in load_examples(path):
        if e["id"] == id:
            return e
    raise KeyError(f"no example with id {id!r}")

def _rebuild(ast, mgr, lits):
    op = ast["op"]
    if op == "var":
        return lits[ast["v"]]
    if op == "not":
        return ~_rebuild(ast["x"], mgr, lits)
    if op == "and":
        r = mgr.true()
        for x in ast["xs"]:
            r = r & _rebuild(x, mgr, lits)
        return r
    if op == "or":
        r = mgr.false()
        for x in ast["xs"]:
            r = r | _rebuild(x, mgr, lits)
        return r
    if op == "const":
        return mgr.true() if ast["val"] else mgr.false()
    if op == "tree":
        return decision_tree_to_sdd(ast["tree"], mgr, lits)
    raise ValueError(f"unknown op {op!r}")

def build_example(ex, vtree_type="right"):
    """Rebuild an example dict into (mgr, sdd, ex). Test instances are in ex['test_instances']
    with string keys from JSON; they are converted to int-keyed dicts here."""
    nvars = ex["nvars"]
    mgr, lit_list = build(nvars, vtree_type=vtree_type)
    lits = {i + 1: lit_list[i] for i in range(nvars)}
    sdd = _rebuild(ex["formula"], mgr, lits)
    # normalise test instances to int keys
    ex = dict(ex)
    ex["test_instances"] = [{int(k): v for k, v in inst.items()}
                            for inst in ex["test_instances"]]
    return mgr, sdd, ex
