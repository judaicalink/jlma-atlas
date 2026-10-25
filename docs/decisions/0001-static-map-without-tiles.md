# 0001 A static map, built from the store, drawn without tiles or libraries

Status: accepted (made autonomously 2026-10-25, to be reviewed with Kai)
Date: 2026-10-25

## Context

The Atlas shows the entities of JudaicaLink on a map, filtered by time and area, with their connections. The platform
prefers static showcases (platform decision 0001); the Library of Haskala draws its maps without a map service
(jlma-haskala 0008), because loading tiles from a third party is a privacy issue for a university site. Unlike
those maps, the Atlas covers the world and needs zooming and panning.

## Decision

- `build.py` reads the stable version of each dataset it uses from a store (the versions named by the data index) and
  writes a static site: the map page, an about page, `data/atlas.json` (places, entities, connections as columns) and
  the assets. Python standard library only (the RDF reader is copied from judaicalink-data); no server, no endpoint.
- The browser draws everything itself on a canvas (plain JavaScript, no library): Web Mercator, panning and zooming
  by mouse, wheel, touch and keyboard. The base map, `assets/basemap.json`, is made once by `tools/make_basemap.py`
  from Natural Earth 1:50m (public domain): the present-day countries (as land, for the borders and the area
  filter), lakes, major rivers; simplified, about 110 kB compressed.
- Filtering is computed in the browser on every change (about 80,000 entities in a few milliseconds).
- Pages follow the platform contract: `/kit/1/jl.css`, the platform bar by SSI, own CSS prefixed `at-`, paths below
  `/atlas/` (`--base`).

## Consequences

No request leaves the site; the data file is about 1.6 MB compressed and loaded once. A new version of the data means:
build, check (`tools/check_dist.py`), deploy. The build takes about a minute and 1.6 GB of memory.
