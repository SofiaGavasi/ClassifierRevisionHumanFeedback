"""Exact small-map PI overlays shared by unary and batch presentation, separate from solver search."""
from itertools import product


def term_label(term, names):
    """Render a consistent term using the loaded classifier's declared variable names."""
    return " ∧ ".join(("" if value > 0 else "¬")+names[i]
                      for i, value in enumerate(term.states) if value) or "True"


def visualize_classifier(classifier, names, reasons=None):
    """Extract every PI only for the at-most-six-variable map, after the solver or on a display request."""
    from batch_revision import PrimeFamily
    points = tuple(product((False, True), repeat=classifier.nvars))
    accepted = [classifier(point) for point in points]
    if classifier.nvars > 6:
        return {"nvars": classifier.nvars, "vars": names, "accepted": accepted,
                "reasons": [], "available": False, "reason_count": None}
    terms = tuple(sorted(PrimeFamily(classifier).terms())) if reasons is None else tuple(reasons)
    return {"nvars": classifier.nvars, "vars": names, "accepted": accepted, "available": True,
            "reasons": [{"id": f"R{i+1}", "states": list(term.states), "text": term_label(term, names)}
                        for i, term in enumerate(terms)], "reason_count": len(terms)}


def visualize_values(names, accepted):
    """Compile an exact display truth vector and obtain PI overlays through the existing PI backend."""
    from batch_revision import Classifier
    values = tuple(bool(v) for v in accepted)
    if len(values) != 2**len(names):
        raise ValueError("Visualization needs a complete truth vector")
    points = tuple(product((False, True), repeat=len(names)))
    lookup = dict(zip(points, values))
    classifier = Classifier.from_callable(len(names), lambda point: lookup[point])
    return visualize_classifier(classifier, names)


def visualize_cnf(data):
    """Use the common transport format without invoking either revision algorithm."""
    from batch_revision.datasets import compile_formula
    from .batch_session import cnf_formula, validate_classifier
    if data["nvars"] > 8:
        return {"nvars": data["nvars"], "vars": data["var_names"], "accepted": [], "reasons": [], "reason_count": None, "available": False}
    validate_classifier(data)
    return visualize_classifier(compile_formula(data["nvars"], cnf_formula(data["clauses"])), data["var_names"])


def unary_choices(trace, data):
    """Attach exact weakening previews to the existing unary reason records without modifying unary search."""
    original = visualize_cnf(data)
    trace["original_visual"] = original
    if not original["available"]:
        return trace
    points = tuple(product((False, True), repeat=data["nvars"]))
    names, omega = data["var_names"], data["omega"]
    for step in trace["steps"]:
        if step["name"] != "reasons":
            continue
        for reason in step["data"]["reasons"]:
            kept = {name: value for name, value in reason["assignment"].items() if omega[name] == value}
            revised = [old or all(point[names.index(name)] == value for name, value in kept.items())
                       for point, old in zip(points, original["accepted"])]
            reason["visualization"] = visualize_values(names, revised)
    return trace
