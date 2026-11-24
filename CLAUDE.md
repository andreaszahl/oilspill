# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Prosjekt

`kartapp` er et geospatialt Python-prosjekt (uv + GeoPandas) som visualiserer
dominerende vindretning langs Nordlandskysten sammen med offshore-installasjoner i
et Leaflet-kart.

Prosjektet er en emneoppgave (Geografisk IT og KI, UiA). Det simulerer hypotetiske
oljeutslipp under ekstremværet «Ingunn» (31.01–01.02.2024) med OpenDrift/OpenOil.
Arbeidet går i tre steg:
- **Steg 1 (ferdig):** ekte innretninger fra Sokkeldirektoratet (NLOD 2.0) erstatter mock.
- **Steg 2:** Colab-notebook `notebooks/openoil_ingunn.ipynb` (OpenOil + NorKyst800 + MEPS)
  → `spills/*.geojson` + PNG i zip, som brukeren committer.
- **Steg 3:** webkartet viser OpenOil-resultatene. `scripts/simulate_spill.py` og
  `scripts/prepare_land.py` (gammel forenklet driftmodell) slettes da.

Vindstasjonene er fortsatt mock og brukes kun som bakgrunnslag.
Publiseres via GitHub Pages fra repoet `andreaszahl/oilspill` (sti `/oilspill/`).

## Kommandoer

Alle kommandoer kjøres fra prosjektroten med `uv` (håndterer `.venv/` og `uv.lock`).

```bash
uv run python scripts/fetch_facilities.py # Sodir -> data/raw + data/processed/installations.geojson
uv run python scripts/make_mock_data.py   # mock-vind -> data/raw/wind_observations.csv (fast seed)
uv run python scripts/process.py          # -> data/processed/wind_stations.geojson
uv run python -m http.server 8080         # server fra ROTEN, ikke fra web/
```

Åpne kartet på **http://localhost:8080/web/index.html**. Lokal HTTP-server er påkrevd
fordi `fetch` av GeoJSON ikke fungerer over `file://`. Fordi serveren starter fra roten
løses `../data/processed/...` i HTML-en korrekt.

> Bruk port 8080, ikke 8000: på denne maskinen holdes port 8000 av uniFLOW SmartClient
> (`momsmartclnt.exe`) som kjører HTTPS der, noe som gir sertifikatfeil i nettleseren.
> Skriv `http://` eksplisitt (evt. `127.0.0.1` i stedet for `localhost`) hvis nettleseren
> prøver å tvinge HTTPS.

- Legg til avhengighet: `uv add <pakke>` (dev: `uv add --dev <pakke>`)
- Synk miljø fra lockfila: `uv sync`

Krever Python >= 3.13. Ingen test-/lint-/formatteringsverktøy er satt opp ennå.

## Arkitektur og dataflyt

Stegene kommuniserer via filer på disk (`data/`):

1. **[scripts/fetch_facilities.py](scripts/fetch_facilities.py)** – henter innretninger fra
   Sokkeldirektoratets DataService (lag 6000 *facility*, NLOD 2.0). Tjenesten lagrer i
   **ED50 (EPSG:4230)**; spør alltid med `outSR=4326` så serveren transformerer (~90 m skift).
   Filter: overflate, `IN SERVICE`, funksjon PRODUCER/PROCESSING, én per felt (foretrekker
   STORAGE/OIL PRODUCER). Rådata → `data/raw/sodir_facilities.geojson`; ryddet →
   `data/processed/installations.geojson` med `name, slug, field, facility_kind, functions,
   operator, water_depth_m, npdid, factpage_url`. `slug` er ASCII (å→aa, æ→ae, ø→o) og
   brukes som filnavn for utslippsdata.

2. **[config/oil_types.csv](config/oil_types.csv)** – kobling `field` → `oil_type` (navn
   nøyaktig som i OpenDrifts oljeliste). Matches mot `field` i installations. Oljenavn skal
   ikke hardkodes i notebooken.

3. **[scripts/make_mock_data.py](scripts/make_mock_data.py)** + **[scripts/process.py](scripts/process.py)**
   – fiktive vindstasjoner (fast seed 42) → dominerende retning per stasjon (16 sektorer,
   vind < 1 m/s utelates) → `data/processed/wind_stations.geojson`. Kun bakgrunnslag.

4. **[notebooks/openoil_ingunn.ipynb](notebooks/openoil_ingunn.ipynb)** – kjøres kun i Colab.
   Leser innretninger og oljetyper fra raw-URL på `main` (må være pushet). Strøm: NorKyst800
   (døgnfiler via `open_mfdataset`, `Uwind/Vwind` fjernes). Vind: MEPS 00Z-kjøringer, de første
   24 t av hver ("beste estimat"). Readerrekkefølge `[meps, norkyst]`. Validerer oljenavn og
   dekning før kjøring. Etterbehandling i EPSG:25833 (buffer 1 km + union + buffer −500 m, klippet
   mot GSHHG fra roaring-landmask). Skriver `spills/<slug>.geojson` (time-polygoner med `pct_*`)
   og `spills/<slug>_stranded.geojson` (punkter) i EPSG:4326, pluss PNG og zip.
   `TESTMODUS=True` gir 6 t, 200 partikler og 2 innretninger.

5. **[web/index.html](web/index.html)** – statisk Leaflet-side (CDN, ingen byggesteg). Henter
   GeoJSON med `fetch` og relative stier. Vindpilene peker **dit vinden blåser**:
   `(dominant_dir_deg + 180) % 360`.

### Konvensjoner å holde på
- CRS-kontrakt: beregn metriske avstander/areal i EPSG:25833, men lagre/eksporter alltid i EPSG:4326.
- Vindretning i dataene er alltid "from"-retning; "to"-retning utledes kun ved visualisering.
- `data/raw/` er git-ignorert og regenereres. `data/processed/` **sjekkes inn**: GitHub Pages
  serverer den, og Colab-notebooken leser `installations.geojson` via raw-URL på GitHub.
- Kilder: Sokkeldirektoratet (NLOD 2.0), met.no, Kartverket – hold README-tabellen oppdatert.

## Struktur

`src/`-layout bygget med `uv_build`-backend. Pakkekoden ligger i `src/kartapp/`;
konsoll-entrypoints deklareres under `[project.scripts]` i `pyproject.toml`
(`uv run kartapp` → `kartapp:main`). Pipeline-scriptene i `scripts/` kjøres frittstående
og er ikke del av `kartapp`-pakken.
