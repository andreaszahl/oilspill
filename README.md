# Oljedrift under ekstremværet «Ingunn»

> **Status:** under arbeid. Steg 1 (ekte innretninger) er ferdig, og notebooken (steg 2) er
> klar til test i Colab. Det nye webkartet (steg 3) kommer. Seksjoner merket *(kommer)* fylles
> ut underveis.

## 1. Hva prosjektet er

Emneoppgave i **Geografisk IT og KI (UiA)**. Prosjektet simulerer **hypotetiske**
oljeutslipp fra produksjonsinnretninger i Norskehavet (64–68° N) under ekstremværet
**«Ingunn»** (31. januar–1. februar 2024). Det bruker OpenDrift/OpenOil fra Meteorologisk
institutt med strøm- og vinddata fra samme periode.

**Dette er ikke et beredskapsverktøy.** Utslippene er tenkte, og resultatene skal ikke
brukes til operative beslutninger.

## 2. Lenker

- Webkart: <https://andreaszahl.github.io/oilspill/web/> *(GitHub Pages)*
- Notebook: [`notebooks/openoil_ingunn.ipynb`](notebooks/openoil_ingunn.ipynb)
  [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/andreaszahl/oilspill/blob/main/notebooks/openoil_ingunn.ipynb)

## 3. Arkitektur

```
Sokkeldirektoratet (FactMaps REST, NLOD)
        │  scripts/fetch_facilities.py
        ▼
data/processed/installations.geojson ──► (GitHub raw-URL)
        │                                     │
        │                     notebooks/openoil_ingunn.ipynb (Google Colab)
        │                     OpenOil + NorKyst800 (strøm) + MEPS (vind) + WW3 (bølger)
        │                                     │
        │                         spills/*.geojson + PNG (zip → commit)
        ▼                                     ▼
                 web/index.html (Leaflet, GitHub Pages)
```

```
config/oil_types.csv          kobling felt → oljetype (leses av notebooken)
scripts/fetch_facilities.py   henter innretninger fra Sokkeldirektoratet
scripts/make_mock_data.py     fiktive vindstasjoner (bakgrunnslag i kartet)
scripts/process.py            dominerende vindretning per mock-stasjon
data/raw/                     rådata (git-ignorert, regenereres)
data/processed/               GeoJSON som kartet og notebooken leser (sjekkes inn)
web/index.html                webkartet
```

### Kjøre lokalt

```bash
uv run python scripts/fetch_facilities.py  # innretninger fra Sokkeldirektoratet
uv run python scripts/make_mock_data.py    # mock-vind til bakgrunnslaget
uv run python scripts/process.py
uv run python -m http.server 8080          # fra roten
```

Åpne <http://localhost:8080/web/index.html>.

### Utvalg av innretninger

`fetch_facilities.py` henter lag 6000 (*facility*) fra Sokkeldirektoratets DataService:

```
https://factmaps.sodir.no/api/rest/services/DataService/Data/FeatureServer/6000/query
  ?where=1=1&geometry=0,64,15,68&geometryType=esriGeometryEnvelope&inSR=4326
  &spatialRel=esriSpatialRelIntersects&outFields=*&outSR=4326&f=geojson
```

Tjenesten lagrer koordinater i **ED50 (EPSG:4230)**. Med `outSR=4326` transformerer serveren
dem til WGS84. Her ute flytter det punktene ~90 m. Det er innenfor Sokkeldirektoratets
oppgitte posisjonsnøyaktighet (±0–300 m), men systematisk. Derfor transformerer vi i stedet
for å tolke ED50-grader som WGS84.

Utvalget består av overflateinnretninger i drift (`IN SERVICE`) som produserer eller
prosesserer, med én per felt. Lagerskip og lastebøyer er utelatt. Resultatet er 8 innretninger:
Njord A, Draugen, Kristin, Åsgard A, Heidrun, Skarv FPSO, Norne FPSO og Aasta Hansteen Spar.

## 4. Slik kjører du notebooken

Notebooken kjøres i Google Colab, ikke lokalt. Den leser `installations.geojson` og
`config/oil_types.csv` fra `main` på GitHub, så de må være pushet først.

1. **Åpne** notebooken med «Open in Colab»-merket over.
2. **Testmodus:** la `TESTMODUS = True` stå og velg *Runtime → Run all*. Da kjøres 6 timer med 200
   partikler for Norne FPSO og Aasta Hansteen Spar. Sjekk at oljenavnene valideres og at
   dekningssjekken går gjennom. Advarselen om at Aasta Hansteen ligger nær kanten av NorKyst er
   forventet.
3. **Full kjøring:** sett `TESTMODUS = False` og kjør alt på nytt. Det blir 72 timer og 2000
   partikler for alle 8 innretningene.
4. **Zip:** siste celle laster ned `ingunn_resultater.zip` med `spills/`, `plots/` og
   `oppsummering.csv`.
5. **Commit:** pakk `spills/` ut til `data/processed/spills/` og commit. Resultater fra testmodus
   (`_TEST`) skal ikke committes.

## 5. Modell og antakelser

| Valg | Verdi |
|---|---|
| Tidsrom | 2024-01-31 00:00 UTC + 72 t, lagret hver time |
| Utslipp | Kontinuerlig fra overflaten i 12 t, 500 m³/t (6 000 m³), hypotetisk |
| Partikler | 2000 per innretning |
| Strøm | NorKyst800 (met.no), 800 m, timesverdier. Strøm = 0 utenfor domenet |
| Vind | MEPS 2,5 km (MetCoOp/met.no), første 24 t av hver 00Z-kjøring |
| Bølger | WAVEWATCH III 4 km (met.no): Hs, periode og Stokes-drift, første 24 t av hver 00Z-kjøring |
| Vertikal blanding | Vindbasert profil (`windspeed_Large1994`). Nedblanding fra brytende bølger (Li mfl. 2017) styres av Hs |
| Horisontal diffusjon | 10 m²/s |
| Forvitring | OpenOil/NOAA: fordampning, emulsjon og dispergering |
| Land | GSHHG full oppløsning (roaring-landmask), partikler strander ved kysten |

**Valg avdekket i røyktesten.** Tre standardinnstillinger i OpenOil passet dårlig for en storm i åpent
hav og er endret:
1. **Bølger:** Uten bølgemodell anslås Hs fra vinden med 25 km fetch. Ved 20 m/s vind ga det
   2,2 m mot ~12 m for fullt utviklet sjø, og nesten ingen olje ble blandet ned. Nå kommer Hs og
   Stokes-drift fra WW3.
2. **Vertikal blanding:** NorKysts vertikale diffusivitet er 0 i overflatelaget. Blandingen beregnes
   derfor fra vinden.
3. **Datablokk:** `drift:max_speed = 3` m/s i stedet for 1,3. Under Ingunn drev olje raskere enn
   standardantakelsen, og da hentet OpenDrift for lite strømdata rundt partiklene.

For Norne etter 24 t endret dette massebalansen fra 37 % i overflaten og 35 % dispergert til
18 % i overflaten og 57 % dispergert.

**Flakpolygoner.** Partiklene i overflaten blir til ett polygon per time i EPSG:25833. Bare partikler
som fortsatt har minst 1 % av sin opprinnelige oljemasse, blir med. Ellers ville partikler som har
mistet nesten all oljen til fordampning og dispergering, tegnet store flak uten olje. Uten filteret
fikk Kristin 532 km² flak med 0,0 % olje i overflaten. Hver partikkel får en buffer på 1 km, bufferne slås sammen, og polygonet krympes med 500 m («closing»). Til slutt
klippes det mot GSHHG-land. Metoden bygger ikke bro over øyer og sund, og flekker som har skilt lag,
forblir egne polygoner. Arealet avhenger av bufferradien og er et mål på utbredelse, ikke på areal
dekket av olje.

Oljetyper per felt ligger i [config/oil_types.csv](config/oil_types.csv). Navnene er
skrevet nøyaktig slik de står i OpenDrifts oljeliste.

| Felt | Oljetype (OpenDrift) | SINTEF-ref. | Merknad |
|---|---|---|---|
| Norne | NORNE BLEND 2010 | SINTEF A16808 | |
| Heidrun | HEIDRUN EXPORT BLEND 2004 | STF80 A04009 | |
| Skarv | SKARV 2004 | STF66 A04027 | |
| Åsgard | AASGARD A 2003 | STF66 A03053 | |
| Kristin | KRISTIN 2006 | STF80MK A06221 | |
| Njord | NJORD 1997 | STF66 F97073 | Heter «NJORD 2002» på dokumentasjonssiden, men «NJORD 1997» i OpenDrift 1.14.x. Samme SINTEF-rapport. |
| Draugen | DRAUGEN 2008 | SINTEF A5637 | |
| Aasta Hansteen | SKARV KONDENSAT 2014 | SINTEF A26022 | **Stedfortreder.** Feltet har ingen egen olje i lista. Gass/kondensat-felt, så et kondensat er valgt. |

## 6. Data, programvare og tillatelser

| Kilde | Brukes til | Lisens | Kreditering |
|---|---|---|---|
| Sokkeldirektoratet, FactMaps DataService | Innretninger (posisjon, felt, operatør) | [NLOD 2.0](https://data.norge.no/nlod/no/2.0) (bekreftet på [sodir.no/apne-data](https://www.sodir.no/fakta/data-og-analyser/apne-data/)) | «Inneholder data under Norsk lisens for offentlige data (NLOD) tilgjengeliggjort av Sokkeldirektoratet» |
| OpenDrift/OpenOil (met.no) | Driftmodell. Installeres med pip i Colab og distribueres ikke i repoet | GPL-2.0 ([LICENSE](https://github.com/OpenDrift/opendrift/blob/master/LICENSE); kildefilene sier «version 2», ikke «or later») | Dagestad, K.-F., Röhrs, J., Breivik, Ø. & Ådlandsvik, B. (2018). OpenDrift v1.0: a generic framework for trajectory modelling. *Geoscientific Model Development*, 11, 1405–1420. <https://doi.org/10.5194/gmd-11-1405-2018> |
| NOAA OilLibrary / ADIOS Oil Database via OpenDrift | Oljeegenskaper (forvitring) | CC0 1.0 ([adios_db på PyPI](https://pypi.org/project/adios-db/)) | Ikke påkrevd. Vi oppgir NOAA og SINTEF-rapporten per oljetype (tabellen over) |
| NorKyst800 (met.no) | Havstrøm | CC BY 4.0 (står i filenes metadata) | «Based on data from MET Norway» |
| MEPS 2,5 km (MetCoOp, met.no) | Vind | NLOD og CC BY 4.0 ([met.no: Licensing and crediting](https://www.met.no/en/free-meteorological-data/Licensing-and-crediting)) | «Based on data from MET Norway» |
| WAVEWATCH III 4 km (met.no) | Bølgehøyde, periode og Stokes-drift | CC BY 4.0 (står i filenes metadata) | «Based on data from MET Norway» |
| GSHHG (via roaring-landmask i OpenDrift) | Landmaske og klipping av flak | LGPL ([GSHHG](https://www.soest.hawaii.edu/pwessel/gshhg/), fra versjon 2.2.2) | Wessel, P. & Smith, W. H. F. (1996). A Global Self-consistent, Hierarchical, High-resolution Shoreline Database. *J. Geophys. Res.*, 101, 8741–8743 |
| Kartverket | Bakgrunnskart | *(sjekkes i steg 3)* | *(kommer)* |

## 7. Lisens for egen kode

Forslag: **MIT** for all egen kode, også notebooken. MIT er forenlig med GPL-2.0. Repoet distribuerer
ikke OpenDrift; den installeres med pip i Colab. GPL-kravene gjelder den som distribuerer OpenDrift,
alene eller i en samlet pakke. Notebooken importerer bare biblioteket. *(Dette er ikke juridisk råd.)*
OpenDrift er en ekstern avhengighet under GPL-2.0. *(LICENSE-fil legges til når du har bestemt deg.)*

## 8. Begrensninger *(kommer)*

## 9. Bruk av KI

Koden og dokumentasjonen er laget i samarbeid med Claude Code (Anthropic). Alle modell- og
datavalg er gjennomgått og godkjent av forfatteren.
