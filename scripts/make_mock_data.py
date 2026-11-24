"""Genererer fiktive vinddata for bakgrunnslaget i kartet.

Skriver data/raw/wind_observations.csv: timesobservasjoner for ett år for 9
fiktive målestasjoner langs Nordlandskysten.

Dataene er helt fiktive, men bruker fast seed slik at resultatet er reproduserbart.
Installasjonene er ekte og hentes av fetch_facilities.py (Sokkeldirektoratet).
Vinden i oljedriftsimuleringene kommer fra MEPS (met.no), ikke herfra.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

SEED = 42
YEAR = 2024
HOURS = 24 * 365  # 8760 timer (ikke-skuddår)

RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"

# Fiktive målestasjoner langs Nordlandskysten. dominant_dir er retningen vinden
# kommer FRA (grader, 0 = nord, med klokka), ulik per stasjon.
STATIONS = [
    {"station_id": "NL01", "name": "Træna fyr",        "lat": 66.50, "lon": 11.98, "dominant_dir": 225},  # SV
    {"station_id": "NL02", "name": "Myken",            "lat": 66.76, "lon": 12.49, "dominant_dir": 200},  # SSV
    {"station_id": "NL03", "name": "Bodø havn",        "lat": 67.28, "lon": 14.38, "dominant_dir": 180},  # S
    {"station_id": "NL04", "name": "Røst",             "lat": 67.52, "lon": 12.10, "dominant_dir": 250},  # VSV
    {"station_id": "NL05", "name": "Sandnessjøen",     "lat": 66.02, "lon": 12.63, "dominant_dir": 160},  # SSØ
    {"station_id": "NL06", "name": "Brønnøysund",      "lat": 65.47, "lon": 12.21, "dominant_dir": 210},  # SV
    {"station_id": "NL07", "name": "Vega",             "lat": 65.67, "lon": 11.90, "dominant_dir": 190},  # S
    {"station_id": "NL08", "name": "Lovund",           "lat": 66.36, "lon": 12.37, "dominant_dir": 235},  # SV
    {"station_id": "NL09", "name": "Værøy",            "lat": 67.66, "lon": 12.69, "dominant_dir": 270},  # V
]


def make_observations(rng: np.random.Generator) -> pd.DataFrame:
    timestamps = pd.date_range(f"{YEAR}-01-01", periods=HOURS, freq="h")
    frames = []
    for st in STATIONS:
        # Retning: dominerende retning + normalfordelt støy, pakket til [0, 360).
        direction = (st["dominant_dir"] + rng.normal(0.0, 40.0, HOURS)) % 360.0
        # Vindstyrke: Weibull-fordelt (realistisk for vind), middel ~7 m/s.
        speed = rng.weibull(2.0, HOURS) * 7.9  # scale valgt slik at middel ~7 m/s
        frames.append(
            pd.DataFrame(
                {
                    "station_id": st["station_id"],
                    "name": st["name"],
                    "lat": st["lat"],
                    "lon": st["lon"],
                    "timestamp": timestamps,
                    "wind_from_direction": direction.round(1),
                    "wind_speed": speed.round(2),
                }
            )
        )
    return pd.concat(frames, ignore_index=True)


def main() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(SEED)

    obs = make_observations(rng)
    obs_path = RAW_DIR / "wind_observations.csv"
    obs.to_csv(obs_path, index=False)

    print(f"Skrev {len(obs):,} observasjoner for {obs['station_id'].nunique()} stasjoner -> {obs_path}")


if __name__ == "__main__":
    main()
