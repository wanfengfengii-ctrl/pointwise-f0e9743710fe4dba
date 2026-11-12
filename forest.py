"""Euler-tour forest. Each sample contributes exactly one weighted occurrence."""
import random


class _Node:
    __slots__ = ("key", "weight", "priority", "left", "right", "parent",
                 "size", "count", "total", "minimum")

    def __init__(self, key, weight, priority):
        self.key, self.weight, self.priority = key, weight, priority
        self.left = self.right = self.parent = None
        self.size = 1
        self.count = int(key is not None)
        self.total = weight
        self.minimum = key


def _size(t):
    return t.size if t else 0


def _pull(t):
    t.size = 1 + _size(t.left) + _size(t.right)
    t.count = int(t.key is not None)
    t.total = t.weight
    choices = [] if t.key is None else [t.key]
    for child in (t.left, t.right):
        if child:
            child.parent = t
            t.count += child.count
            t.total += child.total
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

    def _node(self, key=None, value=0):
        return _Node(key, value, self.random.getrandbits(64))

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
        outward, inward = self._node(), self._node()
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
