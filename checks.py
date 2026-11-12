import json
import random
import sys
from dedup import Deduper
from forest import Forest
from samples import (
    SAMPLES, NORMAL, NORMAL_RETRACTION, INCIDENT, RETRACTION, row
)


def error(call, message):
    try:
        call()
    except ValueError as exc:
        assert str(exc) == message, (str(exc), message)
    else:
        raise AssertionError("expected " + message)


def normal():
    d = Deduper(SAMPLES)
    assert d.apply(NORMAL) == ["n0", "n1", "n2"]
    expected = {"representative": "a", "samples": 3, "signal": 15}
    assert d.read("b") == expected
    assert d.read("d") == {"representative": "d", "samples": 1, "signal": 0}
    assert d.apply(NORMAL_RETRACTION) == ["n0"]
    assert d.read("b") == expected
    before = d.snapshot()
    assert d.apply(NORMAL) == []
    assert d.apply(NORMAL_RETRACTION) == []
    assert d.snapshot() == before
    error(lambda: d.apply([
        row("n1", "b", "c", 2, True), row("n2", "a", "b")
    ]), "REVISION_CONFLICT")
    assert d.snapshot() == before
    assert d.versions["n1"][0] == 1
    error(lambda: d.apply([row("bad", "a", "missing")]), "INPUT")
    error(lambda: d.apply([row("n9", "a", "d"), row("n9", "a", "d")]), "INPUT")
    error(lambda: d.apply([row("bool", "a", "b", True)]), "INPUT")
    assert d.snapshot() == before
    assert d.apply([row("loop", "d", "d"), row("parallel", "a", "c")])
    assert d.read("a") == expected
    d.apply([row("parallel", "a", "c", 2, True), row("loop", "d", "d", 2, True)])
    assert d.read("a") == expected
    d.apply([row("n2", "a", "c", 2, True)])
    assert d.read("a") == {"representative": "a", "samples": 1, "signal": 11}
    assert d.read("c") == {"representative": "b", "samples": 2, "signal": 4}
    d.apply([row("n2", "a", "c", 3)])
    assert d.read("c") == expected
    d.apply([row("n2", "d", "e", 4)])
    assert d.read("d") == {"representative": "d", "samples": 2, "signal": 5}
    assert d.read("b") == {"representative": "b", "samples": 2, "signal": 4}
    error(lambda: d.read("absent"), "UNKNOWN_SAMPLE")
    empty = Deduper({})
    assert empty.apply([]) == [] and empty.snapshot() == {}
    # Forest primitives have an independent topology check.
    f = Forest(SAMPLES)
    f.link("x", "a", "b")
    f.link("y", "b", "c")
    f.link("z", "c", "d")
    assert set(f.vertices("a")) == {"a", "b", "c", "d"}
    f.cut("y")
    assert set(f.vertices("a")) == {"a", "b"}
    assert set(f.vertices("d")) == {"c", "d"}
    f.link("w", "a", "d")
    assert f.read("c") == {"representative": "a", "samples": 4, "signal": 15}
    print("NORMAL_REGRESSION_OK")


def repair():
    d = Deduper(SAMPLES)
    d.apply(INCIDENT)
    expected = {"representative": "a", "samples": 6, "signal": 22}
    assert all(d.read(k) == expected for k in SAMPLES)
    d.apply(RETRACTION)
    actual = d.snapshot()
    wanted = {k: expected for k in sorted(SAMPLES)}
    if actual != wanted:
        print("RETRACTION_COMPONENT_MISMATCH " + json.dumps(
            {"expected": wanted, "actual": actual}, sort_keys=True))
        return 1
    # A later genuine split and resurrection must also update all aggregates.
    d.apply([row("e5", "a", "f", 2, True)])
    for k in ("a", "b", "c"):
        assert d.read(k) == {"representative": "a", "samples": 3, "signal": 15}
    for k in ("d", "e", "f"):
        assert d.read(k) == {"representative": "d", "samples": 3, "signal": 7}
    d.apply([row("e2", "c", "d", 3)])
    assert all(d.read(k) == expected for k in SAMPLES)
    print("CORRECTION_REGRESSION_OK")
    return 0


def demo():
    d = Deduper(SAMPLES)
    d.apply(INCIDENT)
    print(json.dumps({"stage": "before", "samples": d.snapshot()}, sort_keys=True))
    d.apply(RETRACTION)
    print(json.dumps({"stage": "after", "samples": d.snapshot()}, sort_keys=True))


def split_checks():
    d = Deduper(SAMPLES)
    d.apply([row("p0", "a", "b"), row("p1", "b", "c"), row("p2", "c", "d")])
    assert d.read("a") == {"representative": "a", "samples": 4, "signal": 15}
    # A genuine split with no replacement edge anywhere must be exact.
    d.apply([row("p1", "b", "c", 2, True)])
    assert d.read("b") == {"representative": "a", "samples": 2, "signal": 8}
    assert d.read("d") == {"representative": "c", "samples": 2, "signal": 7}
    d.apply([row("p0", "a", "b", 2, True)])
    assert d.read("a") == {"representative": "a", "samples": 1, "signal": 11}
    assert d.read("b") == {"representative": "b", "samples": 1, "signal": -3}
    # Untouched and isolated samples stay singleton clusters.
    assert d.read("e") == {"representative": "e", "samples": 1, "signal": 5}
    assert d.read("f") == {"representative": "f", "samples": 1, "signal": 2}
    # A split deep inside a wider component keeps the rest merged.
    d.apply([row("p3", "d", "e"), row("p4", "e", "f"), row("p5", "c", "d")])
    assert d.read("f") == {"representative": "c", "samples": 4, "signal": 14}
    # One parallel copy retracted: p2 still holds the merge.
    d.apply([row("p5", "c", "d", 2, True)])
    assert d.read("f") == {"representative": "c", "samples": 4, "signal": 14}
    # The last copy goes: the split is genuine and exact.
    d.apply([row("p2", "c", "d", 2, True)])
    assert d.read("c") == {"representative": "c", "samples": 1, "signal": 7}
    assert d.read("f") == {"representative": "d", "samples": 3, "signal": 7}


def replacement_checks():
    # Cutting any single edge of the six-cycle has a remote replacement.
    for cut in ("e0", "e1", "e2", "e3", "e4", "e5"):
        g = Deduper(SAMPLES)
        g.apply(INCIDENT)
        gone = INCIDENT[int(cut[1])]
        g.apply([row(cut, gone["u"], gone["v"], 2, True)])
        expected = {"representative": "a", "samples": 6, "signal": 22}
        assert all(g.read(k) == expected for k in SAMPLES), cut
    # Parallel edges hold the merge; removing every copy splits for real.
    d = Deduper(SAMPLES)
    d.apply([row("x0", "a", "b"), row("x1", "a", "b"), row("x2", "b", "b")])
    d.apply([row("x0", "a", "b", 2, True)])
    assert d.read("b") == {"representative": "a", "samples": 2, "signal": 8}
    d.apply([row("x1", "a", "b", 2, True), row("x2", "b", "b", 2, True)])
    assert d.read("b") == {"representative": "b", "samples": 1, "signal": -3}
    # Two bridges between triangles: one removal merges, both split.
    d = Deduper(SAMPLES)
    d.apply([row("t0", "a", "b"), row("t1", "b", "c"),
             row("t2", "d", "e"), row("t3", "e", "f"),
             row("b0", "c", "d"), row("b1", "a", "f")])
    d.apply([row("b0", "c", "d", 2, True)])
    expected = {"representative": "a", "samples": 6, "signal": 22}
    assert all(d.read(k) == expected for k in SAMPLES)
    d.apply([row("b1", "a", "f", 2, True)])
    assert d.read("c") == {"representative": "a", "samples": 3, "signal": 15}
    assert d.read("f") == {"representative": "d", "samples": 3, "signal": 7}
    # Replacement edges themselves get replaced after later retractions.
    d.apply([row("b0", "c", "d", 3)])
    assert all(d.read(k) == expected for k in SAMPLES)
    d.apply([row("b0", "c", "d", 4, True), row("b1", "a", "f", 3)])
    assert all(d.read(k) == expected for k in SAMPLES)
    d.apply([row("t0", "a", "b", 2, True), row("t1", "b", "c", 2, True),
             row("t2", "d", "e", 2, True), row("t3", "e", "f", 2, True),
             row("b1", "a", "f", 4, True)])
    assert all(d.read(k) == {"representative": k, "samples": 1,
                             "signal": SAMPLES[k]} for k in SAMPLES)


def revision_checks():
    d = Deduper(SAMPLES)
    # A higher revision moves an edge to new endpoints.
    d.apply([row("m0", "a", "b")])
    assert d.apply([row("m0", "c", "d", 2)]) == ["m0"]
    assert d.read("a") == {"representative": "a", "samples": 1, "signal": 11}
    assert d.read("d") == {"representative": "c", "samples": 2, "signal": 7}
    # Stale lower revisions are ignored, tombstones retract, later revive.
    assert d.apply([row("m0", "a", "b")]) == []
    assert d.read("d") == {"representative": "c", "samples": 2, "signal": 7}
    d.apply([row("m0", "c", "d", 3, True)])
    assert d.read("d") == {"representative": "d", "samples": 1, "signal": 0}
    d.apply([row("m0", "e", "f", 4)])
    assert d.read("f") == {"representative": "e", "samples": 2, "signal": 7}
    # Same-revision replay is ignored; conflicting content is rejected
    # atomically with every version and query result unchanged.
    assert d.apply([row("m0", "e", "f", 4)]) == []
    before = d.snapshot()
    error(lambda: d.apply([row("m0", "e", "f", 4, True)]), "REVISION_CONFLICT")
    assert d.snapshot() == before
    # One batch may combine a move, a retraction and a fresh edge.
    d.apply([row("m1", "a", "c"), row("m0", "e", "f", 5, True),
             row("m2", "b", "c")])
    assert d.read("c") == {"representative": "a", "samples": 3, "signal": 15}
    assert d.read("e") == {"representative": "e", "samples": 1, "signal": 5}
    # An invalid row anywhere rejects the whole batch, versions untouched.
    error(lambda: d.apply([row("m3", "a", "f"),
                           row("bad", "a", "missing")]), "INPUT")
    assert "m3" not in d.versions
    assert d.read("f") == {"representative": "f", "samples": 1, "signal": 2}
    # Self-loops are legal, inert, and may be revised into real edges.
    d.apply([row("loop", "f", "f")])
    assert d.read("f") == {"representative": "f", "samples": 1, "signal": 2}
    d.apply([row("loop", "a", "b", 2)])
    assert d.read("b") == {"representative": "a", "samples": 3, "signal": 15}
    # A single sample with only self-loop evidence stays a singleton.
    one = Deduper({"x": -4})
    assert one.apply([row("s", "x", "x")]) == ["s"]
    assert one.read("x") == {"representative": "x", "samples": 1, "signal": -4}
    one.apply([row("s", "x", "x", 2, True)])
    assert one.read("x") == {"representative": "x", "samples": 1, "signal": -4}


class Reference:
    """Brute-force model: recompute components from the version store."""

    def __init__(self, samples):
        self.samples = samples
        self.versions = {}

    def apply(self, rows):
        accepted = {}
        for row_ in rows:
            rec = (row_["rev"], row_["u"], row_["v"], row_["deleted"])
            prev = self.versions.get(row_["id"])
            if prev is not None and (rec[0] < prev[0] or rec == prev):
                continue
            accepted[row_["id"]] = rec
        for eid, rec in accepted.items():
            self.versions[eid] = rec
        return sorted(accepted)

    def snapshot(self):
        parent = {k: k for k in self.samples}

        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        for rev, u, v, deleted in self.versions.values():
            if not deleted:
                parent[find(u)] = find(v)
        comp = {}
        for k in self.samples:
            comp.setdefault(find(k), []).append(k)
        out = {}
        for members in comp.values():
            summary = {"representative": min(members),
                       "samples": len(members),
                       "signal": sum(self.samples[m] for m in members)}
            for k in members:
                out[k] = summary
        return {k: out[k] for k in sorted(self.samples)}


def randomized_rounds(keys, eids, batches, seed):
    rng = random.Random(seed)
    samples = {k: rng.randint(-9, 9) for k in keys}
    d, ref, versions = Deduper(samples), Reference(samples), {}
    for _ in range(batches):
        rows, seen = [], set()
        for _ in range(rng.randrange(6)):
            eid = rng.choice(eids)
            if eid in seen:
                continue
            seen.add(eid)
            prev = versions.get(eid)
            rev = prev[0] if prev else 0
            roll = rng.random()
            if prev and roll < 0.2:
                rec = prev  # identical same-revision replay
            elif prev and roll < 0.35 and rev > 1:
                rec = (rng.randrange(1, rev), rng.choice(keys),
                       rng.choice(keys), rng.random() < 0.25)  # stale
            else:
                rec = (rev + 1, rng.choice(keys), rng.choice(keys),
                       rng.random() < 0.25)
            rows.append({"id": eid, "rev": rec[0], "u": rec[1],
                         "v": rec[2], "deleted": rec[3]})
        assert d.apply(rows) == ref.apply(rows)
        for row_ in rows:
            rec = (row_["rev"], row_["u"], row_["v"], row_["deleted"])
            if rec[0] > versions.get(row_["id"], (0,))[0]:
                versions[row_["id"]] = rec
        assert d.snapshot() == ref.snapshot()
    # Rejected batches leave every observable result untouched.
    before = d.snapshot()
    error(lambda: d.apply([{"id": "zz", "rev": 1, "u": keys[0],
                            "v": "missing", "deleted": False}]), "INPUT")
    eid = next(iter(versions))
    rec = versions[eid]
    error(lambda: d.apply([{"id": eid, "rev": rec[0], "u": rec[1],
                            "v": rec[2], "deleted": not rec[3]}]),
          "REVISION_CONFLICT")
    assert d.snapshot() == before


def randomized_checks():
    randomized_rounds(["s%02d" % i for i in range(10)],
                      ["e%02d" % i for i in range(20)], 500, 20261112)
    randomized_rounds(["t%02d" % i for i in range(40)],
                      ["f%02d" % i for i in range(90)], 400, 7)


def extended():
    split_checks()
    replacement_checks()
    revision_checks()
    randomized_checks()
    print("EXTENDED_REGRESSION_OK")
    return 0


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) == 2 else ""
    if mode == "normal":
        normal()
    elif mode == "repair":
        sys.exit(repair())
    elif mode == "verify":
        normal()
        rc = repair()
        if rc == 0:
            rc = extended()
        sys.exit(rc)
    elif mode == "extra":
        sys.exit(extended())
    elif mode == "demo":
        demo()
    else:
        raise SystemExit(
            "usage: python3 checks.py normal|repair|verify|extra|demo")
