
from .distance import node_dist
from .sdd_utils import term_to_sdd

def fmt_term(term, names=None):
    """A term {var:bool} -> 'a & !b & c'."""
    if not term:
        return "T"
    def nm(v):
        return names[v] if names else f"x{v}"
    return " & ".join(nm(v) if val else "!" + nm(v) for v, val in sorted(term.items()))

def fmt_instance(omega, names=None):
    """An instance -> 'a=1 b=0 c=0'."""
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

def sdd_structure(node, max_depth=6):
    """A nested textual view of the SDD decomposition (primes|subs), for small SDDs."""
    seen = {}
    lines = []
    def walk(n, depth, prefix):
        if depth > max_depth:
            lines.append("  " * depth + prefix + "...")
            return
        if n.is_true():
            lines.append("  " * depth + prefix + "T"); return
        if n.is_false():
            lines.append("  " * depth + prefix + "F"); return
        if n.is_literal():
            lines.append("  " * depth + prefix + f"lit({n.literal})"); return
        if n.id in seen:
            lines.append("  " * depth + prefix + f"<shared node {n.id}>"); return
        seen[n.id] = True
        lines.append("  " * depth + prefix + f"decision (node {n.id}):")
        for i, (p, s) in enumerate(n.elements()):
            walk(p, depth + 1, f"[{i}] prime: ")
            walk(s, depth + 1, f"    sub:   ")
    walk(node, 0, "")
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
