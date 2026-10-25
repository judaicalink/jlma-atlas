#!/usr/bin/env python3
"""Make assets/basemap.json, the base map of the atlas: the present-day countries (as land, for the borders and the
area filter), lakes and major rivers of the world from Natural Earth 1:50m (public domain,
https://www.naturalearthdata.com/), simplified. Run once; the output is committed. The source files are GeoJSON from
https://github.com/nvkelso/natural-earth-vector (tag v5.1.2, directory geojson/):

    python3 tools/make_basemap.py <dir with ne_50m_admin_0_countries.geojson, ne_50m_lakes.geojson,
                                   ne_50m_rivers_lake_centerlines.geojson>

Format: coordinates in hundredths of a degree, every ring or line a flat list [x0, y0, dx1, dy1, ...] (the first
point absolute, then differences). countries: [{"n": name, "c": ISO code, "b": [w, s, e, n], "p": [ring, ...]}].
"""

import json
import os
import sys

Q = 100          # hundredths of a degree
TOL = {"countries": 0.04, "lakes": 0.04, "rivers": 0.05}   # Douglas-Peucker tolerance in degrees
MIN_RING = 0.05  # rings whose bounding box is smaller than this (degrees) are left out


def dp(points, tol):
    """Douglas-Peucker, iterative."""
    if len(points) < 3:
        return points
    keep = [False] * len(points)
    keep[0] = keep[-1] = True
    stack = [(0, len(points) - 1)]
    while stack:
        a, b = stack.pop()
        (x1, y1), (x2, y2) = points[a], points[b]
        dx, dy = x2 - x1, y2 - y1
        n2 = dx * dx + dy * dy
        best, idx = 0.0, None
        for i in range(a + 1, b):
            x, y = points[i]
            if n2 == 0:
                d = (x - x1) ** 2 + (y - y1) ** 2
            else:
                t = max(0.0, min(1.0, ((x - x1) * dx + (y - y1) * dy) / n2))
                d = (x - x1 - t * dx) ** 2 + (y - y1 - t * dy) ** 2
            if d > best:
                best, idx = d, i
        if idx is not None and best > tol * tol:
            keep[idx] = True
            stack += [(a, idx), (idx, b)]
    return [p for p, k in zip(points, keep) if k]


def encode(points):
    out, px, py = [], 0, 0
    last = None
    for x, y in points:
        qx, qy = round(x * Q), round(y * Q)
        if (qx, qy) == last:
            continue
        out += [qx - px, qy - py]
        px, py, last = qx, qy, (qx, qy)
    return out


def rings_of(geom):
    if geom["type"] == "Polygon":
        return [geom["coordinates"]]
    if geom["type"] == "MultiPolygon":
        return geom["coordinates"]
    return []


def big_enough(ring):
    xs, ys = [p[0] for p in ring], [p[1] for p in ring]
    return max(xs) - min(xs) >= MIN_RING or max(ys) - min(ys) >= MIN_RING


def polygons(feature, tol):
    out = []
    for poly in rings_of(feature["geometry"]):
        for ring in poly:
            if not big_enough(ring):
                continue
            r = dp(ring, tol)
            if len(r) >= 4:
                out.append(encode(r))
    return out


def lines(feature, tol):
    g = feature["geometry"]
    parts = [g["coordinates"]] if g["type"] == "LineString" else g["coordinates"] if g["type"] == "MultiLineString" else []
    return [encode(dp(p, tol)) for p in parts if len(p) >= 2]


def main(src):
    def load(name):
        with open(os.path.join(src, name + ".geojson"), encoding="utf-8") as f:
            return json.load(f)["features"]

    countries = []
    for f in load("ne_50m_admin_0_countries"):
        pr = f["properties"]
        if pr.get("ADMIN") == "Antarctica":
            continue
        rings = polygons(f, TOL["countries"])
        if not rings:
            continue
        pts = [p for poly in rings_of(f["geometry"]) for ring in poly for p in ring]
        bbox = [round(min(p[0] for p in pts), 2), round(min(p[1] for p in pts), 2),
                round(max(p[0] for p in pts), 2), round(max(p[1] for p in pts), 2)]
        code = pr.get("ISO_A2_EH") if pr.get("ISO_A2_EH") not in (None, "-99") else pr.get("ADM0_A3")
        countries.append({"n": pr.get("NAME_EN") or pr["NAME"], "c": code, "b": bbox, "p": rings})
    countries.sort(key=lambda c: c["n"])
    lakes = [r for f in load("ne_50m_lakes") if f["properties"].get("scalerank", 9) <= 3
             for r in polygons(f, TOL["lakes"])]
    rivers = [l for f in load("ne_50m_rivers_lake_centerlines") if f["properties"].get("scalerank", 9) <= 4
              for l in lines(f, TOL["rivers"])]
    out = {"source": "Natural Earth 1:50m, v5.1.2 (public domain)", "q": Q,
           "countries": countries, "lakes": lakes, "rivers": rivers}
    path = os.path.join(os.path.dirname(__file__), "..", "assets", "basemap.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
    print(f"{len(countries)} countries, {len(lakes)} lakes, {len(rivers)} rivers, {os.path.getsize(path):,} bytes")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
