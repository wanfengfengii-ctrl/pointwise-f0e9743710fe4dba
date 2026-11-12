"""Euler-tour forest. Each sample contributes exactly one weighted occurrence.

Besides the exact component aggregates (minimum sample id, sample count and
signal sum), every treap node carries two boolean marks used by the dynamic
level scheme in graph.py: an edge mark selects the tree-edge tokens whose
evidence currently sits at this forest's own level, and a vertex mark
selects samples that still hold non-tree edges of this forest's level. The
subtree "any" flags let the owner locate a marked token in expected O(log N).
Random priorities only shape the treap; every reported aggregate is exact.
"""
import random


class _Node:
    __slots__ = ("key", "weight", "priority", "left", "right", "parent",
                 "size", "count", "total", "minimum", "edge_id",
                 "edge_mark", "vert_mark", "edge_any", "vert_any")

    def __init__(self, key, weight, priority, edge_id=None):
        self.key, self.weight, self.priority = key, weight, priority
        self.edge_id = edge_id
        self.left = self.right = self.parent = None
        self.size = 1
        self.count = int(key is not None)
        self.total = weight
        self.minimum = key
        self.edge_mark = self.vert_mark = False
        self.edge_any = self.vert_any = False


def _size(t):
    return t.size if t else 0


def _pull(t):
    t.size = 1 + _size(t.left) + _size(t.right)
    t.count = int(t.key is not None)
    t.total = t.weight
    t.edge_any = t.edge_mark
    t.vert_any = t.vert_mark
    choices = [] if t.key is None else [t.key]
    for child in (t.left, t.right):
        if child:
            child.parent = t
            t.count += child.count
            t.total += child.total
            t.edge_any = t.edge_any or child.edge_any
            t.vert_any = t.vert_any or child.vert_any
            if child.minimum is not None:
                choices.append(child.minimum)
    t.minimum = min(choices) if choices else None


def _merge(a, b):
    if not a or not b:
        t = a or b
        if t:
            t.parent = None
        return t
    if a.priority < b.priority:
        a.right = _merge(a.right, b)
        _pull(a)
        a.parent = None
        return a
    b.left = _merge(a, b.left)
    _pull(b)
    b.parent = None
    return b


def _split(t, k):
    if not t:
        return None, None
    if _size(t.left) >= k:
        a, t.left = _split(t.left, k)
        _pull(t)
        t.parent = None
        if a:
            a.parent = None
        return a, t
    t.right, b = _split(t.right, k - _size(t.left) - 1)
    _pull(t)
    t.parent = None
    if b:
        b.parent = None
    return t, b


def _root(t):
    while t.parent:
        t = t.parent
    return t


def _rank(t):
    n = _size(t.left)
    while t.parent:
        p = t.parent
        if p.right is t:
            n += 1 + _size(p.left)
        t = p
    return n


class Forest:
    def __init__(self, samples):
        self.random = random.Random()
        self.vertex = {key: self._node(key, value)
                       for key, value in samples.items()}
        self.edge = {}

    def _node(self, key=None, value=0, edge_id=None):
        return _Node(key, value, self.random.getrandbits(64), edge_id)

    def connected(self, u, v):
        return _root(self.vertex[u]) is _root(self.vertex[v])

    def _reroot(self, u):
        t = self.vertex[u]
        a, b = _split(_root(t), _rank(t))
        return _merge(b, a)

    def link(self, eid, u, v):
        if eid in self.edge or self.connected(u, v):
            raise ValueError("FOREST_LINK")
        a, b = self._reroot(u), self._reroot(v)
        outward = self._node(edge_id=eid)
        inward = self._node(edge_id=eid)
        _merge(_merge(_merge(a, outward), b), inward)
        self.edge[eid] = outward, inward

    def cut(self, eid):
        a, b = self.edge.pop(eid)
        i, j = _rank(a), _rank(b)
        if i > j:
            i, j = j, i
        prefix, rest = _split(_root(a), i)
        first, rest = _split(rest, 1)
        middle, rest = _split(rest, j - i - 1)
        second, suffix = _split(rest, 1)
        _merge(suffix, prefix)
        for token in (first, second):
            token.left = token.right = token.parent = None
            token.edge_mark = False
            _pull(token)

    def read(self, u):
        t = _root(self.vertex[u])
        return {"representative": t.minimum, "samples": t.count,
                "signal": t.total}

    def vertices(self, u):
        stack, t = [], _root(self.vertex[u])
        while stack or t:
            if t:
                stack.append(t)
                t = t.left
            else:
                t = stack.pop()
                if t.key is not None:
                    yield t.key
                t = t.right

    def tree_count(self, u):
        return _root(self.vertex[u]).count

    def _refresh(self, t):
        while t is not None:
            _pull(t)
            t = t.parent

    def mark_vertex(self, u, on):
        t = self.vertex[u]
        if t.vert_mark != on:
            t.vert_mark = on
            self._refresh(t)

    def mark_edge(self, eid, on):
        for t in self.edge[eid]:
            if t.edge_mark != on:
                t.edge_mark = on
                self._refresh(t)

    def find_edge_mark(self, u):
        t = _root(self.vertex[u])
        while t is not None and t.edge_any:
            if t.left is not None and t.left.edge_any:
                t = t.left
            elif t.edge_mark:
                return t.edge_id
            else:
                t = t.right
        return None

    def find_vert_mark(self, u):
        t = _root(self.vertex[u])
        while t is not None and t.vert_any:
            if t.left is not None and t.left.vert_any:
                t = t.left
            elif t.vert_mark:
                return t.key
            else:
                t = t.right
        return None
