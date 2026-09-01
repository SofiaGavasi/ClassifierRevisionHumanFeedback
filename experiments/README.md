# examples: Example generation & demo

- `generate_examples.py` — writes `data/examples/examples.json` Re-run to regenerate.
- `demo_run_examples.py` — loads every example and runs the pipeline on its test instances, showing distance, reason, weakened reason, and the set-vs-cardinality Definition-6 comparison.


# scaling: pipeline vs naive reason enumeration

`run_scaling.py` times the full edit pipeline against naive prime-implicant enumeration on identical classifiers, across three regimes:

- **worst_case_naive** (parity): small SDD, exponentially many reasons. 
- **worst_case_pipeline** (HWB): no small SDD. Both approaches inherit the large |SDD|; the pipeline is still polynomial in it, but the representation itself is the bottleneck.
- **random**: general satisfiable classifiers of increasing size.

The pipeline is averaged over repetitions (a single run can fall below the timer's resolution). Enumeration is skipped above `ENUM_CAP_VARS` variables, where it becomes infeasible. It's currently set to 12.

Run: `python experiments/scaling/run_scaling.py`
Outputs: `outputs/scaling_results.csv`, `outputs/scaling_table.txt`.



# summer_validation : (regression baseline)

`validate_results.py` reproduces the four summer notebook results and checks them against an independent brute-force ground truth.

- **Result 1** bottom-up distance == brute-force nearest distance
- **Result 2** reconstructed instance is a genuine model at exactly that distance
- **Result 3** greedy-shrink reason is a genuine prime implicant achieving the global-minimum disagreement, robust to shrink order and ties
- **Result 4** each alternative sits at distance d+gap; its reason's disagreement lies in [d, d+gap]

It runs on the canonical dataset examples and on ~300 random classifiers.

Run: `python experiments/summer_validation/validate_results.py`
Output: `outputs/validation_report.txt`.

Note: the original executed Jupyter notebook can be found in `notebooks/`


