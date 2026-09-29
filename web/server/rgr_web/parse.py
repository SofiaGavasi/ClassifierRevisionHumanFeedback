"""Parse user-supplied classifiers into a canonical CNF clause list.

The formula mode accepts a permissive superset of sympy syntax:
- and: & | and | ∧
- or:  | | or  | ∨
- not: ~ | - | ! | not | ¬
- implication:   >> | →
- bi-implication:<> | ↔
Free spacing is fine, the parser normalises to sympy syntax first.
"""
from __future__ import annotations

import re
from typing import List, Tuple


def _var_index(name: str, names: List[str]) -> int:
    if name not in names:
        names.append(name)
    return names.index(name) + 1


# ------------------------------------------------------------------------ CNF

def parse_cnf(text: str) -> Tuple[int, List[str], List[List[int]]]:
    names: List[str] = []
    clauses: List[List[int]] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        toks = [t for t in re.split(r"[\s,]+", line) if t]
        clause = []
        for t in toks:
            neg = False
            while t and t[0] in ("~", "-", "!", "¬"):
                neg = not neg
                t = t[1:]
            if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", t):
                raise ValueError(
                    f"invalid variable name: {t!r}. Variable names must start with a "
                    "letter or underscore and contain only letters, digits and underscores."
                )
            idx = _var_index(t, names)
            clause.append(-idx if neg else idx)
        if clause:
            clauses.append(clause)
    return len(names), names, clauses


# -------------------------------------------------------------------- formula

# Order matters: longer tokens first, and negation forms substitute to '~' with a following space so `-a` becomes `~ a`, not `~a` merged into an odd name.
_FORMULA_REPLACEMENTS = [
    ("∧", " & "), ("∨", " | "),
    ("↔", " <> "), ("→", " >> "),
    ("¬", " ~ "), ("!", " ~ "),
    (r"\band\b", " & "), (r"\bor\b", " | "), (r"\bnot\b", " ~ "),
]


def _normalise_formula(text: str) -> str:
    s = text
    for pat, rep in _FORMULA_REPLACEMENTS:
        s = re.sub(pat, rep, s)
    # Replace '-' used as unary negation.  Two cases:
    #   at the start of an expression:   ^\s*-x           -> ~x
    #   after ( & | ^ ~ >> <> ,:         (& - x) etc.
    # A '-' between two operands would be subtraction on integers, but our
    # formulas are Boolean; there is no legitimate subtraction, so treat every
    # '-' that isn't inside a name (already impossible) as negation.
    s = re.sub(r"-", " ~ ", s)
    # Collapse repeated whitespace so sympy doesn't choke.
    return re.sub(r"\s+", " ", s).strip()


def parse_formula(text: str) -> Tuple[int, List[str], List[List[int]]]:
    from sympy.logic.boolalg import to_cnf, And, Or, Not
    from sympy.parsing.sympy_parser import parse_expr

    normalised = _normalise_formula(text)
    if not normalised:
        raise ValueError("empty formula.")

    try:
        expr = parse_expr(normalised)
    except Exception as e:
        raise ValueError(
            f"could not parse the formula. Check parentheses, operators and variable names. "
            f"(after normalisation: {normalised!r}). Underlying error: {e}"
        )

    try:
        cnf = to_cnf(expr, simplify=False, force=True)
    except Exception as e:
        raise ValueError(f"formula was parsed but sympy could not convert it to CNF: {e}")

    names: List[str] = []

    def lit_to_signed(node) -> int:
        if isinstance(node, Not):
            v = str(node.args[0])
            return -_var_index(v, names)
        return _var_index(str(node), names)

    def clause_to_list(node) -> List[int]:
        if isinstance(node, Or):
            return [lit_to_signed(a) for a in node.args]
        return [lit_to_signed(node)]

    clauses: List[List[int]] = []
    if isinstance(cnf, And):
        for c in cnf.args:
            clauses.append(clause_to_list(c))
    else:
        clauses.append(clause_to_list(cnf))

    if not names:
        raise ValueError("formula contains no variables.")
    return len(names), names, clauses


# ---------------------------------------------------------------------- truth

def parse_truth(text: str) -> Tuple[int, List[str], List[List[int]]]:
    from sympy.logic.boolalg import to_cnf, And, Or, Not
    from sympy import symbols

    lines = [l.strip() for l in text.splitlines() if l.strip() and not l.strip().startswith("#")]
    if len(lines) < 2:
        raise ValueError("truth table needs a header row followed by at least one data row.")

    header = [t for t in re.split(r"[\s,|:]+", lines[0]) if t]
    if len(header) < 2:
        raise ValueError("header must list at least one variable name and a label column.")

    var_names = header[:-1]
    syms = symbols(var_names)
    accepting = []
    for lineno, row in enumerate(lines[1:], start=2):
        toks = [t for t in re.split(r"[\s,|:]+", row) if t]
        if len(toks) != len(header):
            raise ValueError(
                f"row {lineno} has {len(toks)} columns but the header has {len(header)}."
            )
        label = toks[-1]
        if label not in ("0", "1"):
            raise ValueError(f"row {lineno}: label must be 0 or 1, got {label!r}.")
        if label == "1":
            term_parts = []
            for val, sym in zip(toks[:-1], syms):
                if val not in ("0", "1"):
                    raise ValueError(f"row {lineno}: cell must be 0 or 1, got {val!r}.")
                term_parts.append(sym if val == "1" else Not(sym))
            accepting.append(And(*term_parts) if len(term_parts) > 1 else term_parts[0])

    if not accepting:
        raise ValueError("truth table has no accepting rows (label=1); this classifier is unsatisfiable.")

    dnf = Or(*accepting) if len(accepting) > 1 else accepting[0]
    cnf = to_cnf(dnf, simplify=True, force=True)

    names: List[str] = list(var_names)

    def lit_to_signed(node) -> int:
        if isinstance(node, Not):
            return -_var_index(str(node.args[0]), names)
        return _var_index(str(node), names)

    def clause_to_list(node) -> List[int]:
        if isinstance(node, Or):
            return [lit_to_signed(a) for a in node.args]
        return [lit_to_signed(node)]

    clauses: List[List[int]] = []
    if isinstance(cnf, And):
        for c in cnf.args:
            clauses.append(clause_to_list(c))
    else:
        clauses.append(clause_to_list(cnf))
    return len(names), names, clauses


# ---------------------------------------------------------------- dispatcher

def parse_any(mode: str, text: str):
    if mode == "cnf":
        return parse_cnf(text)
    if mode == "formula":
        return parse_formula(text)
    if mode == "truth":
        return parse_truth(text)
    raise ValueError(f"unknown mode: {mode}")