"""Batch-library adapter for verified, pageable revision choices and educational solver explanations."""
from __future__ import annotations

from itertools import product
from typing import Callable


def validate_classifier(data, maximum = 8):
    """Validate the named CNF universe without converting missing or invalid values implicitly."""
    import re
    nvars = data.get("nvars")
    names = data.get("var_names", [])
    if type(nvars) is not int or not 1 <= nvars <= maximum:
        raise ValueError(f"Use between 1 and {maximum} variables in the interactive interface")
    if not isinstance(names, list) or len(names) != nvars or len(set(names)) != nvars:
        raise ValueError("Provide a different name for each variable")
    if any(not isinstance(name, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name) for name in names):
        raise ValueError("Variable names use letters, digits and underscores, starting with a letter or underscore")
    if not isinstance(data.get("clauses"), list):
        raise ValueError("Classifier clauses must be a list")
    for clause in data["clauses"]:
        if not isinstance(clause, list) or any(type(lit) is not int or not 1 <= abs(lit) <= nvars for lit in clause):
            raise ValueError("A classifier literal is outside the declared variable universe")


def cnf_formula(clauses):
    """Compile the shared UI clause format into the independent batch formula vocabulary."""
    return {"op": "and", "xs": [{"op": "or", "xs": [
        {"op": "var", "v": lit} if lit > 0 else {"op": "not", "x": {"op": "var", "v": -lit}}
        for lit in clause]} for clause in clauses]}


def classifier_from_table(names, accepting):
    """Build an exact maxterm CNF from painted accepted assignments, including constants."""
    nvars = len(names)
    values = set(accepting)
    if any(not isinstance(value, str) or len(value) != nvars or set(value)-{"0", "1"} for value in values):
        raise ValueError("Every selected cell must be a complete binary assignment")
    clauses = [[-(i+1) if value else i+1 for i, value in enumerate(point)]
               for point in product((False, True), repeat=nvars)
               if "".join("1" if v else "0" for v in point) not in values]
    data = {"nvars": nvars, "var_names": names, "clauses": clauses}
    validate_classifier(data)
    return data


def term_text(term, names):
    """Format one consistent term without hiding its original-source provenance."""
    return " ∧ ".join(("" if state > 0 else "¬")+names[i]
                      for i, state in enumerate(term.states) if state) or "True"


def diagram(classifier, names):
    """Serialize the reachable classifier BDD as DOT for the existing decision-diagram renderer."""
    import json
    manager = classifier.manager
    lines = ['digraph BDD { rankdir=TB; node [shape=circle]; start [shape=point];',
             f'start -> n{classifier.root};', 'n0 [shape=box,label="0"]; n1 [shape=box,label="1"];']
    pending, seen = [classifier.root], set()
    while pending:
        node = pending.pop()
        if node <= 1 or node in seen:
            continue
        seen.add(node)
        level, low, high = manager.nodes[node]
        lines += [f'n{node} [label={json.dumps(names[level])}];',
                  f'n{node} -> n{low} [style=dashed,label="0"];', f'n{node} -> n{high} [label="1"];']
        pending.extend((low, high))
    return "\n".join(lines+["}"])


class BatchSession:
    """Own one exact result and its lazy output cursor inside an isolated interactive worker."""
    def __init__(self, data, phase = lambda _: None):
        """Compile user inputs and solve using the existing batch dispatcher, never unary search code."""
        from batch_revision import Budgets, Feedback, PrimeFamily, solve, source_free_boundary
        from batch_revision.datasets import compile_formula
        validate_classifier(data)
        self.data, self.names = data, data["var_names"]
        self.points = tuple(product((False, True), repeat=data["nvars"]))
        phase("Compiling the original classifier")
        self.original = compile_formula(data["nvars"], cnf_formula(data["clauses"]))
        self.feedback = Feedback(data["nvars"], data.get("positive", []), data.get("negative", []))
        self.budgets = Budgets(data.get("epsilon", "1"), data.get("gamma", "1"))
        self.plans, self.reports, self.roots = [], [], {}
        self.exhausted = False
        self.result, self.boundary = None, None
        from .batch_trace import BatchTraceRecorder
        self.trace = BatchTraceRecorder(self.original, self.names, self.feedback, self.budgets)
        if self.original.root == 0:
            if data.get("algorithm", "auto") != "auto":
                raise ValueError("The original classifier has no source reasons. Choose Automatic for its source-free semantic rule.")
            self.boundary = source_free_boundary(self.original, self.feedback)
            self.total = "1"
            self.iterator = iter([None])
            self.trace.add("boundary", "Use the source-free semantic result", "There is no original source PI. Accept exactly the requested positives; structural cost remains undefined.")
        else:
            phase("Computing the implicit source-reason family")
            family = PrimeFamily(self.original)
            self.trace.family = family
            phase("Finding the exact minimum-cost revision family")
            self.result = solve(self.original, self.feedback, self.budgets,
                                algorithm=data.get("algorithm", "auto"), family_factory=lambda _: family, observer=self.trace)
            self.iterator = self.result.plans()
            try:
                self.total = str(self.result.count_plans())
            except NotImplementedError:
                self.total = None
        phase("Verifying the first optimal choices")
        from .visualization import visualize_classifier
        self.original_visual = visualize_classifier(self.original, self.names)
        self.visuals = {self.original.root: self.original_visual}

    def metadata(self):
        """Describe actual solver results and preconditions without inventing an execution trace."""
        old_pos = self.original.count()-sum(self.original(p) for p in self.feedback.negative)
        old_neg = 2**self.original.nvars-self.original.count()-sum(not self.original(p) for p in self.feedback.positive)
        loss_limit, gain_limit = self.budgets.thresholds(old_pos, old_neg)
        result = self.result
        return {"algorithm": result.algorithm if result else "source-free boundary",
                "requested_algorithm": self.data.get("algorithm", "auto"), "minimum_cost": result.optimum_cost if result else None,
                "solve_status": "OPTIMAL" if result else "SEMANTIC_BOUNDARY", "total_plans": self.total,
                "source_count": str(result.family.count()) if result else "0", "nvars": self.original.nvars,
                "var_names": self.names, "original_count": self.original.count(),
                "positive_count": len(self.feedback.positive), "negative_count": len(self.feedback.negative),
                "epsilon": str(self.budgets.epsilon), "gamma": str(self.budgets.gamma),
                "old_positive": old_pos, "old_negative": old_neg, "loss_limit": loss_limit, "gain_limit": gain_limit,
                "statistics": result.statistics if result else None, "steps": self.explanations(),
                "original_dot": diagram(self.original, self.names), "original_visual": self.original_visual, "trace": self.trace.export()}

    def explanations(self):
        """Explain the completed computation using genuine DP tables and solver statistics where available."""
        result = self.result
        steps = [{"title": "Read the feedback and protect unrequested cases", "summary": "Positive instances must be accepted; negative instances must be rejected.",
                  "details": ["Loss excludes requested negatives. Gain excludes requested positives.",
                              "Both limits use exact rational fractions of the original classifier's unrequested regions."], "rows": []}]
        if not result:
            steps.append({"title": "Use the source-free boundary rule", "summary": "No original sufficient reason exists, so the theory supplies a separate semantic result.",
                          "details": ["Accept exactly the positive feedback instances.", "No source-based structural minimum cost is defined for this boundary."], "rows": []})
            return steps
        steps.append({"title": "Represent original reasons symbolically", "summary": f"The original classifier has {result.family.count()} prime-implicant source reasons.",
                      "details": ["The solver queries an implicit PI family instead of requiring a complete source list.",
                                  "Each revision keeps source provenance. Sources omitted from an edit keep their identity bundles."], "rows": []})
        algorithm = result.algorithm
        if algorithm == "ORD" and hasattr(result.transformations, "minima"):
            dag = result.transformations
            rows = [{"Feedback group": ", ".join("".join("1" if v else "0" for v in point) for i, point in enumerate(dag.points) if mask & (1 << i)),
                     "Minimum edits": minimum.cost, "Tied source reasons": str(result.family.count(minimum.sources))}
                    for mask, minimum in list(dag.minima.items())[:32]]
            steps.append({"title": "Share coverage with ORD", "summary": "With no negative feedback and unrestricted extra gain, sources can be weakened to cover groups of positives.",
                          "details": [f"Queried {len(dag.minima)} nonempty feedback groups and solved {len(dag.costs)} subset states.",
                                      "The subset dynamic program retains every equality-achieving edge and every tied source witness.",
                                      "Repeated source choices are merged, and duplicate descriptions of the same plan are removed."], "rows": rows})
        elif algorithm == "negative-independent":
            steps.append({"title": "Repair conflicting sources independently", "summary": f"Every negative-conflicting source must pay at least one edit; cost {result.optimum_cost} attains that bound.",
                          "details": ["Safe sources stay unchanged. Each conflicting source is deleted or receives one safe added literal.",
                                      "Unrestricted unintended loss makes these choices independent. All tied source/action combinations remain available."], "rows": []})
        elif algorithm == "BERD":
            stats = result.statistics or {}
            steps.append({"title": "Search baseline plus exceptional repairs", "summary": f"Baseline B={stats.get('baseline_cost', 0)} plus minimum excess E={stats.get('excess', 0)} gives cost {result.optimum_cost}.",
                          "details": [f"Completed {stats.get('excess_levels', 0)} exact excess levels and {stats.get('constraint_profiles', 0)} bounded constraint profiles.",
                                      "Source and descendant constraints enforce provenance, negative safety, preservation, and exact splitting/continuation costs.",
                                      "E=0 needs no exceptional source. The single-exception filter applies only when E=1 has newly positive feedback."], "rows": []})
            steps.append({"title": "Compile feasible baseline policies without overlap", "summary": "Coverage bounds, shared constraints and complete-state memoization compile disjoint policy families.",
                          "details": ["First-cover branches fix a covering action and ban earlier alternatives.",
                                      "A permitted LOST branch bans every covering action for that preservation witness.",
                                      "Product terminals retain all independent completions, and different source provenance is preserved."],
                          "rows": [{"Search states": stats.get("states", 0), "Cache hits": stats.get("cache_hits", 0), "Pruned states": stats.get("pruned_states", 0)}]})
        else:
            steps.append({"title": "Keep the already-valid classifier", "summary": "The feedback is already satisfied, so the unique zero-cost revision is identity.", "details": [], "rows": []})
        steps.append({"title": "Verify every displayed minimal choice", "summary": "Each displayed plan is checked with the shared semantic verifier.",
                      "details": ["Checks include original prime-implicant membership, source provenance, compatible repairs, preservation, feedback success, exact structural cost, loss and gain.",
                                  "Choices are source-indexed plans. Two choices may intentionally produce the same Boolean classifier."], "rows": []})
        return steps

    def _append(self):
        """Extract one tied plan, verify it independently and retain its stable session-local identifier."""
        from batch_revision import verify, bundle_cost
        if self.exhausted:
            return False
        try:
            plan = next(self.iterator)
        except StopIteration:
            self.exhausted = True
            self.total = str(len(self.plans))
            return False
        if self.result:
            report = verify(self.result.family, self.feedback, self.budgets, plan)
            if not report.feasible or report.structural_cost != self.result.optimum_cost:
                raise RuntimeError("The solver produced an invalid revision choice")
            revised, loss, gain = report.classifier, report.loss, report.gain
            edits = [{"source": term_text(b.source, self.names), "source_literals": sorted(b.source.literals),
                      "descendants": [term_text(t, self.names) for t in b.descendants],
                      "descendant_literals": [sorted(t.literals) for t in b.descendants], "cost": bundle_cost(b)} for b in plan.edits]
        else:
            revised, loss, gain, edits = self.boundary, 0, 0, []
        index = len(self.plans)
        same = self.roots.get(revised.root)
        self.roots.setdefault(revised.root, index)
        choice = {"id": index, "cost": self.result.optimum_cost if self.result else None, "edits": edits,
                  "loss": loss, "gain": gain, "accepted_count": revised.count(), "equivalent_to": same,
                  "source_free": not bool(self.result), "identity": bool(self.result) and not plan.edits}
        from .visualization import visualize_classifier
        if revised.root not in self.visuals:
            self.visuals[revised.root] = visualize_classifier(revised, self.names)
        choice["visualization"] = self.visuals[revised.root]
        self.plans.append(plan)
        self.reports.append((choice, revised))
        return True

    def page(self, offset = 0, limit = 8):
        """Page lazily with one-item lookahead; repeated requests never skip or merge tied plans."""
        if offset < 0 or offset > len(self.plans) or not 1 <= limit <= 20:
            raise ValueError("Request an available offset and between 1 and 20 choices")
        while len(self.plans) < offset+limit+1 and self._append():
            pass
        choices = [value[0] for value in self.reports[offset:offset+limit]]
        return {"choices": choices, "next_offset": offset+len(choices), "has_more": len(self.plans) > offset+len(choices),
                "total_plans": self.total, "enumeration_complete": self.exhausted}

    def apply(self, index):
        """Preview an already-issued plan, preserving verified feedback and semantic-budget results."""
        from sympy import Symbol, latex
        from sympy.logic.boolalg import SOPform, POSform
        if not 0 <= index < len(self.reports):
            raise ValueError("Choose a revision returned by this session")
        choice, revised = self.reports[index]
        rows = [{"values": list(point), "old": self.original(point), "new": revised(point),
                 "feedback": "positive" if point in self.feedback.positive else "negative" if point in self.feedback.negative else None}
                for point in self.points]
        symbols = [Symbol(name) for name in self.names]
        original_terms = [list(point) for point in self.points if self.original(point)]
        revised_terms = [list(point) for point in self.points if revised(point)]
        return {"choice": choice, "truth_table": {"headers": self.names, "rows": rows},
                "original_dnf": str(SOPform(symbols, original_terms)), "revised_dnf": str(SOPform(symbols, revised_terms)),
                "original_dnf_latex": latex(SOPform(symbols, original_terms)),
                "revised_dnf_latex": latex(SOPform(symbols, revised_terms)),
                "revised_cnf_latex": latex(POSform(symbols, revised_terms)),
                "old_count": self.original.count(), "new_count": revised.count(),
                "added_count": sum(not row["old"] and row["new"] for row in rows),
                "removed_count": sum(row["old"] and not row["new"] for row in rows),
                "positive_success": all(revised(p) for p in self.feedback.positive),
                "negative_success": all(not revised(p) for p in self.feedback.negative),
                "revised_dot": diagram(revised, self.names), "visualization": choice["visualization"]}
