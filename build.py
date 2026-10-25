#!/usr/bin/env python3
"""Build the atlas: a map of the people, organisations and publications of JudaicaLink in time and space.

Reads the stable version of each dataset it uses from a store (layout <slug>/<version>/<path>, the versions named
by the data index) and writes a static site:

    python3 build.py --store ~/lokal/judaicalink/store --index ../judaicalink-data/catalog/dataindex.json --out dist

dist/index.html (the map), dist/about/, dist/data/atlas.json (places, entities, connections), dist/assets/,
dist/build.json (data versions and counts).
"""

import argparse
import datetime
import hashlib
import html
import json
import shutil
import sys
from pathlib import Path

from atlas import model
from atlas.geo import Countries
from atlas.rdf import IRI, read_triples

ROOT = Path(__file__).resolve().parent
D = "http://data.judaicalink.org/"
DCT = "http://purl.org/dc/terms/"
LICENSES = {"http://creativecommons.org/licenses/by/4.0/": "CC BY 4.0",
            "https://creativecommons.org/licenses/by/4.0/": "CC BY 4.0",
            "http://creativecommons.org/publicdomain/zero/1.0/": "CC0 1.0",
            "https://creativecommons.org/publicdomain/zero/1.0/": "CC0 1.0",
            "http://creativecommons.org/licenses/by-sa/4.0/": "CC BY-SA 4.0",
            "https://creativecommons.org/licenses/by-sa/4.0/": "CC BY-SA 4.0",
            "http://creativecommons.org/licenses/by-nc-sa/4.0/": "CC BY-NC-SA 4.0",
            "https://creativecommons.org/licenses/by-nc-sa/4.0/": "CC BY-NC-SA 4.0"}
# what each dataset gives the atlas (for the about page)
USES = {
    "ep": "the entities: names, years and places of birth, death and burial",
    "gnd": "places of activity and exile, seats and years of organisations, relations between people, coordinates",
    "geonames": "coordinates", "wikidata": "GeoNames identifiers of places", "geo-coordinates": "coordinates",
    "hhkeydocs": "coordinates", "cm-entities": "coordinates", "footprints": "coordinates",
    "haskala": "books: place and year of printing, editions, producers, translators and preface writers; coordinates",
    "compact-memory": "periodicals: place and years of publication",
    "epidat": "family relations of the people buried in Jewish cemeteries",
    "gba": "relatives of the people of the Gidal Image Archive",
}

esc = html.escape


def platform(iri):
    """The platform's view of a JudaicaLink IRI (platform decision 0002)."""
    return iri[len(D) - 1:] if iri.startswith(D) else iri


def short_id(iri):
    """Entity pages by their number, everything else by its IRI."""
    return int(iri[len(model.EP):]) if iri.startswith(model.EP) and iri[len(model.EP):].isdigit() else iri


def licence_of(store, slug):
    e = store.index[slug]
    path = store.root / slug / e["stable"] / f"{slug}-meta.ttl.gz"
    if not path.exists():
        return ""
    for s, p, o in read_triples(path):
        if p == DCT + "license" and isinstance(o, IRI) and s.endswith(f"/datasets/{slug}"):
            return str(o)
    return ""


def data_file(atlas, countries):
    places = atlas.places
    country = [countries.of(p["lon"], p["lat"]) for p in places]
    ents = sorted(atlas.entities.values(), key=lambda e: (model.KINDS.index(e["kind"]), e["start"], e["label"]))
    index = {e["iri"]: i for i, e in enumerate(ents)}
    pl, po = [], [0]
    for e in ents:
        for p, role, year in e["places"]:
            pl += [p, model.ROLES.index(role), year if year is not None else 0]
        po.append(len(pl) // 3)
    conn = []
    for a, b, kind in atlas.connections:
        conn += [index[a], index[b], model.REL_KINDS.index(kind)]
    return {
        "kinds": model.KINDS, "roles": model.ROLES, "relKinds": model.REL_KINDS, "lifespan": model.LIFESPAN,
        "countries": countries.names,
        "places": {"id": [short_id(p["iri"]) for p in places], "label": [p["label"] for p in places],
                   "lon": [p["lon"] for p in places], "lat": [p["lat"] for p in places], "country": country},
        "entities": {"id": [short_id(e["iri"]) for e in ents], "kind": [model.KINDS.index(e["kind"]) for e in ents],
                     "label": [e["label"] for e in ents], "start": [e["start"] for e in ents],
                     "end": [e["end"] for e in ents], "flags": [e["flags"] for e in ents], "po": po, "pl": pl},
        "connections": conn,
    }


def asset_hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()[:10]


def page(base, title, body, description, versions, css, scripts="", cls=""):
    ep = versions.get("ep", "")
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light dark">
<title>{esc(title)}</title>
<meta name="description" content="{esc(description)}">
<link rel="stylesheet" href="/kit/1/jl.css">
<link rel="stylesheet" href="{css}">
</head>
<body class="{cls}">
<!--# include virtual="/kit/1/header.html" -->
{body}
<footer class="jl-footer at-footer">
<p><strong>Data: <a href="/datasets/ep">entity pages ep {esc(ep)}</a></strong> and {len(versions) - 1} further datasets
· <a href="{base}about/#data">About the data</a></p>
<p>A showcase of <a href="/">JudaicaLink Mannheim</a>. Base map: Natural Earth. This site loads nothing from third
parties.</p>
</footer>
{scripts}</body>
</html>
"""


REL_LABELS = {"family": "Family", "friendship": "Friendship", "professional": "Professional",
              "creator": "Books and their makers"}
REL_DASH = {"family": "", "friendship": "5 3", "professional": "1.5 3", "creator": "9 3 2 3"}


def line_key(kind):
    dash = f' stroke-dasharray="{REL_DASH[kind]}"' if REL_DASH[kind] else ""
    return f'<svg class="at-linekey" viewBox="0 0 22 8" aria-hidden="true"><line x1="1" y1="4" x2="21" y2="4"{dash}/></svg>'


def index_page(base, versions, stats, css, js, data_src, basemap_src):
    n = stats
    rel_boxes = "\n".join(f'<label><input type="checkbox" id="r-{i}" checked>{line_key(k)}{REL_LABELS[k]}</label>'
                          for i, k in enumerate(model.REL_KINDS))
    body = f"""<div class="at-app" id="main" data-base="{base}" data-src="{data_src}" data-basemap="{basemap_src}">
<header class="at-head">
<h1>Atlas</h1>
<p class="at-lead">The people, organisations and publications of JudaicaLink in time and space, and how they were
connected. <a href="{base}about/">How the map is made</a></p>
<div class="at-search"><label for="f-q" class="at-vh">Find a person, organisation, publication or place</label>
<input id="f-q" type="search" placeholder="Find a name or place" autocomplete="off" role="combobox"
 aria-expanded="false" aria-controls="f-q-list" aria-autocomplete="list">
<ul id="f-q-list" class="at-suggest" role="listbox" hidden></ul></div>
</header>
<form class="at-filters" id="filters" aria-label="Filters" onsubmit="return false">
<fieldset class="at-f at-f-time"><legend>Time</legend>
<label><span class="at-vh">From</span><input id="f-from" type="number" inputmode="numeric" step="1"></label>–<label><span
 class="at-vh">to</span><input id="f-to" type="number" inputmode="numeric" step="1"></label>
<button type="button" id="f-play" class="at-btn" aria-pressed="false" title="Move the time window forward">Play</button>
</fieldset>
<fieldset class="at-f"><legend>Area</legend>
<select id="f-area" aria-label="Area"><option value="">Whole world</option><option value="box" disabled>Drawn area</option></select>
<button type="button" id="f-draw" class="at-btn" aria-pressed="false" title="Drag a rectangle on the map">Draw area</button>
</fieldset>
<fieldset class="at-f at-kinds"><legend>Show</legend>
<label><input type="checkbox" id="k-0" checked><span class="at-key at-key-0"></span>People</label>
<label><input type="checkbox" id="k-1" checked><span class="at-key at-key-1"></span>Organisations</label>
<label><input type="checkbox" id="k-2" checked><span class="at-key at-key-2"></span>Publications</label>
</fieldset>
<fieldset class="at-f"><legend>People at their places</legend>
<select id="f-mode" aria-label="When people are shown at their places">
<option value="life">for the whole life</option>
<option value="events">births and deaths in their year</option>
</select>
</fieldset>
</form>
<div class="at-timeline" id="timeline">
<canvas id="tl" aria-label="Number of entities per decade in the selected area; drag to choose the time window"
 role="slider" tabindex="0"></canvas>
</div>
<div class="at-main">
<div class="at-map" id="map">
<canvas id="cv" tabindex="0" aria-label="Map: drag to move, scroll or pinch to zoom, select a place for its list"></canvas>
<div class="at-zoom"><button type="button" id="z-in" class="at-btn" aria-label="Zoom in">+</button><button type="button"
 id="z-out" class="at-btn" aria-label="Zoom out">−</button><button type="button" id="z-fit" class="at-btn"
 aria-label="Show the selection">⤢</button></div>
<details class="at-legend" id="legend" open><summary>Legend</summary><fieldset class="at-rels"><legend>Connections</legend>
{rel_boxes}
</fieldset><div id="sizes" aria-hidden="true"></div></details>
<div class="at-tip" id="tip" hidden></div>
<p class="at-loading" id="loading">Loading the map …</p>
</div>
<aside class="at-panel" id="panel" aria-live="polite"></aside>
</div>
<noscript><p class="jl-note">The map needs JavaScript. The data are in <a href="{base}data/atlas.json">atlas.json</a>
and in the <a href="/sparql">SPARQL endpoint</a>.</p></noscript>
</div>
"""
    return page(base, "Atlas · JudaicaLink Mannheim", body,
                "A map of the people, organisations and publications of JudaicaLink, filtered by time and area, "
                "with the connections between them.", versions, css, f'<script src="{js}" defer></script>\n',
                "at-full")


def about_page(base, versions, licences, stats, css):
    s = stats
    rows = "".join(
        f'<tr><td><a href="/datasets/{esc(slug)}">{esc(slug)}</a></td><td>{esc(v)}</td>'
        f'<td>{esc(LICENSES.get(licences.get(slug, ""), licences.get(slug, "")) or "–")}</td>'
        f'<td>{esc(USES.get(slug, ""))}</td></tr>' for slug, v in sorted(versions.items()))
    gaps = "".join(f"<tr><td>{esc(k)}</td><td class=\"num\">{v:,}</td></tr>" for k, v in sorted(s.items())
                   if k.startswith(("people ", "birth ", "death ", "burial ", "place pages", "periodicals ",
                                    "places without")) or "not on the map" in k)
    body = f"""<main class="jl-main at-about" id="main">
<p class="at-back"><a href="{base}">← Back to the map</a></p>
<h1>About the Atlas</h1>
<p class="jl-lead">The Atlas puts the entities of JudaicaLink on a map. Choose a time window and an area, and the map
shows where people lived and where organisations and publications were, and how they were connected.</p>

<h2>What is on the map</h2>
<dl class="jl-facts">
<dt>People</dt><dd>{s['people on the map']:,} people with a year of birth or death and at least one place with
coordinates. A person is shown at all their places (birth, activity, exile, death, burial) for the whole
life, from the year of birth to the year of death. When only one of the two years is known, the life is taken to
last {model.LIFESPAN} years (marked as estimated); a life of more than {model.MAX_LIFESPAN} years is taken as an
error in the data, and the year of birth is not used. With “births and deaths in their year”, the places of birth, death
and burial count only in that year.</dd>
<dt>Organisations</dt><dd>{s['organisations on the map']:,} organisations with a seat and a year of
establishment or termination (from the GND). Without a year of termination an organisation is shown only in the year
of its establishment.</dd>
<dt>Publications</dt><dd>{s['Haskala books on the map']:,} books of the <a href="/haskala/">Library of Haskala</a>
(the place and year of printing, and of later editions) and {s['periodicals on the map']:,} periodicals of
<a href="/compact-memory/">Compact Memory</a> (the place and the years of publication).</dd>
<dt>Connections</dt><dd>{s['connections']:,} connections between entities on the map:
{s['family connections']:,} family relations (GND, Epidat, Gidal Image Archive),
{s['friendship connections']:,} acquaintances and friendships and {s['professional connections']:,} professional
relations (GND), {s['creator connections']:,} authors, translators, printers and other producers of books (Library of
Haskala). A line joins the main places of the two entities: for a person the first place of activity, else the place
of death, burial or birth.</dd>
<dt>Places</dt><dd>{s['places']:,} places: the entity pages of places with coordinates, and places that only an
authority record with coordinates names. Areas are present-day countries (Natural Earth); the map shows no
historical borders.</dd>
</dl>

<h2>What is not on the map yet</h2>
<p>An entity is on the map only when the data give it a time and a place with coordinates. Many places in the data are
named by an identifier that has no coordinates in JudaicaLink yet, among them the cemeteries of Epidat (Getty TGN)
and places of the GND, Wikidata and the Library of Congress outside the selections of GND and GeoNames. These are gaps
in the data, to be filled there, not in this showcase.</p>
<div class="jl-scroll"><table class="jl-table"><thead><tr><th>Count</th><th class="num">Number</th></tr></thead>
<tbody>{gaps}</tbody></table></div>

<h2 id="data">The data</h2>
<p>The Atlas is built from the stable versions of these JudaicaLink datasets (on {esc(s['built'])}); every entity
links to its view in the knowledge graph.</p>
<div class="jl-scroll"><table class="jl-table"><thead><tr><th>Dataset</th><th>Version</th><th>Licence</th>
<th>What the Atlas takes</th></tr></thead><tbody>{rows}</tbody></table></div>
<p>The base map is made from <a href="https://www.naturalearthdata.com/" class="jl-ext">Natural Earth</a> 1:50m
(public domain) and is part of this site; no map tiles or other resources are loaded from elsewhere. All data of the
map: <a href="{base}data/atlas.json">atlas.json</a>.</p>

<h2>Using the map</h2>
<ul>
<li>Drag the timeline or type the years; <em>Play</em> moves the window forward.</li>
<li>Choose a country, or <em>Draw area</em> and drag a rectangle on the map. The timeline then counts only the
area.</li>
<li>Select a place for the list of its entities in the time window, and an entity for its places and connections.</li>
<li>The address of the page keeps the selection, so it can be shared. <code>{base}?iri=…</code> opens the map at an
entity page of JudaicaLink.</li>
</ul>
</main>
"""
    return page(base, "About · Atlas · JudaicaLink Mannheim", body,
                "How the Atlas of JudaicaLink Mannheim is made: data, rules and gaps.", versions, css)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--store", required=True, type=Path)
    ap.add_argument("--index", required=True, type=Path, help="the data index (judaicalink-data catalog/dataindex.json)")
    ap.add_argument("--out", default=ROOT / "dist", type=Path)
    ap.add_argument("--base", default="/atlas/", help="the path of the showcase on the host")
    args = ap.parse_args()

    store = model.Store(args.store, args.index)
    atlas = model.Atlas(store)
    countries = Countries(ROOT / "assets" / "basemap.json")
    data = data_file(atlas, countries)
    stats = dict(atlas.stats)
    stats.update({"places": len(atlas.places), "connections": len(atlas.connections),
                  "built": datetime.date.today().isoformat()})
    versions = dict(sorted(store.used.items()))
    licences = {slug: licence_of(store, slug) for slug in versions}

    out = args.out
    if out.exists():
        shutil.rmtree(out)
    (out / "data").mkdir(parents=True)
    (out / "assets").mkdir()
    (out / "about").mkdir()
    data["versions"] = versions
    raw = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    (out / "data" / "atlas.json").write_bytes(raw)
    for f in ("atlas.css", "atlas.js", "basemap.json"):
        shutil.copy(ROOT / "assets" / f, out / "assets" / f)

    base = args.base
    v = lambda f: f"{base}assets/{f}?v={asset_hash(out / 'assets' / f)}"
    data_src = f"{base}data/atlas.json?v={hashlib.sha256(raw).hexdigest()[:10]}"
    (out / "index.html").write_text(index_page(base, versions, stats, v("atlas.css"), v("atlas.js"), data_src,
                                               v("basemap.json")), encoding="utf-8")
    (out / "about" / "index.html").write_text(about_page(base, versions, licences, stats, v("atlas.css")),
                                              encoding="utf-8")
    (out / "build.json").write_text(json.dumps({"built": stats["built"], "versions": versions, "counts": stats},
                                               indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    for k, n in sorted(atlas.stats.items()):
        print(f"{n:9,} {k}", file=sys.stderr)
    print(f"{len(atlas.places):,} places, {len(atlas.entities):,} entities, {len(atlas.connections):,} connections; "
          f"atlas.json {len(raw):,} bytes", file=sys.stderr)


if __name__ == "__main__":
    main()
