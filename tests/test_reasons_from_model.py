"""Regression tests for rgr.reasons_from_model.

Compares against the ground truth minimal_reasons / all_prime_implicants,
using rgr.nearest_all.all_nearest_models to enumerate every μ at the
minimum distance.
"""
from __future__ import annotations
from itertools import product

import pytest

from rgr.suite import load_suite, build_classifier
from rgr.sdd_utils import term_to_sdd
from rgr.reasons import all_prime_implicants, disagreement
from rgr.nearest_all import all_nearest_models
from rgr.reasons_from_model import (
    reasons_from_model_full, EnumerationStats, ABLATIONS,
)


def _rejected_instances(sdd, mgr, nvars):
    for bits in product([False, True], repeat=nvars):
        omega = {i + 1: bits[i] for i in range(nvars)}
        if (term_to_sdd(omega, mgr) & sdd).is_false():
            yield omega


def _dict_key(d):
    return tuple(sorted(d.items()))


def _mu_contains_pi(mu, pi):
    return all(mu[v] == val for v, val in pi.items())


# --------------------------------------------------------------------- #
# per-example correctness                                               #
# --------------------------------------------------------------------- #

@pytest.mark.parametrize("ablation", ABLATIONS)
def test_matches_ground_truth_on_small_standard_suite(ablation):
    """Pick a handful of small classifiers from the standard suite and
    check every ablation returns exactly the PIs of Δ contained in μ.
    """
    suite = load_suite("standard")
    picks = [e for e in suite["classifiers"] if e["nvars"] <= 5][:6]
    assert picks, "no small classifiers found in standard suite"

    for entry in picks:
        mgr, sdd = build_classifier(entry, vtree_type="right")
        nv = entry["nvars"]
        all_pis = all_prime_implicants(sdd, nv, mgr)

        for omega in _rejected_instances(sdd, mgr, nv):
            nearest = all_nearest_models(sdd, omega, nv)
            for mu in nearest:
                got, stats = reasons_from_model_full(
                    sdd, mu, omega, mgr, nv, ablation=ablation,
                )
                got_keys = {_dict_key(p) for p in got}
                expected = {_dict_key(p) for p in all_pis
                            if _mu_contains_pi(mu, p)}
                assert got_keys == expected, (
                    f"[{entry['id']} nv={nv} ablation={ablation}] "
                    f"missed={expected - got_keys} extra={got_keys - expected}"
                )


def test_flipped_literals_appear_in_every_returned_pi():
    """F_μ ⊆ τ for every returned τ (notes §1)."""
    suite = load_suite("standard")
    picks = [e for e in suite["classifiers"] if e["nvars"] <= 5][:4]
    for entry in picks:
        mgr, sdd = build_classifier(entry, vtree_type="right")
        nv = entry["nvars"]
        for omega in _rejected_instances(sdd, mgr, nv):
            for mu in all_nearest_models(sdd, omega, nv):
                F_mu = {v: mu[v] for v in mu if mu[v] != omega[v]}
                got, _ = reasons_from_model_full(sdd, mu, omega, mgr, nv)
                for pi in got:
                    for v, val in F_mu.items():
                        assert v in pi and pi[v] == val, (
                            f"F_μ literal ({v}, {val}) missing from PI {pi}"
                        )