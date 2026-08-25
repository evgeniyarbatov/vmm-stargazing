from __future__ import annotations

from typing import NamedTuple


class SkyTarget(NamedTuple):
    name: str
    ra_hours: float
    dec_deg: float
    mag: float | None
    kind: str
    constellation: str


STARS: tuple[SkyTarget, ...] = (
    SkyTarget("Sirius", 6.7525, -16.7161, -1.46, "star", "Canis Major"),
    SkyTarget("Canopus", 6.3992, -52.6956, -0.74, "star", "Carina"),
    SkyTarget("Arcturus", 14.2610, 19.1824, -0.05, "star", "Boötes"),
    SkyTarget("Vega", 18.6156, 38.7837, 0.03, "star", "Lyra"),
    SkyTarget("Capella", 5.2782, 45.9980, 0.08, "star", "Auriga"),
    SkyTarget("Rigel", 5.2423, -8.2016, 0.13, "star", "Orion"),
    SkyTarget("Procyon", 7.6553, 5.2250, 0.34, "star", "Canis Minor"),
    SkyTarget("Betelgeuse", 5.9195, 7.4071, 0.42, "star", "Orion"),
    SkyTarget("Achernar", 1.6286, -57.2368, 0.46, "star", "Eridanus"),
    SkyTarget("Hadar", 14.0637, -60.3730, 0.61, "star", "Centaurus"),
    SkyTarget("Altair", 19.8464, 8.8683, 0.76, "star", "Aquila"),
    SkyTarget("Acrux", 12.4433, -63.0991, 0.77, "star", "Crux"),
    SkyTarget("Aldebaran", 4.5987, 16.5093, 0.85, "star", "Taurus"),
    SkyTarget("Antares", 16.4901, -26.4320, 0.96, "star", "Scorpius"),
    SkyTarget("Spica", 13.4199, -11.1613, 0.97, "star", "Virgo"),
    SkyTarget("Pollux", 7.7553, 28.0262, 1.14, "star", "Gemini"),
    SkyTarget("Fomalhaut", 22.9608, -29.6222, 1.16, "star", "Piscis Austrinus"),
    SkyTarget("Deneb", 20.6905, 45.2803, 1.25, "star", "Cygnus"),
    SkyTarget("Mimosa", 12.7953, -59.6888, 1.25, "star", "Crux"),
    SkyTarget("Regulus", 10.1395, 11.9672, 1.35, "star", "Leo"),
    SkyTarget("Adhara", 6.9770, -28.9721, 1.50, "star", "Canis Major"),
    SkyTarget("Castor", 7.5767, 31.8883, 1.58, "star", "Gemini"),
    SkyTarget("Shaula", 17.5603, -37.1038, 1.62, "star", "Scorpius"),
    SkyTarget("Gacrux", 12.5194, -57.1132, 1.63, "star", "Crux"),
    SkyTarget("Bellatrix", 5.4186, 6.3497, 1.64, "star", "Orion"),
    SkyTarget("Elnath", 5.4382, 28.6075, 1.65, "star", "Taurus"),
    SkyTarget("Alnair", 22.1372, -46.9610, 1.74, "star", "Grus"),
    SkyTarget("Alioth", 12.9004, 55.9598, 1.77, "star", "Ursa Major"),
    SkyTarget("Alnitak", 5.6794, -1.9426, 1.77, "star", "Orion"),
    SkyTarget("Dubhe", 11.0621, 61.7510, 1.79, "star", "Ursa Major"),
    SkyTarget("Mirfak", 3.4054, 49.8612, 1.80, "star", "Perseus"),
    SkyTarget("Kaus Australis", 18.4029, -34.3847, 1.85, "star", "Sagittarius"),
    SkyTarget("Atria", 16.8111, -69.0277, 1.91, "star", "Triangulum Australe"),
    SkyTarget("Peacock", 20.4275, -56.7350, 1.94, "star", "Pavo"),
    SkyTarget("Polaris", 2.5303, 89.2641, 1.98, "star", "Ursa Minor"),
    SkyTarget("Alphard", 9.4597, -8.6586, 1.98, "star", "Hydra"),
    SkyTarget("Hamal", 2.1196, 23.4624, 2.00, "star", "Aries"),
    SkyTarget("Diphda", 0.7265, -17.9866, 2.04, "star", "Cetus"),
    SkyTarget("Ankaa", 0.4380, -42.3051, 2.04, "star", "Phoenix"),
    SkyTarget("Nunki", 18.9211, -26.2967, 2.05, "star", "Sagittarius"),
    SkyTarget("Alpheratz", 0.1398, 29.0904, 2.07, "star", "Andromeda"),
    SkyTarget("Rasalhague", 17.5822, 12.5600, 2.08, "star", "Ophiuchus"),
    SkyTarget("Algol", 3.1361, 40.9556, 2.12, "star", "Perseus"),
    SkyTarget("Denebola", 11.8177, 14.5720, 2.14, "star", "Leo"),
    SkyTarget("Schedar", 0.6751, 56.5373, 2.23, "star", "Cassiopeia"),
    SkyTarget("Alphecca", 15.5781, 26.7147, 2.23, "star", "Corona Borealis"),
    SkyTarget("Sadr", 20.3705, 40.2567, 2.23, "star", "Cygnus"),
    SkyTarget("Caph", 0.1529, 59.1498, 2.28, "star", "Cassiopeia"),
    SkyTarget("Enif", 21.7364, 9.8750, 2.38, "star", "Pegasus"),
    SkyTarget("Markab", 23.0793, 15.2053, 2.49, "star", "Pegasus"),
    SkyTarget("Menkar", 3.0380, 4.0897, 2.54, "star", "Cetus"),
    SkyTarget("Unukalhai", 15.7373, 6.4255, 2.65, "star", "Serpens"),
    SkyTarget("Algenib", 0.2206, 15.1836, 2.83, "star", "Pegasus"),
    SkyTarget("Dabih", 21.7780, -16.1273, 3.08, "star", "Capricornus"),
    SkyTarget("Sadalsuud", 21.5259, -5.5712, 2.87, "star", "Aquarius"),
    SkyTarget("Alrescha", 2.0342, 2.7637, 3.82, "star", "Pisces"),
    SkyTarget("Arneb", 5.5455, -17.8223, 2.58, "star", "Lepus"),
    SkyTarget("Naos", 8.1255, -40.0031, 2.21, "star", "Puppis"),
    SkyTarget("Suhail", 9.1320, -43.4326, 2.23, "star", "Vela"),
    SkyTarget("Phact", 5.6608, -34.0741, 2.65, "star", "Columba"),
    SkyTarget("Tarazed", 19.7709, 10.6133, 2.72, "star", "Aquila"),
    SkyTarget("Eltanin", 17.9434, 51.4889, 2.23, "star", "Draco"),
    SkyTarget("Alderamin", 21.3096, 62.5856, 2.45, "star", "Cepheus"),
)

NAV_STARS = {
    "Sirius",
    "Canopus",
    "Arcturus",
    "Vega",
    "Capella",
    "Rigel",
    "Procyon",
    "Betelgeuse",
    "Altair",
    "Aldebaran",
    "Antares",
    "Spica",
    "Pollux",
    "Fomalhaut",
    "Deneb",
    "Regulus",
    "Polaris",
    "Achernar",
}

GALACTIC_CENTER = SkyTarget("Milky Way centre", 17.7611, -29.0078, None, "feature", "Sagittarius")

PLANETS = (
    ("Mercury", "mercury"),
    ("Venus", "venus"),
    ("Mars", "mars"),
    ("Jupiter", "jupiter barycenter"),
    ("Saturn", "saturn barycenter"),
)
