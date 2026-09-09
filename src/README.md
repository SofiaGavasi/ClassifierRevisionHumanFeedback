## Function files in rgr

### The setup files (getting a classifier to work with)

- `sdd_utils` is the foundation: it builds the SDD manager and gives the basic operations (make a term, check if something's an implicant). 

- `compile` has the job of turning various kinds of classifiers into SDDs the pipeline can edit (decision tree, and worst case functions)

- `generate` creates random example classifiers (random logic formulas or random decision trees), seeded so they're reproducible.

- `dataset` loads the fixed example classifiers from the JSON file and rebuilds them into SDDs.

- `suite` loads a suite (benchmark) and rebuilds each classifier into an SDD under any vtree.


### The core pipeline (the actual editing)

- `distance` does the first step: one bottom-up pass over the SDD that computes how far an instance ω is from the nearest instance the classifier accepts.

- `reconstruct` does the second step: it recovers the actual nearest accepted instance (ω0), not just the distance, by following the winning branches back down the SDD.

- `shrink` does the third step: starting from ω0, it strips away unnecessary literals to get a single clean reason (a prime implicant)

- `edit` is the conductor that ties these together: it calls distance -> reconstruct -> shrink, then weakens that reason and ORs it into the classifier. Out comes the edited classifier that now accepts ω.

- `nearest_all` Enumerate ALL minimum-distance models of an SDD to a target instance, by walking the sub-DAG of minimum-cost branches (the 'gap-0' paths). This is the bounded menu extension: instead of one nearest model, recover every nearest model.


### The extras (analysis, not core)

- `alternatives` produces the menu. instead of one fix, it offers a few alternative reasons the user could pick from, each with a cost.

- `reasons` is the brute-force version: it enumerates all prime implicants directly. It's slow (exponential) and exists only as a ground-truth check and for the comparison below.

- `compare` runs the two readings of Definition 6 side by side (the pipeline's single-reason edit vs. the all-minimal edit) and reports whether they agree

- `display` makes things human-readable: printing terms, instances, and the SDD structure nicely.

- `count` counts the minimum-distance models of an SDD to a target instance, without enumerating them. Used by the extended menu experiments.



