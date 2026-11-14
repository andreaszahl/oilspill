"""Simulerer et oljeutslipp som driver med vinden fra en installasjon (fase 1).

Forenklet drift- og spredningsmodell med landklipping. Flaket drives av
dominerende vind fra nærmeste stasjon og vokser som en ellipse strukket i
driftretningen, og klippes mot kystlinjen (data/processed/land_nordland.geojson,
laget av prepare_land.py) slik at det stopper ved land.

Leser data/processed/{installations,wind_stations}.geojson og skriver én
GeoJSON per oljefelt til data/processed/spills/<slug>.geojson med ett polygon
per time og egenskapene: installation, hour, area_km2. Eksporteres i EPSG:4326.

Modellvalg (bevisst enkle):
  - Vind: dominerende retning + middelvind fra nærmeste stasjon. Retningen er
    der vinden kommer FRA, så flaket driver motsatt vei: (retning + 180) % 360.
  - Drift: sentrum flytter seg DRIFT_FACTOR (3 %) av vindhastigheten per time
    (vanlig tommelfingerregel for vinddrift av olje).
  - Spredning: radius(t) = R0 + SPREAD_COEFF * sqrt(t)  (radius ∝ √t).
    Flaket strekkes i driftretningen til en ellipse med arealbevarende forhold
    (halv storakse a = r*√STRETCH, halv lilleakse b = r/√STRETCH), så det
    teoretiske arealet forblir ≈ π·r².

Alle beregninger gjøres i EPSG:25833 (UTM 33N, meter); eksport i EPSG:4326.
"""

from __future__ import annotations

import math
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.affinity import rotate, scale
from shapely.geometry import Point

# --- Tidsrom ---
SIM_HOURS = 96          # total simuleringstid (timer)
TIME_STEP_H = 1         # ett tidssteg per time -> time 0..96 (97 steg)

# --- Driftmodell ---
# Realistisk vinddrift er ~2–4 % av vindfarten. Her er den skrudd opp til 12,5 %
# (bevisst urealistisk) slik at flaket fra Heidrun akkurat når kysten i løpet av
# 96 t med vind fra Træna fyr – feltene ligger ellers for langt til havs (~180+ km).
# Sett tilbake til 0.03 for en fysisk realistisk drift.
DRIFT_FACTOR = 0.125

# Vindkilde: sett til et stasjonsnavn for å bruke én bestemt stasjon for ALLE
# utslipp, eller None for å bruke nærmeste stasjon per installasjon.
# Træna fyr ligger nær kysten med dominerende vind fra SV (225°), så flaket
# driver mot NØ (45°) – inn mot land, i stedet for rett nord langs kysten.
WIND_STATION = "Træna fyr"

# --- Spredningsmodell (meter) ---
R0 = 500.0              # startradius ved time 0
SPREAD_COEFF = 600.0    # radiusvekst: r(t) = R0 + SPREAD_COEFF*sqrt(t_timer)
STRETCH = 2.5           # forholdstall storakse/lilleakse (strekk langs drift)

# Utsnitt for Nordland (lon_min, lat_min, lon_max, lat_max) – brukes i steg 2
# (landklipping). Definert her slik at skriptene deler samme utsnitt.
BBOX = (6.5, 65.0, 15.0, 68.0)

# --- CRS ---
CRS_METRIC = 25833      # UTM 33N, meter – for all geometri-regning
CRS_WGS84 = 4326        # lagringsformat

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
PROCESSED_DIR = DATA_DIR / "processed"
SPILLS_DIR = PROCESSED_DIR / "spills"
LAND_PATH = PROCESSED_DIR / "land_nordland.geojson"


def slugify(name: str) -> str:
    """Enkel slug for filnavn: 'Aasta Hansteen' -> 'aasta_hansteen'."""
    return name.strip().lower().replace(" ", "_")


def spill_timeseries(
    origin: Point,
    drift_bearing: float,
    wind_speed: float,
    installation: str,
    land=None,
) -> gpd.GeoDataFrame:
    """Lager ett ellipse-polygon per time for ett utslipp (i EPSG:25833).

    origin:        installasjonens posisjon (EPSG:25833)
    drift_bearing: kompassretning flaket driver MOT (grader, 0 = nord, med klokka)
    wind_speed:    middelvind (m/s) fra nærmeste stasjon
    land:          sammenslått landgeometri (EPSG:25833) som flaket klippes mot,
                   eller None for ingen landklipping.
    """
    ox, oy = origin.x, origin.y
    bearing_rad = math.radians(drift_bearing)
    # Enhetsvektor i driftretningen (nord = +y, øst = +x).
    ux, uy = math.sin(bearing_rad), math.cos(bearing_rad)
    # Arealbevarende strekk: a = r*√STRETCH langs drift, b = r/√STRETCH på tvers.
    sqrt_stretch = math.sqrt(STRETCH)

    records = []
    for hour in range(0, SIM_HOURS + 1, TIME_STEP_H):
        # Driftstrekning etter `hour` timer (m): 3 % av vindfart * tid.
        dist = DRIFT_FACTOR * wind_speed * hour * 3600.0
        cx, cy = ox + ux * dist, oy + uy * dist

        # Radius vokser som √t; sirkel -> ellipse strukket langs drift.
        radius = R0 + SPREAD_COEFF * math.sqrt(hour)
        circle = Point(cx, cy).buffer(radius, quad_segs=48)
        ellipse = scale(circle, xfact=sqrt_stretch, yfact=1.0 / sqrt_stretch, origin=(cx, cy))
        # Ellipsens storakse ligger langs x (øst); roter så den peker i driftretningen.
        # Kompassretning (med klokka fra nord) -> matematisk vinkel (mot klokka fra øst).
        geom = rotate(ellipse, 90.0 - drift_bearing, origin=(cx, cy))

        # Klipp mot land slik at flaket stopper ved kysten.
        if land is not None:
            geom = geom.difference(land)

        records.append(
            {
                "installation": installation,
                "hour": hour,
                "area_km2": round(geom.area / 1e6, 2),
                "geometry": geom,
            }
        )

    return gpd.GeoDataFrame(records, geometry="geometry", crs=CRS_METRIC)


def main() -> None:
    SPILLS_DIR.mkdir(parents=True, exist_ok=True)

    installations = gpd.read_file(PROCESSED_DIR / "installations.geojson")
    stations = gpd.read_file(PROCESSED_DIR / "wind_stations.geojson")
    station_by_name = stations.set_index("name")

    # Last forenklet land for klipping (valgfritt – kjør prepare_land.py først).
    land = None
    if LAND_PATH.exists():
        land = gpd.read_file(LAND_PATH).to_crs(CRS_METRIC).geometry.union_all()
        print(f"Landklipping PÅ (kilde: {LAND_PATH.name})")
    else:
        print(f"Landklipping AV ({LAND_PATH.name} mangler – kjør prepare_land.py)")

    # Bare oljefeltene får simulert oljeutslipp.
    oil_fields = installations[installations["kind"] == "oil_field"].to_crs(CRS_METRIC)

    src = f"fast stasjon: {WIND_STATION}" if WIND_STATION else "nærmeste stasjon per felt"
    print(f"Simulerer {SIM_HOURS} t ({TIME_STEP_H} t/steg) for {len(oil_fields)} oljefelt ({src}):\n")

    for _, inst in oil_fields.iterrows():
        name = inst["name"]
        station_name = WIND_STATION if WIND_STATION else inst["nearest_station"]
        station = station_by_name.loc[station_name]
        wind_from = float(station["dominant_dir_deg"])
        wind_speed = float(station["mean_wind_speed"])
        drift_bearing = (wind_from + 180.0) % 360.0

        gdf = spill_timeseries(inst.geometry, drift_bearing, wind_speed, name, land=land)

        out_path = SPILLS_DIR / f"{slugify(name)}.geojson"
        gdf.to_crs(CRS_WGS84).to_file(out_path, driver="GeoJSON")

        last = gdf.iloc[-1]
        print(
            f"  {name:<10} vindkilde={station_name:<10} "
            f"vind-fra={wind_from:>5.1f}°  drift-mot={drift_bearing:>5.1f}°  "
            f"vind={wind_speed:.1f} m/s"
        )
        print(
            f"             time 0: {gdf.iloc[0]['area_km2']:>6.2f} km²   "
            f"time {SIM_HOURS}: {last['area_km2']:>7.2f} km²  -> {out_path.name}"
        )

    print(f"\nSkrev {len(oil_fields)} utslippsfiler til {SPILLS_DIR}")


if __name__ == "__main__":
    main()
