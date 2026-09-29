"""FastAPI backend for the RGR web UI."""
from __future__ import annotations

import random
from typing import Any, Dict, List

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .parse import parse_any
from .trace import build_trace, apply_revision

from itertools import product

app = FastAPI(title="RGR web")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ParseReq(BaseModel):
    mode: str
    text: str


class RandomReq(BaseModel):
    nvars: int = 5
    density: float = 4.26
    seed: int | None = 10


class ReviseReq(BaseModel):
    nvars: int
    var_names: List[str]
    clauses: List[List[int]]
    omega: Dict[str, bool]


class ApplyReq(ReviseReq):
    reason: Dict[str, bool]


@app.post("/api/parse")
def parse_endpoint(req: ParseReq):
    try:
        nvars, names, clauses = parse_any(req.mode, req.text)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"nvars": nvars, "var_names": names, "clauses": clauses}


@app.post("/api/random")
def random_endpoint(req: RandomReq):
    rng = random.Random(req.seed)
    nvars = max(2, min(req.nvars, 8))
    nclauses = max(1, round(req.density * nvars))
    names = [chr(ord('a') + i) for i in range(nvars)]
    clauses = []
    for _ in range(nclauses):
        k = min(3, nvars)
        vs = rng.sample(range(1, nvars + 1), k)
        clauses.append([v if rng.random() < 0.5 else -v for v in vs])
    return {"nvars": nvars, "var_names": names, "clauses": clauses}


@app.get("/api/examples")
def examples_endpoint():
    return {"examples": _collect_examples()}


@app.post("/api/revise/cegmhs")
def revise_cegmhs(req: ReviseReq):
    omega = _omega_from_names(req.omega, req.var_names)
    try:
        return build_trace(req.nvars, req.var_names, req.clauses, omega, algorithm="cegmhs")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"pipeline error: {e}")


@app.post("/api/apply")
def apply_endpoint(req: ApplyReq):
    omega = _omega_from_names(req.omega, req.var_names)
    reason = _omega_from_names(req.reason, req.var_names)
    try:
        return apply_revision(req.nvars, req.var_names, req.clauses, omega, reason)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"apply error: {e}")


# --------------------------------------------------------------------- helpers

 




def _omega_from_names(obj: Dict[str, bool], names: List[str]) -> Dict[int, bool]:
    return {names.index(k) + 1: bool(v) for k, v in obj.items() if k in names}


def _clauses_to_cnf_text(clauses: List[List[int]], names: List[str]) -> str:
    """Serialize a clause list into the `parse_cnf` text format."""
    lines = []
    for c in clauses:
        toks = []
        for l in c:
            n = names[abs(l) - 1]
            toks.append(n if l > 0 else f"~{n}")
        lines.append(" ".join(toks))
    return "\n".join(lines) + "\n"


def _collect_examples() -> List[Dict[str, Any]]:
    """Union of: hardcoded demo classifiers, the two paper examples, and every
    entry from data/examples/examples.json (loaded via rgr.dataset).
    """
    out: List[Dict[str, Any]] = []
    out.extend(_PAPER_EXAMPLES)
    out.extend(_BUILTIN_EXAMPLES)
    out.extend(_dataset_examples())
    return out


DATASET_MAX_NVARS = 6

def _dataset_examples() -> List[Dict[str, Any]]:
    try:
        from rgr.dataset import load_examples, build_example
        from rgr.sdd_utils import term_to_sdd
    except Exception:
        return []
    try:
        raw = load_examples()
    except Exception:
        return []
 
    out: List[Dict[str, Any]] = []
    for i, ex in enumerate(raw):
        try:
            nvars = int(ex["nvars"])
        except (KeyError, TypeError, ValueError):
            continue
        if nvars > DATASET_MAX_NVARS:
            continue
 
        try:
            mgr, sdd, ex_norm = build_example(ex)
        except Exception:
            continue
 
        # accepting rows -> CNF clauses
        try:
            clauses = _sdd_to_cnf_clauses(sdd, mgr, nvars, term_to_sdd)
        except Exception:
            continue
 
        names = ex.get("var_names") or [chr(ord('a') + j) for j in range(nvars)]
        eid = ex.get("id") or ex.get("name") or f"dataset_{i}"
        label = ex.get("label") or ex.get("name") or eid
 
        # omega hint: prefer the first stored test instance if present
        omega_hint: Dict[str, bool] = {}
        tests = ex_norm.get("test_instances") if isinstance(ex_norm, dict) else None
        if tests:
            first = tests[0]
            for var_idx, val in first.items():
                if 1 <= int(var_idx) <= nvars:
                    omega_hint[names[int(var_idx) - 1]] = bool(val)
 
        out.append({
            "id": f"dataset_{eid}",
            "label": f"dataset · {label}",
            "mode": "cnf",
            "text": _clauses_to_cnf_text(clauses, names),
            "nvars": nvars,
            "var_names": names,
            "clauses": clauses,
            "omega_hint": omega_hint,
        })
    return out
 
 
def _sdd_to_cnf_clauses(sdd, mgr, nvars: int, term_to_sdd) -> List[List[int]]:
    """Enumerate accepting rows of the SDD, then use sympy to derive a CNF."""
    from sympy import symbols, Not, Or, And
    from sympy.logic.boolalg import to_cnf
 
    accepting = []
    for bits in product([False, True], repeat=nvars):
        assignment = {j + 1: bits[j] for j in range(nvars)}
        if not (term_to_sdd(assignment, mgr) & sdd).is_false():
            accepting.append(bits)
 
    if not accepting:
        return [[1], [-1]]                   # ⊥ - unsatisfiable
    if len(accepting) == 2 ** nvars:
        return []                            # ⊤ - no constraints
 
    syms = symbols([f"x{j+1}" for j in range(nvars)])
    minterms = []
    for bits in accepting:
        conj = [s if b else Not(s) for s, b in zip(syms, bits)]
        minterms.append(And(*conj) if len(conj) > 1 else conj[0])
    dnf = Or(*minterms) if len(minterms) > 1 else minterms[0]
    cnf = to_cnf(dnf, simplify=True, force=True)
 
    def lit_to_int(node) -> int:
        if node.func is Not:
            v = int(str(node.args[0])[1:])
            return -v
        return int(str(node)[1:])
 
    def clause_to_list(node) -> List[int]:
        if node.func is Or:
            return [lit_to_int(a) for a in node.args]
        return [lit_to_int(node)]
 
    if cnf.func is And:
        return [clause_to_list(c) for c in cnf.args]
    return [clause_to_list(cnf)]
 

# ------------------------------------------------------------- static examples

# The two paper-adjacent examples the user asked to pin.
_PAPER_EXAMPLES: List[Dict[str, Any]] = [
    {
        # (d ∨ ¬b) ∧ (a ∨ d ∨ ¬c) ∧ (c ∨ d ∨ ¬a) ∧ (a ∨ b ∨ c ∨ ¬d) ∧ (¬a ∨ ¬c ∨ ¬d)
        "id": "cnf_4var_demo",
        "label": "4-var CNF ((d ∨ ¬b) ∧ … ∧ (¬a ∨ ¬c ∨ ¬d))",
        "mode": "cnf",
        "text": (
            "# (d ∨ ¬b) ∧ (a ∨ d ∨ ¬c) ∧ (c ∨ d ∨ ¬a) ∧ (a ∨ b ∨ c ∨ ¬d) ∧ (¬a ∨ ¬c ∨ ¬d)\n"
            "d ~b\n"
            "a d ~c\n"
            "c d ~a\n"
            "a b c ~d\n"
            "~a ~c ~d\n"
        ),
        "nvars": 4,
        "var_names": ["a", "b", "c", "d"],
        "clauses": [
            [4, -2],
            [1, 4, -3],
            [3, 4, -1],
            [1, 2, 3, -4],
            [-1, -3, -4],
        ],
        "omega_hint": {"a": False, "b": False, "c": True, "d": False},
    },
    {
        # From the ReasonsFromModel appendix example.
        # Δ = (a ∧ b) ∨ (c ∧ d) ∨ (¬a ∧ ¬c), ω = ¬a ¬b c ¬d.
        # CNF (via sympy simplification):
        #   (¬a ∨ b) ∧ (¬a ∨ d) ∧ (b ∨ ¬c) ∧ (¬c ∨ d)
        "id": "paper_appendix",
        "label": "appendix example ((a∧b) ∨ (c∧d) ∨ (¬a∧¬c))",
        "mode": "formula",
        "text": "(a & b) | (c & d) | (~a & ~c)",
        "nvars": 4,
        "var_names": ["a", "b", "c", "d"],
        "clauses": [
            [-1, 2],
            [-1, 4],
            [2, -3],
            [-3, 4],
        ],
        "omega_hint": {"a": False, "b": False, "c": True, "d": False},
    },
]


# The original toy set (kept from earlier revisions of the UI).
_BUILTIN_EXAMPLES: List[Dict[str, Any]] = [
    {
        "id": "ab_or_cd",
        "label": "(a ∧ b) ∨ (c ∧ d)",
        "mode": "formula",
        "text": "(a & b) | (c & d)",
        "nvars": 4,
        "var_names": ["a", "b", "c", "d"],
        "clauses": [[1, 3], [1, 4], [2, 3], [2, 4]],
        "omega_hint": {"a": False, "b": False, "c": True, "d": False},
    },
    {
        "id": "loan_toy",
        "label": "loan approval",
        "mode": "cnf",
        "text": ("income savings\nincome stable_job\n"),
        "nvars": 3,
        "var_names": ["income", "savings", "stable_job"],
        "clauses": [[1, 2], [1, 3]],
        "omega_hint": {"income": False, "savings": True, "stable_job": False},
    },
    {
        "id": "xor3",
        "label": "3-var XOR (odd parity)",
        "mode": "truth",
        "text": ("a b c label\n0 0 0 0\n0 0 1 1\n0 1 0 1\n0 1 1 0\n"
                 "1 0 0 1\n1 0 1 0\n1 1 0 0\n1 1 1 1\n"),
        "nvars": 3,
        "var_names": ["a", "b", "c"],
        "clauses": [[1, 2, 3], [-1, -2, 3], [-1, 2, -3], [1, -2, -3]],
        "omega_hint": {"a": True, "b": True, "c": True},
    },
]