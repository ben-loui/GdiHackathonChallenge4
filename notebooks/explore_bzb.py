# %% [markdown]
# # Exploring BKG responsibility areas
#
# Zed REPL version of `explore_bzb.ipynb`. Run cells with `ctrl-shift-enter`
# (or `shift-enter` to run and move on). Cells are separated by `# %%`.
#
# This explores the BZB-Open WFS using a public point at Schillerplatz in Mainz.
# It is separate from the application's VG250/PVOG search and requires internet access.
#
# Install the optional dependencies (plus ipykernel) in the project venv, from the project root:
# `python -m pip install -r notebooks/requirements.txt`

# %%
import requests
import geopandas as gpd
import folium
from owslib.wfs import WebFeatureService
from shapely import make_valid
from shapely.geometry import Point

WFS_URL = "https://sgx.geodatenzentrum.de/wfs_bzb_open"
LAYER = "bzb-open:ba_arbeitsagenturen"
longitude, latitude = 8.2678725, 49.9982245  # Schillerplatz, Mainz


# %% [markdown]
# ## 1. Discover the service
#
# GetCapabilities describes the available feature types. The live list can change; always check it before querying.

# %%
wfs = WebFeatureService(url=WFS_URL, version="2.0.0", timeout=25)
print("Service:", wfs.identification.title)
print("Feature types:", *wfs.contents.keys(), sep="\n  ")
assert LAYER in wfs.contents, "The selected layer is not currently advertised"

# %% [markdown]
# ## 2. Retrieve candidate areas
#
# The bounding box is only a server-side filter. CRS84 and GeoJSON use longitude, latitude.
# Check the provider's metadata before changing the coordinate system or source.

# %%
crs = "urn:ogc:def:crs:OGC::CRS84"
epsilon = 0.0001
params = {
    "service": "WFS", "version": "2.0.0", "request": "GetFeature",
    "typeNames": LAYER, "outputFormat": "application/json", "srsName": crs,
    "bbox": f"{longitude-epsilon},{latitude-epsilon},{longitude+epsilon},{latitude+epsilon},{crs}",
    "count": 1000,
}
response = requests.get(WFS_URL, params=params, timeout=25)
response.raise_for_status()
data = response.json()
assert data.get("type") == "FeatureCollection", "Unexpected WFS response"
matched = data.get("numberMatched", "unknown")
if (str(matched).isdigit() and int(matched) > len(data["features"])) or len(data["features"]) >= 1000:
    raise ValueError("The WFS response may be truncated")
if not data["features"]:
    raise ValueError("No candidate areas returned for this point")
areas = gpd.GeoDataFrame.from_features(data["features"], crs="OGC:CRS84")
print("Candidates:", len(areas), "CRS:", areas.crs, "bounds:", areas.total_bounds)
areas.drop(columns="geometry").head()

# %% [markdown]
# ## 3. Check the point and show the result
#
# `covers` includes points on an area boundary. Invalid candidate geometries are repaired before the check;
# repairs may alter a boundary, so confirm the result with the authority. Multiple matches should all be investigated.

# %%
point = Point(longitude, latitude)
invalid = ~areas.geometry.is_valid
print("Invalid candidate geometries repaired:", int(invalid.sum()))
areas.loc[invalid, "geometry"] = areas.loc[invalid, "geometry"].map(make_valid)
matches = areas[areas.geometry.covers(point)].copy()
print("Matching areas:", len(matches))
matches.drop(columns="geometry")

# %% [markdown]
# ## 4. Visualise
#
# Zed's REPL cannot render interactive Leaflet maps inline, so the map is saved to an HTML file
# next to this script and opened in your browser.

# %%
import webbrowser
from datetime import date
from pathlib import Path

m = folium.Map(location=[latitude, longitude], zoom_start=11, tiles=None)

folium.WmsTileLayer(
    url="https://sgx.geodatenzentrum.de/wms_topplus_open", layers="web_grau",
    fmt="image/png", transparent=False, name="TopPlusOpen Grau",
    attr=f'© <a href="https://www.bkg.bund.de">BKG</a> ({date.today().year}) <a href="https://www.govdata.de/dl-de/by-2-0">dl-de/by-2-0</a>, <a href="https://sgx.geodatenzentrum.de/web_public/gdz/datenquellen/datenquellen_topplusopen.html">TopPlusOpen sources</a>; <a href="https://sgx.geodatenzentrum.de/web_public/gdz/datenquellen/datenquellen_bzb-open.pdf">BZB-Open sources</a>; areas selected and geometries repaired where necessary'
).add_to(m)
if not matches.empty:
    folium.GeoJson(matches.__geo_interface__, style_function=lambda _: {"color": "#008b95", "fillOpacity": 0.2}).add_to(m)
folium.Marker([latitude, longitude], tooltip="Selected point").add_to(m)

out = Path.cwd() / "bzb_map.html"
m.save(out)
print("Saved map to", out)
webbrowser.open(out.as_uri())
