#!/usr/bin/env python3
"""Check a build: every page has the platform bar exactly once and the kit stylesheet, every asset a page references
exists, and atlas.json is consistent (indices in range, years in order, every entity with a place).

    python3 tools/check_dist.py dist
"""

import json
import re
import sys
from pathlib import Path

SSI = '<!--# include virtual="/kit/1/header.html" -->'


def main(dist):
    dist = Path(dist)
    errors = []
    pages = list(dist.rglob("*.html"))
    for p in pages:
        t = p.read_text(encoding="utf-8")
        if t.count("<!--#") != 1 or SSI not in t:
            errors.append(f"{p}: not exactly one platform bar")
        if '<link rel="stylesheet" href="/kit/1/jl.css">' not in t:
            errors.append(f"{p}: no kit stylesheet")
        for ref in re.findall(r'(?:href|src|data-src|data-basemap)="(/atlas/[^"?#]*)', t):
            f = dist / ref[len("/atlas/"):]
            if f.is_dir():
                f = f / "index.html"
            if not f.exists():
                errors.append(f"{p}: missing {ref}")
    d = json.loads((dist / "data" / "atlas.json").read_text(encoding="utf-8"))
    P, e = len(d["places"]["id"]), d["entities"]
    N = len(e["id"])
    for k in ("label", "lon", "lat", "country"):
        if len(d["places"][k]) != P:
            errors.append(f"places.{k}: {len(d['places'][k])} values for {P} places")
    for k in ("kind", "label", "start", "end", "flags"):
        if len(e[k]) != N:
            errors.append(f"entities.{k}: {len(e[k])} values for {N} entities")
    if len(e["po"]) != N + 1 or e["po"][-1] * 3 != len(e["pl"]):
        errors.append("entities.po does not match entities.pl")
    for i in range(N):
        if e["start"][i] > e["end"][i]:
            errors.append(f"entity {e['id'][i]}: start after end")
        if e["po"][i + 1] <= e["po"][i]:
            errors.append(f"entity {e['id'][i]}: no place")
    for j in range(0, len(e["pl"]), 3):
        if not 0 <= e["pl"][j] < P or not 0 <= e["pl"][j + 1] < len(d["roles"]):
            errors.append(f"presence {j // 3}: place or role out of range")
    c = d["connections"]
    for j in range(0, len(c), 3):
        if not (0 <= c[j] < N and 0 <= c[j + 1] < N and 0 <= c[j + 2] < len(d["relKinds"])):
            errors.append(f"connection {j // 3}: out of range")
    if len(set(map(str, e["id"]))) != N:
        errors.append("entity ids are not unique")
    for msg in errors[:50]:
        print(msg)
    print(f"{len(pages)} pages, {P:,} places, {N:,} entities, {len(c) // 3:,} connections: "
          f"{'OK' if not errors else str(len(errors)) + ' errors'}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "dist"))
