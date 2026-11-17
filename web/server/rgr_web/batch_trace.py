"""Bounded records of actual solver events, converted into example-specific tables and map frames."""
from batch_revision import Classifier, Term, bundle_cost
from .visualization import term_label, visualize_classifier


def point_text(point):
    """Show complete assignments in the same variable order as the input maps."""
    return "".join("1" if value else "0" for value in point)


class BatchTraceRecorder:
    """Observe exact search without steering it or expanding a complete implicit source family."""
    def __init__(self, original, names, feedback, budgets, family=None, limit=400):
        """Reserve a bounded display log, retaining the final optimum even when earlier events overflow."""
        self.original, self.names, self.feedback, self.family = original, names, feedback, family
        self.limit, self.events, self.total, self.omitted = limit, [], 0, 0
        self.excess, self.candidate = None, 0
        rows = [{"Target": "P+ Must accept", "Instance": point_text(point), "Original": "Accepted" if original(point) else "Rejected"} for point in sorted(feedback.positive)]
        rows += [{"Target": "N− Must reject", "Instance": point_text(point), "Original": "Accepted" if original(point) else "Rejected"} for point in sorted(feedback.negative)]
        self.add("input", "Read this classifier and feedback", f"{len(feedback.positive)} positive and {len(feedback.negative)} negative instances; ε={budgets.epsilon}, γ={budgets.gamma}.", rows)

    def frame(self, root, title, reasons=()):
        """Visualize an actual classifier root without enumerating PIs of every intermediate search state."""
        if self.original.nvars > 6:
            return []
        classifier = Classifier(self.original.manager, root)
        return [{"title": title, "visualization": visualize_classifier(classifier, self.names, reasons=reasons)}]

    def term_frame(self, term, title):
        """Show a queried source or descendant cylinder, explicitly distinct from a complete revision."""
        classifier = Classifier.from_terms(self.original.nvars, [term], self.original.manager)
        return self.frame(classifier.root, title, (term,))

    def domain_rows(self, domains):
        """Count opaque source guards, preserving symbolic action sharing rather than listing every PI."""
        return [{"Action": "Delete source" if not action else "Add "+term_label(Term.from_literals(self.original.nvars, [action]), self.names),
                 "Eligible original sources": self.family.count(root)} for action, root in domains]

    def bundles(self, bundles):
        """Describe every actual exceptional bundle in one queried configuration with its exact cost."""
        return [{"Source": term_label(bundle.source, self.names), "Descendants": " OR ".join(term_label(term, self.names) for term in bundle.descendants) or "Delete",
                 "Bundle cost": bundle_cost(bundle)} for bundle in bundles]

    def add(self, kind, title, summary, rows=(), frames=(), final=False):
        """Append a real event and account honestly for omitted diagnostic records."""
        self.total += 1
        event = {"id": self.total, "kind": kind, "title": title, "summary": summary,
                 "rows": list(rows), "frames": list(frames), "excess": self.excess, "candidate": self.candidate}
        if len(self.events) < self.limit:
            self.events.append(event)
        elif final:
            self.events[-1] = event
            self.omitted += 1
        else:
            self.omitted += 1

    def __call__(self, kind, data):
        """Translate callback arguments from the actual solver branch that just executed."""
        if kind == "excess_level":
            self.excess = data["excess"]
        if kind == "exceptional_candidate":
            self.candidate += 1
        if len(self.events) >= self.limit and kind != "optimum":
            self.total += 1
            self.omitted += 1
            return
        family, names = self.family, self.names
        rows, frames = [], []
        title, summary = kind.replace("_", " ").capitalize(), ""
        if kind == "identity":
            title, summary = "No correction is needed", "Every feedback instance already has its requested label. The identity plan has structural cost 0."
        elif kind in ("negative_partition", "berd_partition"):
            safe, conflicting = family.count(data["safe"]), family.count(data["conflicting"])
            title = "Separate safe sources from conflicting sources"
            summary = f"{safe} safe source reasons and {conflicting} conflicting source reasons. The unavoidable source baseline is B={conflicting}."
            rows = [{"Source family": "N-safe", "Sources": safe}, {"Source family": "Conflicts with N", "Sources": conflicting}]
            for key, label in (("safe", "One N-safe source witness"), ("conflicting", "One N-conflicting source witness")):
                source = next(family.terms(data[key]), None)
                if source is not None:
                    frames += self.term_frame(source, label)
        elif kind == "ord_group":
            count = family.count(data["sources"])
            title = "Query sources for positive group "+", ".join(point_text(p) for p in data["points"])
            summary = f"Group {data['mask']}: minimum feature-condition distance {data['cost']}, with {count} tied original-source witnesses."
            source = next(family.terms(data["sources"]), None)
            rows = [{"Positive instance": point_text(p), "Original": "Rejected"} for p in data["points"]]
            if source is not None:
                repaired = source.retain_common(data["points"])
                rows.append({"Witness source": term_label(source, names), "Weakened descendant": term_label(repaired, names), "Edit cost": data["cost"]})
                frames = self.term_frame(source, "One tied original source witness") + self.term_frame(repaired, "Its weakened descendant covers this group")
        elif kind == "ord_state":
            title, summary = f"Solve ORD subset state {data['mask']}", f"The optimum for this remaining positive subset is {data['cost']}. Every equality-achieving transition below is retained."
            points = data["points"]
            describe = lambda mask: ", ".join(point_text(p) for i, p in enumerate(points) if mask & (1 << i)) or "∅"
            rows = [{"Cover together": describe(t["group"]), "Remaining": describe(t["rest"]), "Group cost": t["group_cost"], "Remaining cost": t["rest_cost"], "Total": t["group_cost"]+t["rest_cost"]} for t in data["transitions"]]
        elif kind == "negative_action":
            count = family.count(data["sources"])
            literal = term_label(Term.from_literals(self.original.nvars, [data["literal"]]), names)
            title, summary = f"Query the safe added literal {literal}", f"{count} conflicting sources can be repaired by adding this absent literal. Deletion remains available for every conflicting source."
            if count:
                source = next(family.terms(data["sources"]))
                descendant = Term.from_literals(source.nvars, source.literals | {data["literal"]})
                rows = [{"One eligible source": term_label(source, names), "Descendant": term_label(descendant, names), "Cost": 1}]
                frames = self.term_frame(source, "One eligible source") + self.term_frame(descendant, "One-literal specialization")
        elif kind == "excess_level":
            title, summary = f"Try exact excess E={data['excess']}", f"The tested total cost is B+E={data['baseline']}+{data['excess']}={data['cost']}. All lower excess levels have already failed."
            rows = [{"Baseline B": data["baseline"], "Exact excess E": data["excess"], "Tested total cost": data["cost"]}]
        elif kind == "exceptional_query":
            title = "Synthesize source and descendant slots symbolically"
            summary = f"This constraint profile has {data['models']} satisfying source-indexed assignments. No complete PI edit-ball list is built."
            rows = [{"Source slot": i+1, "Local excess": excess, "Descendant slots": size} for i, (excess, size) in enumerate(zip(data["excesses"], data["sizes"]))]
            rows.append({"Eligible original PIs": family.count(data["eligible"]), "Symbolic query nodes": data["nodes"], "Satisfying assignments": str(data["models"])})
        elif kind == "exceptional_candidate":
            title = f"Inspect exceptional configuration {self.candidate}"
            summary = "The exact symbolic query returned these source bundles." if data["bundles"] else "E=0 supplies no exceptional bundles. Test a baseline policy alone."
            rows = self.bundles(data["bundles"])
            for bundle in data["bundles"][:3]:
                frames += self.term_frame(bundle.source, "Exceptional source: "+term_label(bundle.source, names))
                for descendant in bundle.descendants[:3]:
                    frames += self.term_frame(descendant, "Candidate descendant: "+term_label(descendant, names))
        elif kind == "baseline_domains":
            title, summary = "Build this candidate's shared baseline domains", f"Residual source/action guards share coverage constraints. Loss limit {data['loss_limit']}; gain limit {data['gain_limit']}."
            rows = self.domain_rows(data["domains"])
            frames = self.frame(data["base"], "Fixed coverage before choosing residual baseline actions")
        elif kind == "baseline_state":
            title = "Compare guaranteed and possible preservation"
            summary = f"Guaranteed coverage leaves {data['loss_forced']} original unrequested positives uncovered. Even optimistic coverage loses {data['loss_possible']}; the allowed loss is {data['loss_limit']}. These are partial search states."
            rows = self.domain_rows(data["domains"])
            frames = self.frame(data["forced"], "Coverage already guaranteed") + self.frame(data["possible"], "Coverage still possible across remaining actions")
        elif kind == "baseline_witness":
            point = point_text(data["point"])
            title = "Branch on outstanding instance "+point
            summary = "This requested positive must be covered by a remaining action." if data["hard"] else "This original positive is not guaranteed preserved yet. Branch on its first covering action, or permitted loss."
            rows = [{"Witness": point, "Obligation": "Positive success" if data["hard"] else "Semantic preservation"}]
        elif kind == "baseline_force":
            title, summary = "Fix a baseline source action", "This branch fixes one source action and removes that source from every remaining action domain."
            from batch_revision import Bundle
            rows = self.bundles((Bundle(data["source"], data["descendants"]),))
            frames = self.term_frame(data["source"], "Chosen original source")
            for descendant in data["descendants"]:
                frames += self.term_frame(descendant, "Chosen safe baseline descendant")
        elif kind == "baseline_lost":
            title, summary = "Take a permitted LOST branch", f"Instance {point_text(data['point'])} is marked lost. Every action that would cover it is excluded in this disjoint branch. Loss allowance: {data['loss_limit']}."
            rows = [{"Lost witness": point_text(data["point"]), "Total marked lost": self.original.manager.count(data["lost"])}]
        elif kind == "baseline_prune":
            title = "Reject this residual baseline state"
            summary = "A domain/semantic bound fails or no feasible child completion exists. This branch cannot contribute an optimal plan."
            rows = [{"Direct infeasibility detected": str(data["invalid"]), "Optimistic loss": data["loss_possible"], "Loss limit": data["loss_limit"], "Uncoverable positive instances": ", ".join(point_text(p) for p in data["uncovered"]) or "None"}]
        elif kind == "baseline_cache":
            title, summary = "Reuse an equivalent residual subproblem", "The complete residual-domain/provenance state was already compiled; reuse its exact result."
            rows = [{"Fixed source actions": data["forced"], "Residual action guards": data["domains"], "Feasible": str(data["feasible"])}]
        elif kind == "baseline_terminal":
            title, summary = "Compile all independent completions of this state", "Positive coverage and the loss bound already hold under guaranteed coverage. Every remaining independent source/action completion is retained in a product terminal."
            rows = self.domain_rows(data["domains"])
            frames = self.frame(data["forced"], "Coverage sufficient before independent completions")
        elif kind == "baseline_feasible":
            title, summary = "Retain a feasible baseline-plus-exception family", f"Configuration {self.candidate} has a feasible compiled baseline. Continue the same E={data['excess']} level to retain every tie."
            rows = self.bundles(data["bundles"])
        elif kind == "optimum":
            title, summary = "Prove the minimum and retain all ties", f"{data['algorithm']} completed exact optimization at structural cost {data['cost']}. Choice maps below show each source-indexed optimum."
            rows = [{"Algorithm": data["algorithm"], "Minimum cost": data["cost"]}]
        self.add(kind, title, summary, rows, frames, final=kind == "optimum")

    def export(self):
        """Separate diagnostic truncation from the complete compiled optimal-plan family."""
        return {"events": self.events, "total_events": self.total, "omitted_events": self.omitted,
                "limit": self.limit, "complete": not self.omitted}
