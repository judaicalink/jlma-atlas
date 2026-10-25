"""Tests of the readers of years, coordinates and IRIs (python3 -m unittest discover tests)."""

import unittest

from atlas import model
from atlas.geo import inside


class Years(unittest.TestCase):
    def test_year_of(self):
        self.assertEqual(model.year_of("1816-12-18"), 1816)
        self.assertEqual(model.year_of("1890"), 1890)
        self.assertEqual(model.year_of("-0500"), -500)
        self.assertIsNone(model.year_of("ca. 1790"))
        self.assertIsNone(model.year_of("2150"))

    def test_first_year(self):
        self.assertEqual(model.first_year("30.10.1998"), 1998)
        self.assertEqual(model.first_year("XX.XX.2019"), 2019)
        self.assertIsNone(model.first_year("[1./2. Jh.]"))

    def test_hebrew_year(self):
        self.assertEqual(model.hebrew_year("תקמט"), 1789)
        self.assertEqual(model.hebrew_year("תקמ\"ט"), 1789)
        self.assertIsNone(model.hebrew_year("1789"))


class Places(unittest.TestCase):
    def test_wkt(self):
        self.assertEqual(model.parse_wkt("POINT(25.940277 48.291388)"), (25.9403, 48.2914))
        self.assertEqual(model.parse_wkt("Point ( +006.083333 +050.776388 )"), (6.0833, 50.7764))
        self.assertIsNone(model.parse_wkt("POINT(0 0)"))
        self.assertIsNone(model.parse_wkt("POINT(200 10)"))

    def test_key(self):
        self.assertEqual(model.key("https://sws.geonames.org/710719/"), model.key("http://sws.geonames.org/710719"))
        self.assertEqual(model.key("https://www.wikidata.org/wiki/Q1"), model.key("http://www.wikidata.org/entity/Q1"))

    def test_area_features(self):
        self.assertTrue(model.AREA_FEATURES.search("https://www.geonames.org/ontology#A.PCLI"))
        self.assertTrue(model.AREA_FEATURES.search("https://www.geonames.org/ontology#A.ADM1"))
        self.assertFalse(model.AREA_FEATURES.search("https://www.geonames.org/ontology#A.ADM2"))
        self.assertFalse(model.AREA_FEATURES.search("https://www.geonames.org/ontology#P.PPLC"))

    def test_inside(self):
        square = [(0, 0), (10, 0), (10, 10), (0, 10), (0, 0)]
        self.assertTrue(inside((5, 5), square))
        self.assertFalse(inside((15, 5), square))


if __name__ == "__main__":
    unittest.main()
