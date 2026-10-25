# 0002 Places: entity pages of places with coordinates; no countries or regions as points

Status: accepted (made autonomously 2026-10-25, to be reviewed with Kai)
Date: 2026-10-25

## Context

People's places are IRIs of authorities (GND, Wikidata, LC, Getty TGN, GeoNames, geo-coordinates). The entity pages
of places (ep) join the records of a place and give one coordinate (`geosparql:asWKT`, chosen by the record order
of judaicalink-data 0022/0029). Many place IRIs have no coordinates anywhere in JudaicaLink (2026-10-25: the burial
places of 18,650 Epidat people, Getty TGN; about 15,000 birth and 6,000 death places, mostly Wikidata, GND and LC
places outside the GeoNames and GND selections). Some places are countries or regions; as points they would put
people at a centroid (1,896 people were born in "Israel").

## Decision

- A place IRI is resolved to the entity page that has it as a member (`jl:sameAs`, `owl:sameAs`). Its coordinates
  are the page's own, else the first member with coordinates. An IRI that is no member of a place page with
  coordinates, but has coordinates in a record dataset (GeoNames, GND, geo-coordinates, hhkeydocs, haskala,
  cm-entities, footprints, or Wikidata through its GeoNames identifier), becomes a place of its own.
- A place page whose point is that of a GeoNames country, first-level division, region or river (`A.PCL*`,
  `A.ADM1`, `A.ADMD`, `L.RGN`, `L.AREA`, `L.CONT`, `H.STM`) and that has no GeoNames populated place is left out, and
  with it the people known only there. City-states keep their place through their populated-place record.
- No matching of place names, with one exception: the places of publication of the Compact Memory periodicals are
  names only; they are matched to the labels of place pages (the most linked page wins) after a short, reviewed table
  of spellings (`PLACE_NAMES` in `atlas/model.py`, e.g. "Frankfurt, M.", "Ṿarsha", "St. Petersburg").
- Missing coordinates are gaps in the data, to be filled there (TGN coordinates for the Epidat cemeteries; places of
  GND, Wikidata and LC in the selections); the about page lists the counts.
- Areas are present-day countries (Natural Earth; each place gets the country its point is in, or the nearest within
  0.3°) or a rectangle drawn on the map. There are no historical borders.

## Consequences

About 7,200 places. Every gap filled in the data shows up with the next build.
