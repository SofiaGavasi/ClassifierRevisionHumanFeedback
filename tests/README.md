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
