
# Existing experiments
- `summer_validation/` - the four-results regression check.
- `examples/` - handcrafted dataset generation and demo.
- `suites/` - generation of benchmark.
- `pi_recovery/` - fraction of minimal reasons recovered by the menu vs enumeration.
- `scaling/` - pipeline vs enumeration timing, and SDD size across vtrees.
- `menu_extension/` - compares tiers of tie-reason recovery and measures the cost of extending the menu.



## MODULE summer_validation : (regression baseline)

`validate_results.py` reproduces the four summer notebook results and checks them against an independent brute-force ground truth.

- **Result 1** bottom-up distance == brute-force nearest distance
- **Result 2** reconstructed instance is a genuine model at exactly that distance
- **Result 3** greedy-shrink reason is a genuine prime implicant achieving the global-minimum disagreement, robust to shrink order and ties
- **Result 4** each alternative sits at distance d+gap; its reason's disagreement lies in [d, d+gap]

It runs on the canonical dataset examples and on ~300 random classifiers.

Run: `python experiments/summer_validation/validate_results.py`
Output: `outputs/validation_report.txt`.

Note: the original executed Jupyter notebook can be found in `notebooks/`


## MODULE examples: Example generation & demo

- `generate_examples.py` — writes `data/examples/examples.json` Re-run to regenerate.
- `demo_run_examples.py` — loads every example and runs the pipeline on its test instances, showing distance, reason, weakened reason, and the set-vs-cardinality Definition-6 comparison.


## MODULE suites: shared suite 
- `suites/generate_suite.py` writes a benchmark of random 3-CNF classifiers across a density grid (straddling the 3-SAT phase transition), with fixed seeds, to
  `data/suites/standard.json`. Run once; the suite is then a fixed, shared artifact.
- `rgr.suite` (in the library) loads a suite and rebuilds each classifier into an SDD under any vtree, exactly as `rgr.dataset` does for the handcrafted examples.


## Shared harness
- `harness.py`: load the suite, iterate classifiers (and optionally rejected instances), loop vtrees, collect rows, aggregate, write CSV + summary. Each experiment supplies only a `measure(...)` function returning the metrics for one case. 
  Granularities: `per="classifier"` (once per classifier) or `per="instance"` (per rejected instance).

### Writing a new experiment
```python
from harness import run_experiment, avg_time
def measure(mgr, sdd, entry):            # or (mgr, sdd, entry, omega) for per="instance"
    return {"metric": ...}
run_experiment("standard", measure, per="classifier", out="my_experiment", group_keys=["nvars", "density"], vtrees=("right",))
```

## MODULE: scaling

- `run_scaling.py`: Scaling experiment (harness-based): pipeline vs naive prime-implicant enumeration. Runs on the shared frozen suite and on the handcrafted worst-case examples (parity, HWB, Q_V)
- `rerun_summary.py`: Only used to regerenate the summary text file from the CSV without having to rerun the scaling experiment
- `make_chart.py`: used both to regenerate the chart image generated when running the scaling experiment, and to generate additional useful charts.



## MODULE: pi_recovery

- `run_pi_recovery.py`: Measures, per rejected instance, the fraction of minimal-disagreement reasons recovered by the gap-0 alternatives menu, under each vtree. Runs on the shared frozen suite so it uses the same classifiers as every other experiment.
- `analyze_and_chart.py`: analyses the harness-produced PI-recovery results and generate a chart
- `extra_charts.py`: makes other charts for the results

## MODULE: menu_extension

- `run_diagnostic.py`: Standalone counting diagnostic: for each tie case, count the number of nearest models, and relate that count to whether the bounded single-path menu is incomplete. 
- `run_menu_extension.py`: Menu-extension experiment: three tiers of tie-reason recovery, plus the cost of the extension measured at two levels.
- `run_three_way.py`: Three-way comparison on the same task: recover the tied minimal reasons for a rejected instance. (original bounded menu, extended menu, PI enumeration)
- `three_way_charts.py`: Charts for visualization of three way results
