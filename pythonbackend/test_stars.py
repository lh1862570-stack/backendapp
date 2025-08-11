from __future__ import annotations

from typing import List, Dict

from star_service import compute_visible_stars


def format_star(star: Dict[str, float]) -> str:
    return (
        f"{star['name']} | mag {star['magnitude']:.2f} | "
        f"alt {star['altitude_deg']:.2f}° | az {star['azimuth_deg']:.2f}°"
    )


def main() -> None:
    # Ejemplo: Ciudad de México y una fecha/hora en UTC
    lat = 19.4326
    lon = -99.1332
    date_iso = "2025-01-10T03:00:00Z"

    visible: List[Dict[str, float]] = compute_visible_stars(lat=lat, lon=lon, date_iso=date_iso)

    print(f"Visible stars ({len(visible)}):")
    for star in visible:
        print(" -", format_star(star))


if __name__ == "__main__":
    main()


