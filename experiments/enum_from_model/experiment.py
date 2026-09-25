"""experiments/enum_from_model/experiment.py

Exhaustive CEGAR-based ReasonsFromModel benchmark on the standard suite.

Per row (one rejected instance ω): times each ablation with a wall-clock
budget. If a run exceeds the budget or the MHS search budget, that
ablation is marked truncated for the row and the runner continues.

python -m experiments.enum_from_model.experiment --budget-s 30
"""
from __future__ import annotations
import argparse
import statistics
import time
from itertools import product
from typing import Dict, Tuple

from experiments.harness import run_experiment, clock

from rgr.sdd_utils import term_to_sdd
from rgr.reasons import all_prime_implicants, disagreement
from rgr.nearest_all import all_nearest_models
from rgr.reasons_from_model import (
    reasons_from_model, reasons_from_model_full,
    EnumerationStats, ABLATIONS, PipelineTimeout,
)
from rgr.enumeration import ResidualCache
from rgr.enumeration.hitting_sets import MHSSearchLimitExceeded


# --------------------------------------------------------------------- #
# helpers                                                               #
# --------------------------------------------------------------------- #

def _dict_key(d): return tuple(sorted(d.items()))

def _mu_contains(mu, pi):
    return all(mu[v] == val for v, val in pi.items())


def _time_stream_bounded(gen_factory, reps: int, budget_s: float):
    """Run the generator up to `reps` times, aborting the current rep
    if it overruns budget_s wall-clock. Returns timings dict + truncated flag.
    """
    total_times, first_times, last_delays = [], [], []
    truncated = False
    for _ in range(reps):
        deadline = time.perf_counter() + budget_s
        t0 = time.perf_counter()
        last = t0
        times = []
        try:
            for _ in gen_factory(deadline):
                now = time.perf_counter()
                times.append(now - last)
                last = now
        except (PipelineTimeout, MHSSearchLimitExceeded):
            truncated = True
        total = last - t0
        total_times.append(total)
        first_times.append(times[0] if times else 0.0)
        last_delays = times
    return {
        "time_first_pi_s": statistics.mean(first_times) if first_times else 0.0,
        "time_total_s": statistics.mean(total_times) if total_times else 0.0,
        "delay_avg_s": statistics.mean(last_delays) if last_delays else 0.0,
        "delay_max_s": max(last_delays) if last_delays else 0.0,
    }, truncated


def _ground_truth_minimal_pis(sdd, omega, nvars, mgr):
    S = all_prime_implicants(sdd, nvars, mgr)
    if not S:
        return set(), None
    mind = min(disagreement(t, omega) for t in S)
    return {_dict_key(p) for p in S if disagreement(p, omega) == mind}, mind


def _run_pipeline_over_all_mu(sdd, omega, mgr, nvars, ablation,
                              cache, deadline):
    for mu in all_nearest_models(sdd, omega, nvars):
        for pi in reasons_from_model(
            sdd, mu, omega, mgr, nvars,
            ablation=ablation, cache=cache, deadline=deadline,
        ):
            yield _dict_key(pi)


def _run_baseline(sdd, omega, mgr, nvars):
    S = all_prime_implicants(sdd, nvars, mgr)
    if not S:
        return
    mind = min(disagreement(t, omega) for t in S)
    for pi in S:
        if disagreement(pi, omega) == mind:
            yield _dict_key(pi)


# --------------------------------------------------------------------- #
# progress                                                              #
# --------------------------------------------------------------------- #

_progress = {"n": 0}

def _tick(entry, omega):
    _progress["n"] += 1
    if _progress["n"] % 25 == 1:
        print(f"  [{_progress['n']}] id={entry['id']} "
              f"nv={entry['nvars']} d={entry['density']}", flush=True)


# --------------------------------------------------------------------- #
# per-instance measure                                                  #
# --------------------------------------------------------------------- #

def make_measure(reps: int, ablations: Tuple[str, ...], budget_s: float,
                 skip_baseline_above_n: int):

    def measure(mgr, sdd, entry, omega):
        _tick(entry, omega)
        nvars = entry["nvars"]

        nearest = all_nearest_models(sdd, omega, nvars)
        gt_keys, d_star = _ground_truth_minimal_pis(sdd, omega, nvars, mgr)

        row: Dict = {
            "sdd_size": sdd.size(),
            "d_star": d_star if d_star is not None else -1,
            "n_nearest_models": len(nearest),
            "n_pis_minimal_gt": len(gt_keys),
        }

        # per-ablation timings (fresh cache each time so ablations are fair)
        for abl in ablations:
            cache = ResidualCache() if abl == "full" else None

            def factory(deadline, _abl=abl, _cache=cache):
                return _run_pipeline_over_all_mu(
                    sdd, omega, mgr, nvars,
                    ablation=_abl, cache=_cache, deadline=deadline,
                )

            timings, truncated = _time_stream_bounded(factory, reps, budget_s)

            # correctness + counter aggregation (one pass, respect deadline)
            got_keys = set()
            agg_ec = agg_cm = agg_cf = agg_pf = 0
            r_mu = core = res = 0
            deadline_one = time.perf_counter() + budget_s
            partial = False
            for mu in nearest:
                try:
                    pis, st = reasons_from_model_full(
                        sdd, mu, omega, mgr, nvars,
                        ablation=abl,
                        cache=(ResidualCache() if abl == "full" else None),
                        deadline=deadline_one,
                    )
                except (PipelineTimeout, MHSSearchLimitExceeded):
                    partial = True
                    break
                if st.truncated:
                    partial = True
                got_keys |= {_dict_key(p) for p in pis}
                agg_ec += st.entailment_checks
                agg_cm += st.countermodel_calls
                agg_cf += st.conflicts_added
                agg_pf += st.pis_found
                r_mu = max(r_mu, st.r_mu)
                core = max(core, st.core_size)
                res = max(res, st.residual_sdd_size)

            truncated = truncated or partial
            row[f"{abl}_time_first_pi_s"] = timings["time_first_pi_s"]
            row[f"{abl}_time_total_s"]    = timings["time_total_s"]
            row[f"{abl}_delay_avg_s"]     = timings["delay_avg_s"]
            row[f"{abl}_delay_max_s"]     = timings["delay_max_s"]
            row[f"{abl}_pis_found"]       = agg_pf
            row[f"{abl}_entailment_checks"] = agg_ec
            row[f"{abl}_countermodel_calls"] = agg_cm
            row[f"{abl}_conflicts_added"] = agg_cf
            row[f"{abl}_r_mu"]            = r_mu
            row[f"{abl}_core_size"]       = core
            row[f"{abl}_residual_sdd_size"] = res
            row[f"{abl}_complete"]        = int(
                (not truncated) and got_keys == gt_keys
            )
            row[f"{abl}_truncated"]       = int(truncated)

        # baseline: skip for large nvars where 3^n is prohibitive
        if nvars <= skip_baseline_above_n:
            def bfactory(_deadline):
                return _run_baseline(sdd, omega, mgr, nvars)
            bt, btrunc = _time_stream_bounded(bfactory, reps, budget_s)
            row["baseline_time_first_pi_s"] = bt["time_first_pi_s"]
            row["baseline_time_total_s"]    = bt["time_total_s"]
            row["baseline_delay_avg_s"]     = bt["delay_avg_s"]
            row["baseline_delay_max_s"]     = bt["delay_max_s"]
            row["baseline_pis_found"]       = len(gt_keys)
            row["baseline_complete"]        = int(not btrunc)
            row["baseline_truncated"]       = int(btrunc)
        else:
            for k in ("time_first_pi_s", "time_total_s",
                      "delay_avg_s", "delay_max_s"):
                row[f"baseline_{k}"] = 0.0
            row["baseline_pis_found"] = 0
            row["baseline_complete"] = 0
            row["baseline_truncated"] = 1

        # derived speedups
        ft = row.get("full_time_total_s") or 0.0
        row["speedup_vs_baseline"] = (
            (row.get("baseline_time_total_s") or 0.0) / ft if ft else 0.0
        )
        row["speedup_vs_no_cegar"] = (
            (row.get("no_cegar_time_total_s") or 0.0) / ft if ft else 0.0
        )
        return row

    return measure


# --------------------------------------------------------------------- #
# CLI                                                                   #
# --------------------------------------------------------------------- #

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--suite", default="standard")
    ap.add_argument("--reps", type=int, default=3)
    ap.add_argument("--vtrees", nargs="+", default=["right"])
    ap.add_argument("--ablations", nargs="+", default=list(ABLATIONS))
    ap.add_argument("--budget-s", type=float, default=30.0,
                    help="wall-clock budget per ablation, per row")
    ap.add_argument("--skip-baseline-above-n", type=int, default=10)
    ap.add_argument("--out", default="enum_from_model")
    args = ap.parse_args()

    for abl in args.ablations:
        if abl not in ABLATIONS:
            raise SystemExit(f"unknown ablation {abl!r}; choose {ABLATIONS}")

    measure = make_measure(args.reps, tuple(args.ablations),
                           args.budget_s, args.skip_baseline_above_n)
    run_experiment(
        args.suite, measure, per="instance", out=args.out,
        vtrees=tuple(args.vtrees), group_keys=("nvars", "density"),
    )


if __name__ == "__main__":
    main()