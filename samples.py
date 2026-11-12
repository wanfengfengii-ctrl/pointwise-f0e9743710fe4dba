"""Recorded samples and evidence batches; integers are signed signal units."""
SAMPLES = {"a": 11, "b": -3, "c": 7, "d": 0, "e": 5, "f": 2}


def row(eid, u, v, rev=1, deleted=False):
    return {"id": eid, "rev": rev, "u": u, "v": v, "deleted": deleted}


NORMAL = [
    row("n0", "a", "b"),
    row("n1", "b", "c"),
    row("n2", "a", "c"),
]
NORMAL_RETRACTION = [row("n0", "a", "b", 2, True)]
INCIDENT = [row("e" + str(i), u, v) for i, (u, v) in enumerate([
    ("a", "b"), ("b", "c"), ("c", "d"),
    ("d", "e"), ("e", "f"), ("a", "f"),
])]
RETRACTION = [row("e2", "c", "d", 2, True)]
