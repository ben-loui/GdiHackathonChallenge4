# Zed-REPL-Version von exercise_gdi_urban_comfort_de_student.ipynb
# Zellen sind durch `# %%` getrennt. Ausführen: ctrl-shift-enter (Zelle ausführen) / shift-enter (ausführen & weiter).
# Voraussetzung: Kernel mit ipykernel (z. B. `Python (hack4gdi .venv)`) und die Ordner surveys/, scripts/, images/
# im Arbeitsverzeichnis des REPL (Projektordner, den Zed geöffnet hat).


# %% [markdown]
# # 🌍 Übung Geodateninfrastrukturen (GDI-DE): Urban Comfort & Amtliche OGC-Geodienste
#
# ---
#
# ## 🎯 Ziele & Zeitplan
# In dieser Übung verknüpfen wir **empirische Umfragedaten und 360°-Straßenbildanalysen zum Thema Urban Comfort** in Mainz ([www.pace-routing.com](https://www.pace-routing.com)) mit **amtlichen Geodateninfrastruktur-Diensten (GDI-DE / GDI-RP)** über standardisierte **OGC-Webdienste**:
#
# | Abschnitt | Dauer | Inhalt & OGC / GDI-DE Standards | Projektdaten & Werkzeuge |
# |---|---|---|---|
# | **0. Setup** | ~10 Min. | JSON-**Umfragedaten** aufbereiten & mit **360°-Bildindizes** verknüpfen | `surveys/responses/`, `surveys/questions/`, **Python** (`pandas`) |
# | **1. Aufbereitung** | ~25 Min. | **`scripts/mainz_image_coordinates.gpkg`** (`EPSG:25832`) + **GDI-RP API** + **BKG WFS 2.0** (`vg250_gem`) | 107 Kamerastandorte, **Python** oder **QGIS (`.gpkg` + WFS)** |
# | **2. Korrelation** | ~25 Min. | **LVermGeo RLP `VBORIS 2026` WMS**: Amtliche **Bodenrichtwerte (€/m²)** & **Nutzungsarten (`W`, `MI`, `GB`, `MK`, `FH`)** | `visual_comfort_survey-435.json`, SemSeg (`GVI`, `DoGS`, `SVF`) |
# | **3. Synthese** | ~20 Min. | Teilnehmer-Gewichte aus **Parameter-Ranking** -> Stadtteil-Analyse & GeoJSON-Export für **QGIS** | `city_comfort_ranking-110.json`, `general_feedback_survey-290.json`, `thermal_comfort_survey-90.json` |
# | **4. Analyse** | Bonus | **LVermGeo `DOP20` Orthophoto WMS** & **Umgebungslärm $L_{\text{den}}$ WMS** vs. 360°-Straßenpanorama | `images/*.jpeg` vs. GDI-RP `GetMap` / **QGIS WMS** |
#
# <br>
#
# > 💡 **Freie Werkzeugwahl (Google Colab / VS Code / Python / QGIS / ArcGIS):**
# > Sie können alle Analysen und Karten **direkt hier im Jupyter Notebook** erstellen **oder** das bereitgestellte GeoPackage (`scripts/mainz_image_coordinates.gpkg`) bzw. die exportierten Geodaten (`mainz_urban_comfort_results.geojson`) in **QGIS** zusammen mit den amtlichen OGC-WFS- und OGC-WMS-Diensten der GDI-DE / GDI-RP visualisieren und verschneiden. In jeder Aufgabe finden Sie sowohl die Python-Anleitung als auch die passenden Dienste für QGIS.
# >
# > 📚 **Dokumentation der wichtigsten verwendeten Python-Pakete:**
# > - **pandas**: [https://pandas.pydata.org/docs/](https://pandas.pydata.org/docs/)
# > - **matplotlib**: [https://matplotlib.org/stable/users/index.html](https://matplotlib.org/stable/users/index.html)

# %% [markdown]
# ---
# ## 🔧 0. Setup & Datenimport (~10 Min.)
#
# Führen Sie die anschließende Zelle aus, um die benötigten Python-Bibliotheken zu laden und die Projektstruktur zu prüfen:
#
# | Verzeichnis | Inhalt / Dateien | Beschreibung |
# | :--- | :--- | :--- |
# | **`surveys/responses/`** | 5 JSON-Dateien (`visual_comfort_*`, `pairwise_*`, etc.) | Rohdaten der durchgeführten Umfragen |
# | **`surveys/questions/`** | Fragenkataloge, `visual_comfort_image_analysis.json` | Zugehörige Fragen und 360°-Bildanalysen (Übersicht in `surveys/surveys_overview.pdf`) |
# | **`scripts/`** | `mainz_image_coordinates.gpkg`, `mainz_gdi_locations.*` | GeoPackage (`EPSG:25832`) & GDI-RP-Referenzattribute |
# | **`images/`** | 107 Bilddateien | Sphärische 360°-Panoramabilder (Mainz) |

# %%
# Einmalig im Terminal ausführen (statt %pip): pip install requests numpy pandas matplotlib seaborn pillow

# %%
import json
import re
import html
import sqlite3
import struct
from io import BytesIO
from pathlib import Path

import requests
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from PIL import Image

plt.rcParams["figure.figsize"] = (10, 5)
sns.set_theme(style="whitegrid")

# Automatische Pfaderkennung (lokal oder Google Colab)
BASE_DIR = Path(".")
if not (BASE_DIR / "surveys" / "responses").exists():
    for candidate in [Path("/content/uebung-gdi-urban-comfort"), Path("/content/Geodateninfrastrukturen")]:
        if (candidate / "surveys" / "responses").exists():
            BASE_DIR = candidate
            break

DATA_DIR = BASE_DIR / "surveys" / "responses"
QUESTIONS_DIR = BASE_DIR / "surveys" / "questions"
SCRIPTS_DIR = BASE_DIR / "scripts"
IMAGES_DIR = BASE_DIR / "images"
IMAGE_FILES_DIR = IMAGES_DIR / "files"

indent = lambda items: "\n    • " + "\n    • ".join(items) if items else " (keine)"

print(f"📊 Umfragen in surveys/responses/:{indent(sorted(p.name for p in DATA_DIR.glob('*.json')))}")
print(f"\n❓ Fragenkataloge in surveys/questions/:{indent(sorted(p.name for p in QUESTIONS_DIR.glob('*.*')))}")
print(f"\n🗺️  Geodaten in scripts/:{indent(sorted(p.name for p in SCRIPTS_DIR.glob('*.*') if p.suffix in {'.gpkg', '.csv', '.geojson'}))}")
print(f"\n📈 Bildindikatoren in images/:{indent(sorted(p.name for p in IMAGES_DIR.glob('*.csv')))}")

img_count = len(list(IMAGE_FILES_DIR.glob("*.jpeg"))) if IMAGE_FILES_DIR.exists() else 0
print(f"\n📷 360°-Panoramabilder in images/files/: {img_count} Bilder gefunden.")

# %% [markdown]
# ---
# ### 📝 Aufgabe 0.1: Einlesen der Visual Comfort Survey & 360°-Bildindizes
# In `surveys/questions/visual_comfort_image_analysis.json` liegen für alle 107 Mainzer 360°-Szenen (`"images"`) objektive und modellbasierte Indikatoren vor:
# - **Semantische Segmentierung (`Mask2Former`in flächentreuer `CEA`-Projektion & `AEQD`-Fisheye)**:
#   - `GVI` (*Green View Index*): Anteil sichtbarer Vegetation
#   - `SVF` (*Sky View Factor*): Anteil sichtbaren Himmels in der oberen Hemisphäre
#   - `BVI` (*Building View Index*): Anteil von Gebäudefassaden
#   - `VEY` (*Visual Entropy*): Shannon-Entropie der semantischen Klassenverteilung (Szenenvielfalt)
#   - `DoGS` (*Degree of Grey Surfaces*): Anteil grauer, versiegelter und bebauter Oberflächen
#   - `BFC` (*Building Facade Complexity*): Kantendichte (Canny) innerhalb der Gebäudefassaden
# - **Vision-Language-Model-Bewertungen (`CLIP`)**:
#   - `vlm_v0`..`vlm_v3` und `vlm_f0`..`vlm_f2` auf denselben Likert-Skalen (1-7) wie die menschliche Befragung.
#
# ### 📝 Ihre Aufgabe:
# 1. Laden Sie die 360°-Bildanalyse aus `surveys/questions/visual_comfort_image_analysis.json` in ein pandas-DataFrame `img_analysis_df` sowie die Umfragedatei `surveys/responses/visual_comfort_survey-435.json` (435 Teilnehmende x 10 zufällig ausgewählte Szenen) und überführen Sie alle Einzelbild-Bewertungen (`response_data["items"]`) in ein DataFrame `vc_items_df`.
# 2. Berechnen Sie pro Szene (`imageName`) die Mittelwerte der Antworten (`v-0`..`v-3`, `f-0`..`f-2`) und verknüpfen (`pd.merge`) Sie diese über `imageName` mit `img_analysis_df` zum DataFrame `scene_df`.

# %%
# 1. Laden der Bildanalyse-Tabelle (107 Szenen aus JSON)
with open(QUESTIONS_DIR / "visual_comfort_image_analysis.json", encoding="utf-8") as f:
    img_analysis_df = pd.DataFrame(json.load(f)["images"])

# 2. Laden der Visual-Comfort-Umfrage (435 Teilnehmende, 7-stufige Likert-Skala 1-7)
with open(DATA_DIR / "visual_comfort_survey-435.json", encoding="utf-8") as f:
    vc_survey_raw = json.load(f)

# TODO 0.1: Extrahieren Sie alle Einzelbewertungen aus `vc_survey_raw` in die Liste `records`.
# Jedes Element `item` in `rec["response_data"]["items"]` besitzt `"imageName"` und `"ratings"` (Dict mit v-0..v-3, f-0..f-2).
records = []
for rec in vc_survey_raw:
    resp = rec.get("response_data", {})
    for item in resp.get("items", []):
        r = item["ratings"]
        # TODO: Fügen Sie ein Dict mit imageName, ageGroup, gender, familiarityScore sowie v-0..v-3 und f-0..f-2 zu `records` hinzu
        pass

vc_items_df = pd.DataFrame(records)
print(f"Anzahl extrahierter Bildbewertungen: {len(vc_items_df)}")

# TODO 0.2: Gruppieren Sie `vc_items_df` nach `"imageName"` (Mittelwert der 7 Fragen)
# und verknüpfen Sie das Ergebnis per `pd.merge(..., on="imageName")` mit `img_analysis_df` zu `scene_df`.
rating_cols = ["v-0", "v-1", "v-2", "v-3", "f-0", "f-1", "f-2"]
# scene_means = ...
# scene_df = ...

# %% [markdown]
# ---
# ## 🗺️ Aufgabe 1: Aufbereitung von GeoPackage (`mainz_image_coordinates.gpkg`), GDI-RP & BKG WFS 2.0 (~25 Min.)
#
# ### Hintergrund: Deterministische Standortzuordnung & OGC Web Feature Service (WFS 2.0)
# Alle 107 Aufnahmestandorte der 360°-Panoramabilder sind in `scripts/mainz_image_coordinates.gpkg` (Layer `places_of_interest`) im amtlichen Koordinatenreferenzsystem `EPSG:25832` (ETRS89 / UTM Zone 32N) gespeichert. Da jedes GeoPackage eine SQLite-Datenbank mit standardisiertem OGC-WKB-Geometrie-Header ist, können wir die exakten Punktkoordinaten (`easting_25832`, `northing_25832`) und den eindeutigen Schlüssel `imageName` deterministisch auslesen und 1:1 mit `scene_df` verknüpfen.
#
# Zusätzlich nutzen wir zwei Live-Dienste der **GDI-DE / GDI-RP**:
# > 1. **Geoportal RLP**:
# >    - **Endpoint**: `https://www.geoportal.rlp.de/mapbender/geoportal/gaz_geom_mobile.php?resultTarget=web&outputFormat=json&searchText=Mainz+<Suchbegriff>`
# >    - Liefert amtliche Straßengeometrien, Postleitzahl (`PLZ`) und den Mainzer **Stadtteil (`Ortsteil`)**.
# > 2. **BKG GDI-DE Web Feature Service (WFS 2.0 - Verwaltungsgebiete 1:250.000 `vg250`)**:
# >    - **Endpoint**: `https://sgx.geodatenzentrum.de/wfs_vg250`
# >    - **Operation**: `SERVICE=WFS&VERSION=2.0.0&REQUEST=GetFeature&TYPENAMES=vg250:vg250_gem&CQL_FILTER=gen='Mainz'&OUTPUTFORMAT=application/json&SRSNAME=EPSG:4326`
#
# ### 📝 Ihre Aufgabe:
#
# | 🐍 In Python (Jupyter / Colab) | 🗺️ Alternative in QGIS |
# | :--- | :--- |
# | **1.** Lesen Sie die 107 Kamerastandorte (`fid`, `Name`, `imageName`, `easting_25832`, `northing_25832`) direkt aus `scripts/mainz_image_coordinates.gpkg` aus und verknüpfen Sie diese deterministisch über `imageName` mit `scene_df` sowie `scripts/mainz_gdi_locations.csv`.<br><br>**2.** Laden Sie die Stadt- und Ortsbezirksgrenzen (`scripts/mainz_boundaries.geojson` bzw. über den **BKG WFS 2.0**) und erstellen Sie eine **Kartenübersicht**. | **1.** Ziehen Sie `scripts/mainz_image_coordinates.gpkg` (`EPSG:25832`), `scripts/mainz_boundaries.geojson` (`EPSG:4326`) oder `scripts/mainz_gdi_locations.geojson` (`EPSG:4326`) direkt in **QGIS**.<br><br>**2.** Binden Sie den **BKG WFS 2.0** über *Layer → Layer hinzufügen → WFS / OGC API-Features-Layer hinzufügen* mit der URL `https://sgx.geodatenzentrum.de/wfs_vg250` (Layer `vg250:vg250_gem`) ein. |

# %%
def read_poi_geopackage(gpkg_path: Path) -> pd.DataFrame:
    """Liest alle 107 Kamerastandorte (EPSG:25832) deterministisch aus scripts/mainz_image_coordinates.gpkg."""
    conn = sqlite3.connect(gpkg_path)
    rows = conn.execute("SELECT fid, geom, Name, imageName FROM places_of_interest").fetchall()
    conn.close()
    records = []
    for fid, blob, name, img_name in rows:
        # GeoPackage Binary Header (8 Bytes + optionale Envelope) -> Standard WKB Point (<BIdd)
        flags = blob[3]
        env_ind = (flags >> 1) & 0x07
        env_bytes = {0: 0, 1: 32, 2: 48, 3: 48, 4: 64}[env_ind]
        wkb = blob[8 + env_bytes :]
        endian = "<" if wkb[0] == 1 else ">"
        _, easting, northing = struct.unpack(endian + "Idd", wkb[1:21])
        records.append({
            "poi_fid": fid,
            "poi_name": name,
            "imageName": img_name,
            "easting_25832": round(easting, 2),
            "northing_25832": round(northing, 2),
        })
    return pd.DataFrame(records)

poi_df = read_poi_geopackage(SCRIPTS_DIR / "mainz_image_coordinates.gpkg")
print(f"Aus mainz_image_coordinates.gpkg geladene Standorte (EPSG:25832): {len(poi_df)}")
display(poi_df.head())

# Deterministische 1:1-Verknüpfung mit scene_df und den GDI-RP-Referenzattributen (PLZ, Stadtteil, WGS84, VBORIS)
gdi_attrs = pd.read_csv(SCRIPTS_DIR / "mainz_gdi_locations.csv")[
    ["imageName", "lon_4326", "lat_4326", "plz", "district", "bodenrichtwert_eur_m2", "nutzungsart"]
]
gdi_df = scene_df.merge(poi_df, on="imageName").merge(gdi_attrs, on="imageName")
print(f"Deterministisch verknüpfte Szenen: {len(gdi_df)} / {len(scene_df)}")

# Laden der Stadt- und Ortsbezirkspolygone (Mainz, Altstadt, Gonsenheim)
with open(SCRIPTS_DIR / "mainz_boundaries.geojson", encoding="utf-8") as f:
    bounds_geojson = json.load(f)
poly_by_name = {
    feat["properties"]["name"]: np.array(feat["geometry"]["coordinates"][0])
    for feat in bounds_geojson["features"]
}
mainz_ring = poly_by_name["Mainz"]
altstadt_ring = poly_by_name["Altstadt"]
gonsenheim_ring = poly_by_name["Gonsenheim"]

# TODO 1.1: Erstellen Sie eine 2x2-Subplot-Figur (`fig, axes = plt.subplots(2, 2, figsize=(13, 11.5))`):
# - axes[0, 0] (1.1): Stadtgrenze Mainz (`mainz_ring`) + `altstadt_ring` in Rot
# - axes[0, 1] (1.2): Stadtgrenze Mainz (`mainz_ring`) + `gonsenheim_ring` in Rot
# - axes[1, 0] (2.1): Detailansicht `altstadt_ring` + Standorte in `Altstadt` farbcodiert nach `GVI`
# - axes[1, 1] (2.2): Detailansicht `gonsenheim_ring` + Standorte in `Gonsenheim` farbcodiert nach `GVI`

# %% [markdown]
# ---
# ## 💶 Aufgabe 2: Korrelation von WMS 1.3.0 `GetFeatureInfo` (`VBORIS RLP 2026`) & Indikatoren (`GVI, SVF, BVI, ...`) (~25 Min.)
#
# ### Hintergrund: Sachdatenabfrage über OGC WMS `GetFeatureInfo`
# Während `GetMap` ein gerendertes Kartenbild liefert, erlaubt die OGC-Operation **`GetFeatureInfo`** die Abfrage der hinterlegten Sachattribute für ein Pixel `(I, J)` innerhalb eines angeforderten Kartenausschnitts (`BBOX`, `CRS=EPSG:25832`, `WIDTH=101`, `HEIGHT=101`). Der amtliche Dienst **VBORIS RLP Basisdienst 2026** liefert über OGC WMS `GetFeatureInfo` stichtagsbezogene Sachdaten (01.01.2026):
#
# > 🌐 **Dienst-URL:** `https://geo5.service24.rlp.de/wms/RLP_VBORISFREE2026.fcgi`
# > ⚙️ **Parameter:** `LAYERS=RLP_1,RLP_0` | `QUERY_LAYERS=RLP_1,RLP_0` | `INFO_FORMAT=text/html`
#
# * 💶 **`Bodenrichtwert`**: Amtlicher Wert in **€/m²** (Stichtag 01.01.2026)
# * 🏷️ **`Nutzungsart`**: Bau- und planungsrechtliche Entwicklungsstufe (nach BauNVO / ImmoWertV):
#
# | Kürzel | Nutzungsart | Mainzer Referenzbeispiele |
# | :---: | :--- | :--- |
# | **`W`** | Wohnbaufläche | Reine und allgemeine Wohnquartiere |
# | **`MI`** | Mischgebiet | Gemischte Wohn- und Gewerbenutzung |
# | **`MK`** | Kerngebiet | Zentrale Innenstadtlagen (Handel, Dienstleistungen) |
# | **`GB`** | Gemeinbedarfsfläche | Bildung & Öffentlichkeit (z. B. Campus JGU / Hochschule Mainz) |
# | **`FH`** | Friedhofsfläche | Grün- und Ruhezonen (z. B. Hauptfriedhof) |
#
# ### 📝 Ihre Aufgabe:
#
# | 🐍 In Python (Jupyter / Colab) | 🗺️ Alternative in QGIS |
# | :--- | :--- |
# | **1.** Vervollständigen Sie `query_vboris_feature_info(easting, northing)` für die exakte Koordinate des Schillerplatzes aus `mainz_image_coordinates.gpkg`.<br><br>**2.** Gruppieren Sie `gdi_df` nach der amtlichen **`nutzungsart`** (`W`, `MI`, `MK`, `GB`, `FH`) und vergleichen Sie den mittleren **Bodenrichtwert (`bodenrichtwert_eur_m2`)**, den **Versiegelungsgrad (`DoGS`)**, den **Green View Index (`GVI`)** sowie die subjektive **Aufenthaltsqualität (`f-2`)** und **Bedrückung (`f-1`)**. | **1.** Binden Sie den WMS `https://geo5.service24.rlp.de/wms/RLP_VBORISFREE2026.fcgi` in QGIS unter *Layer → WMS/WMTS-Layer hinzufügen* ein.<br><br>**2.** Nutzen Sie das Werkzeug *Objekte abfragen (`i`)* direkt auf den Punkten aus `scripts/mainz_image_coordinates.gpkg`, um Bodenrichtwert und Nutzungsart interaktiv zu inspizieren. |
#
# 🔍 **Forschungsfrage**: Sind teure Innenstadtlagen (`MK`/`MI` mit hohen Bodenrichtwerten) automatisch die Orte mit dem höchsten visuellen Komfort (`f-2`), oder schneiden Wohn- (`W`), Gemeinbedarfs- (`GB`) und Grün-/Friedhofsareale (`FH`) trotz niedrigerer Bodenrichtwerte besser ab?

# %%
def query_vboris_feature_info(easting: float, northing: float) -> dict:
    """Fragt Bodenrichtwert (€/m²) & Nutzungsart per OGC WMS 1.3.0 GetFeatureInfo ab."""
    wms_url = "https://geo5.service24.rlp.de/wms/RLP_VBORISFREE2026.fcgi"
    params = {
        "SERVICE": "WMS",
        "VERSION": "1.3.0",
        "REQUEST": "GetFeatureInfo",
        "LAYERS": "RLP_1,RLP_0",
        "QUERY_LAYERS": "RLP_1,RLP_0",
        "STYLES": "",
        "FORMAT": "image/png",
        "CRS": "EPSG:25832",
        "BBOX": f"{easting - 50:.1f},{northing - 50:.1f},{easting + 50:.1f},{northing + 50:.1f}",
        "WIDTH": "101",
        "HEIGHT": "101",
        "I": "50",
        "J": "50",
        "INFO_FORMAT": "text/html",
    }
    txt = html.unescape(requests.get(wms_url, params=params, timeout=10).text)
    m_brw = re.search(r"Bodenrichtwert\s*</td>\s*<td>\s*([0-9.,]+)", txt)
    m_nutz = re.search(r"Nutzungsart\s*</td>\s*<td>\s*([A-Za-z]+)", txt)
    return {
        "bodenrichtwert_eur_m2": float(m_brw.group(1).replace(".", "").replace(",", ".")) if m_brw else None,
        "nutzungsart": m_nutz.group(1).strip() if m_nutz else "G/Grün",
    }

# Live-Test für den Schillerplatz (exakte Koordinate aus mainz_image_coordinates.gpkg)
schiller_row = gdi_df[gdi_df["imageName"] == "schillerplatz"].iloc[0]
print("VBORIS am Schillerplatz:", query_vboris_feature_info(schiller_row["easting_25832"], schiller_row["northing_25832"]))

# TODO 2.1: Gruppieren Sie `gdi_df` nach `"nutzungsart"` und berechnen Sie Mittelwert & Anzahl
# für ["bodenrichtwert_eur_m2", "GVI", "SVF", "DoGS", "BFC", "v-0", "v-2", "f-0", "f-1", "f-2"].
# nutz_summary = ...

# TODO 2.2: Erstellen Sie einen sortierten Boxplot + Stripplot für `f-2` (Aufenthaltsqualität) nach `nutzungsart`
# sowie einen Korrelations-Scatterplot (`bodenrichtwert_eur_m2` auf Log-Skala vs. `DoGS`) inklusive diagonaler Regressionsgerade.

# %% [markdown]
# ---
# ## 📊 Aufgabe 3: Multi-Survey-Synthese & QGIS-Export (~20 Min.)
#
# Neben der **Visual Comfort Survey** stehen im Ordner `surveys/` vier weitere Befragungen für die Synthese bereit:
#
# | Umfragedaten (`responses/`) | Fragenkatalog (`questions/`) | Stichprobe ($N$) | Erhobene Merkmale & Zielsetzung |
# | :--- | :--- | :---: | :--- |
# | **`city_comfort_ranking-110.json`** | `city_comfort_ranking.json` | 110 | Priorisierung von 20 Umweltfaktoren für den urbanen Komfort (Rang 1 bis 20) |
# | **`pairwise_comparison-255.json`** | `pairwise_comparison.json` | 255 | Paarweise A/B-Vergleiche zwischen 7 Kernparametern (AHP-Gewichtung) |
# | **`general_feedback_survey-290.json`** | `general_feedback_survey.json` | 290 | 10 Thesen zu Grünflächen, Lärm, Sicherheit und Lebensqualität (`postalCode`) |
# | **`thermal_comfort_survey-90.json`** | `thermal_comfort_survey.json` | 90 | Subjektiver thermischer Komfort und Hitzestress im Stadtgebiet (`postalCode`) |
#
# ### 📝 Ihre Aufgabe:
#
# 1. **Borda-Gewichte aus Teilnehmer-Ranking ableiten**:
#    Berechnen Sie aus `surveys/responses/city_comfort_ranking-110.json` für alle $M = 20$ Umweltfaktoren:
#    * Den **mittleren Rang** $\overline{R}_k$ über alle $N = 110$ Teilnehmenden ($R_{i,k} \in \{1, \dots, 20\}$):
#      $$\overline{R}_k = \frac{1}{N} \sum_{i=1}^{N} R_{i,k}$$
#    * Das absolute **Borda-Gewicht** $w_k$ (Rang 1 erhält $M=20$ Punkte, Rang 20 erhält 1 Punkt):
#      $$w_k = (M + 1) - \overline{R}_k = 21 - \overline{R}_k$$
#    * Die **normalisierten Gewichte** $W_k$ bezogen auf die Teilmenge $\mathcal{V}$ der 4 visuellen Segmentierungsfaktoren (`Greenery`, `Sky Openness`, `Degree of Greyness`, `Building Facade Complexity`):
#      $$W_k = \frac{w_k}{\sum_{j \in \mathcal{V}} w_j} \quad \text{mit} \quad \sum_{k \in \mathcal{V}} W_k = 1$$
#
# 2. **Urban Comfort Index (`UCI_citizen`) berechnen**:
#    Min-Max-normalisieren Sie die 4 Segmentierungsindizes auf $[0, 1]$ und berechnen Sie für alle 107 Standorte in `gdi_df` den teilnehmergewichteten Gesamtindex:
#    $$\text{UCI}_{\text{citizen}} = W_{\text{Green}} \cdot \text{GVI}^* + W_{\text{Sky}} \cdot \text{SVF}^* + W_{\text{Grey}} \cdot (1 - \text{DoGS}^*) + W_{\text{BFC}} \cdot \text{BFC}^*$$
#    *(Hinweis: Bei $\text{DoGS}$ kehrt $1 - \text{DoGS}^*$ die Polarität um, da ein hoher Versiegelungsgrad den visuellen Komfort mindert).*
#
# 3. **Multi-Survey-Synthese & QGIS-Export**:
#    Aggregieren Sie `gdi_df` nach **Mainzer Stadtteil** (`district`), verschneiden Sie das Ergebnis über die **Postleitzahl** (`plz`) mit der **General Feedback Survey** und der **Thermal Comfort Survey**, und exportieren Sie die angereicherten Punktdaten als **`mainz_urban_comfort_results.geojson`** für **QGIS**.

# %%
# 1. Laden des Parameter-Rankings (110 Teilnehmende) & der Faktor-Namen
with open(QUESTIONS_DIR / "city_comfort_ranking.json", encoding="utf-8") as f:
    rk_questions = json.load(f)
with open(DATA_DIR / "city_comfort_ranking-110.json", encoding="utf-8") as f:
    rk_raw = json.load(f)

feature_names = {feat["id"]: feat["name"] for feat in rk_questions["features_to_rank"]}

# TODO 3.1: Berechnen Sie aus `rk_raw` (Feld `rec["response_data"]["ranking"]`, Liste mit `"id"` und `"rank"`)
# den mittleren Rang und den Borda-Score `21 - rank` pro Faktor.
rk_rows = []
for rec in rk_raw:
    for item in rec.get("response_data", {}).get("ranking", []):
        rk_rows.append({"feature": feature_names.get(item["id"], item["id"]), "rank": int(item["rank"])})

rk_df = pd.DataFrame(rk_rows)
# rk_summary = ...

# TODO 3.2: Berechnen Sie für jede der 107 Szenen in `gdi_df` den gewichteten Index `UCI_citizen`
# aus den 4 normalisierten Gewichten für Greenery (GVI), Sky Openness (SVF),
# Degree of Greyness (1 - DoGS) und Building Facade Complexity (BFC),
# und exportieren Sie die Ergebnisse als GeoJSON (`mainz_urban_comfort_results.geojson`) für QGIS.

# %% [markdown]
# ---
# ## 🛰️ Aufgabe 4: Analyse von WMS Orthophotos (`DOP20`) & Lärmkartierung vs. 360°-Straßenperspektive (Bonus)
#
# ### Hintergrund: Warum unterscheiden sich Vogelperspektive (Fernerkundung / GDI) und Fußgängerperspektive (360° Street View)?
# In der Stadtplanung werden Grünflächen und Umweltbelastungen oft aus der Vogelperspektive über amtliche **Orthophotos (`DOP20`, 20 cm Bodenauflösung)** oder **Umgebungslärmkarten ($L_{\text{den}}$)** bewertet:
#
# > 🛰️ **LVermGeo RLP `DOP20` WMS 1.3.0:**
# > • **URL:** `https://geo4.service24.rlp.de/wms/rp_dop20.fcgi`
# > • **Parameter:** `LAYERS=rp_dop20` | `CRS=EPSG:25832` | `FORMAT=image/jpeg`
# >
# > 📢 **Lärmkartierung Stadt Mainz / RLP WMS 1.3.0 ($L_{\text{den}}$):**
# > • **URL (Stadt Mainz):** `https://gint.mainz.de/gint1-cgi/mapserv?map=/data/mapbender-int/umn-www/client/a17/a17-laerm.map` (`LAYERS=strasse_t_fl_09` | `CRS=EPSG:25832` | `FORMAT=image/png`)
# > • **URL (RLP Umgebungslärm):** `https://map-umgebungslaerm.rlp-umwelt.de/laermkartierung/mod_ogc/wms_getmap.php?mapfile=lden_2017` (`LAYERS=lden_2017` | `CRS=EPSG:25832` | `FORMAT=image/png`)
#
# ### 📝 Ihre Aufgabe:
#
# | 🐍 In Python (Jupyter / Colab) | 🗺️ Alternative in QGIS |
# | :--- | :--- |
# | **1.** Rufen Sie für den Standort mit dem **höchsten `UCI_citizen`**, dem **niedrigsten `UCI_citizen`** sowie für **`Hessisches_Kriegerdenkmal`** jeweils einen $160\,\text{m} \times 160\,\text{m}$ großen **Orthophoto-Ausschnitt (`GetMap`)** über den amtlichen `rp_dop20`-WMS sowie die **amtliche Lärmkartierung ($L_{\text{den}}$ `GetMap`)** in `EPSG:25832` ab.<br><br>**2.** Stellen Sie das **360°-Straßenpanorama (`images/files/*.jpeg`)** (bzw. falls nicht lokal vorhanden, die **VBORIS-Flächennutzungskarte per `GetMap`**), das **amtliche GDI-RP-Luftbild (`DOP20`)** und die **Lärmkartierung ($L_{\text{den}}$)** direkt nebeneinander dar. | **1.** Fügen Sie in QGIS beide amtlichen WMS-Dienste (`rp_dop20` und `strasse_t_fl_09` bzw. `lden_2017`) über *Layer → Layer hinzufügen → WMS/WMTS-Layer hinzufügen* ein.<br><br>**2.** Überlagern Sie die Rasterkarten mit den aggregierten Punktdaten aus `mainz_urban_comfort_results.geojson` und vergleichen Sie die Draufsicht (Luftbild / Lärmpegel) mit den Vor-Ort-Attributen (`GVI`, `SVF`, `DoGS`, `UCI_citizen`). |

# %%
def fetch_wms_map(
    wms_url: str,
    layer: str,
    easting: float,
    northing: float,
    radius_m: float = 85.0,
    img_format: str = "image/jpeg",
    transparent: bool = False,
) -> Image.Image:
    """Ruft einen Kartenausschnitt per OGC WMS 1.3.0 GetMap in EPSG:25832 ab."""
    params = {
        "SERVICE": "WMS",
        "VERSION": "1.3.0",
        "REQUEST": "GetMap",
        "LAYERS": layer,
        "STYLES": "",
        "CRS": "EPSG:25832",
        "BBOX": f"{easting - radius_m:.1f},{northing - radius_m:.1f},{easting + radius_m:.1f},{northing + radius_m:.1f}",
        "WIDTH": "400",
        "HEIGHT": "400",
        "FORMAT": img_format,
    }
    if transparent:
        params["TRANSPARENT"] = "TRUE"
    resp = requests.get(wms_url, params=params, timeout=12)
    resp.raise_for_status()
    mode = "RGBA" if transparent else "RGB"
    return Image.open(BytesIO(resp.content)).convert(mode)


def fetch_noise_overlay_map(dop_url: str, laerm_url: str, easting: float, northing: float, radius_m: float = 150.0) -> Image.Image:
    """Legt den transparenten Mainzer Lärmkartierungs-WMS (strasse_t_fl_09) über das amtliche DOP20-Luftbild."""
    base_img = fetch_wms_map(dop_url, "rp_dop20", easting, northing, radius_m=radius_m).convert("RGBA")
    noise_rgba = fetch_wms_map(laerm_url, "strasse_t_fl_09", easting, northing, radius_m=radius_m, img_format="image/png", transparent=True)
    arr = np.array(noise_rgba)
    is_bg = (arr[..., 3] == 0) | ((arr[..., 0] > 248) & (arr[..., 1] > 248) & (arr[..., 2] > 248))
    arr[is_bg, 3] = 0
    arr[~is_bg, 3] = 170
    return Image.alpha_composite(base_img, Image.fromarray(arr, mode="RGBA")).convert("RGB")

# TODO 4.1: Ermitteln Sie in `gdi_df` die Szene mit dem höchsten und niedrigsten `UCI_citizen`
# sowie `hessisches_kriegerdenkmal` und stellen Sie diese in einem 3x3-Plot (`plt.subplots(3, 3, figsize=(18, 12))`) dar:
# Spalte 0: 360°-Panorama (aus `IMAGE_FILES_DIR / row["file"]` oder VBORIS-WMS als Fallback)
# Spalte 1: Amtliches Orthophoto (`rp_dop20`, radius_m=85.0)
# Spalte 2: Amtliche Lärmkartierung (`strasse_t_fl_09` über `rp_dop20`, radius_m=150.0)
