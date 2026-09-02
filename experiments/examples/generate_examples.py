"""
Generates a diverse dataset of example classifiers as JSON

Each example is stored as:
  {
    "id": str, "family": str, "nvars": int, "description": str,
    "formula": {...}            # a small AST the loader rebuilds into an SDD
    "test_instances": [ {var:bool}, ... ]   # interesting instances to try
    "notes": str
  }

Formula AST node types (rebuilt by the loader):
  {"op":"var","v":i}  {"op":"not","x":A}
  {"op":"and","xs":[...]}  {"op":"or","xs":[...]}
  {"op":"tree","tree":<nested-dict decision tree>}
  {"op":"const","val":true/false}

Run:  python experiments/examples/generate_examples.py
"""
import json, os, random

OUT = os.path.join(os.path.dirname(__file__), "..", "..", "data", "examples")
os.makedirs(OUT, exist_ok=True)

def V(i):   return {"op":"var","v":i}
def NOT(a): return {"op":"not","x":a}
def AND(*xs): return {"op":"and","xs":list(xs)}
def OR(*xs):  return {"op":"or","xs":list(xs)}

examples = []

def add(id, family, nvars, formula, tests, description, notes=""):
    examples.append({"id":id,"family":family,"nvars":nvars,"description":description,
                     "formula":formula,"test_instances":tests,"notes":notes})

# ---- Canonical hand examples ----
add("wine", "canonical", 4,
    AND(NOT(V(1)), OR(NOT(V(3)),V(4)), OR(V(4),V(2))),
    [{1:True,2:True,3:True,4:True}, {1:False,2:True,3:True,4:True}],
    "Wine classifier !m & (f->w) & (w|r) from the IJCAI paper (m,r,f,w = 1,2,3,4).",
    "The running example; rejected instance all-true has nearest reason !m&w -> weakened w.")

add("ab_or_c", "canonical", 3,
    OR(AND(V(1),V(2)), V(3)),
    [{1:False,2:False,3:False}],
    "(a & b) | c.",
    "Used throughout the notes for the bottom-up pass and reconstruction.")

# ---- Definition-6 divergence cases (set vs single-reason differ) ----
add("def6_divergence", "def6_divergence", 3,
    OR(V(3), AND(NOT(V(1)),NOT(V(2)))),
    [{1:True,2:False,3:False}],
    "c | (!a & !b): two reasons tie at disagreement 1.",
    "All-minimal reading weakens both (c -> T, opening the classifier); single-reason stays conservative.")

# ---- Worst case for the NAIVE method: parity (small SDD, exponentially many PIs) ----
def parity(n):
    # xor chain rebuilt as nested (a xor b) = (a&!b)|(!a&b)
    def xor(a,b): return OR(AND(a,NOT(b)),AND(NOT(a),b))
    expr = V(1)
    for i in range(2,n+1):
        expr = xor(expr, V(i))
    return expr
for n in [4,6,8,10,12]:
    add(f"parity_{n}", "worst_case_naive", n, parity(n),
        [{v: False for v in range(1,n+1)}],
        f"Parity (XOR) of {n} variables.",
        "Small SDD but 2^(n-1) prime implicants: the naive reason-enumeration blows up, the pipeline does not.")

# ---- Worst case for the PIPELINE: Hidden Weighted Bit (no small SDD) ----
for n in [4,6,8,10,12]:
    add(f"hwb_{n}", "worst_case_pipeline", n, {"op":"hwb","n":n},
        [{v: False for v in range(1,n+1)}, {v: (v==1) for v in range(1,n+1)}],
        f"Hidden Weighted Bit HWB_{n}: output is x_k where k = number of 1s in the input.",
        "The pipeline's worst case: HWB has NO small SDD (size grows exponentially in n")

# ----  Worst case for the PIPELINE, proven for ALL vtrees: Q_V ----
# Q_V has m*m + 2m variables; kept to small m so it stays loadable.
for m in [2, 3, 4]:
    nv = m * m + 2 * m
    # a rejected instance: all variables false (no pair has two bits set)
    rej = {v: False for v in range(1, nv + 1)}
    add(f"q_v_{m}", "worst_case_pipeline_allvtrees", nv, {"op": "q_v", "m": m},
        [rej],
        f"Q_V database-query lineage, m={m} ({nv} variables).",
        "The cleanest PROVEN worst case for the pipeline. Every SDD for Q_V has size "
        "at least 2^(sqrt(m/3)-1) under EVERY vtree")

# ---- Decision trees (structured input, linear-size SDD) ----
def balanced_tree(depth, start=1):
    # a full binary decision tree of given depth; leaves alternate accept/reject
    counter = [start]
    def build(d):
        if d==0:
            return bool(random.getrandbits(1))
        f = counter[0]; counter[0]+=1
        return {"feature":f, "true":build(d-1), "false":build(d-1)}
    return build(depth), counter[0]-start
rng = random.Random(1)
random.seed(1)
tree, used = balanced_tree(3, 1)
add("decision_tree_d3", "decision_tree", used,
    {"op":"tree","tree":tree},
    [{v: False for v in range(1,used+1)}, {v: True for v in range(1,used+1)}],
    f"A depth-3 balanced decision tree over {used} features.")

# ---- Necessary-reason case (a shared literal across all reasons) ----
add("has_necessary", "structured", 3,
    AND(V(1), OR(V(2),V(3))),
    [{1:False,2:False,3:False},{1:False,2:True,3:False}],
    "a & (b | c): 'a' is a necessary reason (appears in every model).",
    "Good for testing the (PC)/(CC) conservation behaviour.")

# ---- Tie-rich symmetric case ----
add("xnor", "ties", 2,
    OR(AND(V(1),V(2)), AND(NOT(V(1)),NOT(V(2)))),
    [{1:True,2:False},{1:False,2:True}],
    "x <-> y (XNOR): two symmetric models, ties everywhere.")

# ---- WRandom satisfiable classifiers of increasing size ----
def random_cnf(nvars, nclauses, seed):
    r = random.Random(seed)
    # satisfiable by construction: fix a witness, keep clauses it satisfies
    witness = {v: r.random()<0.5 for v in range(1,nvars+1)}
    clauses = []
    for _ in range(nclauses):
        chosen = r.sample(range(1,nvars+1), min(3,nvars))
        keep = r.choice(chosen)
        lits = [ V(keep) if witness[keep] else NOT(V(keep)) ]
        for v in chosen:
            if v==keep: continue
            lits.append(V(v) if r.random()<0.5 else NOT(V(v)))
        clauses.append(OR(*lits) if len(lits)>1 else lits[0])
    return AND(*clauses), witness
for i,(nv,nc) in enumerate([(4,3),(6,4),(8,5),(10,6),(12,7)],):
    f,wit = random_cnf(nv,nc, 100+i)
    # a rejected instance: flip the witness fully
    rej = {v: not wit[v] for v in range(1,nv+1)}
    add(f"random_{nv}v", "random", nv, f, [rej],
        f"Random satisfiable CNF, {nv} vars, {nc} clauses.",
        "For scaling and general stress testing.")

# ---- write out ----
with open(os.path.join(OUT,"examples.json"),"w") as fh:
    json.dump(examples, fh, indent=2)
print(f"wrote {len(examples)} examples to data/examples/examples.json")
for e in examples:
    print(f"  {e['id']:20s} [{e['family']}] nvars={e['nvars']}")