from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from report import build_pages, fmt_hours


def _cfg() -> dict:
    return {"race": {"name": "VMM 100 Miles 2026", "location": "Sa Pa, Lào Cai, Vietnam"}}


def _nights() -> dict:
    return {
        "timezone": "Asia/Ho_Chi_Minh",
        "pace_kmh": 3.2,
        "nights": [
            {
                "night_id": 1,
                "start": "2026-09-18T19:40:00+07:00",
                "end": "2026-09-19T04:50:00+07:00",
                "duration_h": 9.166,
                "elapsed0_h": 11.666,
                "elapsed1_h": 20.833,
                "dist0_km": 37.0,
                "dist1_km": 67.0,
            }
        ],
        "events": [
            {
                "event": "astronomical_dusk",
                "time": "2026-09-18T19:40:00+07:00",
                "elapsed_h": 11.666,
            }
        ],
    }


def _sample(**overrides: object) -> dict:
    row = {
        "i": 0,
        "night_id": 1,
        "time": "2026-09-18T23:00:00+07:00",
        "elapsed_h": 15.0,
        "dist_km": 48.0,
        "elev_m": 1700,
        "heading_deg": 90,
    }
    row.update(overrides)
    return row


def _sky() -> list[dict]:
    return [
        {
            "sample_i": 0,
            "kind": "planet",
            "name": "Jupiter",
            "alt_deg": 45.0,
            "az_deg": 140.0,
            "mag": -2.5,
            "obscured": False,
            "tag": "up",
        },
        {
            "sample_i": 0,
            "kind": "star",
            "name": "Vega",
            "constellation": "Lyra",
            "alt_deg": 70.0,
            "az_deg": 10.0,
            "mag": 0.03,
            "obscured": False,
            "tag": "overhead",
        },
        {
            "sample_i": 0,
            "kind": "moon",
            "name": "Moon",
            "alt_deg": 30.0,
            "az_deg": 220.0,
            "illumination": 0.7,
            "phase_name": "waxing gibbous",
            "obscured": False,
            "tag": "up",
        },
    ]


class TestReport(unittest.TestCase):
    def test_fmt_hours(self) -> None:
        self.assertEqual(fmt_hours(11.5), "11h 30m")

    def test_site_splits_into_linked_pages(self) -> None:
        pages = build_pages(_cfg(), _nights(), [_sample()], _sky())
        self.assertIn("index.html", pages)
        self.assertIn("course.html", pages)
        self.assertIn("night-1.html", pages)
        self.assertIn("night-1-km48.html", pages)
        self.assertIn("night-1-sky.html", pages)

        index = pages["index.html"]
        self.assertIn("VMM 100 Miles 2026", index)
        self.assertIn("Look up.", index)
        self.assertIn("Contents", index)
        self.assertIn("One night on the course", index)
        self.assertNotIn("Two nights", index)
        self.assertNotIn("Hoàng Liên Sơn", index)
        self.assertIn('href="course.html"', index)
        self.assertIn('href="night-1.html"', index)
        self.assertIn('href="night-1-km48.html"', index)
        self.assertIn("best stop", index)
        self.assertIn("Overhead: Lyra", index)
        self.assertNotIn("https://grokipedia.com/page/Lyra", index)
        self.assertNotIn("https://en.wikipedia.org/wiki/Lyra", index)
        self.assertNotIn('href="#night-1"', index)

        course = pages["course.html"]
        self.assertIn("predicted pace", course.lower())
        self.assertIn("sampled every 2 km", course)
        self.assertIn("Aid stations are not used", course)
        self.assertNotIn("last kilometres", course)
        self.assertNotIn("Hoàng Liên Sơn", course)
        self.assertIn("<details", course)
        self.assertIn("data.json", course)
        self.assertIn('download="vmm-stargazing.json"', course)
        self.assertIn('href="night-1.html"', course)
        self.assertIn('data-label="Night"', course)
        self.assertIn('data-label="Astro dusk"', course)

        night = pages["night-1.html"]
        self.assertIn("Night 1", night)
        self.assertIn("best stop", night)
        self.assertIn("Stargazing stops", night)
        self.assertIn('href="night-1-km48.html"', night)
        self.assertIn('href="night-1-sky.html"', night)
        self.assertIn("Lyra", night)

        stop = pages["night-1-km48.html"]
        self.assertIn("Jupiter", stop)
        self.assertIn("Lyra", stop)
        self.assertIn("waxing gibbous", stop)
        self.assertIn("References", stop)
        self.assertIn("https://grokipedia.com/page/Jupiter", stop)
        self.assertIn("https://grokipedia.com/page/Vega", stop)
        self.assertIn("https://grokipedia.com/page/Lyra", stop)
        self.assertIn("https://en.wikipedia.org/wiki/Jupiter", stop)
        self.assertIn("https://en.wikipedia.org/wiki/Vega", stop)
        self.assertIn("https://grokipedia.com/page/Moon", stop)
        self.assertNotIn('target="_blank" rel="noopener noreferrer">Jupiter</a>', stop)
        self.assertIn('href="night-1.html"', stop)
        self.assertIn('href="index.html"', stop)

        for page in pages.values():
            self.assertNotIn("steer", page)

    def test_html_embeds_plot_download_links(self) -> None:
        cfg = {"race": {"name": "VMM"}}
        nights = {
            "timezone": "Asia/Ho_Chi_Minh",
            "nights": [
                {
                    "night_id": 1,
                    "start": "2026-09-18T19:40:00+07:00",
                    "end": "2026-09-19T04:50:00+07:00",
                    "duration_h": 9.0,
                    "elapsed0_h": 11.7,
                    "elapsed1_h": 20.8,
                    "dist0_km": 37.0,
                    "dist1_km": 67.0,
                }
            ],
            "events": [],
        }
        samples = [_sample(time="2026-09-18T19:40:00+07:00", elapsed_h=11.7, dist_km=37.0, elev_m=900, heading_deg=10)]
        sky = [
            {
                "sample_i": 0,
                "kind": "planet",
                "name": "Saturn",
                "alt_deg": 10.0,
                "az_deg": 90.0,
                "mag": 0.4,
                "obscured": False,
                "tag": "up",
            }
        ]
        pages = build_pages(
            cfg,
            nights,
            samples,
            sky,
            plots={
                "course": "plots/course.png",
                "spots": "plots/spots.png",
                "night1-alt-planet-saturn": "plots/night1-alt-planet-saturn.png",
                "night1-alt-star-vega": "plots/night1-alt-star-vega.png",
                "night1-s0": "plots/night1-s0.png",
                "night1-s0-ahead": "plots/night1-s0-ahead.png",
            },
        )
        course = pages["course.html"]
        self.assertIn("plots/course.png", course)
        self.assertIn("plots/spots.png", course)
        self.assertNotIn("Download chart", course)

        stop = pages["night-1-km37.html"]
        self.assertIn("plots/night1-s0.png", stop)
        self.assertIn("plots/night1-s0-ahead.png", stop)
        self.assertNotIn("Download chart", stop)

        sky_page = pages["night-1-sky.html"]
        self.assertIn("plots/night1-alt-planet-saturn.png", sky_page)
        self.assertIn("plots/night1-alt-star-vega.png", sky_page)
        self.assertIn('<h4 id="saturn">Saturn</h4>', sky_page)
        self.assertIn('<h4 id="vega">Vega</h4>', sky_page)
        self.assertIn("https://grokipedia.com/page/Saturn", sky_page)
        self.assertIn("https://grokipedia.com/page/Vega", sky_page)
        self.assertIn("Grokipedia", sky_page)
        self.assertNotIn("Download chart", sky_page)
        self.assertNotIn("night1-steer", sky_page)
        self.assertNotIn("night1-alt-planets", sky_page)
        self.assertNotIn("night1-alt-stars", sky_page)
        self.assertNotIn("night1-alt.png", sky_page)

        pages_gpx = build_pages(cfg, nights, samples, sky, spots_gpx=True)
        self.assertIn("stargazing-spots.gpx", pages_gpx["index.html"])
        self.assertIn("stargazing-spots.gpx", pages_gpx["course.html"])

    def test_sample_step_follows_config(self) -> None:
        cfg = _cfg()
        cfg["sampling"] = {"distance_m": 1500}
        course = build_pages(cfg, _nights(), [_sample()], _sky())["course.html"]
        self.assertIn("sampled every 1.5 km", course)
        self.assertNotIn("sampled every 2 km", course)

    def test_html_embeds_iau_constellation_gallery(self) -> None:
        cfg = {"race": {"name": "VMM"}}
        nights = {
            "timezone": "Asia/Ho_Chi_Minh",
            "nights": [
                {
                    "night_id": 1,
                    "start": "2026-09-18T19:40:00+07:00",
                    "end": "2026-09-19T04:50:00+07:00",
                    "duration_h": 9.0,
                    "elapsed0_h": 11.7,
                    "elapsed1_h": 20.8,
                    "dist0_km": 37.0,
                    "dist1_km": 67.0,
                }
            ],
            "events": [],
        }
        samples = [
            _sample(
                time="2026-09-18T19:40:00+07:00",
                elapsed_h=11.7,
                dist_km=37.0,
                elev_m=900,
                heading_deg=10,
            )
        ]
        sky = [
            {
                "sample_i": 0,
                "kind": "star",
                "name": "Alpheratz",
                "constellation": "Andromeda",
                "alt_deg": 60.0,
                "az_deg": 20.0,
                "mag": 2.07,
                "obscured": False,
                "tag": "overhead",
            }
        ]
        pages = build_pages(
            cfg,
            nights,
            samples,
            sky,
            iau_plots={
                1: [
                    (
                        "Andromeda",
                        [
                            ("IAU chart", "plots/constellations/night1/Andromeda.png"),
                            ("Azimuth", "plots/constellations/night1/Andromeda-az.png"),
                            ("Altitude", "plots/constellations/night1/Andromeda-alt.png"),
                        ],
                    ),
                    (
                        "Ara",
                        [("IAU chart", "plots/constellations/night1/Ara.png")],
                    ),
                ],
            },
        )
        self.assertIn("night-1-iau.html", pages)
        iau = pages["night-1-iau.html"]
        self.assertIn("constellation this night", iau)
        self.assertIn("plots/constellations/night1/Andromeda.png", iau)
        self.assertIn("plots/constellations/night1/Andromeda-az.png", iau)
        self.assertIn("plots/constellations/night1/Andromeda-alt.png", iau)
        self.assertIn("Azimuth", iau)
        self.assertIn("Altitude", iau)
        self.assertNotIn("Download chart", iau)
        self.assertIn("<summary>Andromeda</summary>", iau)
        self.assertIn('id="andromeda"', iau)
        self.assertIn("https://grokipedia.com/page/Andromeda_(constellation)", iau)
        self.assertIn("https://en.wikipedia.org/wiki/Andromeda_(constellation)", iau)
        self.assertIn("night-1-km37.html", iau)
        self.assertNotIn("Ara", iau)

        index = pages["index.html"]
        self.assertIn('href="night-1-iau.html"', index)

        stop = pages["night-1-km37.html"]
        self.assertIn('href="night-1-iau.html#andromeda"', stop)
        self.assertNotIn('class="chart"', stop)
        self.assertIn("References", stop)
        self.assertIn("https://grokipedia.com/page/Andromeda_(constellation)", stop)

    def test_nights_cross_link(self) -> None:
        nights = _nights()
        nights["nights"].append(
            {
                "night_id": 2,
                "start": "2026-09-19T19:40:00+07:00",
                "end": "2026-09-20T04:50:00+07:00",
                "duration_h": 9.166,
                "elapsed0_h": 35.666,
                "elapsed1_h": 44.833,
                "dist0_km": 140.0,
                "dist1_km": 157.0,
            }
        )
        samples = [
            _sample(),
            _sample(i=1, night_id=2, time="2026-09-19T23:00:00+07:00", elapsed_h=39.0, dist_km=152.0),
        ]
        sky = _sky() + [
            {
                "sample_i": 1,
                "kind": "star",
                "name": "Vega",
                "constellation": "Lyra",
                "alt_deg": 65.0,
                "az_deg": 15.0,
                "mag": 0.03,
                "obscured": False,
                "tag": "overhead",
            }
        ]
        pages = build_pages(
            _cfg(),
            nights,
            samples,
            sky,
            iau_plots={
                1: [("Lyra", [("IAU chart", "plots/constellations/night1/Lyra.png")])],
                2: [("Lyra", [("IAU chart", "plots/constellations/night2/Lyra.png")])],
            },
        )
        night1 = pages["night-1.html"]
        night2 = pages["night-2.html"]
        self.assertIn("Same sky, different place", night1)
        self.assertIn("Two nights", pages["index.html"])
        self.assertIn('href="night-2.html"', night1)
        self.assertIn('href="night-2-km152.html"', night1)
        self.assertIn('href="night-1.html"', night2)
        self.assertIn('href="night-1-km48.html"', night2)
        iau1 = pages["night-1-iau.html"]
        self.assertIn('href="night-2-iau.html#lyra"', iau1)
