"""Henter ekte innretninger fra Sokkeldirektoratet (fase 2, steg 1).

Kilde: Sokkeldirektoratets DataService (FactMaps), lag 6000 «facility».
Lisens: Norsk lisens for offentlige data (NLOD 2.0).

Skriver:
  - data/raw/sodir_facilities.geojson       : alle innretninger i utsnittet (rådata)
  - data/processed/installations.geojson    : én produksjonsinnretning per felt (EPSG:4326)

GIS-merknad om datum:
  Sokkeldirektoratet lagrer posisjoner i ED50 (EPSG:4230), ikke WGS84. Her ute
  er forskjellen ~90 m (ca. 85 m vest og 25 m sør; målt for Norne, Heidrun og
  Aasta Hansteen). Vi ber tjenesten om outSR=4326, slik at serveren gjør
  datumtransformasjonen. Å tolke ED50-grader som WGS84 er en klassisk feil som
  gir slike forskyvninger uten noen feilmelding.

Utvalg:
  1. Utsnitt 64–68° N (Norskehavet utenfor Trøndelag/Nordland).
  2. Overflateinnretning (fclSurface = 'Y') og fase 'IN SERVICE'.
  3. Funksjon som inneholder PRODUCER eller PROCESSING. Lagerskip (FSU) og
     lastebøyer utelates, fordi de ikke produserer selv.
  4. Én innretning per felt. Har feltet flere, foretrekkes den som håndterer
     væske (STORAGE eller OIL PRODUCER); ved likhet velges laveste npdid.
     For Åsgard betyr det Åsgard A (FPSO med lager) fremfor Åsgard B (gass).
"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from pathlib import Path

import geopandas as gpd

ROOT = Path(__file__).resolve().parent.parent
RAW_PATH = ROOT / "data" / "raw" / "sodir_facilities.geojson"
OUT_PATH = ROOT / "data" / "processed" / "installations.geojson"

LAT_MIN, LAT_MAX = 64.0, 68.0
LON_MIN, LON_MAX = 0.0, 15.0

SERVICE_URL = (
    "https://factmaps.sodir.no/api/rest/services/DataService/Data/FeatureServer/6000/query"
)
QUERY = {
    "where": "1=1",
    "geometry": f"{LON_MIN},{LAT_MIN},{LON_MAX},{LAT_MAX}",
    "geometryType": "esriGeometryEnvelope",
    "inSR": "4326",
    "spatialRel": "esriSpatialRelIntersects",
    "outFields": "*",
    "outSR": "4326",  # serveren transformerer ED50 -> WGS84
    "f": "geojson",
}

# Ord som skrives med store bokstaver også etter tittel-formatering.
KEEP_UPPER = {"FPSO", "FSU", "TLP", "STL"}


def nice_name(sodir_name: str) -> str:
    """'NORNE FPSO' -> 'Norne FPSO', 'ÅSGARD A' -> 'Åsgard A'."""
    return " ".join(w if w in KEEP_UPPER else w.capitalize() for w in sodir_name.split())


def slugify(name: str) -> str:
    """ASCII-slug for filnavn/URL-er: 'Åsgard A' -> 'aasgard_a'."""
    s = name.strip().lower()
    for a, b in (("å", "aa"), ("æ", "ae"), ("ø", "o")):
        s = s.replace(a, b)
    return "_".join("".join(c if c.isalnum() else " " for c in s).split())


def download() -> dict:
    url = f"{SERVICE_URL}?{urllib.parse.urlencode(QUERY)}"
    print(f"Henter: {url}")
    with urllib.request.urlopen(url, timeout=120) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    RAW_PATH.parent.mkdir(parents=True, exist_ok=True)
    RAW_PATH.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    print(f"Skrev {len(data['features'])} innretninger (rådata) -> {RAW_PATH}")
    return data


def select(raw: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    fn = raw["fclFunctions"].fillna("")
    lat = raw.geometry.y
    mask = (
        (raw["fclSurface"] == "Y")
        & (raw["fclPhase"] == "IN SERVICE")
        & fn.str.contains("PRODUCER|PROCESSING")
        & lat.between(LAT_MIN, LAT_MAX)
    )
    cand = raw[mask].copy()
    cand["handles_liquid"] = cand["fclFunctions"].str.contains("STORAGE|OIL PRODUCER")
    cand = cand.sort_values(
        ["fclBelongsToName", "handles_liquid", "fclNpdidFacility"],
        ascending=[True, False, True],
    )
    return cand.drop_duplicates("fclBelongsToName", keep="first")


def main() -> None:
    data = download()
    raw = gpd.GeoDataFrame.from_features(data["features"], crs="EPSG:4326")
    sel = select(raw)

    out = gpd.GeoDataFrame(
        {
            "name": sel["fclName"].map(nice_name),
            "slug": sel["fclName"].map(nice_name).map(slugify),
            "field": sel["fclBelongsToName"].map(nice_name),
            "facility_kind": sel["fclKind"],
            "functions": sel["fclFunctions"],
            "operator": sel["fclCurrentOperatorName"],
            "water_depth_m": sel["fclWaterDepth"],
            "npdid": sel["fclNpdidFacility"],
            "factpage_url": sel["fclFactPageUrl"],
            "lon": sel.geometry.x.round(5),
            "lat": sel.geometry.y.round(5),
        },
        geometry=sel.geometry,
        crs="EPSG:4326",
    ).sort_values("lat")

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    out.to_file(OUT_PATH, driver="GeoJSON")
    print(f"Skrev {len(out)} innretninger -> {OUT_PATH}\n")
    cols = ["name", "field", "facility_kind", "operator", "water_depth_m", "lat", "lon"]
    print(out[cols].to_string(index=False))


if __name__ == "__main__":
    main()
