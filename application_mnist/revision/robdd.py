from __future__ import annotations

from itertools import islice
from math import inf
from typing import Iterable, Mapping
import numpy as np

from ._rgr import require_rgr


class BDDLimitError(RuntimeError):
    """An SDD has exceeded the requested diagnostic size guard."""


class ROBDD:
    def __init__(self, n_features, *, max_nodes = 100_000, active_indices = None):
        if n_features < 1:
            raise ValueError('Expected at least one feature')
        require_rgr()
        from rgr.sdd_utils import build
        self.n_features = int(n_features)
        self.max_nodes = int(max_nodes)
        indices = (tuple(range(self.n_features)) if active_indices is None
                   else tuple(sorted(set(int(i) for i in active_indices))))
        if any(i < 0 or i >= self.n_features for i in indices):
            raise ValueError('active_indices contains an invalid feature')
        self.active_indices = indices
        self.original_to_sdd = {idx: j + 1 for j, idx in enumerate(indices)}
        self.sdd_to_original = {v: k for k, v in self.original_to_sdd.items()}
        # A 1-var SDD also works for constant Boolean functions.
        self.manager, _ = build(max(1, len(indices)))
        self._handles: dict[int, object] = {}
        self._by_node_id: dict[int, int] = {}
        self._next_handle = 2
        self._source_dnfs: dict[int, list[list[list[int | bool]]]] = {}

    @property
    def n_sdd_variables(self):
        return max(1, len(self.active_indices))

    def _store(self, node):
        if node.is_false():
            return 0
        if node.is_true():
            return 1
        if node.size() > self.max_nodes:
            raise BDDLimitError(f'SDD exceeded {self.max_nodes} elements')
        identifier = int(node.id)
        if identifier not in self._by_node_id:
            handle = self._next_handle
            self._next_handle += 1
            self._by_node_id[identifier] = handle
            self._handles[handle] = node
        return self._by_node_id[identifier]

    def node(self, handle):
        if handle == 0:
            return self.manager.false()
        if handle == 1:
            return self.manager.true()
        return self._handles[int(handle)]

    def _mapped(self, term):
        converted: dict[int, bool] = {}
        for i, val in term:
            i, val = int(i), bool(val)
            if i < 0 or i >= self.n_features:
                raise ValueError(f'Invalid feature index: {i}')
            if i not in self.original_to_sdd:
                raise ValueError(f'Feature {i} was excluded from this SDD manager')
            v = self.original_to_sdd[i]
            if v in converted and converted[v] != val:
                raise ValueError('Inconsistent term')
            converted[v] = val
        return converted

    def _omega(self, values):
        x = np.asarray(values)
        if x.shape != (self.n_features,) or not np.all(np.isin(x, [0, 1])):
            raise ValueError(f'Expected Boolean vector of length {self.n_features}')
        result = {var: bool(x[index]) for index, var in self.original_to_sdd.items()}
        if not result:  # dummy SDD variable for a constant function
            result[1] = bool(x[0])
        return result

    def _from_model(self, values, reference):
        x = np.asarray(reference, dtype=np.uint8).copy()
        for var, val in values.items():
            if int(var) in self.sdd_to_original:
                x[self.sdd_to_original[int(var)]] = int(bool(val))
        return x

    def variable(self, index, value = True):
        index = int(index)
        if index not in self.original_to_sdd:
            raise ValueError(f'Feature {index} not in the compiled SDD variable map')
        return self._store(self.manager.literal(
            self.original_to_sdd[index] * (1 if value else -1)))

    def negate(self, root):
        return self._store(~self.node(root))

    def apply(self, op, left, right):
        if op == 'and':
            return self._store(self.node(left) & self.node(right))
        if op == 'or':
            return self._store(self.node(left) | self.node(right))
        raise ValueError('Only and/or supported')

    def cube(self, term):
        from rgr.sdd_utils import term_to_sdd
        return self._store(term_to_sdd(self._mapped(term), self.manager))

    def dnf(self, terms):
        from rgr.sdd_utils import term_to_sdd
        frozen = [tuple((int(i), bool(v)) for i, v in term) for term in terms]
        root = self.manager.false()
        for term in frozen:
            root = root | term_to_sdd(self._mapped(term), self.manager)
        handle = self._store(root)
        self._source_dnfs[handle] = [ [[i, v] for i, v in term] for term in frozen ]
        return handle

    def support(self, root):
        from rgr.enumeration.conditioning import support_of
        return tuple(sorted(self.sdd_to_original[v] for v in support_of(self.node(root)) if v in self.sdd_to_original))

    def reachable_nodes(self, root):
        return int(self.node(root).size())

    def evaluate(self, root, assignment):
        node = self.node(root)
        for variable, val in self._omega(assignment).items():
            node = node.condition(variable if val else -variable)
            if node.is_false():
                return False
            if node.is_true():
                return True
        return bool(node.is_true())

    def evaluate_batch(self, root, X):
        arr = np.asarray(X)
        if arr.ndim != 2 or arr.shape[1] != self.n_features:
            raise ValueError(f'Expected shape (n, {self.n_features})')
        return np.fromiter((self.evaluate(root, x) for x in arr), dtype=np.uint8, count=len(arr))

    def restrict(self, root, assignment):
        node = self.node(root)
        for index, value in assignment.items():
            index = int(index)
            if not 0 <= index < self.n_features:
                raise ValueError(f'Invalid feature: {index}')
            if index in self.original_to_sdd:
                v = self.original_to_sdd[index]
                node = node.condition(v if value else -v)
        return self._store(node)

    def entails(self, desired, term):
        from rgr.sdd_utils import is_implicant
        return bool(is_implicant(self._mapped(term), self.node(desired), self.manager))

    def witness(self, root, reference, fixed= None):
        from rgr.reconstruct import nearest_model
        constrained = self.restrict(root, fixed or {})
        adjusted = np.asarray(reference, dtype=np.uint8).copy()
        for index, value in (fixed or {}).items():
            adjusted[int(index)] = int(bool(value))
        omega = self._omega(adjusted)
        model, dist = nearest_model(self.node(constrained), omega, self.n_sdd_variables)
        return None if model is None else self._from_model(model, adjusted)

    def min_distance(self, root, target):
        from rgr.distance import node_dist
        value = node_dist(self.node(root), self._omega(target), {})
        return None if value == inf else int(value)

    def nearest_models(self, root, target, max_models = 64):
        from rgr.enumerate import models_at
        if max_models < 1:
            raise ValueError('max_models must be positive')
        omega = self._omega(target)
        distance = self.min_distance(root, target)
        if distance is None:
            return [], False, None
        stream = models_at(self.node(root), omega, self.n_sdd_variables, distance)
        bounded = list(islice(stream, max_models + 1))
        return ([self._from_model(m, target) for m in bounded[:max_models]], len(bounded) > max_models, distance)
