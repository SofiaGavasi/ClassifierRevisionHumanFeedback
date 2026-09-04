
from .distance import node_dist
from .sdd_utils import term_to_sdd

def fmt_term(term, names=None):
    """Turns a term dictionary like {1: True, 2: False, 3: True} into a string like "a & !b & c" """
    if not term:
        return "T"
    def nm(v):
        return names[v] if names else f"x{v}"
    return " & ".join(nm(v) if val else "!" + nm(v) for v, val in sorted(term.items()))

def fmt_instance(omega, names=None):
    """An instance -> 'a=1 b=0 c=0' """
    def nm(v):
        return names[v] if names else f"x{v}"
    return " ".join(f"{nm(v)}={int(val)}" for v, val in sorted(omega.items()))

def sdd_info(node, mgr, nvars, names=None):
    """Summary dict of an SDD: size, model count, node count."""
    return {
        "size": node.size(),
        "model_count": node.global_model_count(),
        "is_true": bool(node.is_true()),
        "is_false": bool(node.is_false()),
        "num_vars": nvars,
    }

def sdd_structure(node, names=None, max_depth=6):
    """A nested textual view of the SDD decomposition, for small SDDs.
    """
    seen = set() # tracks nodes already printed, so shared nodes (reached from multiple parents) aren't expanded twice

    def lit_str(n): # formats a literal node (a or !a), using names if given
        v = abs(n.literal)
        name = names[v] if names else f"x{v}"
        return name if n.literal > 0 else "!" + name

    def terminal(n):
        """Return an inline string if n is terminal/literal, else None."""
        if n.is_true():    return "T"
        if n.is_false():   return "F"
        if n.is_literal(): return lit_str(n)
        return None

    lines = []

    def walk(n, indent): # recursively walk the SDD, printing each node and its children, with indentation
        pad = "    " * indent
        t = terminal(n)
        if t is not None:
            lines.append(pad + t)
            return
        if n.id in seen:
            lines.append(pad + f"<node {n.id}, shown above>")
            return
        if indent > max_depth:
            lines.append(pad + "...")
            return
        seen.add(n.id)
        lines.append(pad + f"node {n.id}  (choose one branch):")
        for p, s in n.elements():
            pt, st = terminal(p), terminal(s)
            # prime is always a literal/terminal in a compressed SDD; show it inline
            head = pad + f"  if {pt if pt is not None else '(decision)'}  then"
            if st is not None:
                lines.append(head + f"  {st}")
            else:
                lines.append(head + ":")
                walk(s, indent + 2)
    walk(node, 0)
    return "\n".join(lines)

def explain_edit(delta, omega, mgr, nvars, result, names=None):
    """Produce a readable multi-line explanation of an edit result."""
    L = []
    L.append(f"instance:        {fmt_instance(omega, names)}")
    L.append(f"classified:      {'ACCEPT' if not (term_to_sdd(omega,mgr)&delta).is_false() else 'REJECT'}")
    L.append(f"nearest distance:{result.get('distance')}")
    if result.get("reason") is not None:
        L.append(f"reason found:    {fmt_term(result['reason'], names)}")
        L.append(f"weakened to:     {fmt_term(result['weakened'], names)}")
    L.append(f"models before:   {delta.global_model_count()}")
    L.append(f"models after:    {result['edited'].global_model_count()}")
    return "\n".join(L)