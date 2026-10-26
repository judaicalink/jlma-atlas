# 0005 Footprints: imprints, the places of their copies, their makers

Status: accepted · Date: 2026-10-26 · Amends [0004](0004-entities-and-connections.md)

## Context

Since footprints 2026-10-26 JudaicaLink has the whole of Footprints: 6,860 imprints with their place and year of
printing, the copies of these imprints, and 24,482 footprints, each a place and a time where a copy was. The showcase
jlma-footprints shows them on a map of their own; in the Atlas they belong with the other publications.

## Decision

- An imprint of Footprints with a year and a place with coordinates is a publication (its entity page, or the imprint
  itself), at its place of printing in its year ("printed").
- The footprints of its copies with a year and a place are presences of the publication in their year ("a copy
  there"), like the editions of a Haskala book: the first year of the EDTF date, one presence per place and year.
- Authors and editors of its work, and its printers, publishers, translators, compilers and anthologizers are
  connections of the kind "books and their makers", where both are on the map.
- An entity page that is already a publication through another dataset gets the presences of the imprint added.
