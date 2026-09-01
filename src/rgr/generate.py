"""
Seeded random example generation, mirroring the dataset families.

Every generator returns an example dict compatible with rgr.dataset.build_example:
    {"id","family","nvars","formula","test_instances","notes"}
so that all tasks can consume fixed OR randomly-generated examples identically.
"""
import random

def _V(i):    return {"op": "var", "v": i}
def _NOT(a):  return {"op": "not", "x": a}
def _AND(*x): return {"op": "and", "xs": list(x)}
def _OR(*x):  return {"op": "or", "xs": list(x)}

def random_cnf_example(rng, nvars=None, nclauses=None, idx=0):
    """A random satisfiable CNF classifier with a rejected test instance."""
    nvars = nvars or rng.randint(3, 6)
    nclauses = nclauses or rng.randint(1, max(1, nvars))
    witness = {v: rng.random() < 0.5 for v in range(1, nvars + 1)}
    clauses = []
    for _ in range(nclauses):
        chosen = rng.sample(range(1, nvars + 1), min(3, nvars))
        keep = rng.choice(chosen)
        lits = [_V(keep) if witness[keep] else _NOT(_V(keep))]
        for v in chosen:
            if v == keep:
                continue
            lits.append(_V(v) if rng.random() < 0.5 else _NOT(_V(v)))
        clauses.append(_OR(*lits) if len(lits) > 1 else lits[0])
    formula = _AND(*clauses) if len(clauses) > 1 else clauses[0]
    # a rejected instance: flip the witness fully (usually rejected; caller may re-draw)
    rej = {v: (not witness[v]) for v in range(1, nvars + 1)}
    return {
        "id": f"rand_{idx}", "family": "random", "nvars": nvars,
        "formula": formula, "test_instances": [rej],
        "notes": f"seeded random CNF ({nvars} vars, {nclauses} clauses)",
    }

def random_tree_example(rng, depth=None, idx=0):
    """A random decision tree classifier."""
    depth = depth or rng.randint(2, 4)
    counter = [1]
    def build(d):
        if d == 0:
            return bool(rng.getrandbits(1))
        f = counter[0]; counter[0] += 1
        return {"feature": f, "true": build(d - 1), "false": build(d - 1)}
    tree = build(depth)
    nvars = counter[0] - 1
    tests = [{v: False for v in range(1, nvars + 1)},
             {v: True for v in range(1, nvars + 1)}]
    return {
        "id": f"randtree_{idx}", "family": "decision_tree", "nvars": nvars,
        "formula": {"op": "tree", "tree": tree}, "test_instances": tests,
        "notes": f"seeded random decision tree (depth {depth}, {nvars} vars)",
    }

GENERATORS = {
    "random": random_cnf_example,
    "tree":   random_tree_example,
}

def make_examples(kind="random", n=1, seed=0, **kw):
    """Return a list of n seeded random example dicts of the given kind."""
    rng = random.Random(seed)
    gen = GENERATORS.get(kind, random_cnf_example)
    return [gen(rng, idx=i, **kw) for i in range(n)]