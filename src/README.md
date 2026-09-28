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


### Ordered PI enumeration from a nearest model (pipeline)


- `reasons_from_model` is the top-level entry point. Given the classifier SDD, a nearest model μ, and ω, it yields the PIs of Δ contained in μ, one at a time, as dicts `{var: bool}`. Runs the full pipeline: fix the flipped literals F_μ, condition on them to get the residual D_μ, restrict to D_μ's semantic support, detect the mandatory core C_μ, and then CEGAR-enumerate the optional part U_μ.

The `enumeration/` subpackage holds the machinery:

- `enumeration/conditioning` builds D_μ = Δ | F_μ, the residual after fixing the mandatory flipped literals. Every PI contained in μ has the form F_μ ∪ (optional part), so enumeration is done on D_μ instead of Δ.

- `enumeration/mandatory_core` detects the core C_μ ⊆ O_μ: literals in the optional set that appear in **every** PI contained in μ. For each candidate ℓ, checks whether removing it from the full optional set still entails D_μ; if not, ℓ is core. Semantically equivalent to per-variable dependency: the pipeline uses the same idea to check which vars D_μ actually depends on (avoiding structural undercounts after PySDD's `condition`).

- `enumeration/hitting_sets` is a lazy best-first minimal-hitting-set enumerator over an incrementally growing family of conflict sets. Maintains a size-ordered heap of candidate hitting sets, a list of blocked PIs (whose supersets are non-prime), and a `branch(cand, conflict)` hook that CEGAR uses to re-branch a failed candidate on a newly-added conflict. Has iteration and queue caps that raise `MHSSearchLimitExceeded` if the search blows up.

- `enumeration/cegar` is the CEGAR loop itself. Repeatedly asks the MHS enumerator for the next minimal hitting set A, tests whether A ∪ C_μ entails D_μ, and either yields F_μ ∪ C_μ ∪ A as a PI or extracts a countermodel-derived conflict, adds it, and branches. Also exports `blind_enumerate` (subset enumeration by increasing size with superset blocking) as the no-CEGAR ablation.

- `enumeration/cache` memoises residual → PI-set results across nearest models within a single call, so repeated μ's with identical residuals reuse work.


