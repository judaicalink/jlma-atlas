"""The atlas as read from the data: places with coordinates, entities with a time and their places, connections.

Everything is read from the files of the stable versions in a store (layout <slug>/<version>/<path>, the versions
named by the data index). The entities are the entity pages (dataset ep); a Compact Memory periodical, which has
no entity page, is its own record. Decisions 0002-0005 say what is taken and why.
"""

import collections
import json
import re
import sys
from pathlib import Path

from .rdf import IRI, Literal, read_triples

JL = "http://data.judaicalink.org/ontology/"
DATA = "http://data.judaicalink.org/data/"
EP = DATA + "ep/"
RDF_TYPE = "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"
SKOS = "http://www.w3.org/2004/02/skos/core#"
OWL_SAMEAS = "http://www.w3.org/2002/07/owl#sameAs"
WKT = "http://www.opengis.net/ont/geosparql#asWKT"
FOAF = "http://xmlns.com/foaf/0.1/"
SCHEMA = "http://schema.org/"
GNDO = "https://d-nb.info/standards/elementset/gnd#"
AGRELON = "https://d-nb.info/standards/elementset/agrelon#"
HV = DATA + "haskala/vocab/"
FPV = DATA + "footprints/vocab/"
FP = DATA + "footprints/"
# the roles of persons in footprints that make them makers of an imprint or its work (decision 0005)
FP_MAKERS = {GNDO + "author", GNDO + "editor", "http://purl.org/dc/terms/publisher", FPV + "printer", FPV + "translator",
             FPV + "compiler", FPV + "anthologizer"}
DCT = "http://purl.org/dc/terms/"

# datasets whose records state coordinates (geosparql:asWKT), for places without an entity page with coordinates
COORD_DATASETS = ["geonames", "gnd", "geo-coordinates", "hhkeydocs", "haskala", "cm-entities", "footprints"]

# GeoNames features that are no point on a map: countries, first-level divisions, regions, rivers (decision 0002)
AREA_FEATURES = re.compile(r"#(A\.PCL[A-Z]*|A\.ADM1H?|A\.ADMD|L\.RGNH?|L\.AREA|L\.CONT|H\.STMH?)$")
GN_FEATURE = "https://www.geonames.org/ontology#featureCode"

KINDS = ["person", "organisation", "publication"]
# the roles of a place for an entity; the order is the order of the legend and of the panels
ROLES = ["birth", "activity", "exile", "death", "burial", "seat", "printed", "edition", "published", "copy"]
# a person's life when only one end is known, and the longest life taken as given (decision 0003)
LIFESPAN = 70
MAX_LIFESPAN = 110
NOW = 2026
# connections: kind -> the properties that state it
REL_KINDS = ["family", "friendship", "professional", "creator"]
GND_RELATIONS = {
    GNDO + "familialRelationship": "family", AGRELON + "hasChild": "family", AGRELON + "hasParent": "family",
    AGRELON + "hasSpouse": "family", AGRELON + "hasSibling": "family", AGRELON + "hasGrandParent": "family",
    AGRELON + "hasGrandChild": "family", AGRELON + "hasUncle": "family", AGRELON + "hasAunt": "family",
    AGRELON + "hasNephew": "family", AGRELON + "hasNiece": "family", AGRELON + "hasCousin": "family",
    AGRELON + "hasParentInLaw": "family", AGRELON + "hasChildInLaw": "family", AGRELON + "hasSiblingInLaw": "family",
    GNDO + "acquaintanceshipOrFriendship": "friendship", AGRELON + "hasFriend": "friendship",
    GNDO + "professionalRelationship": "professional", AGRELON + "hasColleague": "professional",
    AGRELON + "hasTeacher": "professional", AGRELON + "hasStudent": "professional",
}
EPIDAT_RELATIONS = {SCHEMA + "parent": "family", SCHEMA + "spouse": "family", SCHEMA + "sibling": "family",
                    JL + "grandparent": "family"}
GBA_RELATIONS = {GNDO + "relatedPerson": "family"}   # all ten are relatives (parents, children, spouses)


def warn(msg):
    print(msg, file=sys.stderr)


def key(iri):
    """A key for comparing IRIs written in different ways: no scheme, no trailing slash, Wikidata items as entities."""
    k = re.sub(r"^https?://", "", iri.strip()).rstrip("/")
    return re.sub(r"^www\.wikidata\.org/wiki/", "www.wikidata.org/entity/", k)


_NUM = r"([+-]?\d+(?:\.\d+)?)"
_POINT = re.compile(r"point\s*\(\s*" + _NUM + r"\s+" + _NUM + r"\s*\)", re.I)


def parse_wkt(s):
    m = _POINT.search(s)
    if not m:
        return None
    lon, lat = float(m.group(1)), float(m.group(2))
    if not (-180 <= lon <= 180 and -90 <= lat <= 90) or (lon == 0 and lat == 0):
        return None
    return round(lon, 4), round(lat, 4)


def year_of(s):
    """A year from a normalised year (xsd:gYear, may be negative) or a date that starts with one; else None."""
    m = re.fullmatch(r"\s*(-?\d{1,4})(?:-\d\d(?:-\d\d)?)?(?:T.*)?\s*", s or "")
    if not m:
        return None
    y = int(m.group(1))
    return y if -3000 <= y <= NOW else None


def first_year(s):
    """The first four-digit year in a free date ("30.10.1998", "XX.XX.2019", "1860"); else None."""
    m = re.search(r"(?<!\d)(\d{4})(?!\d)", s or "")
    if not m:
        return None
    y = int(m.group(1))
    return y if 500 <= y <= NOW else None


_HEB = dict(zip("אבגדהוזחטיכלמנסעפצקרשת", [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 20, 30, 40, 50, 60, 70, 80, 90,
                                              100, 200, 300, 400]))
_HEB.update({"ך": 20, "ם": 40, "ן": 50, "ף": 80, "ץ": 90})


def hebrew_year(s):
    """The later Gregorian year of a Hebrew year in the minor era (תקמט = 5549 → 1789), as in jlma-haskala."""
    t = re.sub(r"[֑-ׇ\"'\s.\[\]()?׳״]", "", s or "")
    if not t or any(c not in _HEB for c in t):
        return None
    v = sum(_HEB[c] for c in t)
    am = v + 5000 if v < 1000 else v
    return am - 3760 if 5400 <= am <= 5700 else None


def label_of(labels):
    """One label: English, then German, then without language, then any (labels: [Literal])."""
    by = {}
    for lit in labels:
        by.setdefault(lit.lang or "", lit.value)
    for lang in ("en", "de", ""):
        if lang in by:
            return by[lang]
    return next(iter(by.values()), "")


class Store:
    """The files of the stable version of each dataset, from the data index."""

    def __init__(self, store, index):
        self.root = Path(store)
        self.index = json.loads(Path(index).read_text(encoding="utf-8"))["datasets"]
        self.used = {}

    def version(self, slug):
        return self.index[slug]["stable"]

    def triples(self, slug, name=None):
        """The triples of the stable version of a dataset (all RDF files but the -meta file, or those containing
        name)."""
        e = self.index[slug]
        v = next(x for x in e["versions"] if x["version"] == e["stable"])
        self.used[slug] = e["stable"]
        for f in v["files"]:
            p = f["path"]
            if p.endswith("-meta.ttl.gz") or not re.search(r"\.(ttl|nt|n3)(\.gz)?$", p):
                continue
            if name and name not in p:
                continue
            yield from read_triples(self.root / slug / e["stable"] / p)


class Atlas:
    def __init__(self, store):
        self.store = store
        self.stats = collections.Counter()
        self._coordinates()
        self._entity_pages()
        self._places()
        self._gnd()
        self._persons()
        self._organisations()
        self._haskala()
        self._periodicals()
        self._footprints()
        self._connections()

    # --- coordinates of records ------------------------------------------------------------------------------------
    def _coordinates(self):
        """coord: key of a record IRI or of an IRI it is the same as -> (lon, lat); label: key -> a label."""
        self.coord, self.coord_label, self.feature, self.area_keys, self.area_points = {}, {}, {}, set(), set()
        for slug in COORD_DATASETS:
            wkt, same, labels = {}, collections.defaultdict(list), collections.defaultdict(list)
            for s, p, o in self.store.triples(slug):
                if p == GN_FEATURE:
                    self.feature[s] = str(o)
                elif p == WKT and isinstance(o, Literal):
                    c = parse_wkt(o.value)
                    if c:
                        wkt.setdefault(s, c)
                elif p == OWL_SAMEAS and isinstance(o, IRI):
                    same[s].append(o)
                elif p == SKOS + "prefLabel" and isinstance(o, Literal):
                    labels[s].append(o)
            for s, c in wkt.items():
                if AREA_FEATURES.search(self.feature.get(s, "")):
                    self.area_points.add(c)
                    for i in [s] + same.get(s, []):
                        self.area_keys.add(key(i))
                    continue
                for i in [s] + same.get(s, []):
                    k = key(i)
                    if k not in self.coord:
                        self.coord[k] = c
                        if labels.get(s):
                            self.coord_label[k] = label_of(labels[s])
            self.stats[f"coordinates {slug}"] = len(wkt)
        # Wikidata items of places: their GeoNames identifier
        self.wd_geonames = {}
        wd_same = {}
        for s, p, o in self.store.triples("wikidata"):
            if p == "http://www.wikidata.org/prop/direct-normalized/P1566":
                self.wd_geonames[s] = o
            elif p == OWL_SAMEAS and str(o).startswith("http://www.wikidata.org/entity/"):
                wd_same[s] = o
        for s, g in self.wd_geonames.items():
            if s in wd_same and key(g) in self.coord and key(wd_same[s]) not in self.coord:
                self.coord[key(wd_same[s])] = self.coord[key(g)]

    # --- entity pages ----------------------------------------------------------------------------------------------
    EP_KEEP = {RDF_TYPE, SKOS + "prefLabel", JL + "sameAs", OWL_SAMEAS, WKT, JL + "birthDate", JL + "deathDate",
               JL + "birthDateNormalized", JL + "deathDateNormalized", JL + "birthLocationURI",
               JL + "deathLocationURI", JL + "burialLocationURI", JL + "birthLocation", JL + "deathLocation",
               JL + "burialLocation", SKOS + "altLabel"}

    def _entity_pages(self):
        """ep: entity IRI -> {predicate: [objects]}; member: key of a record or identifier IRI -> entity IRI."""
        ep = collections.defaultdict(lambda: collections.defaultdict(list))
        for s, p, o in self.store.triples("ep", "ep.ttl"):
            if p in self.EP_KEEP:
                ep[s][p].append(o)
        self.ep = ep
        self.member = {}
        self.kind = {}
        for s, d in ep.items():
            types = set(d.get(RDF_TYPE, []))
            if FOAF + "Person" in types:
                self.kind[s] = "person"
            elif FOAF + "Organization" in types:
                self.kind[s] = "organisation"
            elif SCHEMA + "Place" in types:
                self.kind[s] = "place"
            elif SCHEMA + "CreativeWork" in types:
                self.kind[s] = "work"
            for m in d.get(JL + "sameAs", []) + d.get(OWL_SAMEAS, []):
                self.member.setdefault(key(m), s)
            self.member.setdefault(key(s), s)
        self.stats["entity pages"] = len(ep)

    def entity(self, iri):
        return self.member.get(key(iri))

    # --- places ----------------------------------------------------------------------------------------------------
    def _places(self):
        """The places on the map: entity pages of places with coordinates (their own or a member's), and IRIs with
        coordinates that are no member of a place page. place_index: key -> index in self.places."""
        self.places = []          # [{"iri", "label", "lon", "lat"}]
        self.place_index = {}
        self.place_of_entity = {}
        self.area_pages = set()
        for s, d in self.ep.items():
            if self.kind.get(s) != "place":
                continue
            c = None
            for w in d.get(WKT, []):
                c = parse_wkt(w.value)
                if c:
                    break
            if not c:
                for m in d.get(JL + "sameAs", []) + d.get(OWL_SAMEAS, []):
                    c = self.coord.get(key(m))
                    if c:
                        break
            if not c:
                self.stats["place pages without coordinates"] += 1
                continue
            if c in self.area_points and not any(self.feature.get(m, "").split("#")[-1].startswith("P.")
                                                 for m in d.get(JL + "sameAs", []) if m.startswith(DATA + "geonames/")):
                # the point of a country, region or river (decision 0002)
                self.stats["place pages of countries and regions (left out)"] += 1
                self.area_pages.add(s)
                continue
            self.place_of_entity[s] = len(self.places)
            self.places.append({"iri": s, "label": label_of(d.get(SKOS + "prefLabel", [])), "lon": c[0], "lat": c[1]})
        self.stats["place pages with coordinates"] = len(self.places)

    def place(self, iri, hint=""):
        """The index of the place an IRI names, or None. Creates a place for an IRI with coordinates that is no
        member of a place page with coordinates."""
        k = key(iri)
        if k in self.place_index:
            return self.place_index[k]
        e = self.member.get(k)
        if k in self.area_keys or e in self.area_pages:
            i = None
        elif e is not None and e in self.place_of_entity:
            i = self.place_of_entity[e]
        elif k in self.coord:
            lon, lat = self.coord[k]
            i = len(self.places)
            self.places.append({"iri": iri, "label": self.coord_label.get(k) or hint or iri, "lon": lon, "lat": lat})
            self.stats["places without a place page"] += 1
        else:
            i = None
        self.place_index[k] = i
        return i

    # --- GND: places of activity and exile, seats and dates of organisations, relations ------------------------------
    def _gnd(self):
        g = collections.defaultdict(lambda: collections.defaultdict(list))
        keep = {GNDO + "placeOfActivity", GNDO + "placeOfExile", GNDO + "placeOfBusiness",
                GNDO + "dateOfEstablishment", GNDO + "dateOfTermination"} | set(GND_RELATIONS)
        for s, p, o in self.store.triples("gnd"):
            if p in keep:
                g[s][p].append(o)
        self.gnd = g

    def gnd_records(self, e):
        return [m for m in self.ep[e].get(JL + "sameAs", []) if m.startswith(DATA + "gnd/") and m in self.gnd]

    # --- entities --------------------------------------------------------------------------------------------------
    def _new_entity(self, iri, kind, label, start, end, flags, presences):
        self.entities[iri] = {"iri": iri, "kind": kind, "label": label, "start": start, "end": end, "flags": flags,
                              "places": presences}

    def _persons(self):
        """People with a year of birth or death and at least one place with coordinates (decision 0003)."""
        self.entities = {}
        for s, d in self.ep.items():
            if self.kind.get(s) != "person":
                continue
            b = next((year_of(v.value) for v in d.get(JL + "birthDateNormalized", []) if year_of(v.value) is not None),
                     None)
            if b is None:
                b = next((year_of(v.value) for v in d.get(JL + "birthDate", []) if year_of(v.value) is not None), None)
            de = next((year_of(v.value) for v in d.get(JL + "deathDateNormalized", []) if year_of(v.value) is not None),
                      None)
            if de is None:
                de = next((year_of(v.value) for v in d.get(JL + "deathDate", []) if year_of(v.value) is not None), None)
            if b is not None and de is not None and de < b:
                self.stats["people with death before birth (left out)"] += 1
                continue
            if b is not None and de is not None and de - b > MAX_LIFESPAN:
                self.stats[f"people with a life of more than {MAX_LIFESPAN} years (year of birth not used)"] += 1
                b = None
            pres = []
            for role, prop, lit in (("birth", "birthLocationURI", "birthLocation"),
                                    ("death", "deathLocationURI", "deathLocation"),
                                    ("burial", "burialLocationURI", "burialLocation")):
                hint = d[JL + lit][0].value if d.get(JL + lit) else ""
                for u in d.get(JL + prop, []):
                    i = self.place(u, hint)
                    if i is not None:
                        pres.append((i, role))
                        break
                else:
                    if d.get(JL + prop):
                        self.stats[f"{role} places without coordinates (or a country or region)"] += 1
            for r in self.gnd_records(s):
                for role, prop in (("activity", "placeOfActivity"), ("exile", "placeOfExile")):
                    for u in self.gnd[r].get(GNDO + prop, []):
                        i = self.place(u)
                        if i is not None and (i, role) not in pres:
                            pres.append((i, role))
            if not pres:
                self.stats["people without a place with coordinates"] += 1
                continue
            if b is None and de is None:
                self.stats["people with places but no years"] += 1
                continue
            flags = 0
            if b is None:
                b, flags = de - LIFESPAN, flags | 1
            if de is None:
                de, flags = min(b + LIFESPAN, NOW), flags | 2
            self._new_entity(s, "person", label_of(d.get(SKOS + "prefLabel", [])), b, de, flags,
                             [[i, role, None] for i, role in pres])
            self.stats["people on the map"] += 1

    def _organisations(self):
        """Organisations with a seat (GND place of business) and a year of establishment; without a year of
        termination they are shown in the year of establishment only (decision 0003)."""
        for s in self.ep:
            if self.kind.get(s) != "organisation":
                continue
            seat, start, end = [], None, None
            for r in self.gnd_records(s):
                g = self.gnd[r]
                for u in g.get(GNDO + "placeOfBusiness", []):
                    i = self.place(u)
                    if i is not None and i not in seat:
                        seat.append(i)
                start = start or next((first_year(v.value) for v in g.get(GNDO + "dateOfEstablishment", [])), None)
                end = end or next((first_year(v.value) for v in g.get(GNDO + "dateOfTermination", [])), None)
            if not seat or (start is None and end is None):
                continue
            flags = 0
            if start is None:
                start, flags = end, flags | 1
            if end is None:
                end, flags = start, flags | 2
            if end < start:
                continue
            self._new_entity(s, "organisation", label_of(self.ep[s].get(SKOS + "prefLabel", [])), start, end, flags,
                             [[i, "seat", None] for i in seat])
            self.stats["organisations on the map"] += 1

    def _haskala(self):
        """Books of the Library of Haskala: the place and year of printing, the places and years of editions;
        producers, translators and preface writers as connections (decision 0004)."""
        g = collections.defaultdict(lambda: collections.defaultdict(list))
        for s, p, o in self.store.triples("haskala"):
            if p.startswith(HV) or p == RDF_TYPE:
                g[s][p].append(o)
        self.haskala = g

        def lit(s, p):
            v = g[s].get(HV + p)
            return v[0].value if v and isinstance(v[0], Literal) else ""

        def year(b):
            greg = lit(b, "gregorian_year").strip()
            if greg.isdigit():
                return int(greg)
            m = re.search(r"(?<!\d)(1[5-9]\d\d)(?!\d)", lit(b, "publication_year_in_book"))
            if m:
                return int(m.group(1))
            return hebrew_year(lit(b, "hebrew_year_of_publication")) or hebrew_year(lit(b, "publication_year_in_book"))

        books = [s for s in g if s.startswith(DATA + "haskala/book/")]
        editions = collections.defaultdict(list)
        for s in g:
            if s.startswith(DATA + "haskala/edition/") and g[s].get(HV + "book"):
                editions[g[s][HV + "book"][0]].append(s)
        self.haskala_book_entity = {}
        for b in books:
            y = year(b)
            e = self.entity(b) or b
            self.haskala_book_entity[b] = e
            if y is None:
                continue
            pres = []
            for c in g[b].get(HV + "publication_place", []):
                i = self.place(c)
                if i is not None:
                    pres.append([i, "printed", None])
            years = [y]
            for ed in editions.get(b, []):
                ey = first_year(lit(ed, "edition_year"))
                for c in g[ed].get(HV + "edition_city", []):
                    i = self.place(c)
                    if i is not None and ey is not None and ey != y:
                        pres.append([i, "edition", ey])
                        years.append(ey)
            if not pres:
                continue
            title = lit(b, "title_in_latin_characters") or lit(b, "full_title")
            if e in self.ep and self.ep[e].get(SKOS + "prefLabel"):
                title = label_of(self.ep[e][SKOS + "prefLabel"])
            self._new_entity(e, "publication", title, y, y, 0, pres)
            self.stats["Haskala books on the map"] += 1

    # names of places of publication in Compact Memory that are no label of the place they name (decision 0004)
    PLACE_NAMES = {"Frankfurt, M.": "Frankfurt am Main", "Frankfurt a.M.": "Frankfurt am Main",
                   "Frankfurt a. M.": "Frankfurt am Main", "Frankfurt, Main": "Frankfurt am Main",
                   "Frankfurt, O.": "Frankfurt (Oder)", "Ṿarsha": "Warsaw", "Ṿarshe": "Warsaw",
                   "Yerushalayim": "Jerusalem", "Wilne": "Vilnius", "Tel-Aviv": "Tel Aviv", "Pest": "Budapest",
                   "Szegedin": "Szeged", "Washington, DC": "Washington, D.C.", "Gräfelfing bei München": "Gräfelfing",
                   "Bratislava, Dunajská Streda": "Bratislava", "Bratislava-Prešov": "Bratislava",
                   "Mährisch-Ostrau": "Ostrava", "Strassburg": "Strasbourg", "Brünn": "Brno", "Lemberg": "Lviv",
                   "Ramat-Gan": "Ramat Gan", "St. Petersburg": "Saint Petersburg"}

    def _periodicals(self):
        """Compact Memory periodicals: the first place of publication (a name, matched to the label of a place page)
        and the years of the publication period (decision 0004)."""
        labels = collections.defaultdict(list)
        for s, d in self.ep.items():
            if s in self.place_of_entity:
                weight = len(d.get(JL + "sameAs", [])) + len(d.get(OWL_SAMEAS, []))
                for lit in d.get(SKOS + "prefLabel", []):
                    labels[lit.value.casefold()].append((1, weight, s))
                for lit in d.get(SKOS + "altLabel", []):
                    labels[lit.value.casefold()].append((0, weight, s))
        cm = collections.defaultdict(lambda: collections.defaultdict(list))
        for s, p, o in self.store.triples("compact-memory", "journals"):
            cm[s][p].append(o)
        self.place_matches = collections.Counter()
        for s, d in cm.items():
            if SCHEMA + "Periodical" not in d.get(RDF_TYPE, []):
                continue
            periods = [v.value for v in d.get(JL + "publicationPeriod", [])]
            span = None
            for v in periods:
                m = re.fullmatch(r"\s*(\d{4})\s*-\s*(\d{4})\s*", v)
                if m and int(m.group(1)) <= int(m.group(2)):
                    span = int(m.group(1)), int(m.group(2))
                    break
            if not span:
                years = [int(y) for v in periods for y in re.findall(r"(?<!\d)(1[6-9]\d\d|20[0-2]\d)(?!\d)", v)]
                span = (min(years), max(years)) if years else None
            name = d[JL + "placeOfPublication"][0].value if d.get(JL + "placeOfPublication") else ""
            name = re.sub(r"\[[^\]]*\]|\[|\]", "", name.split(";")[0]).strip()
            name = self.PLACE_NAMES.get(name, name)
            cands = labels.get(name.casefold(), [])
            if not span or not cands:
                self.stats["periodicals without years or a matched place"] += 1
                if span:
                    self.stats[f"periodical place not matched: {name}"] += 1
                continue
            best = max(cands)[2]
            self.place_matches[(name, best)] += 1
            title = d[DCT + "title"][0].value if d.get(DCT + "title") else s
            self._new_entity(s, "publication", title, span[0], span[1], 0,
                             [[self.place_of_entity[best], "published", None]])
            self.stats["periodicals on the map"] += 1

    def _footprints(self):
        """Imprints of Footprints: the place and year of printing, and the places and years of the footprints of their
        copies; authors, editors, printers and publishers as connections (decision 0005)."""
        g = collections.defaultdict(lambda: collections.defaultdict(list))
        for s, p, o in self.store.triples("footprints"):
            if s.startswith(FP) and not s.startswith(FPV):
                g[s][p].append(o)
        self.footprints = g

        def years(objs):
            for o in objs:
                if isinstance(o, Literal):
                    m = re.match(r"\s*(\d{3}[\dxX])", o.value)
                    if m:
                        y = int(m.group(1).lower().replace("x", "0"))
                        if 1000 <= y <= NOW:
                            return y
            return None

        def place(s):
            for o in g[s].get(FPV + "place", []):
                i = self.place(o, label_of(g[o].get(SKOS + "prefLabel", [])))
                if i is not None:
                    return i
            return None

        copies = collections.defaultdict(list)
        for s, d in g.items():
            if s.startswith(FP + "footprint/"):
                for c in d.get(FPV + "copy", []):
                    for i in g[c].get(FPV + "imprint", []):
                        copies[i].append(s)
        self.fp_imprint_entity = {}
        for s, d in g.items():
            if not s.startswith(FP + "imprint/"):
                continue
            y, i = years(d.get(FPV + "publicationDate", [])), place(s)
            if y is None or i is None:
                self.stats["Footprints imprints without a year or a place with coordinates"] += 1
                continue
            e = self.entity(s) or s
            self.fp_imprint_entity[s] = e
            pres = [[i, "printed", None]]
            for f in copies.get(s, []):
                fy, fi = years(g[f].get(FPV + "associatedDate", [])), place(f)
                if fy is not None and fi is not None and [fi, "copy", fy] not in pres:
                    pres.append([fi, "copy", fy])
                    self.stats["Footprints footprints on the map"] += 1
            title = ""
            if e in self.ep and self.ep[e].get(SKOS + "prefLabel"):
                title = label_of(self.ep[e][SKOS + "prefLabel"])
            title = title or label_of(d.get(FPV + "title", [])) or label_of(d.get(SKOS + "prefLabel", []))
            if e in self.entities:   # an entity page that is already a publication (another dataset)
                self.entities[e]["places"] += [x for x in pres if x not in self.entities[e]["places"]]
            else:
                self._new_entity(e, "publication", title, y, y, 0, pres)
            self.stats["Footprints imprints on the map"] += 1

    # --- connections -----------------------------------------------------------------------------------------------
    def _connections(self):
        rel = set()

        def add(a, b, kind):
            if a and b and a != b and a in self.entities and b in self.entities:
                rel.add((min(a, b), max(a, b), kind))
            else:
                self.stats[f"{kind} connections not on the map"] += 1

        for r, d in self.gnd.items():
            a = self.entity(r)
            for p, kind in GND_RELATIONS.items():
                for o in d.get(p, []):
                    add(a, self.entity(o), kind)
        for slug, props in (("epidat", EPIDAT_RELATIONS), ("gba", GBA_RELATIONS)):
            for s, p, o in self.store.triples(slug):
                if p in props and isinstance(o, IRI):
                    add(self.entity(s), self.entity(o), props[p])
        g = self.haskala
        for n, d in g.items():
            b = d.get(HV + "book", [None])[0]
            if b not in self.haskala_book_entity:
                continue
            for p in ("producer", "translator", "preface_writer"):
                for person in d.get(HV + p, []):
                    add(self.entity(person), self.haskala_book_entity[b], "creator")
        g = self.footprints
        for s, e in self.fp_imprint_entity.items():
            makers = set()
            for src in [s] + list(g[s].get(FPV + "work", [])):
                for p in FP_MAKERS:
                    makers |= {o for o in g[src].get(p, []) if isinstance(o, IRI)}
            for person in sorted(makers):
                add(self.entity(person), e, "creator")
        self.connections = sorted(rel)
        for a, b, kind in self.connections:
            self.stats[f"{kind} connections"] += 1
