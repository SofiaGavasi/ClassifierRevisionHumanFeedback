

## install env
```
pip install -e .          # editable install (needs PySDD)
pip install -e ".[dev]"   # + pytest
```




## Tests module

The `tests/` folder holds the regression suite: it re-checks every part of the engine against independent brute-force ground truth, so any change to the pipeline that breaks a proven property gets caught. 


## Experiments Module

The `experiments/` folder holds standalone scripts that *produce results and files*, as opposed to the engine (`rgr/`), which holds the reusable logic, and the tests (`tests/`), which only check correctness. Each experiment lives in its own subfolder. A seperate README file is in the experiments module to describe the various subfolders


## src/rgr

The library with all functions reused by every task



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





