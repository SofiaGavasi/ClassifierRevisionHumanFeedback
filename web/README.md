# Unary and batch revision workbench

The local React/FastAPI interface supports the existing unary pipeline and the independent exact batch backend. The framework chooser keeps their inputs and results separate. Switching frameworks resets the workspace and cancels any batch worker.

## Install and run

Use Python 3.10 or newer and Node.js with npm. From the repository root, in your Python environment:

```powershell
python -m pip install -e . -e ./batch -e "./web/server[test]"
python -m uvicorn rgr_web.app:app --host 127.0.0.1 --port 8000
```

In a second terminal:

```powershell
cd web/app
npm install
npm run dev
```

Open http://localhost:5173. Vite proxies `/api` to the backend on port 8000. Run one backend process; session state belongs to that process. This is a local research interface, without multi-user authentication or persistent saved sessions.

If port 8000 is occupied, use another backend port and set `REVISION_API_TARGET` before starting Vite. For example, run the backend with `--port 8001`, then `$env:REVISION_API_TARGET='http://127.0.0.1:8001'` in the frontend PowerShell terminal. Existing servers do not need to be stopped.

If you prefer source paths to editable installation, run the backend from `web/server` with `PYTHONPATH=../../src;../../batch/src` in PowerShell (use `:` as the path separator in bash). The installed-package commands above require no `PYTHONPATH`.

## Classifier and feedback input

Both frameworks start with **Karnaugh map** and also accept formulas, clause-per-line CNF, an editable truth table, random classifiers and handcrafted examples. The map tools sit beside the map in a vertical palette. Press **Load classifier** to commit an edit. Choosing an example commits it immediately; batch examples also supply their actual feedback and budgets from `batch/datasets/examples.json`.

Classifier input is one shared scratchpad. Changing tabs preserves the classifier and shows its corresponding representation, including examples loaded from a different input format. Unedited views retain unused variables and constant classifiers. Valid text edits are converted when switching views; invalid edits stay visible with an error. Random generation retains the existing input until a new classifier is generated. **Erase input** clears the input and committed classifier, feedback/instance, bounds, trace and result, cancels a batch worker, and restores defaults.

The Karnaugh editor supports 1 through 6 variables. Gray-code row/column order places neighboring assignments together; for 5 or 6 variables it uses separate panels for the last variables. Each cell shows its full bitstring. Toggle cells, paint accepted or rejected regions, clear/fill/invert the map, or undo recent cell edits. Painting and the truth table preserve the declared variable universe, including unused features, tautology and contradiction.

Unary keeps its existing one-positive-instance semantics, CEGMHS trace, reason selection, and revised-classifier views. Select the instance with the existing variable switches or click its map cell. A contradictory original classifier is directed to the batch source-free rule rather than being sent into the unary pipeline.

Batch offers three views of the same feedback:

- **Edit rows:** choose P+ or N−, flip variable values, and add the instance. Adding an existing instance updates its target.
- **Paste / import:** replace feedback with bitstrings, complete Boolean arrays, named assignments or a JSON/CSV file. The variable order is displayed beside the input.
- **Karnaugh map:** the default feedback view. Choose the P+, N− or erase brush from the side palette and click or drag over cells. Shading describes the original classifier; markers describe the target. Switching to pasted feedback shows the existing instances rather than blank boxes.

Pasted targets cannot conflict. Same-target duplicates are collapsed. Every assignment must specify every variable, and non-Boolean values are rejected. Text/file import replaces the current batch only after successful validation. A file is limited to 200 KB in the interface.

Examples for variables `a,b`:

```text
00
10
```

```json
{"positive": [{"a": false, "b": false}], "negative": [[true, true]]}
```

```csv
a,b,label
0,0,positive
1,1,negative
```

CSV columns may be reordered. Use `label`, `target` or `feedback` for the target column, choosing a name that is not already a classifier variable. JSON arrays and named objects must contain complete assignments.

## Bounds and algorithm choice

Enter loss bound ε and gain bound γ as exact fractions or decimals in [0,1], for example `0`, `1/3`, `0.5`, or `1`. The interface shows the corresponding integer limit before running the algorithm. Loss excludes requested negatives; gain excludes requested positives. Each limit is `floor(bound * size of original unrequested region)`, exactly as in the batch verifier.

**Automatic** uses the existing batch dispatcher: identity when feedback is already satisfied, ORD for no negative feedback and γ=1, independent negative revision for no positive feedback and ε=1, and BERD otherwise. You can explicitly choose ORD, the negative specialization, or BERD. Inapplicable specialized choices are disabled with their preconditions displayed. Changing the inputs after selecting an algorithm also checks its preconditions again.

The contradictory-original boundary is available through Automatic. It accepts exactly P and reports structural cost as undefined, consistent with the backend's source-free rule. It is not counted as a zero-cost source revision.

## Resolution and choices

After solving, **Follow this run** lets you select recorded execution steps or move through them with Previous/Next and a slider. These are actual observation events from the solver. ORD shows queried positive groups, minimum distances, tied source counts, a witness weakening, and equality-achieving subset transitions. Negative revision shows the safe/conflicting partition and literal-indexed repair queries. BERD shows exact excess levels, source/descendant query profiles and model counts, candidate bundles, baseline action domains, guaranteed versus possible coverage, outstanding witnesses, forced actions, LOST branches, cache reuse, pruning and feasible terminals.

Each event includes its example-specific table and relevant map frames. Intermediate maps are explicitly labelled as a partial state or source/descendant cylinder, not a completed revision. Algorithm notes remain expandable below the worked viewer. The log retains up to 400 diagnostic events and the final optimum; any omitted event count is displayed. This display limit never truncates the compiled optimal plan family. The running indicator still reports coarse worker phases until exact optimization completes.

Choices show edited source reasons, their descendants (or deletion), bundle cost, and unintended loss/gain with their allowed limits. Omitted sources stay unchanged. Identity is stated explicitly. Distinct source-indexed plans remain separate even when they produce the same classifier; equivalent results are labelled without merging them.

Every batch choice and unary reason has compact **Original → Revised** maps below its description, before selection. Both final views use the same map component. The instance-picker and final maps show complete prime-implicant families as unfilled coloured rectangles. Colours are stable for the same term across maps. A wrapping reason uses matching fragments across opposite edges or panels. Hover/focus a legend item to isolate it, or toggle outlines individually. Compact legends stay collapsed until opened. Original-classifier painting has no PI overlay; its region is still being defined.

Complete PI extraction for display is restricted to map-sized classifiers (1 through 6 variables), using the existing implicit PI backend on an explicit display request or after optimization. Revised-function visualizations are cached without merging source-indexed plans. The research solvers do not require this display enumeration. Search-state frames outline only the named witness when relevant; feedback and final maps contain every PI of their displayed classifiers.

The first page contains up to 8 choices. **Load more optimal choices** resumes the same lazy iterator. Counts are exact compiled counts where the backend supplies them, or exact once enumeration is exhausted. Otherwise the count remains unknown. A displayed page is never claimed to be the complete family.

Select a choice to see a verified preview: changed regions on a Karnaugh map, the original/revised truth table with feedback markers, DNF/CNF formulas, and an expandable BDD. Added/removed totals include requested corrections; loss/gain exclude them. Changing committed classifier, feedback, bounds or algorithm clears stale results and cancels the worker. Selection does not overwrite the original classifier or write a revised dataset.

## Interactive resource limits

The batch UI supports 1 through 8 variables; maps support up to 6. Exact solving can still be expensive at small sizes. Each batch session runs in an isolated spawned process, with a default 60-second deadline per solve/page/preview operation, adjustable to 300 seconds. Its monitor observes a 512 MiB RSS limit. There are four session slots; sessions expire after 30 minutes without worker activity. Cancel terminates the process.

Timeout, memory-limit, cancellation and worker errors are reported separately from revision feasibility. Paging or preview failure retains already displayed choices but requires a new run to continue after a worker stops. These interactive guards do not restrict the batch library or experiment runners. No research benchmarks are launched by the GUI or these tests.

## Architecture

| Module | Responsibility |
| --- | --- |
| `app/src/App.tsx` | Framework chooser and independent workspace mounting |
| `app/src/UnaryWorkspace.tsx` | Existing unary input/trace/reason/application flow, with map instance selection |
| `app/src/BatchWorkspace.tsx` | Bounds, algorithm eligibility, worker polling/cancellation, choices and previews |
| `app/src/components/BatchTraceView.tsx` | Recorded per-example solver steps, navigation, tables and intermediate maps |
| `app/src/components/InputPanel.tsx` | Shared classifier inputs and framework-specific examples |
| `ClassifierMap.tsx`, `EditableKmap.tsx` | Classifier scratchpad, Gray maps, pointer/keyboard input and feedback overlays |
| `FeedbackEditor.tsx`, `app/src/lib/feedback.ts` | One feedback model, strict import, exact rational thresholds and map indexing |
| `app/src/lib/api.ts` | Shared CNF contract and typed unary/batch API client |
| `inputViews.ts`, `mapGeometry.ts`, `useVisualization.ts` | Lossless input conversion, exact Gray-grid PI fragments and original-reason loading |
| `app/src/components/MiniRevisionMaps.tsx` | Shared compact before/after views for unary and batch choices |
| `server/rgr_web/app.py` | Existing unary endpoints and registration of batch routes |
| `server/rgr_web/batch_routes.py` | Validated classifier/map and batch session endpoints |
| `server/rgr_web/batch_jobs.py` | Isolated workers, phase polling, deadlines, memory observation and cancellation |
| `server/rgr_web/batch_session.py` | Existing batch-library adapter, lazy plans, explanations, verifier and previews |
| `server/rgr_web/batch_trace.py`, `visualization.py` | Bounded actual execution records and exact map PI data for both frameworks |

The shared transport is `{nvars, var_names, clauses}`, with signed one-based CNF literals. It is compiled separately into the selected backend. Batch code imports `batch_revision`, not unary `src/` functions. The unary solver remains unchanged. Batch solvers have an optional `observer` callback that reports actual operations without changing search, pruning, cost, or plan identity. CLI/experiment callers leave it unset.

Python function signatures in batch sources, experiments and the new batch web modules use plain parameters without annotations. Dataclass fields and Pydantic request fields retain the declarations needed for model construction and validation. Web request validation remains explicit even without annotated route parameters.

API lifecycle: `POST /api/batch/jobs`, poll `GET /api/batch/jobs/{id}`, page `GET /api/batch/jobs/{id}/choices?offset=...&limit=...`, preview `GET /api/batch/jobs/{id}/choices/{choice_id}`, cancel `DELETE /api/batch/jobs/{id}`. IDs refer only to issued plans in that session. `POST /api/classifier/from-table` commits accepted bitstrings for either framework; `POST /api/classifier/visualization` returns complete original PI overlays for small maps. Existing unary endpoints keep their original fields and additionally return choice/final visualization data.

## Validation

From `web/server`, using the installed test extra:

```powershell
python -m pytest -q
```

From `web/app`:

```powershell
npm test
npm run typecheck
npm run build
```

Backend tests compare complete GUI plan families with the independent exhaustive oracle, check preservation/splitting, exact counts and provenance, painted constants, invalid requests, unary regression, real process paging/preview/cancel, and time/memory stops. Frontend tests check import formats, conflicts, exact bounds, specialization preconditions and every map assignment for 1 through 6 variables. Python's asynchronous tests and local servers require loopback networking on Windows.

The Graphviz renderer and KaTeX are the existing frontend dependencies. KaTeX styles currently load from the CDN configured in `app/index.html`. The production build retains the existing large graph-rendering dependency and may report a chunk-size warning.
