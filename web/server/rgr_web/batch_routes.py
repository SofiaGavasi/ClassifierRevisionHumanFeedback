"""Validated classifier painting and asynchronous batch API routes alongside the existing unary routes."""
from __future__ import annotations
from functools import lru_cache
from pathlib import Path
from typing import Literal
from fastapi import APIRouter, Body, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, ValidationError, model_validator
from .batch_jobs import BatchJobs
from .batch_session import classifier_from_table, validate_classifier


router = APIRouter(prefix="/api")
jobs = BatchJobs()


def validated(model, value):
    """Keep explicit Pydantic body validation while leaving Python function signatures unannotated."""
    try:
        return model.model_validate(value)
    except ValidationError as exc:
        detail = [dict(error, loc=["body", *error["loc"]]) for error in exc.errors(include_context=False)]
        raise HTTPException(422, detail) from exc


def integer_parameter(value, name, minimum=0, maximum=None):
    """Validate path/query numbers explicitly instead of relying on parameter type annotations."""
    try:
        parsed = int(value)
        if str(parsed) != str(value) or parsed < minimum or maximum is not None and parsed > maximum:
            raise ValueError
        return parsed
    except (TypeError, ValueError) as exc:
        raise HTTPException(422, f"{name} must be an integer from {minimum}"+(f" to {maximum}" if maximum is not None else "")) from exc


class NamedClassifier(BaseModel):
    """The shared named CNF format, limited to exact interactive-size classifiers."""
    model_config = ConfigDict(extra="ignore")
    nvars: int = Field(ge=1, le=8)
    var_names: list[str]
    clauses: list[list[StrictInt]]

    @model_validator(mode="after")
    def validate_universe(self):
        """Check names and literal bounds before starting a worker."""
        validate_classifier(self.model_dump())
        return self


class BatchRequest(NamedClassifier):
    """Explicit complete feedback and exact rational budget strings; no source edits are client-supplied."""
    positive: list[list[StrictBool | StrictInt]] = Field(default_factory=list, max_length=256)
    negative: list[list[StrictBool | StrictInt]] = Field(default_factory=list, max_length=256)
    epsilon: str = Field(default="1", max_length=128)
    gamma: str = Field(default="1", max_length=128)
    algorithm: Literal["auto", "ord", "negative", "berd"] = "auto"
    timeout_s: int = Field(default=60, ge=1, le=300)

    @model_validator(mode="after")
    def validate_feedback(self):
        """Reject conflicting feedback, partial instances and inapplicable specializations immediately."""
        from batch_revision import Feedback, Budgets
        feedback = Feedback(self.nvars, self.positive, self.negative)
        try:
            budgets = Budgets(self.epsilon, self.gamma)
        except (ZeroDivisionError, TypeError) as exc:
            raise ValueError("Semantic bounds must be fractions or decimals between 0 and 1 with nonzero denominators") from exc
        if self.algorithm == "ord" and (feedback.negative or budgets.gamma != 1):
            raise ValueError("ORD requires positive-only feedback and unrestricted gain (gamma=1)")
        if self.algorithm == "negative" and (feedback.positive or budgets.epsilon != 1):
            raise ValueError("Independent negative revision requires negative-only feedback and unrestricted loss (epsilon=1)")
        return self


class PaintedClassifier(BaseModel):
    """Complete accepted-cell bitstrings from the truth-table or Karnaugh-map editor."""
    var_names: list[str] = Field(min_length=1, max_length=8)
    accepting: list[str] = Field(max_length=256)


@router.post("/classifier/from-table")
def from_table(request=Body(...)):
    """Use exactly the painted accepted region as a classifier for either framework."""
    request = validated(PaintedClassifier, request)
    try:
        return classifier_from_table(request.var_names, request.accepting)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/classifier/visualization")
def classifier_visualization(request=Body(...)):
    """Return all original PIs for the loaded small map, independently of revision algorithm selection."""
    request = validated(NamedClassifier, request)
    from .visualization import visualize_cnf
    return visualize_cnf(request.model_dump())


@lru_cache(maxsize=1)
def batch_examples():
    """Adapt the actual handcrafted batch dataset without loading unary examples or inventing feedback."""
    from batch_revision.datasets import load_records, build_case
    from itertools import product
    path = Path(__file__).resolve().parents[3] / "batch/datasets/examples.json"
    output = []
    for record in load_records(path):
        if not 1 <= record["nvars"] <= 6:
            continue
        original, _ = build_case(record)
        names = [chr(97+i) for i in range(record["nvars"])]
        accepting = ["".join("1" if v else "0" for v in point) for point in product((False, True), repeat=record["nvars"]) if original(point)]
        classifier = classifier_from_table(names, accepting)
        text = "\n".join([" ".join(names+["label"])]+[" ".join(list(format(i, f"0{len(names)}b"))+["1" if format(i, f"0{len(names)}b") in accepting else "0"]) for i in range(2**len(names))])
        output.append(classifier | {"id": record["id"], "label": record["id"].replace("_", " "), "mode": "truth", "text": text,
                                   "omega_hint": {}, "description": record["description"], "positive_hint": record["positive"],
                                   "negative_hint": record["negative"], "budgets": record["budgets"]})
    return output


@router.get("/batch/examples")
def examples():
    """Provide examples with their real feedback and budgets for the batch input panel."""
    return {"examples": batch_examples()}


@router.post("/batch/jobs", status_code=202)
def start(request=Body(...)):
    """Start an exact process-isolated batch search without blocking the unary pipeline."""
    request = validated(BatchRequest, request)
    try:
        return jobs.start(request.model_dump()).snapshot()
    except ValueError as exc:
        raise HTTPException(429, str(exc)) from exc


def get_job(job_id):
    """Convert missing or expired session references into a clear API response."""
    try:
        return jobs.get(job_id)
    except KeyError as exc:
        raise HTTPException(404, str(exc.args[0])) from exc


@router.get("/batch/jobs/{job_id}")
def status(job_id):
    """Poll real phase information and the first page when a cost proof is ready."""
    return get_job(job_id).snapshot()


@router.delete("/batch/jobs/{job_id}")
def cancel(job_id):
    """Stop the actual worker when the user cancels or changes the revision inputs."""
    job = get_job(job_id)
    job.cancel()
    return job.snapshot()


@router.get("/batch/jobs/{job_id}/choices")
def choices(job_id, offset=Query(default="0"), limit=Query(default="8")):
    """Fetch more tied source-indexed plans without pretending a page is the whole optimum family."""
    offset, limit = integer_parameter(offset, "offset"), integer_parameter(limit, "limit", 1, 20)
    try:
        return get_job(job_id).call("page", offset=offset, limit=limit)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.get("/batch/jobs/{job_id}/choices/{choice_id}")
def apply(job_id, choice_id):
    """Preview an issued revision choice with its verified classifier and feedback-marked truth table."""
    choice_id = integer_parameter(choice_id, "choice_id")
    try:
        return get_job(job_id).call("apply", choice_id=choice_id)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
