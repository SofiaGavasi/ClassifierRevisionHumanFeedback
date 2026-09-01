"""Demo: load the example dataset and run the pipeline on each, with readable output.
Run:  python experiments/examples/demo_run_examples.py
or just access from main.py
"""
from rgr.dataset import load_examples, build_example
from rgr.edit import edit
from rgr.alternatives import alternatives
from rgr.compare import compare_readings
from rgr.display import fmt_term, fmt_instance, sdd_info

for ex in load_examples():
    mgr, sdd, ex = build_example(ex)
    nv = ex["nvars"]
    print("="*70)
    print(f"{ex['id']}  [{ex['family']}]  ({ex['description']})")
    info = sdd_info(sdd, mgr, nv)
    print(f"  SDD size={info['size']}  models={info['model_count']}")
    for inst in ex["test_instances"]:
        res = edit(sdd, inst, mgr, nv)
        print(f"  instance {fmt_instance(inst)}: dist={res['distance']}", end="")
        if res["reason"] is not None:
            print(f", reason={fmt_term(res['reason'])} -> weakened {fmt_term(res['weakened'])}")
        else:
            print("  (already accepted, no-op)")
        # show set-vs-cardinality comparison where applicable
        rep = compare_readings(sdd, inst, nv, mgr)
        if rep.get("applicable"):
            print(f"      def6 readings coincide: {bool(rep['coincide'])} "
                  f"(all-minimal models={rep['models_all_minimal']}, single={rep['models_single']}, "
                  f"#minimal reasons={rep['num_minimal_reasons']})")
