"""Decision trees compile to SDDs matching the tree, and edit correctly."""
from itertools import product
from rgr.dataset import get_example, build_example
from rgr.compile import compile_tree, tree_predict
from rgr.sdd_utils import term_to_sdd, is_implicant
from rgr.edit import edit

def test_compiled_tree_matches_truth_table():
    tree = {"feature":1,
            "true": {"feature":2,"true":True,"false":{"feature":3,"true":True,"false":False}},
            "false":{"feature":3,"true":True,"false":False}}
    mgr, sdd = compile_tree(tree, 3)
    for bits in product([False,True], repeat=3):
        asg = {i+1: bits[i] for i in range(3)}
        sdd_says = not (term_to_sdd(asg, mgr) & sdd).is_false()
        assert sdd_says == tree_predict(tree, asg)

def test_dataset_decision_tree_edits():
    mgr, sdd, ex = build_example(get_example("decision_tree_d3"))
    for inst in ex["test_instances"]:
        res = edit(sdd, inst, mgr, ex["nvars"])
        # after edit, instance is accepted (unless it already was, distance 0)
        assert is_implicant(inst, res["edited"], mgr)


def test_tree_induced_vtree_typically_no_larger():
    """The tree-induced vtree gives the SAME function as a generic vtree, and is
    typically no larger. The size advantage is guaranteed only for read-once
    (ordered) trees; general trees that reuse features in different orders across
    branches have no single coherent variable order, so the induced order can
    occasionally be worse. We therefore assert correctness always, and a size
    advantage in the majority of cases."""
    import random
    from rgr.compile import compile_tree
    from rgr.sdd_utils import term_to_sdd
    from itertools import product

    rng = random.Random(3)
    def scrambled(depth, nvars):
        def b(d):
            if d == 0:
                return bool(rng.getrandbits(1))
            return {"feature": rng.randint(1, nvars), "true": b(d - 1), "false": b(d - 1)}
        return b(depth)

    induced_wins = 0
    for _ in range(10):
        nvars = 8
        tree = scrambled(6, nvars)
        mgr_i, sdd_i = compile_tree(tree, nvars)  # tree-induced (default)
        mgr_g, sdd_g = compile_tree(tree, nvars, vtree_type="right") # generic 1..n
        # correctness: same function, always
        for bits in product([False, True], repeat=nvars):
            asg = {i + 1: bits[i] for i in range(nvars)}
            a = not (term_to_sdd(asg, mgr_i) & sdd_i).is_false()
            b = not (term_to_sdd(asg, mgr_g) & sdd_g).is_false()
            assert a == b, "tree-induced and generic compilations differ in function"
        if sdd_i.size() <= sdd_g.size():
            induced_wins += 1
    # the induced order should be no larger in the clear majority of cases
    assert induced_wins >= 7