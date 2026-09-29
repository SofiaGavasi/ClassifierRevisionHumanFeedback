# RGR web UI

Interactive interface to the reason-guided revision pipeline. Type a Boolean classifier, pick an instance ω, watch the pipeline compute the minimal sufficient reasons for ω step by step, choose one, and see the revised classifier alongside the original.

Runs locally: FastAPI backend (thin wrapper around the `rgr` library) + Vite/React frontend.

## Running

Two terminals:

**Backend** (from repo root):
```bash
cd web/server
pip install -e .
```
Then, from `web/server`:
```powershell
# PowerShell (Windows)
$env:PYTHONPATH="../../src"; uvicorn rgr_web.app:app --reload --port 8000
```
```bash
# bash / zsh
PYTHONPATH=../../src uvicorn rgr_web.app:app --reload --port 8000
```

**Frontend**:
```bash
cd web/app
npm install
npm run dev
```
Open <http://localhost:5173>.
---


## Backend - `web/server/`

FastAPI wrapper that exposes the reason-guided revision pipeline over HTTP.
Imports the `rgr` package directly from `src/rgr/` and adds nothing: every endpoint is a thin serialiser around library functions.

- **`rgr_web/app.py`** - FastAPI app and endpoints (`/api/parse`, `/api/random`, `/api/examples`, `/api/revise/cegmhs`, `/api/apply`); also holds the hardcoded and dataset-loaded example classifiers.
- **`rgr_web/parse.py`** - turns user text (propositional formula, CNF, truth table) into the canonical `{nvars, var_names, clauses}` shape; formula parser accepts unicode operators (∧ ∨ ¬ → ↔), keywords (`and`/`or`/`not`), and mixed spacing.
- **`rgr_web/trace.py`** - orchestrates the pipeline for one `(classifier, ω)` pair, emitting a JSON step-trace (`{steps: [{name, description, data}], sdd_dot, reasons, ...}`) that the frontend renders generically; also implements `apply_revision` (weaken + OR + CNF/DNF/truth-table derivation for the revised classifier).
- **`rgr_web/traced_pipeline.py`** - trace-emitting reimplementation of `reasons_from_model` that reuses the library's building blocks (`condition_sdd`, `find_mandatory_core`, MinimalHittingSetEnumerator`) but drives the min.hit.set loop by hand so every iteration (candidate, countermodel, conflict, yielded PI) is recorded for the UI.

---


## Frontend - `web/app/`

Vite + React + TypeScript. KaTeX renders math inline; `d3-graphviz` renders SDDs from the DOT strings the backend returns.

### `src/`

- **`App.tsx`** - top-level page: orchestrates the flow (input → ω → algorithm → SDD → trace → revised) and holds the shared state.


### `src/components/`

- **`InputPanel.tsx`** - the two-column input box: left is the "type your own" area with tabs (formula / CNF / truth table / random) and inline syntax help; right is the flat, scrollable list of examples.
- **`OmegaPicker.tsx`** - one clickable chip per variable to toggle its value in ω.
- **`SDDView.tsx`** - renders an SDD from its Graphviz DOT string using `d3-graphviz`, with a `full DAG` / `summary` toggle.
- **`StepView.tsx`** - generic renderer for one trace step: switches on `step.name` to draw the right sub-view; new step kinds just add a case.
- **`MuBlock.tsx`** - the detailed per-nearest-model panel: F_μ, D_μ (side by side with D), O_μ, N_μ (with per-literal witnesses), U_μ, an animated slider through the min.hit.set iterations, and the final PIs. Every subsection starts collapsed.
- **`RevisedView.tsx`** - the revised-classifier view: header stats (accepts ω?, weakened reason, SDD size, model count, rows added) plus three tabs (truth table with newly-accepted rows highlighted, DNF, CNF).


### `src/lib/`

- **`api.ts`** - thin `fetch` wrapper over the backend endpoints; the TypeScript types (`Classifier`, `Example`, `Trace`, `TraceStep`) live here.
- **`latex.tsx`** - KaTeX helpers: `<Tex src="…"/>` for a whole expression, `<TexInline text="… $ω$ …" />` for prose with inline `$…$` math spans.

---



## Flow

```
 user
   |
   V
 InputPanel  -- /api/parse    ---->  parse.py         (text → CNF)
 (or example) -- /api/random  ---->  app.py            (random 3-CNF)
   |
   V
 App.tsx state:  {nvars, var_names, clauses, omega}
   |
   V
 "Run pipeline"  -- /api/revise/cegmhs ---->  trace.build_trace
   |                                             |
   |                                             V
   |                                          rgr.suite.build_classifier   (mgr, sdd)
   |                                          rgr.distance.node_dist       (d*)
   |                                          rgr.nearest_all              (all μ)
   |                                          traced_pipeline.trace_reasons_from_model
   |                                             |
   |                                             V
   |                                          rgr.enumeration:
   |                                             condition_sdd  → D_μ
   |                                             find_mandatory_core → N_μ
   |                                             MinimalHittingSetEnumerator + hand-driven min.hit.set loop (each iteration recorded for the UI)
   |                            
   |
   V (Trace JSON)
 StepView / MuBlock / SDDView     --  render the trace
   |
   V
 user picks one reason
   |
   V
 "choose this reason" -- /api/apply ---->  trace.apply_revision
   |                                           |
   |                                           V
   |                                        rgr.reasons.weaken
   |                                        term_to_sdd + sdd | W  (revised SDD)
   |                                        enumerate accepting rows
   |                                        sympy → simplified DNF / CNF
   V (revised JSON)
 RevisedView    --     shows old vs new (truth table, DNF, CNF, SDD)
```

Every algorithm endpoint returns the same JSON shape (`{algorithm, steps, sdd_dot, reasons, nvars, var_names, clauses}`), so future algorithms (batch revision, sequential revision, ...) plug in with a new backend endpoint + one entry in `ALGORITHMS` in `App.tsx`, without touching the renderer.