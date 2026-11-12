import json
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


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) == 2 else ""
    if mode == "normal":
        normal()
    elif mode == "repair":
        sys.exit(repair())
    elif mode == "verify":
        normal()
        sys.exit(repair())
    elif mode == "demo":
        demo()
    else:
        raise SystemExit("usage: python3 checks.py normal|repair|verify|demo")
