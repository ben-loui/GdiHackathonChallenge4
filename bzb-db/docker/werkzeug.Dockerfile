# Werkzeug-Image für die Einmal-Container "laden" und "einrichten":
# ogr2ogr/ogrinfo (GDAL), psql, curl und jq.
FROM ghcr.io/osgeo/gdal:ubuntu-small-3.11.3

RUN apt-get update \
 && apt-get install -y --no-install-recommends postgresql-client curl jq ca-certificates \
 && rm -rf /var/lib/apt/lists/*
