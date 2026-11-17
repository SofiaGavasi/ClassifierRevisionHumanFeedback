"""Independent checks for displayed PI families, unary/batch choice maps and actual diagnostic events."""
import ast
from itertools import product
from pathlib import Path
import random

from fastapi.testclient import TestClient
from batch_revision import Budgets, Feedback, solve
from batch_revision.datasets import compile_formula
from batch_revision.oracle import brute_primes
from rgr_web.app import app
from rgr_web.batch_session import BatchSession
from rgr_web.batch_trace import BatchTraceRecorder
from rgr_web.visualization import visualize_values


def test_displayed_pis_match_independent_truth_table_oracle():
    """No missing or nonprime reason can become an outline, including constants and unused features."""
    rng = random.Random(42)
    for n in range(1, 5):
        names = [f"v{i}" for i in range(n)]
        truth_vectors = [[False]*2**n, [True]*2**n]
        truth_vectors += [[bool(rng.getrandbits(1)) for _ in range(2**n)] for _ in range(12)]
        for truth in truth_vectors:
            view = visualize_values(names, truth)
            expected = {tuple(term.states) for term in brute_primes(n, truth)}
            assert {tuple(reason["states"]) for reason in view["reasons"]} == expected
            assert view["accepted"] == truth and view["reason_count"] == len(expected)


def test_unary_choice_maps_equal_actual_reason_application():
    """Every displayed mini-map is checked against the unchanged unary apply operation."""
    with TestClient(app) as client:
        for clauses in ([[1], [2]], [[1, 2]]):
            data = {"nvars": 2, "var_names": ["a", "b"], "clauses": clauses, "omega": {"a": False, "b": False}}
            response = client.post("/api/revise/cegmhs", json=data)
            assert response.status_code == 200, response.text
            trace = response.json()
            reasons = next(step["data"]["reasons"] for step in trace["steps"] if step["name"] == "reasons")
            for reason in reasons:
                applied = client.post("/api/apply", json=data | {"reason": reason["assignment"]}).json()
                assert reason["visualization"] == applied["visualization"]
                assert applied["visualization"]["accepted"] == [row["new"] for row in applied["truth_table"]["rows"]]


def test_loaded_original_pi_endpoint_preserves_named_universe():
    """The instance-picker receives the complete original family with the exact loaded feature names."""
    with TestClient(app) as client:
        value = client.post("/api/classifier/visualization", json={"nvars": 3, "var_names": ["income", "saving", "job"], "clauses": [[1]]})
        assert value.status_code == 200, value.text
        data = value.json()
        assert data["vars"] == ["income", "saving", "job"]
        assert data["reasons"][0]["states"] == [1, 0, 0]
        assert data["reasons"][0]["text"] == "income"


def test_batch_choice_maps_are_complete_new_classifier_pi_families():
    """Output outlines are PIs of the revised function, including when descendants are not themselves prime."""
    session = BatchSession({"nvars": 2, "var_names": ["a", "b"], "clauses": [[1,2]], "positive": [[0,0]], "negative": [], "epsilon": "1", "gamma": "1"})
    page = session.page()
    assert len(page["choices"]) == 2
    for choice in page["choices"]:
        view = choice["visualization"]
        assert view["accepted"] == [True]*4
        assert [r["states"] for r in view["reasons"]] == [[0,0]]
        assert view == session.apply(choice["id"])["visualization"]


def test_berd_observer_records_real_witness_branches_and_preserves_all_optima():
    """Observation must leave exact plans, cost and solver work counters unchanged."""
    original = compile_formula(2, {"op": "or", "xs": [{"op": "var", "v": 1}, {"op": "var", "v": 2}]})
    feedback, budgets = Feedback(2, negative=[[1,1]]), Budgets("1/2", "1")
    plain = solve(original, feedback, budgets, algorithm="berd")
    events = []
    observed = solve(original, feedback, budgets, algorithm="berd", observer=lambda kind, values: events.append((kind, values)))
    assert observed.optimum_cost == plain.optimum_cost == 2
    assert set(observed.plans()) == set(plain.plans())
    assert observed.statistics == plain.statistics
    kinds = [kind for kind, _ in events]
    assert {"excess_level", "baseline_witness", "baseline_force", "baseline_lost", "baseline_terminal", "optimum"} <= set(kinds)
    witness = next(values for kind, values in events if kind == "baseline_witness")
    assert tuple(witness["point"]) in ((False, True), (True, False))
    assert events[-1][1]["cost"] == observed.optimum_cost


def test_actual_ord_trace_contains_specific_groups_costs_and_equality_transitions():
    """The step viewer receives computed data for this example rather than generic descriptions."""
    session = BatchSession({"nvars": 2, "var_names": ["a", "b"], "clauses": [[1,2]], "positive": [[0,0]], "negative": [], "epsilon": "1", "gamma": "1"})
    session.page()
    trace = session.metadata()["trace"]
    group = next(event for event in trace["events"] if event["kind"] == "ord_group")
    assert "00" in group["title"] and "distance 1" in group["summary"]
    assert len(group["frames"]) == 2
    state = next(event for event in trace["events"] if event["kind"] == "ord_state")
    assert state["rows"][0]["Total"] == 1
    assert trace["events"][-1]["kind"] == "optimum"


def test_bounded_event_display_does_not_truncate_optimal_plan_families():
    """The diagnostic limit is explicit and retains the exact final optimum event."""
    from batch_revision import PrimeFamily
    original = compile_formula(2, {"op": "or", "xs": [{"op": "var", "v": 1}, {"op": "var", "v": 2}]})
    feedback, budgets = Feedback(2, negative=[[1,1]]), Budgets("1/2", "1")
    family = PrimeFamily(original)
    recorder = BatchTraceRecorder(original, ["a", "b"], feedback, budgets, family, limit=3)
    result = solve(original, feedback, budgets, algorithm="berd", observer=recorder, family_factory=lambda _: family)
    trace = recorder.export()
    assert len(trace["events"]) == 3 and trace["omitted_events"] > 0
    assert trace["events"][-1]["kind"] == "optimum"
    assert trace["total_events"] == len(trace["events"])+trace["omitted_events"]
    assert len(set(result.plans())) == result.count_plans() == 3


def test_python_batch_function_signatures_have_no_annotations():
    """Plain function signatures coexist with the field annotations required by dataclasses and request schemas."""
    import batch_revision
    roots = [Path(batch_revision.__file__).parent, Path(__file__).resolve().parents[1] / "rgr_web"]
    for root in roots:
        for path in root.rglob("*.py"):
            if root.name == "rgr_web" and not (path.name.startswith("batch_") or path.name == "visualization.py"):
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    args = node.args.posonlyargs+node.args.args+node.args.kwonlyargs+[a for a in (node.args.vararg, node.args.kwarg) if a is not None]
                    assert node.returns is None and all(arg.annotation is None for arg in args), f"{path}:{node.lineno}"
