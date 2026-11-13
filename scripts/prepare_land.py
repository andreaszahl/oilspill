"""Lager en forenklet landpolygon for Nordland-utsnittet (steg 2).

Leser Kartverket N250 (File Geodatabase i data/raw/), plukker ut landarealet
(alt areal som ikke er sjø), klipper til utsnittet, slår sammen til én geometri,
forenkler den, og skriver en lett GeoJSON til data/processed/land_nordland.geojson.

Denne fila brukes av simulate_spill.py til å klippe oljeflaket mot kysten, og kan
også tegnes i webkartet. Rådata (N250) ligger i data/raw/ (git-ignorert); det
forenklede utsnittet i data/processed/ (sjekkes inn, som øvrige prosesserte data).

N250-detaljer (verifisert mot nedlastet fil):
  - Lag: N250_Arealdekke_omrade (MultiPolygon, allerede i EPSG:25833).
  - Sjø er objtype == 'Havflate'; land = alle andre arealtyper.
"""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
from shapely.geometry import box

# Del utsnitt og CRS med simuleringsskriptet (ligger i samme mappe).
from simulate_spill import BBOX, CRS_METRIC, CRS_WGS84, DATA_DIR, PROCESSED_DIR

RAW_DIR = DATA_DIR / "raw"

# Nedlastet N250-fil for Nordland (FGDB). Juster navnet hvis du laster ned på nytt.
N250_GDB = RAW_DIR / "Basisdata_18_Nordland_25833_N250Kartdata_FGDB.gdb"
LAND_LAYER = "N250_Arealdekke_omrade"
SEA_OBJTYPE = "Havflate"  # arealtypen som er sjø – alt annet regnes som land

LAND_SIMPLIFY_TOLERANCE_M = 100.0  # forenklingstoleranse i meter (EPSG:25833)

OUT_PATH = PROCESSED_DIR / "land_nordland.geojson"


def main() -> None:
    if not N250_GDB.exists():
        raise SystemExit(
            f"Fant ikke N250-data: {N250_GDB}\n"
            "Last ned 'N250 Kartdata' for Nordland (FGDB) fra Geonorge og legg "
            "mappa i data/raw/ (se CLAUDE.md / planen)."
        )

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    arealdekke = gpd.read_file(N250_GDB, layer=LAND_LAYER)
    # Behold land: alt areal som ikke er sjø.
    land = arealdekke[arealdekke["objtype"] != SEA_OBJTYPE].to_crs(CRS_METRIC)

    # Klipp til utsnittet (BBOX er i lon/lat -> reprojiser til meter).
    clip_box = (
        gpd.GeoSeries([box(*BBOX)], crs=CRS_WGS84).to_crs(CRS_METRIC).iloc[0]
    )
    land = gpd.clip(land, clip_box)

    # Slå sammen til én geometri og forenkle (reduserer punkter, beholder form).
    merged = land.geometry.union_all().simplify(
        LAND_SIMPLIFY_TOLERANCE_M, preserve_topology=True
    )

    out = gpd.GeoDataFrame({"name": ["Nordland (forenklet)"]}, geometry=[merged], crs=CRS_METRIC)
    out.to_crs(CRS_WGS84).to_file(OUT_PATH, driver="GeoJSON")

    print(
        f"Skrev forenklet land ({len(land)} kildepolygoner slått sammen, "
        f"toleranse {LAND_SIMPLIFY_TOLERANCE_M:.0f} m) -> {OUT_PATH}"
    )


if __name__ == "__main__":
    main()
