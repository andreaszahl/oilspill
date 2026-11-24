"""Prosesserer mock-vinddata til GeoJSON med GeoPandas.

Leser data/raw/wind_observations.csv og skriver
data/processed/wind_stations.geojson (EPSG:4326) med dominerende vindretning,
middelvind og andel per stasjon. Laget er bakgrunn i kartet.

Installasjonene behandles ikke her lenger. De hentes fra Sokkeldirektoratet av
scripts/fetch_facilities.py.
"""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"

CALM_THRESHOLD = 1.0  # m/s – observasjoner under dette regnes som stille og utelates
N_SECTORS = 16
SECTOR_WIDTH = 360.0 / N_SECTORS  # 22.5 grader

# Kompasslabel per sektor (0 = N, med klokka).
SECTOR_LABELS = [
    "N", "NNØ", "NØ", "ØNØ", "Ø", "ØSØ", "SØ", "SSØ",
    "S", "SSV", "SV", "VSV", "V", "VNV", "NV", "NNV",
]


def dominant_wind_per_station(obs: pd.DataFrame) -> pd.DataFrame:
    """Beregner dominerende sektor, middelvind og andel per stasjon."""
    active = obs[obs["wind_speed"] >= CALM_THRESHOLD].copy()
    active["sector"] = (np.round(active["wind_from_direction"] / SECTOR_WIDTH) % N_SECTORS).astype(int)

    rows = []
    for station_id, grp in active.groupby("station_id"):
        counts = grp["sector"].value_counts()
        dominant_sector = int(counts.idxmax())
        meta = grp.iloc[0]
        rows.append(
            {
                "station_id": station_id,
                "name": meta["name"],
                "lat": float(meta["lat"]),
                "lon": float(meta["lon"]),
                "dominant_sector": dominant_sector,
                "dominant_label": SECTOR_LABELS[dominant_sector],
                "dominant_dir_deg": round(dominant_sector * SECTOR_WIDTH, 1),
                "mean_wind_speed": round(float(grp["wind_speed"].mean()), 2),
                "dominant_share": round(float(counts.max() / len(grp)), 3),
                "n_obs": int(len(grp)),
            }
        )
    return pd.DataFrame(rows)


def main() -> None:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    obs = pd.read_csv(RAW_DIR / "wind_observations.csv")
    stations_df = dominant_wind_per_station(obs)
    stations = gpd.GeoDataFrame(
        stations_df,
        geometry=gpd.points_from_xy(stations_df["lon"], stations_df["lat"]),
        crs="EPSG:4326",
    )

    stations_out = PROCESSED_DIR / "wind_stations.geojson"
    stations.to_file(stations_out, driver="GeoJSON")
    print(f"Skrev {len(stations)} stasjoner -> {stations_out}")


if __name__ == "__main__":
    main()
