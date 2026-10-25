#!/usr/bin/env python3
"""Make the data of the title animation of web.judaicalink.org (the people, organisations and publications of the
atlas appearing on the map decade by decade) from a build of the atlas and the base map:

    python3 tools/make_title_animation.py dist ../judaicalink-site/assets/data/title-animation.json

Every presence of an entity at a place gets a year (its own, else birth, death or burial, activity at 25, founding
or publication); presences are counted per place, kind and decade. A connection gets the decade in which the later
of its two entities first appears and is drawn between their main places (as on the map).

Format: "lon", "lat" of the places used; "events" [decade, place, kind (0 people, 1 organisations and
publications), count, ...] in the order of the decades; "connections" [decade, place, place, ...] in the same order;
"land" and "lakes" as in assets/basemap.json, with its "q".
"""

import json
import sys
from collections import Counter
from pathlib import Path

STEP = 10
BASEMAP = Path(__file__).resolve().parent.parent / "assets" / "basemap.json"


def main(dist, out):
    d = json.loads((Path(dist) / "data" / "atlas.json").read_text())
    bm = json.loads(BASEMAP.read_text())
    e, places = d["entities"], d["places"]
    R = {r: i for i, r in enumerate(d["roles"])}
    n = len(e["id"])
    po, pl = e["po"], e["pl"]
    first, prim = [None] * n, [None] * n
    bins = Counter()
    order = [R["activity"], R["death"], R["burial"], R["birth"]]   # the main place, as in assets/atlas.js
    for i in range(n):
        person = e["kind"][i] == 0
        rank = 99
        for j in range(po[i], po[i + 1]):
            p, r, y = pl[3 * j], pl[3 * j + 1], pl[3 * j + 2]
            if not y:
                if r in (R["death"], R["burial"]):
                    y = e["end"][i]
                elif r in (R["activity"], R["exile"]):
                    y = e["start"][i] + (25 if person else 0)
                else:
                    y = e["start"][i]
            if not y:
                continue
            bins[(y // STEP * STEP, p, 0 if person else 1)] += 1
            first[i] = y if first[i] is None else min(first[i], y)
            k = order.index(r) if r in order else 98
            if k < rank:
                rank, prim[i] = k, p
    used = sorted({p for (_, p, _) in bins})
    idx = {p: k for k, p in enumerate(used)}
    events = []
    for (dec, p, kind), count in sorted(bins.items()):
        events += [dec, idx[p], kind, count]
    con = []
    c = d["connections"]
    for k in range(0, len(c), 3):
        a, b = c[k], c[k + 1]
        if first[a] is None or first[b] is None or prim[a] == prim[b] or prim[a] not in idx or prim[b] not in idx:
            continue
        con.append((max(first[a], first[b]) // STEP * STEP, idx[prim[a]], idx[prim[b]]))
    con.sort()
    data = {
        "step": STEP,
        "q": bm["q"],
        "land": [r for country in bm["countries"] for r in country["p"]],
        "lakes": bm["lakes"],
        "lon": [places["lon"][p] for p in used],
        "lat": [places["lat"][p] for p in used],
        "events": events,
        "connections": [x for t in con for x in t],
    }
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_text(json.dumps(data, separators=(",", ":")))
    print(f"{out}: {len(used)} places, {len(events) // 4} counts, {len(con)} connections")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(*sys.argv[1:])
