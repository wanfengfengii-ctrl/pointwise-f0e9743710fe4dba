"""Public batch interface for revisioned laboratory evidence."""
from graph import EvidenceGraph


class Deduper:
    def __init__(self, samples):
        if not isinstance(samples, dict) or any(
            not isinstance(k, str) or not k or type(v) is not int
            for k, v in samples.items()
        ):
            raise ValueError("INPUT")
        self.samples = dict(samples)
        self.versions = {}
        self.graph = EvidenceGraph(self.samples)

    def _record(self, row):
        if not isinstance(row, dict) or set(row) != {
            "id", "rev", "u", "v", "deleted"
        }:
            raise ValueError("INPUT")
        eid, rev, u, v, deleted = (
            row["id"], row["rev"], row["u"], row["v"], row["deleted"]
        )
        if (not isinstance(eid, str) or not eid or type(rev) is not int
                or rev < 1 or not isinstance(u, str)
                or not isinstance(v, str) or u not in self.samples
                or v not in self.samples or type(deleted) is not bool):
            raise ValueError("INPUT")
        return eid, (rev, u, v, deleted)

    def apply(self, rows):
        if not isinstance(rows, list):
            raise ValueError("INPUT")
        seen, accepted = set(), {}
        for row in rows:
            eid, record = self._record(row)
            if eid in seen:
                raise ValueError("INPUT")
            seen.add(eid)
            previous = self.versions.get(eid)
            if previous is not None:
                if record[0] < previous[0]:
                    continue
                if record[0] == previous[0]:
                    if record != previous:
                        raise ValueError("REVISION_CONFLICT")
                    continue
            accepted[eid] = record
        # No graph changes take place until every row passes validation.
        for eid in sorted(accepted):
            previous = self.versions.get(eid)
            if previous is not None and not previous[3]:
                self.graph.remove(eid)
            rev, u, v, deleted = accepted[eid]
            if not deleted:
                self.graph.add(eid, u, v)
            self.versions[eid] = accepted[eid]
        return sorted(accepted)

    def read(self, sample):
        if not isinstance(sample, str) or sample not in self.samples:
            raise ValueError("UNKNOWN_SAMPLE")
        return self.graph.read(sample)

    def snapshot(self):
        return {key: self.read(key) for key in sorted(self.samples)}
