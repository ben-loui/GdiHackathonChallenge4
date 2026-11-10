# Architecture

The app is a Flask service with a plain JavaScript frontend and a Leaflet map. It needs no database or user account.

| Endpoint | Purpose |
| --- | --- |
| `POST /api/geocode` | Search the chosen geocoder and return location candidates for confirmation. |
| `POST /api/municipalities` | Find municipal boundaries around the selected point, then use Shapely's `covers` test to obtain matching official regional keys (ARS). |
| `POST /api/services` | Search PVOG for the task and ARS. Results are loaded in pages of eight. |
| `POST /api/service-detail` | Fetch the selected service and details for up to five associated authorities. Further authorities are flagged. |

The WFS bounding box supplies candidates; it is followed by a geometry check. Boundary points can match more than one municipality, in which case the interface asks for a choice. Invalid geometries are repaired with a visible notice. Incomplete source responses are rejected.

Source HTML is converted to text. Links must use HTTP(S); online services marked as private or outside production are excluded. Directions require source coordinates in a supported WGS84/CRS84 format. Missing details and failed requests remain visible.

## Project files

- `app/server.py`: source requests, validation and spatial matching.
- `app/static/`: interface, translations and map.
- `tests/`: backend and frontend behaviour checks.
- `notebooks/`: separate BZB-Open exploration using GeoPandas, Shapely, OWSLib and Folium.

The older `/api/layers` and `/api/lookup` endpoints support that BZB-Open work; the main interface uses VG250 and PVOG. Provider configuration and operating limits are covered in the [README](../README.md) and [source notes](data-sources.md).
