"""Fully dynamic evidence graph (Holm, de Lichtenberg and Thorup levels).

Every live evidence edge carries a level in [0, L], L = O(log n) for n
samples. Forest F_i is a spanning forest of the edges with level >= i, the
forests are nested (F_0 covers every edge), each F_i tree spans at most
n / 2**i samples, and every non-tree edge of level i has both endpoints
inside one F_i tree. F_0 alone answers component aggregates, so clusters
always equal the connected components of the effective undirected graph.

Deleting a tree edge of level l cuts it from F_0..F_l. Any non-tree edge
reconnecting the two sides must sit at level <= l (a higher-level one
would keep its endpoints linked inside F_l+1..F_L all along), so the
repair searches levels l down to 0: at level i the smaller side T_u (at
most n / 2**(i+1) samples) first promotes all of its level-i tree edges
to level i+1, then scans its level-i non-tree edges. Edges falling back
into T_u are promoted; the first edge crossing to the other side is
linked into F_0..F_i as the replacement and the search stops. Levels
above the found replacement keep genuine cuts. If no level yields a
crossing edge the split is genuine. Edge levels only rise, so each
evidence edge pays O(log N) expected treap work at most L times in its
life: expected amortized O(log^2 N) per evidence update, O(log N)
expected per sample query, and O(N log N) space over the whole
structure. Self-loops never influence connectivity and are kept as
inert records only.
"""
from forest import Forest


class EvidenceGraph:
    def __init__(self, samples):
        self.samples = samples
        self.depth = max(1, len(samples).bit_length())
        self.forests = [Forest(samples) for _ in range(self.depth + 1)]
        self.edges = {}
        self.nontree = [{key: set() for key in samples}
                        for _ in range(self.depth + 1)]

    def _note_add(self, eid, u, v, i):
        self.nontree[i][u].add(eid)
        self.forests[i].mark_vertex(u, True)
        self.nontree[i][v].add(eid)
        self.forests[i].mark_vertex(v, True)

    def _note_remove(self, eid, u, v, i):
        self.nontree[i][u].discard(eid)
        if not self.nontree[i][u]:
            self.forests[i].mark_vertex(u, False)
        self.nontree[i][v].discard(eid)
        if not self.nontree[i][v]:
            self.forests[i].mark_vertex(v, False)

    def add(self, eid, u, v):
        if u == v:
            self.edges[eid] = (u, v, 0, False)
            return
        if self.forests[0].connected(u, v):
            self.edges[eid] = (u, v, 0, False)
            self._note_add(eid, u, v, 0)
        else:
            self.edges[eid] = (u, v, 0, True)
            self.forests[0].link(eid, u, v)
            self.forests[0].mark_edge(eid, True)

    def remove(self, eid):
        u, v, level, is_tree = self.edges.pop(eid)
        if u == v:
            return
        if not is_tree:
            self._note_remove(eid, u, v, level)
            return
        for i in range(level + 1):
            self.forests[i].cut(eid)
        self._replace(u, v, level)

    def _replace(self, u, v, level):
        for i in range(level, -1, -1):
            forest = self.forests[i]
            if forest.tree_count(u) > forest.tree_count(v):
                u, v = v, u
            # Promote the smaller side's level-i tree edges to level i+1.
            while True:
                found = forest.find_edge_mark(u)
                if found is None:
                    break
                a, b, _, _ = self.edges[found]
                forest.mark_edge(found, False)
                self.forests[i + 1].link(found, a, b)
                self.forests[i + 1].mark_edge(found, True)
                self.edges[found] = (a, b, i + 1, True)
            # Scan the smaller side's level-i non-tree edges.
            while True:
                x = forest.find_vert_mark(u)
                if x is None:
                    break
                for found in list(self.nontree[i][x]):
                    a, b, _, _ = self.edges[found]
                    y = b if a == x else a
                    self._note_remove(found, a, b, i)
                    if forest.connected(x, y):
                        self._note_add(found, a, b, i + 1)
                        self.edges[found] = (a, b, i + 1, False)
                    else:
                        for j in range(i + 1):
                            self.forests[j].link(found, a, b)
                        self.forests[i].mark_edge(found, True)
                        self.edges[found] = (a, b, i, True)
                        return

    def read(self, sample):
        return self.forests[0].read(sample)
