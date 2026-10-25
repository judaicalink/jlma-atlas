# 0004 What is on the map: people, organisations, publications, and their connections

Status: accepted (made autonomously 2026-10-25, to be reviewed with Kai)
Date: 2026-10-25

## Context

The graph has few events with a place and a time; it has many people with places and years, some organisations, and
publications with a place and year. Connections between entities are stated in the GND (family, acquaintance,
professional relations), in Epidat (parents, spouses, siblings, grandparents), in the Gidal Image Archive (relatives)
and in the Library of Haskala (producers, translators, preface writers of books).

## Decision

- Three kinds, one colour each (the first three slots of the validated categorical palette, the most a map with
  overlapping dots can tell apart): people, organisations, publications (Haskala books and Compact Memory
  periodicals). An entity is an entity page; a periodical, which has none, is its record.
- A place shows nested dots, one per kind, their area by the number of entities in the time and area; the panel lists
  the places with their counts (the table view of the map) and, for a place or an entity, the details.
- Connections are kept when both entities are on the map. They are drawn between the main places of the two
  entities (a person's first place of activity, else death, burial or birth; for the others their first place),
  joined per pair of places and kind (width by number), as dashed lines by kind: family, acquaintance or friendship,
  professional, books and their makers. Connections within one place are counted in its panel. For a selected entity
  its own connections and the way through its places are drawn.
- Every entity and place links to its view on the platform (`/data/…`, platform decision 0002). `/atlas/?iri=<IRI>`
  opens the map at an entity page (or a periodical's record) and is the `resolve` of the registry entry. The registry
  entry names no `datasets` yet: the platform would then link every entity page to the Atlas, also those not on the
  map.
- The address keeps the state (time, area, kinds, mode, connections, selection, view) in the fragment.

## Consequences

The Compact Memory and Haskala showcases remain the place for their records; the Atlas links to them through the
platform's views. Footprints (book copies moving through time and place) can be added when its harvest is complete.
