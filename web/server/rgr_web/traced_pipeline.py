"""Trace-emitting reimplementation of `reasons_from_model` for the web UI.
Mirrors `rgr.reasons_from_model.reasons_from_model` step by step, but instead of just yielding PIs it returns a rich record with every intermediate state and every iteration of the hitting-set loop. 
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, FrozenSet, List, Set

from rgr.sdd_utils import term_to_sdd
from rgr.enumeration import (
    condition_sdd, mu_to_literals, flipped_literals,
    find_mandatory_core,
)
from rgr.enumeration.hitting_sets import (
    MinimalHittingSetEnumerator, MHSSearchLimitExceeded,
)


# ---------------------------------------------------------------- formatting

def _lit_latex(lit: int, names: List[str]) -> str:
    n = names[abs(lit) - 1]
    return n if lit > 0 else rf"\neg {n}"


def _lits_latex(lits: Set[int] | FrozenSet[int], names: List[str]) -> str:
    if not lits:
        return r"\emptyset"
    return r" \wedge ".join(_lit_latex(l, names) for l in sorted(lits, key=abs))


def _conflict_latex(conflict: Set[int], names: List[str]) -> str:
    if not conflict:
        return r"\emptyset"
    return "{" + ", ".join(_lit_latex(l, names) for l in sorted(conflict, key=abs)) + "}"


def _dot_of(sdd) -> str:
    try:
        return sdd.dot()
    except Exception:
        return 'digraph { node[shape=box]; "x" [label="SDD (dot unavailable)"]; }'


# --------------------------------------------------------------------- trace

def trace_reasons_from_model(sdd, mu, omega, mgr, nvars, names) -> Dict[str, Any]:
    """Run the pipeline on one nearest model μ and return a full trace."""
    # 1. F_μ ------------------------------------------------------------------
    F_mu = flipped_literals(mu, omega)
    d_star = len(F_mu)

    # 2. D_μ = D | F_μ --------------------------------------------------------
    residual = condition_sdd(sdd, mgr, F_mu)
    try:
        residual_size = residual.size()
    except AttributeError:
        residual_size = 0

    # 3. semantic support of D_μ ---------------------------------------------
    mu_term = mu_to_literals(mu)
    candidate_lits = mu_term - F_mu
    candidate_vars = {abs(l) for l in candidate_lits}
    residual_vars = _semantic_support(residual, mgr, candidate_vars)
    O_mu: Set[int] = {l for l in candidate_lits if abs(l) in residual_vars}
    dropped = candidate_lits - O_mu

    # 4. entailment / countermodel closures (over the residual) ---------------
    not_residual = ~residual

    def entails_raw(term_literals: Set[int]) -> bool:
        assignment = {abs(l): (l > 0) for l in term_literals}
        term_sdd = term_to_sdd(assignment, mgr) if assignment else mgr.true()
        return (term_sdd & not_residual).is_false()

    def counter_raw(term_literals: Set[int]) -> Dict[int, bool]:
        assignment = {abs(l): (l > 0) for l in term_literals}
        term_sdd = term_to_sdd(assignment, mgr) if assignment else mgr.true()
        anti = term_sdd & not_residual
        for model in anti.models():
            return {v: bool(model[v]) for v in residual_vars if v in model}
        return {}

    # 5. N_μ (necessary conditions) ------------------------------------------
    N_mu: Set[int] = find_mandatory_core(O_mu, entails_raw)

    # per-literal witnesses for the panel
    N_witnesses = []
    for lit in sorted(O_mu, key=abs):
        reduced = O_mu - {lit}
        entailed = entails_raw(reduced)
        N_witnesses.append({
            "literal_latex": _lit_latex(lit, names),
            "in_N": lit in N_mu,
            "reduced_entails": entailed,
            "reduced_latex": _lits_latex(reduced, names),
        })

    # 6. U_μ ------------------------------------------------------------------
    U_mu: Set[int] = O_mu - N_mu

    # 7. hitting-set loop, instrumented ---------------------------------------
    iterations: List[Dict[str, Any]] = []
    yielded_pis: List[Set[int]] = []
    conflict_family: List[Set[int]] = []
    blocked_family: List[Set[int]] = []

    mhs = MinimalHittingSetEnumerator(U_mu)
    truncated_reason = None
    try:
        while True:
            cand = mhs.next_candidate()
            if cand is None:
                break
            A = set(cand)

            step: Dict[str, Any] = {
                "A_latex": _lits_latex(A, names),
                "A_size": len(A),
            }
            test_set = A | N_mu
            if entails_raw(test_set):
                tau = F_mu | N_mu | A
                yielded_pis.append(tau)
                mhs.add_blocked_pi(A)
                blocked_family.append(A)
                step.update({
                    "verdict": "yield",
                    "tau_latex": _lits_latex(tau, names),
                    "blocked_added_latex": _lits_latex(A, names),
                })
            else:
                nu = counter_raw(test_set)
                conflict = {l for l in U_mu if _falsifies(l, nu)}
                mhs.add_conflict(conflict)
                mhs.branch(frozenset(A), conflict)
                conflict_family.append(conflict)
                nu_readable = {
                    names[v - 1]: bool(nu[v]) for v in sorted(nu)
                }
                step.update({
                    "verdict": "conflict",
                    "nu": nu_readable,
                    "conflict_latex": _conflict_latex(conflict, names),
                })
            step["conflict_family_size"] = len(conflict_family)
            step["blocked_family_size"] = len(blocked_family)
            iterations.append(step)
    except MHSSearchLimitExceeded as e:
        truncated_reason = str(e)

    # ------------------------------------------------------------------- pack
    return {
        "mu_latex": _lits_latex(mu_term, names),

        "F_mu": {
            "latex": _lits_latex(F_mu, names),
            "size": len(F_mu),
            "d_star": d_star,
        },

        "D_mu": {
            "size": residual_size,
            "dot": _dot_of(residual),
            "vars_in_support": sorted(residual_vars),
            "vars_dropped": sorted(candidate_vars - residual_vars),
        },
        "D_original_dot": _dot_of(sdd),

        "O_mu": {
            "latex": _lits_latex(O_mu, names),
            "size": len(O_mu),
            "dropped_by_support_latex": _lits_latex(dropped, names),
        },

        "N_mu": {
            "latex": _lits_latex(N_mu, names),
            "size": len(N_mu),
            "witnesses": N_witnesses,
        },

        "U_mu": {
            "latex": _lits_latex(U_mu, names),
            "size": len(U_mu),
        },

        "iterations": iterations,
        "final_conflicts": [_conflict_latex(c, names) for c in conflict_family],
        "final_blocked": [_lits_latex(b, names) for b in blocked_family],
        "truncated_reason": truncated_reason,

        "pis": [
            {"latex": _lits_latex(pi, names),
             "assignment": {names[abs(l) - 1]: (l > 0) for l in pi}}
            for pi in yielded_pis
        ],
    }


# --------------------------------------------------------------------- utils

def _semantic_support(residual, mgr, candidate_vars: Set[int]) -> Set[int]:
    from rgr.enumeration.conditioning import condition_sdd
    if residual.is_true() or residual.is_false():
        return set()
    support = set()
    for v in candidate_vars:
        pos = condition_sdd(residual, mgr, {v})
        neg = condition_sdd(residual, mgr, {-v})
        if pos.id != neg.id:
            support.add(v)
    return support


def _falsifies(lit: int, nu: Dict[int, bool]) -> bool:
    var = abs(lit)
    if var not in nu:
        return False
    val = nu[var]
    return (lit > 0 and val is False) or (lit < 0 and val is True)