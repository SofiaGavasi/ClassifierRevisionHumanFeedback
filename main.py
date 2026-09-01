"""

USE: change the one TASK line, then run  python main.py

TASK options:
    "list"                 list every dataset example
    "run:<id>"             run the pipeline on one example        (e.g. "run:wine")
    "run_all"              run the pipeline on every example
    "structure:<id>"       print the SDD decomposition structure
    "compare:<id>"         compare the two Definition-6 readings
    "alternatives:<id>"    show the bounded menu of alternatives
    "enum_vs_pipeline:<id>"time enumeration vs the pipeline on one example
    "tree_demo"            compile a small decision tree and edit it
    "scaling"              time pipeline vs enumeration across the worst-case families
    "vtree_compare:<id>"   compare SDD size across vtree types (size varies, result must not)
    "tests"                run the pytest suite
    "custom"               run the editable CUSTOM block at the bottom

if you don't want to run these commands on a fixed example, you can generate one or multiple seeded random examples.
RANDOM EXAMPLES: set USE_RANDOM = True below. 
For per-example tasks they run on the random suite; for "scaling", "vtree_check", and "vtree_compare" results are AVERAGED/ SUMMARISED.
"""

#____________________________________________________________________________________________________
# CONFIGURATION: change only the TASK line below, then run  python main.py

TASK = "tests"          # <--- CHANGE THIS LINE with one of the TASK options above


# --- random-example configuration (change this configuration to run the task on random examples) ---
USE_RANDOM    = False       # True -> tasks run on seeded random examples
RANDOM_KIND   = "random"    # "random" (CNF) or "tree"
RANDOM_N      = 10          # how many random examples in the suite
RANDOM_SEED   = 100          # seed for reproducibility
RANDOM_NVARS  = None        # None = generator chooses; or fix an int
VTREE_TYPES   = ["right", "left", "balanced"]   # used by vtree_check / vtree_compare
#____________________________________________________________________________________________________


import sys
from rgr.dataset import load_examples, build_example, get_example
from rgr.generate import make_examples
from rgr.edit import edit
from rgr.alternatives import alternatives
from rgr.compare import compare_readings
from rgr.reasons import all_prime_implicants
from rgr.compile import compile_tree, tree_predict
from rgr.sdd_utils import term_to_sdd, is_implicant
from rgr.display import fmt_term, fmt_instance, sdd_info, sdd_structure, explain_edit
import time


# _______________ example sourcing: fixed dataset OR seeded random _____________
def _suite():
    if USE_RANDOM:
        kw = {} if RANDOM_NVARS is None else {"nvars": RANDOM_NVARS}
        return make_examples(RANDOM_KIND, n=RANDOM_N, seed=RANDOM_SEED, **kw)
    return load_examples()

def _one(id_from_task):
    if USE_RANDOM:
        return _suite()[0]
    return get_example(id_from_task)


# ______________ per-example helpers ___________________
def _rejected_instances(sdd, mgr, ex):
    #Returns test instances that are currently rejected
    for inst in ex["test_instances"]:
        if (term_to_sdd(inst, mgr) & sdd).is_false():
            yield inst

def _run_example(ex):
    mgr, sdd, ex = build_example(ex)
    nv = ex["nvars"]
    print(f"\n=== {ex['id']}  [{ex['family']}] ===")
    print(f"    {ex.get('description', ex.get('notes',''))}")
    print(f"    SDD size={sdd.size()}  models={sdd.global_model_count()}")
    for inst in ex["test_instances"]:
        res = edit(sdd, inst, mgr, nv)
        print("    " + "-" * 58)
        print("    " + explain_edit(sdd, inst, mgr, nv, res).replace("\n", "\n    "))


# _______________ tasks __________________________
def task_list():
    print(f"{'id':22s} {'family':20s} {'nvars':>5}")
    print("-" * 50)
    for ex in _suite():
        print(f"{ex['id']:22s} {ex['family']:20s} {ex['nvars']:>5}")

def task_run(id):
    if USE_RANDOM:
        for ex in _suite():
            _run_example(ex)
    else:
        _run_example(get_example(id))

def task_run_all():
    for ex in _suite():
        _run_example(ex)

def task_structure(id):
    ex = _one(id)
    mgr, sdd, ex = build_example(ex)
    print(f"___ SDD structure: {ex['id']} ___")
    print(sdd_structure(sdd, names=ex.get("names")))

def task_compare(id):
    exs = _suite() if USE_RANDOM else [get_example(id)]
    n_coincide = n_applicable = 0
    for ex in exs:
        mgr, sdd, ex = build_example(ex)
        for inst in ex["test_instances"]:
            rep = compare_readings(sdd, inst, ex["nvars"], mgr)
            if not rep.get("applicable"):
                continue
            n_applicable += 1
            if rep["coincide"]:
                n_coincide += 1
            if not USE_RANDOM or len(exs) <= 3:
                print(f"  {ex['id']} / {fmt_instance(inst)}: coincide={bool(rep['coincide'])} "
                      f"(#minimal={rep['num_minimal_reasons']}, "
                      f"all-min models={rep['models_all_minimal']}, single={rep['models_single']})")
    if USE_RANDOM:
        print(f"\n  SUMMARY over {n_applicable} applicable cases: "
              f"{n_coincide} coincide, {n_applicable - n_coincide} differ "
              f"({100*n_coincide/max(1,n_applicable):.0f}% coincide)")

def task_alternatives(id):
    exs = _suite() if USE_RANDOM else [get_example(id)]
    total_alts = cases = 0
    for ex in exs:
        mgr, sdd, ex = build_example(ex)
        for inst in _rejected_instances(sdd, mgr, ex):
            d, alts = alternatives(sdd, inst, ex["nvars"])
            cases += 1; total_alts += len(alts)
            if not USE_RANDOM or len(exs) <= 3:
                print(f"  {ex['id']} / {fmt_instance(inst)}  d={d}")
                for a in alts:
                    print(f"    gap={a['gap']}  {fmt_instance(a['instance'])}  dist={a['instance_distance']}")
    if USE_RANDOM and cases:
        print(f"\n  SUMMARY: {cases} edits, {total_alts} alternatives total, "
              f"avg {total_alts/cases:.2f} per edit")

def _time_pipeline(sdd, omega, mgr, nv, reps=200):
    t0 = time.time()
    for _ in range(reps):
        edit(sdd, omega, mgr, nv)
    return (time.time() - t0) / reps

def task_enum_vs_pipeline(id):
    exs = _suite() if USE_RANDOM else [get_example(id)]
    print(f"{'id':14s} {'nv':>3} {'|SDD|':>6} {'#reasons':>9} {'enum(s)':>10} {'pipe(s)':>11} {'speedup':>8}")
    print("-" * 62)
    enum_times, pipe_times, speedups = [], [], []
    for ex in exs:
        mgr, sdd, ex = build_example(ex)
        nv = ex["nvars"]
        insts = list(_rejected_instances(sdd, mgr, ex))
        if not insts:
            continue
        omega = insts[0]
        t_pipe = _time_pipeline(sdd, omega, mgr, nv)
        if nv <= 12:
            t0 = time.time(); pis = all_prime_implicants(sdd, nv, mgr); t_enum = time.time() - t0
            sp = t_enum / t_pipe if t_pipe else 0
            enum_times.append(t_enum); pipe_times.append(t_pipe); speedups.append(sp)
            print(f"{ex['id']:14s} {nv:>3} {sdd.size():>6} {len(pis):>9} "
                  f"{t_enum:>10.5f} {t_pipe:>11.6f} {sp:>7.0f}x")
        else:
            print(f"{ex['id']:14s} {nv:>3} {sdd.size():>6} {'?':>9} {'skipped':>10} {t_pipe:>11.6f} {'-':>8}")
    if USE_RANDOM and speedups:
        import statistics
        print("-" * 62)
        print(f"AVERAGES over {len(speedups)} examples: "
              f"enum={statistics.mean(enum_times):.5f}s  "
              f"pipe={statistics.mean(pipe_times):.6f}s  "
              f"speedup={statistics.mean(speedups):.0f}x")

def task_tree_demo():
    if USE_RANDOM and RANDOM_KIND == "tree":
        task_run_all(); return
    tree = {"feature": 1,
            "true":  {"feature": 2, "true": True,
                      "false": {"feature": 3, "true": True, "false": False}},
            "false": {"feature": 3, "true": True, "false": False}}
    mgr, sdd = compile_tree(tree, 3)
    print("___ Decision tree demo: (a & b) | c as a tree ___")
    print(f"    compiled SDD size={sdd.size()}, models={sdd.global_model_count()}")
    omega = {1: False, 2: False, 3: False}
    print(f"    tree predicts on {fmt_instance(omega)}: {tree_predict(tree, omega)}")
    res = edit(sdd, omega, mgr, 3)
    print(f"    edit distance={res['distance']}, reason={fmt_term(res['reason'])} "
          f"-> weakened {fmt_term(res['weakened'])}")
    print(f"    accepted after edit: {is_implicant(omega, res['edited'], mgr)}")

def task_scaling():
    exs = _suite() if USE_RANDOM else [e for e in load_examples()
              if e["family"] in ("worst_case_naive", "worst_case_pipeline", "random")]
    print(f"{'id':14s} {'family':20s} {'nv':>3} {'|SDD|':>6} {'#PIs':>6} "
          f"{'enum(s)':>10} {'pipe(s)':>11} {'speedup':>8}")
    print("-" * 74)
    enum_t, pipe_t, sizes = [], [], []
    for ex in exs:
        mgr, sdd, ex = build_example(ex)
        nv = ex["nvars"]
        insts = list(_rejected_instances(sdd, mgr, ex)) or ex["test_instances"]
        omega = insts[0]
        t_pipe = _time_pipeline(sdd, omega, mgr, nv)
        pipe_t.append(t_pipe); sizes.append(sdd.size())
        if nv <= 12:
            t0 = time.time(); pis = all_prime_implicants(sdd, nv, mgr); t_enum = time.time() - t0
            enum_t.append(t_enum)
            sp = f"{t_enum/t_pipe:.0f}x" if t_pipe else "n/a"
            print(f"{ex['id']:14s} {ex['family']:20s} {nv:>3} {sdd.size():>6} {len(pis):>6} "
                  f"{t_enum:>10.5f} {t_pipe:>11.6f} {sp:>8}")
        else:
            print(f"{ex['id']:14s} {ex['family']:20s} {nv:>3} {sdd.size():>6} {'?':>6} "
                  f"{'skipped':>10} {t_pipe:>11.6f} {'-':>8}")
    if USE_RANDOM and pipe_t:
        import statistics
        print("-" * 74)
        line = (f"AVERAGES over {len(pipe_t)} examples: |SDD|={statistics.mean(sizes):.1f}  "
                f"pipe={statistics.mean(pipe_t):.6f}s")
        if enum_t:
            line += f"  enum={statistics.mean(enum_t):.5f}s"
        print(line)


def task_vtree_compare(id):
    """Compare SDD size across vtree types for the same function"""
    import statistics
    exs = _suite() if USE_RANDOM else [get_example(id)]
    print(f"{'id':16s} " + " ".join(f"{vt:>10s}" for vt in VTREE_TYPES) + f" {'min/max':>10s}")
    print("-" * (16 + 11 * len(VTREE_TYPES) + 11))
    ratios = []
    for ex in exs:
        sizes = {}
        for vt in VTREE_TYPES:
            mgr, sdd, _ = build_example(ex, vtree_type=vt)
            sizes[vt] = sdd.size()
        smin, smax = min(sizes.values()), max(sizes.values())
        ratio = smax / smin if smin else 1.0
        ratios.append(ratio)
        print(f"{ex['id']:16s} " + " ".join(f"{sizes[vt]:>10d}" for vt in VTREE_TYPES)
              + f" {ratio:>9.2f}x")
    if USE_RANDOM and ratios:
        print("-" * (16 + 11 * len(VTREE_TYPES) + 11))
        print(f"AVERAGE max/min size ratio over {len(ratios)} examples: "
              f"{statistics.mean(ratios):.2f}x  (max observed {max(ratios):.2f}x)")

def task_tests():
    import subprocess
    subprocess.run([sys.executable, "-m", "pytest", "tests/", "-q"])

def task_custom():
    # ---- EDIT THIS BLOCK FREELY for one-off experiments ----
    mgr, sdd, ex = build_example(get_example("wine"))
    omega = {1: True, 2: True, 3: True, 4: True}
    res = edit(sdd, omega, mgr, 4)
    print("custom run:", fmt_term(res["reason"]), "->", fmt_term(res["weakened"]))
    # --------------------------------------------------------


def main():
    t = TASK.strip()
    if   t == "list":                     task_list()
    elif t.startswith("run:"):            task_run(t.split(":", 1)[1])
    elif t == "run_all":                  task_run_all()
    elif t.startswith("structure:"):      task_structure(t.split(":", 1)[1])
    elif t.startswith("compare:"):        task_compare(t.split(":", 1)[1])
    elif t.startswith("alternatives:"):   task_alternatives(t.split(":", 1)[1])
    elif t.startswith("enum_vs_pipeline:"):task_enum_vs_pipeline(t.split(":", 1)[1])
    elif t == "tree_demo":                task_tree_demo()
    elif t == "scaling":                  task_scaling()
    elif t.startswith("vtree_compare:"):  task_vtree_compare(t.split(":", 1)[1])
    elif t == "tests":                    task_tests()
    elif t == "custom":                   task_custom()
    else:
        print(f"Unknown TASK={TASK!r}. See the docstring at the top of main.py.")


if __name__ == "__main__":
    main()