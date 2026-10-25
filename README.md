# jlma-atlas: the Atlas of JudaicaLink on mannheim.judaicalink.org

A static showcase of JudaicaLink Mannheim: a map of the people, organisations and publications of the knowledge graph
in time and space, with the connections between them, at <https://mannheim.judaicalink.org/atlas/>.

What it offers (details and reasons in [`docs/decisions/`](docs/decisions/)):

- **A time window** (timeline with the number of entities per decade, years to type, *Play*) and **an area**
  (a present-day country or a rectangle drawn on the map); the map shows a dot where, in that time, a person lived
  or an organisation or publication was, sized by the number of entities.
- **People** at their places of birth, activity, exile, death and burial for their whole life (or only births and
  deaths in their year), **organisations** at their seat, **publications** (Library of Haskala books, Compact Memory
  periodicals) at their place of printing or publication.
- **Connections**: family, acquaintance, professional relations, books and their makers, drawn between places.
- Lists of places and entities for the selection, search by name, every entity linked to its view in the knowledge
  graph; the address keeps the state; `/atlas/?iri=<entity page IRI>` opens the map at an entity.
- Light and dark, phones, no cookies, **no requests to third parties** (the base map is part of the site).

## Build

Python ≥ 3.11, standard library only. The data are the stable versions of the datasets in a store (layout
`<slug>/<version>/<path>`, as published at <https://archive.judaicalink.org/store/>), named by the data index of
judaicalink-data:

```sh
python3 build.py --store ~/lokal/judaicalink/store --index ../judaicalink-data/catalog/dataindex.json --out dist
python3 tools/check_dist.py dist         # platform bar, kit stylesheet, assets, consistency of atlas.json
python3 -m unittest discover tests
python3 tools/serve.py                   # preview at http://localhost:8120/atlas/
```

About a minute and 1.6 GB of memory; `dist/` is about 6 MB (1.7 MB compressed). The about page and
`dist/build.json` name the data versions and counts, including what is not on the map for lack of coordinates.

## Deploy

With the platform repository [judaicalink-mannheim](https://github.com/judaicalink/judaicalink-mannheim) (registry
entry `path = "atlas"`, static):

```sh
../judaicalink-mannheim/host/deploy.sh lima-mannheim atlas dist   # the local test VM: https://localhost/atlas/
../judaicalink-mannheim/host/deploy.sh <ssh-host> atlas dist      # mannheim.judaicalink.org
```

The nginx location comes from the registry (`host/nginx/showcases.py` on the VM).

## Layout

| Path | What |
|---|---|
| `build.py` | the build: data file, map page, about page |
| `atlas/model.py` | the atlas as read from the data: places, entities, times, connections |
| `atlas/geo.py` | the present-day country of a point |
| `atlas/rdf.py` | the RDF reader of judaicalink-data (copied) |
| `assets/atlas.js`, `assets/atlas.css` | the map, timeline, filters, panel and search in the browser |
| `assets/basemap.json` | the base map (Natural Earth 1:50m), made by `tools/make_basemap.py` (run once) |
| `tools/check_dist.py`, `tools/serve.py` | check a build; preview it locally |
| `docs/decisions/` | the decisions about this showcase |

## Data and credits

The entity pages of JudaicaLink and the datasets listed on the about page, each under its licence (named there).
Base map: Natural Earth (public domain).
