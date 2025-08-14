from __future__ import annotations

from typing import Dict, List


# Constellation definitions for circumpolar constellations visible from
# Dominican Republic latitudes (~18–20° N). Each constellation lists a
# representative subset of bright stars (names must match `star_catalog.json`)
# and an edge list that connects those stars for drawing lines.


Constellation = Dict[str, List[str]]


CONSTELLATIONS: Dict[str, Dict[str, List[List[str]]]] = {
    "Ursa Minor": {
        "stars": [
            "Polaris",
            "Yildun",
            "Epsilon UMi",
            "Zeta UMi",
            "Pherkad",
            "Kochab",
        ],
        # Lines follow the Little Dipper handle -> bowl and close the bowl.
        "edges": [
            ["Polaris", "Yildun"],
            ["Yildun", "Epsilon UMi"],
            ["Epsilon UMi", "Zeta UMi"],
            ["Zeta UMi", "Pherkad"],
            ["Pherkad", "Kochab"],
            ["Kochab", "Polaris"],
            ["Kochab", "Pherkad"],  # bowl side
        ],
    },

    "Ursa Major": {
        "stars": [
            "Dubhe",
            "Merak",
            "Phecda",
            "Megrez",
            "Alioth",
            "Mizar",
            "Alkaid",
        ],
        # Classic Big Dipper outline
        "edges": [
            ["Dubhe", "Merak"],
            ["Merak", "Phecda"],
            ["Phecda", "Megrez"],
            ["Megrez", "Dubhe"],   # close bowl
            ["Megrez", "Alioth"],
            ["Alioth", "Mizar"],
            ["Mizar", "Alkaid"],
        ],
    },

    "Draco": {
        "stars": [
            "Eltanin",
            "Rastaban",
            "Grumium",
            "Kuma",
            "Edasich",
            "Thuban",
            "Gianfar",
            "Aldhibah",
        ],
        # Serpentine chain from head (Eltanin/Rastaban) across the sky
        "edges": [
            ["Eltanin", "Rastaban"],
            ["Rastaban", "Grumium"],
            ["Grumium", "Kuma"],
            ["Kuma", "Edasich"],
            ["Edasich", "Thuban"],
            ["Thuban", "Gianfar"],
            ["Gianfar", "Aldhibah"],
        ],
    },

    "Cepheus": {
        "stars": [
            "Alderamin",
            "Alfirk",
            "Delta Cephei",
            "Zeta Cephei",
            "Errai",
        ],
        # House/pentagon shape (closed loop)
        "edges": [
            ["Alderamin", "Alfirk"],
            ["Alfirk", "Delta Cephei"],
            ["Delta Cephei", "Zeta Cephei"],
            ["Zeta Cephei", "Errai"],
            ["Errai", "Alderamin"],
        ],
    },

    "Cassiopeia": {
        "stars": [
            "Schedar",
            "Caph",
            "Gamma Cassiopeiae",
            "Ruchbah",
            "Segin",
        ],
        # Classic W shape
        "edges": [
            ["Schedar", "Caph"],
            ["Caph", "Gamma Cassiopeiae"],
            ["Gamma Cassiopeiae", "Ruchbah"],
            ["Ruchbah", "Segin"],
        ],
    },
}


def list_constellations() -> List[str]:
    return list(CONSTELLATIONS.keys())


def get_constellation_definition(name: str) -> Dict[str, List[List[str]]]:
    if name not in CONSTELLATIONS:
        raise KeyError(f"Constellation not found: {name}")
    return CONSTELLATIONS[name]


