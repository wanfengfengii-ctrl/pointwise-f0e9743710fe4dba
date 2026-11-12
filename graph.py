"""Incremental evidence graph backed by an Euler-tour spanning forest."""
from forest import Forest


class EvidenceGraph:
    def __init__(self, samples):
        self.forest = Forest(samples)
        self.edges = {}
        self.extra = {key: set() for key in samples}

    def add(self, eid, u, v):
        is_tree = not self.forest.connected(u, v)
        self.edges[eid] = (u, v, is_tree)
        if is_tree:
            self.forest.link(eid, u, v)
        else:
            self.extra[u].add(eid)
            self.extra[v].add(eid)

    def remove(self, eid):
        u, v, is_tree = self.edges.pop(eid)
        if not is_tree:
            self.extra[u].discard(eid)
            self.extra[v].discard(eid)
            return
        self.forest.cut(eid)
        # Endpoint-local repair avoids traversing the entire former cluster.
        candidates = self.extra[u] | self.extra[v]
        for replacement in sorted(candidates):
            a, b, _ = self.edges[replacement]
            if not self.forest.connected(a, b):
                self.extra[a].discard(replacement)
                self.extra[b].discard(replacement)
                self.forest.link(replacement, a, b)
                self.edges[replacement] = (a, b, True)
                break

    def read(self, sample):
        return self.forest.read(sample)
