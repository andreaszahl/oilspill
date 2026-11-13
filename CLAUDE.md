# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Prosjekt

`kartapp` er et geospatialt Python-prosjekt (uv + GeoPandas) som visualiserer
dominerende vindretning langs Nordlandskysten sammen med offshore-installasjoner i
et Leaflet-kart.

Prosjektet bygges i faser:
- **Fase 1 (ferdig):** mockdata → GeoPandas-pipeline → lokalt Leaflet-kart, uten API-kall.
- **Fase 2:** hente reelle data fra Frost (vind) og Sokkeldirektoratet (installasjoner).
- **Fase 3:** deploy via Cloudflare.

## Kommandoer

Alle kommandoer kjøres fra prosjektroten med `uv` (håndterer `.venv/` og `uv.lock`).

```bash
uv run python scripts/make_mock_data.py   # genererer data/raw/*.csv (fast seed)
uv run python scripts/process.py          # genererer data/processed/*.geojson
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

Pipelinen er tre adskilte steg som kommuniserer via filer på disk (`data/`):

1. **[scripts/make_mock_data.py](scripts/make_mock_data.py)** – eneste kilde til fiktive data.
   Stasjoner og installasjoner er definert som konstanter (`STATIONS`, `INSTALLATIONS`) øverst
   i fila. Hver stasjon har en `dominant_dir` (retning vinden kommer FRA); observasjoner
   genereres som den retningen + normalfordelt støy, med Weibull-fordelt vindstyrke. Fast
   seed (`SEED = 42`) gjør alt reproduserbart. Skriver `wind_observations.csv` og
   `installations.csv` til `data/raw/`.

2. **[scripts/process.py](scripts/process.py)** – all GeoPandas-logikk.
   - Dominerende vindretning: filtrer bort vind < 1 m/s, bin til 16 kompass-sektorer
     (22,5° hver, sektor 0 = nord), finn hyppigste sektor per stasjon, pluss middelvind
     og andel observasjoner i dominerende sektor.
   - Avstand installasjon → nærmeste stasjon beregnes i **EPSG:25833** (UTM 33N, meter)
     med `gpd.sjoin_nearest`.
   - Eksporterer alltid i **EPSG:4326** til `data/processed/*.geojson`.

3. **[web/index.html](web/index.html)** – statisk Leaflet-side (biblioteker via CDN, ingen
   byggesteg). Henter de to GeoJSON-filene med `fetch`. Vindpilene roteres til å peke
   **dit vinden blåser**: `(dominant_dir_deg + 180) % 360`, siden `dominant_dir_deg` er
   retningen vinden kommer fra.

### Konvensjoner å holde på
- CRS-kontrakt: beregn metriske avstander i EPSG:25833, men lagre/eksporter alltid i EPSG:4326.
- Vindretning i dataene er alltid "from"-retning; "to"-retning utledes kun ved visualisering.
- Innhold i `data/` er fullt regenererbart og git-ignorert – ikke sjekk det inn.

## Struktur

`src/`-layout bygget med `uv_build`-backend. Pakkekoden ligger i `src/kartapp/`;
konsoll-entrypoints deklareres under `[project.scripts]` i `pyproject.toml`
(`uv run kartapp` → `kartapp:main`). Pipeline-scriptene i `scripts/` kjøres frittstående
og er ikke del av `kartapp`-pakken.
