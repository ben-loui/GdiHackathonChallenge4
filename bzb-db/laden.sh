#!/usr/bin/env bash
# =============================================================================
# BZB in PostGIS laden
#
#   ./laden.sh            Schema anlegen (falls noch nicht vorhanden) und laden
#   ./laden.sh --neu      Schemata bzb, bzb_ows, bzb_stage LÖSCHEN, neu anlegen, laden
#
# Verbindung über die üblichen libpq-Variablen (PGHOST, PGPORT, PGDATABASE,
# PGUSER, PGPASSWORD bzw. ~/.pgpass).
# BZB_DATEN  Verzeichnis mit bzb_bpol/, bzb_sta/, bzb_thw/, bzb_zoll/
#            (Standard: ../bzb-bund/bzb/de relativ zu diesem Skript)
# BZB_DOKU   Verzeichnis mit aktualitaet.txt (Standard: $BZB_DATEN/../../dokumentation)
#
# Benötigt: psql, ogr2ogr, ogrinfo (GDAL >= 3.4)
# =============================================================================
set -euo pipefail

HIER=$(cd "$(dirname "$0")" && pwd)
DATEN=${BZB_DATEN:-$HIER/../bzb-bund/bzb/de}
DOKU=${BZB_DOKU:-$DATEN/../../dokumentation}
PSQL=(psql -X -q -v ON_ERROR_STOP=1)

[[ -d $DATEN ]] || { echo "Datenverzeichnis nicht gefunden: $DATEN" >&2; exit 1; }

if [[ ${1:-} == --neu ]]; then
  echo "» Schemata bzb, bzb_ows, bzb_stage werden gelöscht"
  "${PSQL[@]}" -c 'DROP SCHEMA IF EXISTS bzb_ows, bzb, bzb_stage CASCADE'
fi

if [[ $("${PSQL[@]}" -tAc "SELECT to_regnamespace('bzb') IS NULL") == t ]]; then
  echo "» Schema anlegen"
  for f in 00_rollen 01_schema 02_metadaten 03_ows; do
    "${PSQL[@]}" -f "$HIER/sql/$f.sql"
  done
else
  # Metadaten und Views sind idempotent und werden immer aktualisiert
  "${PSQL[@]}" -f "$HIER/sql/02_metadaten.sql"
  "${PSQL[@]}" -f "$HIER/sql/03_ows.sql"
fi

echo "» Rohimport nach bzb_stage"
"${PSQL[@]}" -c 'DROP SCHEMA IF EXISTS bzb_stage CASCADE; CREATE SCHEMA bzb_stage;
                 CREATE TABLE bzb_stage.dbf_stand (quelle_layer text PRIMARY KEY, stand date)'

anzahl=0
while IFS= read -r shp; do
  layer=$(basename "$shp" .shp)
  tabelle=$(printf '%s' "$layer" | tr '[:upper:]' '[:lower:]')
  ogr2ogr -f PostgreSQL PG: "$shp" \
    -nln "$tabelle" -lco SCHEMA=bzb_stage \
    -nlt GEOMETRY -a_srs EPSG:25832 \
    -lco GEOMETRY_NAME=geom -lco FID=fid -lco SPATIAL_INDEX=NONE -lco PRECISION=NO \
    --config PG_USE_COPY YES
  stand=$(ogrinfo -so -al "$shp" | sed -n 's/^ *DBF_DATE_LAST_UPDATE=//p')
  if [[ -n $stand ]]; then
    "${PSQL[@]}" -c "INSERT INTO bzb_stage.dbf_stand VALUES ('$layer', '$stand')"
  fi
  echo "   $layer"
  anzahl=$((anzahl + 1))
done < <(find "$DATEN" -name '*.shp' | sort)

[[ $anzahl -gt 0 ]] || { echo "Keine Shapefiles in $DATEN" >&2; exit 1; }

produktstand=""
if [[ -f $DOKU/aktualitaet.txt ]]; then
  produktstand=$(grep -oE '^[0-9]{4}-[0-9]{2}' "$DOKU/aktualitaet.txt" || true)
fi

echo "» Laden und Prüfen (eine Transaktion)"
"${PSQL[@]}" -v produktstand="$produktstand" -f "$HIER/sql/04_laden.sql"

echo "» Statistiken"
"${PSQL[@]}" <<'SQL'
SELECT format('VACUUM (ANALYZE) %s', c.oid::regclass)
FROM pg_class c
WHERE c.relnamespace = 'bzb'::regnamespace AND c.relkind = 'r'
\gexec
SQL

"${PSQL[@]}" -P footer=off -c "SELECT datensatz_id, anzahl_objekte, dbf_stand FROM bzb.datensatz ORDER BY sortierung"
echo "» Fertig"
