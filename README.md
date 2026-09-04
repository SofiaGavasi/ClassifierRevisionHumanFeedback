

## install env
```
pip install -e .          # editable install (needs PySDD)
pip install -e ".[dev]"   # + pytest
```

## Function files in rgr

### The setup files (getting a classifier to work with)

- `sdd_utils` is the foundation: it builds the SDD manager and gives the basic operations (make a term, check if something's an implicant). 

- `compile` has the job of turning various kinds of classifiers into SDDs the pipeline can edit (decision tree, and worst case functions)

- `generate` creates random example classifiers (random logic formulas or random decision trees), seeded so they're reproducible.

- `dataset` loads the fixed example classifiers from the JSON file and rebuilds them into SDDs.


### The core pipeline (the actual editing)

- `distance` does the first step: one bottom-up pass over the SDD that computes how far an instance ω is from the nearest instance the classifier accepts.

- `reconstruct` does the second step: it recovers the actual nearest accepted instance (ω0), not just the distance, by following the winning branches back down the SDD.

- `shrink` does the third step: starting from ω0, it strips away unnecessary literals to get a single clean reason (a prime implicant)

- `edit` is the conductor that ties these together: it calls distance -> reconstruct -> shrink, then weakens that reason and ORs it into the classifier. Out comes the edited classifier that now accepts ω.


### The extras (analysis, not core)

- `alternatives` produces the menu. instead of one fix, it offers a few alternative reasons the user could pick from, each with a cost.

- `reasons` is the brute-force version: it enumerates all prime implicants directly. It's slow (exponential) and exists only as a ground-truth check and for the comparison below.

- `compare` runs the two readings of Definition 6 side by side (the pipeline's single-reason edit vs. the all-minimal edit) and reports whether they agree

- `display` makes things human-readable: printing terms, instances, and the SDD structure nicely.



## Usage guide

Everything runs through `main.py`: change the single `TASK` line at the top, then run `python main.py`.

### Running on the fixed examples

examples: 

- TASK = "list" # list every example in the dataset
- TASK = "run:wine" # run the full edit pipeline on one example
- TASK = "run_all" # run it on every example
- TASK = "structure:wine" # print an SDD's decomposition structure
- TASK = "compare:def6_divergence" # compare the two Definition-6 readings
- TASK = "alternatives:wine" # show the costed menu of alternatives
- TASK = "tree_demo" # compile a decision tree and edit it
- TASK = "scaling" # time the pipeline vs naive enumeration
- TASK = "vtree_compare:hwb_6" # SDD size across different vtrees
- TASK = "tests" # run the pytest suite
- TASK = "custom" # run the editable block at the bottom of main.py

`run:<id>`, `structure:<id>`, etc. take any example id shown by `TASK = "list"`.

### Running on random examples

Set `USE_RANDOM = True` below `TASK`. Every task above then runs on a seeded random suite instead of the fixed dataset. Control the suite with:

USE_RANDOM = True
RANDOM_KIND = "random" # can be "random" (CNF classifiers) or "tree" (decision trees)
RANDOM_N = 10 # how many random examples
RANDOM_SEED = 100 # same seed -> same examples (reproducible)

In random mode, the aggregate tasks print summaries: `compare` reports what % of cases the two readings coincide, `scaling` and `enum_vs_pipeline` print averaged timings, and `alternatives` prints the average number of options per edit.



### Using the library directly

For anything beyond the preset tasks, either edit the `custom` block at the bottom of `main.py`, or import the engine yourself:

```python
from rgr.dataset import get_example, build_example
from rgr.edit import edit
from rgr.display import explain_edit

mgr, sdd, ex = build_example(get_example("wine"))
omega = ex["test_instances"][0]
result = edit(sdd, omega, mgr, ex["nvars"])
print(explain_edit(sdd, omega, mgr, ex["nvars"], result))
```

`edit(delta, omega, mgr, nvars, weights=None)` is the one function that runs the whole pipeline; it returns a dict with the edited classifier, the reason, the weakened reason, the distance, and the alternatives.





## Tests module

The `tests/` folder holds the regression suite: it re-checks every part of the engine against independent brute-force ground truth, so any change to the pipeline that breaks a proven property gets caught. 

### How to run

From `main.py`, set `TASK = "tests"` and run `python main.py`. Or run `pytest tests/ -q` directly. Requires the dev install: `pip install -e ".[dev]"`.

### `test_edit.py` : smoke tests
Basic "does the engine work at all" checks on the two canonical hand examples.
- **`test_ab_or_c_edit_covers_omega`** : edits `(a & b) | c` on a rejected instance; verifies the distance is correct, the instance is accepted after the edit, and nothing previously accepted was lost.
- **`test_wine_reason`** : edits the wine classifier; verifies the distance and that the weakened reason comes out as expected (`w`).

### `test_complexity_worstcase.py` : complexity and worst cases
Checks the two worst-case families behave as the theory predicts.
- **`test_parity_small_sdd_many_reasons`** : confirms parity has a linear-size SDD but 2^(n-1) prime implicants (the naive method's worst case), and the pipeline still runs.
- **`test_hwb_is_pipeline_worst_case`** : confirms HWB's SDD grows with n (faster than parity's at equal n), making it a pipeline's worst case rather than the naive method's.
- **`test_pipeline_faster_than_enumeration`** : times the pipeline against reason enumeration on parity and confirms the pipeline is cheaper.

### `test_decision_tree.py` : decision-tree compilation
Checks the tree-to-SDD bridge.
- **`test_compiled_tree_matches_truth_table`** : compiles a decision tree and verifies the SDD agrees with the tree on every possible input.
- **`test_dataset_decision_tree_edits`** : edits the dataset's decision-tree example and verifies the instance is accepted afterward.

### `test_def6_readings.py` : the two readings of Definition 6
Backs the cardinality investigation.
- **`test_divergence_example_differs`** : on the crafted `def6_divergence` example, confirms the all-minimal and single-reason readings genuinely do *not* coincide, and that the all-minimal reading accepts strictly more.
- **`test_pipeline_reason_always_minimal_and_singleton_matches`** : across random classifiers, confirms the pipeline's reason is always one of the minimal reasons, and that the pipeline's edit is exactly Definition 6 with S_w set to that single reason.

### `test_vtree.py` : vtree invariance and sensitivity
Separates what the vtree does and doesn't affect.
- **`test_distance_invariant_and_edit_valid`** : across all vtree types, the distance is identical and each edit is valid and minimal (correctness is vtree-invariant).
- **`test_all_dataset_examples_distance_invariant`** : the same check swept across every dataset example.
- **`test_size_can_depend_on_vtree`** : confirms SDD size genuinely varies with vtree (HWB under right vs left vtrees).
- **`test_tie_case_may_differ_across_vtrees`** : documents that when reasons tie, different vtrees may pick different (still-valid) reasons, so the edited classifier can differ while both remain correct.

### `test_random_stress.py` : placeholder
- **`test_random_stress_placeholder`** : currently skipped; a stub for porting the ~300-classifier randomised checks from the summer validation notebook into the pytest suite.



## Experiments Module

## Experiments module

The `experiments/` folder holds standalone scripts that *produce results and files*, as opposed to the engine (`rgr/`), which holds the reusable logic, and the tests (`tests/`), which only check correctness. Each experiment lives in its own subfolder. A seperate README file is in the experiments module to describe the various subfolders


