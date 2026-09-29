"""Produce a step-trace for the reason-guided revision pipeline."""
from __future__ import annotations

from itertools import product
from typing import Any, Dict, List

from rgr.distance import node_dist
from rgr.nearest_all import all_nearest_models
from rgr.sdd_utils import term_to_sdd

from .traced_pipeline import trace_reasons_from_model


def _term_str(term: Dict[int, bool], names: List[str]) -> str:
    if not term:
        return r"\top"
    parts = []
    for v in sorted(term):
        name = names[v - 1]
        parts.append(name if term[v] else rf"\neg {name}")
    return r" \wedge ".join(parts)


def _instance_str(omega: Dict[int, bool], names: List[str]) -> str:
    return _term_str(omega, names)


def build_trace(nvars, names, clauses, omega, algorithm="cegmhs") -> Dict[str, Any]:
    from rgr.suite import build_classifier
    entry = {"nvars": nvars, "clauses": clauses}
    mgr, sdd = build_classifier(entry, vtree_type="right")

    steps: List[Dict[str, Any]] = []

    omega_sdd = term_to_sdd(omega, mgr)
    rejected = (omega_sdd & sdd).is_false()
    steps.append({
        "name": "input",
        "description": "The instance and classifier.",
        "data": {
            "omega_latex": _instance_str(omega, names),
            "rejected": rejected,
            "nvars": nvars,
            "var_names": names,
            "clauses_latex": _clauses_latex(clauses, names),
        },
    })

    if not rejected:
        steps.append({
            "name": "accepted",
            "description": "The classifier already accepts this instance.",
            "data": {},
        })
        return {"algorithm": algorithm, "steps": steps, "sdd_dot": _sdd_dot(sdd)}

    memo: Dict[int, int] = {}
    d = node_dist(sdd, omega, memo)
    steps.append({
        "name": "distance",
        "description": r"Minimum Hamming distance from $\omega$ to an accepted model.",
        "data": {"d_star": d},
    })

    mus = all_nearest_models(sdd, omega, nvars)
    steps.append({
        "name": "nearest_models",
        "description": r"All models of $\Delta$ at distance $d^\star$ from $\omega$.",
        "data": {
            "count": len(mus),
            "models": [{"latex": _instance_str(mu, names)} for mu in mus],
        },
    })

    per_mu = [trace_reasons_from_model(sdd, mu, omega, mgr, nvars, names) for mu in mus]
    steps.append({
        "name": "per_model_enumeration",
        "description": r"For each nearest model $\mu$, enumerate the prime implicants of $\Delta$ contained in $\mu$.",
        "data": {"per_model": per_mu},
    })

    all_reasons: List[Dict[str, bool]] = []
    seen = set()
    for block in per_mu:
        for pi in block["pis"]:
            key = tuple(sorted(pi["assignment"].items()))
            if key in seen:
                continue
            seen.add(key)
            all_reasons.append(pi["assignment"])
    steps.append({
        "name": "reasons",
        "description": r"The minimal sufficient reasons offered to the user.",
        "data": {
            "reasons": [
                {"index": i,
                 "latex": _term_str({names.index(k) + 1: v for k, v in r.items()}, names),
                 "assignment": r}
                for i, r in enumerate(all_reasons)
            ],
        },
    })

    return {
        "algorithm": algorithm,
        "steps": steps,
        "sdd_dot": _sdd_dot(sdd),
        "nvars": nvars,
        "var_names": names,
        "clauses": clauses,
    }


# ------------------------------------------------------------- apply revision

def apply_revision(nvars, names, clauses, omega, chosen_reason):
    """Weaken the chosen reason to cover ω, OR it into the classifier, and
    return the revised classifier alongside CNF / DNF / truth-table views
    with row-level diffs against the original.
    """
    from rgr.suite import build_classifier
    from rgr.reasons import weaken

    entry = {"nvars": nvars, "clauses": clauses}
    mgr, sdd = build_classifier(entry, vtree_type="right")

    weakened = weaken(chosen_reason, omega)
    w_sdd = term_to_sdd(weakened, mgr) if weakened else mgr.true()
    revised = sdd | w_sdd
    omega_sdd = term_to_sdd(omega, mgr)
    accepts = not (omega_sdd & revised).is_false()

    # -------------------------------------------------- forms of both classifiers
    old_accepting = _accepting_rows(sdd, mgr, nvars)
    new_accepting = _accepting_rows(revised, mgr, nvars)

    # rows added by the revision (old rejected → new accepted); rows removed
    # should be empty by construction (OR only widens), but we compute them
    # anyway as a sanity display.
    added = new_accepting - old_accepting
    removed = old_accepting - new_accepting

    truth_table = _truth_table(nvars, names, old_accepting, new_accepting)
    old_dnf = _dnf_latex(old_accepting, names, nvars)
    new_dnf = _dnf_latex(new_accepting, names, nvars)
    old_cnf = _clauses_latex(clauses, names)
    new_cnf = _cnf_latex_from_rows(new_accepting, names, nvars, added_rows=added)

    weakened_latex = _term_str(weakened, names) if weakened else r"\top"

    return {
        "weakened_reason": weakened,
        "weakened_latex": weakened_latex,
        "accepts_omega": accepts,
        "revised_dot": _sdd_dot(revised),
        "revised_size": revised.size(),
        "old_size": sdd.size(),
        "diff": {
            "added_count": len(added),
            "removed_count": len(removed),
        },
        "old_cnf_latex": old_cnf,
        "new_cnf_latex": new_cnf,
        "old_dnf_latex": old_dnf,
        "new_dnf_latex": new_dnf,
        "truth_table": truth_table,
        "old_count": len(old_accepting),
        "new_count": len(new_accepting),
    }


# ------------------------------------------------------------------ formatting

def _accepting_rows(node, mgr, nvars):
    """Return a set of tuples (bool, bool, ...) — the accepting assignments."""
    out = set()
    for bits in product([False, True], repeat=nvars):
        assignment = {i + 1: bits[i] for i in range(nvars)}
        if not (term_to_sdd(assignment, mgr) & node).is_false():
            out.add(bits)
    return out


def _truth_table(nvars, names, old_rows, new_rows):
    """List of row dicts: {values, old, new, changed}. Capped at 2^8."""
    if nvars > 8:
        return {"too_large": True, "nvars": nvars}
    rows = []
    for bits in product([False, True], repeat=nvars):
        old = bits in old_rows
        new = bits in new_rows
        rows.append({
            "values": [bool(b) for b in bits],
            "old": old,
            "new": new,
            "changed": old != new,
        })
    return {"too_large": False, "headers": names, "rows": rows}


def _minterm_latex(bits, names):
    parts = []
    for i, b in enumerate(bits):
        parts.append(names[i] if b else rf"\neg {names[i]}")
    return "(" + r" \wedge ".join(parts) + ")"


def _dnf_latex(accepting_rows, names, nvars):
    """Simplified DNF via sympy.  Falls back to canonical minterms only if
    sympy is missing."""
    if not accepting_rows:
        return r"\bot"
    if len(accepting_rows) == 2 ** nvars:
        return r"\top"
    try:
        from sympy import symbols, Not, Or, And
        from sympy.logic.boolalg import to_dnf
    except ImportError:
        return r" \vee ".join(_minterm_latex(b, names) for b in sorted(accepting_rows))

    syms = symbols(names)
    minterms = []
    for bits in accepting_rows:
        conj = [s if b else Not(s) for s, b in zip(syms, bits)]
        minterms.append(And(*conj) if len(conj) > 1 else conj[0])
    expr = Or(*minterms) if len(minterms) > 1 else minterms[0]
    dnf = to_dnf(expr, simplify=True, force=True)

    def sym_lit(s):
        if s.func is Not:
            return rf"\neg {str(s.args[0])}"
        return str(s)

    def term(t):
        if t.func is And:
            return "(" + r" \wedge ".join(sym_lit(a) for a in t.args) + ")"
        return "(" + sym_lit(t) + ")"

    if dnf.func is Or:
        return r" \vee ".join(term(t) for t in dnf.args)
    return term(dnf)

def _clauses_latex(clauses, names):
    parts = []
    for c in clauses:
        lits = []
        for l in c:
            n = names[abs(l) - 1]
            lits.append(n if l > 0 else rf"\neg {n}")
        parts.append("(" + r" \vee ".join(lits) + ")")
    return r" \wedge ".join(parts) if parts else r"\top"


def _cnf_latex_from_rows(accepting_rows, names, nvars, added_rows=None):
    """Derive a CNF for the revised classifier from its accepting rows via
    sympy's `to_cnf`, and highlight literals that differ from the input's
    original CNF.  Falls back to a plain string if sympy chokes.
    """
    try:
        from sympy import symbols, Not, Or, And
        from sympy.logic.boolalg import to_cnf
    except ImportError:
        return _clauses_latex([], names)

    if not accepting_rows:
        return r"\bot"
    if len(accepting_rows) == 2 ** nvars:
        return r"\top"

    syms = symbols(names)
    minterms = []
    for bits in accepting_rows:
        conj = []
        for s, b in zip(syms, bits):
            conj.append(s if b else Not(s))
        minterms.append(And(*conj) if len(conj) > 1 else conj[0])
    dnf = Or(*minterms) if len(minterms) > 1 else minterms[0]
    cnf = to_cnf(dnf, simplify=True, force=True)

    def sym_lit(s):
        if s.func is Not:
            return rf"\neg {str(s.args[0])}"
        return str(s)

    def clause(c):
        if c.func is Or:
            return "(" + r" \vee ".join(sym_lit(a) for a in c.args) + ")"
        return "(" + sym_lit(c) + ")"

    if cnf.func is And:
        return r" \wedge ".join(clause(c) for c in cnf.args)
    return clause(cnf)


def _sdd_dot(sdd):
    try:
        return sdd.dot()
    except Exception:
        return 'digraph { node[shape=box]; "x" [label="SDD (dot unavailable)"]; }'