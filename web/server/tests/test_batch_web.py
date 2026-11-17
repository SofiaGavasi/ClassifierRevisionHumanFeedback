"""Exercise the GUI adapter against the independent oracle and the real unary and worker APIs."""
from itertools import product
import time

import pytest
from fastapi.testclient import TestClient
from rgr_web.app import app
from rgr_web.batch_jobs import BatchJob, BatchJobs
from rgr_web.batch_routes import batch_examples, jobs
from rgr_web.batch_session import BatchSession, classifier_from_table, cnf_formula
from batch_revision import Budgets, Feedback
from batch_revision.datasets import compile_formula
from batch_revision.oracle import exhaustive_optima


@pytest.fixture
def client():
    """Clean up all actual worker processes even when a request assertion fails."""
    with TestClient(app) as value:
        yield value
    jobs.close()


def request_data(**changes):
    """Build a small satisfiable default input with one requested positive correction."""
    return dict(nvars=2, var_names=["a", "b"], clauses=[[1], [2]],
                positive=[[False, False]], negative=[], epsilon="1", gamma="1", algorithm="auto") | changes


def wait_ready(client, job_id):
    """Poll a real spawned process with a bounded test deadline rather than mocking solver output."""
    deadline = time.monotonic()+20
    while time.monotonic() < deadline:
        value = client.get(f"/api/batch/jobs/{job_id}").json()
        if value["status"] != "running":
            assert value["status"] == "ready", value
            return value["result"]
        time.sleep(0.03)
    pytest.fail("Interactive worker did not complete within the test deadline")


@pytest.mark.parametrize("n", range(1, 5))
def test_painted_table_preserves_exact_universe(n):
    """Painting compiles true, false and selected regions without dropping unused features."""
    names = [f"v{i}" for i in range(n)]
    points = tuple(product((False, True), repeat=n))
    keys = ["".join(str(int(b)) for b in p) for p in points]
    for selected in ([], keys, keys[::2], keys[1:3]):
        data = classifier_from_table(names, selected)
        original = compile_formula(n, cnf_formula(data["clauses"]))
        assert original.nvars == n
        assert [original(p) for p in points] == [key in selected for key in keys]


@pytest.mark.parametrize("algorithm,positive,negative,epsilon,gamma", [
    ("auto", [], [], "0", "0"),
    ("ord", [[0, 0]], [], "1", "1"),
    ("negative", [], [[1, 1]], "1", "1"),
    ("berd", [[0, 0]], [[1, 1]], "1", "1"),
    ("auto", [[0, 0]], [[1, 1]], "0", "0"),
    ("berd", [[0, 0]], [[1, 1]], "1/2", "1/3"),
    ("ord", [[1, 1]], [], "0", "1"),
    ("negative", [], [[0, 0]], "1", "0"),
    ("berd", [], [], "0", "0"),
])
def test_web_choices_equal_independent_oracle(algorithm, positive, negative, epsilon, gamma):
    """All displayed choices are exactly the oracle's tied source-indexed optima, not function classes."""
    session = BatchSession(request_data(algorithm=algorithm, positive=positive, negative=negative, epsilon=epsilon, gamma=gamma))
    page = session.page(limit=1)
    while page["has_more"]:
        page = session.page(page["next_offset"], limit=1)
    original = session.original
    truth = tuple(original(p) for p in product((False, True), repeat=2))
    oracle = exhaustive_optima(2, truth, Feedback(2, positive, negative), Budgets(epsilon, gamma))
    assert session.result.optimum_cost == oracle.optimum_cost
    assert frozenset(session.plans) == oracle.plans
    assert len(session.plans) == len(set(session.plans))
    assert page["total_plans"] == str(len(oracle.plans))
    assert session.page(0, 1)["choices"][0]["id"] == 0
    for index in range(len(session.plans)):
        preview = session.apply(index)
        assert preview["positive_success"] and preview["negative_success"]
        assert preview["choice"]["cost"] == oracle.optimum_cost
        rows = preview["truth_table"]["rows"]
        assert preview["added_count"] == sum(not r["old"] and r["new"] for r in rows)
        assert preview["removed_count"] == sum(r["old"] and not r["new"] for r in rows)


def test_provenance_ties_are_not_merged():
    """Equivalent revised truth tables retain their separate source-indexed identities."""
    examples = batch_examples()
    ex = next(e for e in examples if e["id"] == "positive_ties")
    session = BatchSession(dict(ex, positive=ex["positive_hint"], negative=ex["negative_hint"], **ex["budgets"]))
    page = session.page(limit=20)
    assert int(page["total_plans"]) >= 2
    assert len({p for p in session.plans}) == len(session.plans)
    assert any(c["equivalent_to"] is not None for c in page["choices"])


def test_strict_splitting_example():
    """The interface exposes the strict negative splitting case with its genuine continuation cost."""
    ex = next(e for e in batch_examples() if e["id"] == "strict_negative_split")
    session = BatchSession(dict(ex, positive=ex["positive_hint"], negative=ex["negative_hint"], **ex["budgets"]))
    page = session.page(limit=20)
    assert session.metadata()["minimum_cost"] == 5
    assert all(choice["loss"] == 0 for choice in page["choices"])
    assert any(len(edit["descendants"]) > 1 for choice in page["choices"] for edit in choice["edits"])


def test_contradictory_original_uses_semantic_boundary():
    """No original source means a semantic boundary, without a fabricated structural optimum."""
    session = BatchSession(request_data(clauses=[[]], gamma="0", epsilon="0"))
    page = session.page()
    assert session.metadata()["minimum_cost"] is None
    assert session.metadata()["solve_status"] == "SEMANTIC_BOUNDARY"
    assert page["total_plans"] == "1"
    preview = session.apply(0)
    assert preview["new_count"] == 1
    assert preview["positive_success"] and preview["negative_success"]
    assert page["choices"][0]["source_free"]
    with pytest.raises(ValueError, match="Automatic"):
        BatchSession(request_data(clauses=[[]], algorithm="berd"))


@pytest.mark.parametrize("changes", [
    {"negative": [[0, 0]]}, {"positive": [[0]]}, {"positive": [[0, 2]]},
    {"positive": [["false", "true"]]}, {"clauses": [[0]]}, {"clauses": [[3]]},
    {"var_names": ["a", "a"]}, {"nvars": 9}, {"gamma": "1/0"},
    {"epsilon": "1.1"}, {"algorithm": "ord", "gamma": "1/2"},
    {"algorithm": "ord", "negative": [[1, 1]]}, {"algorithm": "negative"},
    {"algorithm": "negative", "positive": [], "epsilon": "0"},
])
def test_api_rejects_invalid_requests_before_search(client, changes):
    """Malformed input and invalid specialization assumptions cannot reach an exact worker."""
    response = client.post("/api/batch/jobs", json=request_data(**changes))
    assert response.status_code == 422, response.text


def test_map_api_and_examples(client):
    """Both workspaces use the same painted classifier contract and actual batch examples."""
    response = client.post("/api/classifier/from-table", json={"var_names": ["a", "b"], "accepting": ["11"]})
    assert response.status_code == 200
    assert response.json()["nvars"] == 2
    assert client.post("/api/classifier/from-table", json={"var_names": ["a", "a"], "accepting": []}).status_code == 400
    assert client.post("/api/classifier/from-table", json={"var_names": ["a"], "accepting": ["11"]}).status_code == 400
    examples = client.get("/api/batch/examples").json()["examples"]
    assert len(examples) == 16
    assert all("budgets" in e and "positive_hint" in e and "negative_hint" in e for e in examples)


def test_actual_process_api_paging_preview_and_cancel(client):
    """The complete HTTP lifecycle uses a spawned solver, stable identifiers and verified previews."""
    response = client.post("/api/batch/jobs", json=request_data())
    assert response.status_code == 202
    job_id = response.json()["id"]
    result = wait_ready(client, job_id)
    assert result["algorithm"] == "ORD"
    assert result["minimum_cost"] == 2
    page = client.get(f"/api/batch/jobs/{job_id}/choices?offset=0&limit=1").json()
    assert page["choices"][0]["id"] == 0
    value = client.get(f"/api/batch/jobs/{job_id}/choices/0").json()
    assert value["positive_success"] and value["negative_success"]
    assert client.get(f"/api/batch/jobs/{job_id}/choices/99999").status_code == 409
    assert client.get(f"/api/batch/jobs/{job_id}/choices?offset=99999").status_code == 409
    assert client.delete(f"/api/batch/jobs/{job_id}").json()["status"] == "cancelled"
    assert client.get(f"/api/batch/jobs/{job_id}/choices").status_code == 409
    assert client.get("/api/batch/jobs/not-issued").status_code == 404


@pytest.mark.parametrize("limits,expected", [({"timeout": 0.001}, "timeout"), ({"memory_mb": 0.001}, "memory_limit")])
def test_process_limits_stop_actual_workers(limits, expected):
    """Time and memory stops are explicit statuses rather than infeasibility claims."""
    job = BatchJob(request_data(), **limits)
    try:
        assert job.stopped.wait(10)
        job.thread.join(5)
        assert job.snapshot()["status"] == expected
        assert not job.process.is_alive()
    finally:
        job.cancel()


def test_manager_capacity_and_cleanup():
    """Cancelled workers release their capacity before the next interactive run."""
    manager = BatchJobs(max_jobs=1)
    try:
        first = manager.start(request_data())
        with pytest.raises(ValueError, match="slots"):
            manager.start(request_data())
        first.cancel()
        second = manager.start(request_data())
        assert second.id != first.id
    finally:
        manager.close()


def test_unary_endpoints_still_compute_and_apply(client):
    """The original unary parser, reason trace and application endpoints remain usable."""
    parsed = client.post("/api/parse", json={"mode": "formula", "text": "a & b"})
    assert parsed.status_code == 200
    data = parsed.json() | {"omega": {"a": False, "b": True}}
    trace = client.post("/api/revise/cegmhs", json=data)
    assert trace.status_code == 200, trace.text
    reasons = next(s for s in trace.json()["steps"] if s["name"] == "reasons")["data"]["reasons"]
    assert reasons
    response = client.post("/api/apply", json=data | {"reason": reasons[0]["assignment"]})
    assert response.status_code == 200, response.text
    assert response.json()["accepts_omega"]
