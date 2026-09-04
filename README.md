

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

TASK = "list" # list every example in the dataset
TASK = "run:wine" # run the full edit pipeline on one example
TASK = "run_all" # run it on every example
TASK = "structure:wine" # print an SDD's decomposition structure
TASK = "compare:def6_divergence" # compare the two Definition-6 readings
TASK = "alternatives:wine" # show the costed menu of alternatives
TASK = "tree_demo" # compile a decision tree and edit it
TASK = "scaling" # time the pipeline vs naive enumeration
TASK = "vtree_compare:hwb_6" # SDD size across different vtrees
TASK = "tests" # run the pytest suite
TASK = "custom" # run the editable block at the bottom of main.py

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



## tests Module


## experiments Module

