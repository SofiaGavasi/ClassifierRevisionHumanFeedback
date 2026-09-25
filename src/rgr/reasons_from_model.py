"""rgr.reasons_from_model — CEGAR enumeration of PIs contained in μ.

Returns PIs as dicts {var:int -> bool}. Ablations:
    "full" | "no_conditioning" | "no_support" | "no_core" | "no_cegar"

Robustness:
    - `deadline` (perf_counter absolute time): raises PipelineTimeout if
      any entailment/countermodel step overruns.
    - `~residual` cached per measurement (avoids rebuilding on every check).
    - MHS enumerator has a hard iteration budget: raises
      MHSSearchLimitExceeded on runaway search.
"""
from __future__ import annotations
import time
from dataclasses import dataclass
from typing import Dict, FrozenSet, Iterator, List, Optional, Set, Tuple

from rgr.sdd_utils import term_to_sdd

from rgr.enumeration import (
    condition_sdd, support_of, mu_to_literals, flipped_literals,
    find_mandatory_core, cegar_enumerate, blind_enumerate, ResidualCache,
)
from rgr.enumeration.hitting_sets import MHSSearchLimitExceeded


ABLATIONS = ("full", "no_conditioning", "no_support", "no_core", "no_cegar")


class PipelineTimeout(Exception):
    """Raised when the per-measurement deadline is exceeded."""


@dataclass
class EnumerationStats:
    d_star: int = 0
    n_optional_candidates: int = 0
    core_size: int = 0
    r_mu: int = 0
    residual_sdd_size: int = 0
    entailment_checks: int = 0
    countermodel_calls: int = 0
    conflicts_added: int = 0
    pis_found: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    ablation: str = "full"
    truncated: bool = False
    truncation_reason: str = ""


def _semantic_support(residual, mgr, candidate_vars):
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



def _entailment_fn(residual, mgr, not_residual):
    def entails(term_literals: Set[int]) -> bool:
        assignment = {abs(l): (l > 0) for l in term_literals}
        term_sdd = term_to_sdd(assignment, mgr) if assignment else mgr.true()
        return (term_sdd & not_residual).is_false()
    return entails


def _countermodel_fn(residual, mgr, not_residual, optional_vars):
    def countermodel(term_literals: Set[int]) -> Dict[int, bool]:
        assignment = {abs(l): (l > 0) for l in term_literals}
        term_sdd = term_to_sdd(assignment, mgr) if assignment else mgr.true()
        anti = term_sdd & not_residual
        for model in anti.models():
            return {v: bool(model[v]) for v in optional_vars if v in model}
        raise RuntimeError("no countermodel available")
    return countermodel


def reasons_from_model(
    sdd, mu: Dict[int, bool], omega: Dict[int, bool], mgr, nvars: int,
    *,
    ablation: str = "full",
    cache: Optional[ResidualCache] = None,
    stats: Optional[EnumerationStats] = None,
    deadline: Optional[float] = None,
) -> Iterator[Dict[int, bool]]:
    if ablation not in ABLATIONS:
        raise ValueError(f"unknown ablation {ablation!r}")

    st = stats if stats is not None else EnumerationStats()
    st.ablation = ablation

    def check_deadline():
        if deadline is not None and time.perf_counter() > deadline:
            raise PipelineTimeout(f"deadline exceeded (ablation={ablation})")

    F_mu = flipped_literals(mu, omega)
    st.d_star = len(F_mu)

    if ablation == "no_conditioning":
        residual = sdd
    else:
        residual = condition_sdd(sdd, mgr, F_mu)
    try:
        st.residual_sdd_size = residual.size()
    except AttributeError:
        st.residual_sdd_size = 0

    mu_term = mu_to_literals(mu)
    if ablation in ("no_conditioning", "no_support"):
        optional_candidates: Set[int] = set(mu_term - F_mu)
    else:
        candidate_vars = {abs(l) for l in (mu_term - F_mu)}
        residual_vars = _semantic_support(residual, mgr, candidate_vars)
        optional_candidates = {
            lit for lit in (mu_term - F_mu) if abs(lit) in residual_vars
        }
    st.n_optional_candidates = len(optional_candidates)

    # cache ~residual once (rebuilding it on every entailment check is
    # the main source of quadratic slowdown for large measurements).
    not_residual = ~residual

    entails_raw = _entailment_fn(residual, mgr, not_residual)
    counter_raw = _countermodel_fn(
        residual, mgr, not_residual,
        optional_vars={abs(l) for l in optional_candidates},
    )

    def entails(term: Set[int]) -> bool:
        check_deadline()
        st.entailment_checks += 1
        if ablation == "no_conditioning":
            return entails_raw(term | F_mu)
        return entails_raw(term)

    def counter(term: Set[int]) -> Dict[int, bool]:
        check_deadline()
        st.countermodel_calls += 1
        if ablation == "no_conditioning":
            return counter_raw(term | F_mu)
        return counter_raw(term)

    if ablation == "no_core":
        C_mu: Set[int] = set()
    else:
        try:
            C_mu = find_mandatory_core(optional_candidates, entails)
        except (PipelineTimeout, MHSSearchLimitExceeded) as e:
            st.truncated = True; st.truncation_reason = f"core: {e}"
            return

    st.core_size = len(C_mu)
    U_mu = optional_candidates - C_mu
    st.r_mu = len(U_mu)

    fixed_out = F_mu | C_mu

    cache_key = frozenset(C_mu)
    if cache is not None and ablation == "full":
        cached = cache.get(id(residual), cache_key)
        if cached is not None:
            st.cache_hits += 1
            for A in cached:
                st.pis_found += 1
                yield _lits_to_dict(fixed_out | set(A))
            return
        st.cache_misses += 1

    def entails_with_core(A: Set[int]) -> bool:
        return entails(A | C_mu)

    def counter_with_core(A: Set[int]) -> Dict[int, bool]:
        return counter(A | C_mu)

    collected: List[FrozenSet[int]] = []
    try:
        if ablation == "no_cegar":
            it = blind_enumerate(U_mu, entails_with_core, stats={})
        else:
            it = cegar_enumerate(U_mu, entails_with_core, counter_with_core,
                                 stats={})
        for A in it:
            collected.append(frozenset(A))
            st.pis_found += 1
            yield _lits_to_dict(fixed_out | set(A))
    except (PipelineTimeout, MHSSearchLimitExceeded) as e:
        st.truncated = True
        st.truncation_reason = f"search: {type(e).__name__}: {e}"
        # don't re-raise: caller reads st.truncated
        return

    if cache is not None and ablation == "full":
        cache.put(id(residual), cache_key, collected)
        st.cache_hits = cache.hits
        st.cache_misses = cache.misses


def reasons_from_model_full(
    sdd, mu, omega, mgr, nvars,
    *,
    ablation="full", cache=None, deadline: Optional[float] = None,
) -> Tuple[List[Dict[int, bool]], EnumerationStats]:
    st = EnumerationStats()
    pis = list(reasons_from_model(
        sdd, mu, omega, mgr, nvars,
        ablation=ablation, cache=cache, stats=st, deadline=deadline,
    ))
    return pis, st


def _lits_to_dict(lits: Set[int]) -> Dict[int, bool]:
    return {abs(l): (l > 0) for l in lits}