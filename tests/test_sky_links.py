from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from catalog import PLANETS, STARS
from sky_links import fold_name, load_sky_links, sky_entry


class TestSkyLinks(unittest.TestCase):
    def setUp(self) -> None:
        self.links = load_sky_links()

    def test_catalog_names_are_mapped(self) -> None:
        for star in STARS:
            sky_entry(star.name, self.links)
            sky_entry(star.constellation, self.links)
        for name, _ in PLANETS:
            sky_entry(name, self.links)
        sky_entry("Moon", self.links)
        sky_entry("Milky Way centre", self.links)

    def test_iau_aliases_share_urls(self) -> None:
        boot = sky_entry("Bootes", self.links)
        self.assertEqual(boot, sky_entry("Boötes", self.links))
        serpens = sky_entry("Serpens", self.links)
        self.assertEqual(serpens, sky_entry("Serpens Caput", self.links))
        self.assertEqual(serpens, sky_entry("Serpens Cauda", self.links))

    def test_entries_are_http_urls(self) -> None:
        for name, row in self.links.items():
            self.assertTrue(row["grokipedia"].startswith("http"), name)
            self.assertTrue(row["wikipedia"].startswith("http"), name)

    def test_fold_matches_bootes(self) -> None:
        self.assertEqual(fold_name("Boötes"), fold_name("Bootes"))

    def test_missing_name_raises(self) -> None:
        with self.assertRaises(KeyError):
            sky_entry("Not A Real Star", self.links)
