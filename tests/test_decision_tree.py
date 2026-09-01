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
