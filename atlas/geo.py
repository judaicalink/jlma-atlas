"""The present-day country of a point, from the countries of assets/basemap.json."""

import json


def decode(flat, q):
    pts, x, y = [], 0, 0
    for i in range(0, len(flat), 2):
        x += flat[i]
        y += flat[i + 1]
        pts.append((x / q, y / q))
    return pts


def inside(pt, ring):
    x, y = pt
    c = False
    j = len(ring) - 1
    for i in range(len(ring)):
        xi, yi = ring[i]
        xj, yj = ring[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            c = not c
        j = i
    return c


class Countries:
    NEAR = 0.3   # degrees: a point on a coast outside the simplified outline belongs to the nearest country

    def __init__(self, basemap_path):
        with open(basemap_path, encoding="utf-8") as f:
            bm = json.load(f)
        self.names = [c["n"] for c in bm["countries"]]
        self.codes = [c["c"] for c in bm["countries"]]
        self.shapes = [(c["b"], [decode(r, bm["q"]) for r in c["p"]]) for c in bm["countries"]]

    def of(self, lon, lat):
        """The index of the country, or -1. Rings are tested with the even-odd rule (holes are rings too)."""
        pt = (lon, lat)
        for i, (b, rings) in enumerate(self.shapes):
            if b[0] <= lon <= b[2] and b[1] <= lat <= b[3]:
                if sum(inside(pt, r) for r in rings) % 2:
                    return i
        best, idx = self.NEAR ** 2, -1
        for i, (b, rings) in enumerate(self.shapes):
            if b[0] - self.NEAR <= lon <= b[2] + self.NEAR and b[1] - self.NEAR <= lat <= b[3] + self.NEAR:
                for r in rings:
                    for x, y in r:
                        d = (x - lon) ** 2 + (y - lat) ** 2
                        if d < best:
                            best, idx = d, i
        return idx
