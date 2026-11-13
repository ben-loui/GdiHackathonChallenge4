#!/usr/bin/env bash
# =============================================================================
# Container "laden": BZB-Shapefiles nach PostGIS laden (laden.sh) und das
# Dienstkonto für GeoServer anlegen bzw. sein Passwort setzen.
#
# Umgebung: PG* (Superuser-Verbindung), GEOSERVER_DB_PASSWORD,
#           DB_LESEROLLE (Standard bzb_leser = alle Themen; z. B. bzb_leser_zoll)
# =============================================================================
set -euo pipefail

: "${GEOSERVER_DB_PASSWORD:?GEOSERVER_DB_PASSWORD fehlt}"
ROLLE=${DB_LESEROLLE:-bzb_leser}

for _ in $(seq 1 60); do pg_isready -q && break; sleep 1; done
pg_isready -q || { echo "Datenbank nicht erreichbar" >&2; exit 1; }

bash /bzb-db/laden.sh

echo "» Dienstkonto geoserver_bzb (Leserolle: $ROLLE)"
psql -X -q -v ON_ERROR_STOP=1 -v pw="$GEOSERVER_DB_PASSWORD" -v rolle="$ROLLE" <<'SQL'
SELECT 'CREATE ROLE geoserver_bzb LOGIN'
WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'geoserver_bzb') \gexec
ALTER ROLE geoserver_bzb LOGIN PASSWORD :'pw';
-- Mitgliedschaften neu setzen, damit ein Wechsel von DB_LESEROLLE wirkt
SELECT format('REVOKE %I FROM geoserver_bzb', r.rolname)
FROM pg_auth_members m
JOIN pg_roles r ON r.oid = m.roleid
JOIN pg_roles u ON u.oid = m.member
WHERE u.rolname = 'geoserver_bzb' \gexec
GRANT :"rolle" TO geoserver_bzb;
SQL
echo "» Datenbank bereit"
