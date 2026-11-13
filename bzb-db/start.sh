#!/usr/bin/env bash
# =============================================================================
# BZB-WFS im lokalen Netz starten (Docker).
#
#   ./start.sh          .env anlegen (falls nötig), bauen, starten, Zugangsdaten anzeigen
#   ./start.sh --neu    zusätzlich Datenbank und GeoServer-Konfiguration löschen (Volumes)
#
# Danach liegt in weitergeben/ eine Quellen-Datei für den Zuständigkeitsfinder.
# =============================================================================
set -euo pipefail
cd "$(dirname "$0")"

command -v docker >/dev/null || { echo "Docker fehlt." >&2; exit 1; }
docker info >/dev/null 2>&1 || { echo "Docker läuft nicht (Docker Desktop starten)." >&2; exit 1; }

zufall() { LC_ALL=C tr -dc 'A-Za-z0-9' </dev/urandom | head -c "${1:-24}"; }
belegt() { (exec 3<>"/dev/tcp/127.0.0.1/$1") 2>/dev/null; }
frei_ab() { local p=$1; while belegt "$p"; do p=$((p + 1)); done; echo "$p"; }

if [[ ! -f .env ]]; then
  echo "» Lege .env mit Zufallspasswörtern an"
  umask 077
  cat > .env <<EOF
# Erzeugt von start.sh am $(date +%F). Nicht einchecken, nicht weitergeben.
POSTGRES_PASSWORD=$(zufall)
GEOSERVER_DB_PASSWORD=$(zufall)
GEOSERVER_ADMIN_PASSWORD=$(zufall)

# Konto für Kolleginnen und Kollegen (WFS/WMS lesen)
WFS_BENUTZER=kollege
WFS_PASSWORT=$(zufall 16)
# 1 = WFS ohne Login lesbar (nur, wenn die BZB-Nutzungsbedingungen das erlauben)
WFS_OEFFENTLICH=0
# Für Nicht-Angemeldete: CHALLENGE = Layerliste sichtbar, Daten nur nach Login-Abfrage;
# HIDE = Workspace komplett unsichtbar (404, Browser fragt nicht nach dem Passwort)
KATALOG_MODUS=CHALLENGE

# Welche Themen der Dienst ausliefert: bzb_leser (alle) oder eine Themenrolle,
# z. B. bzb_leser_zoll, bzb_leser_sta, bzb_leser_thw, bzb_leser_bpol
DB_LESEROLLE=bzb_leser

WFS_PORT=$(frei_ab 8080)
DB_PORT=$(frei_ab 5433)
# Verzeichnis der BZB-Lieferung (mit bzb/de/ und dokumentation/)
BZB_LIEFERUNG=../bzb-bund
EOF
fi
set -a; source .env; set +a

if [[ ${1:-} == --neu ]]; then
  echo "» Lösche Volumes (Datenbank und GeoServer-Konfiguration)"
  docker compose down -v
fi

echo "» Baue und starte"
seit=$(date -u +%Y-%m-%dT%H:%M:%SZ)
docker compose up -d --build

echo "» Warte auf Laden und Einrichtung (erster Start: 1–3 Minuten)"
if ! docker compose wait einrichten >/dev/null || \
   [[ $(docker compose ps -a --format '{{.ExitCode}}' einrichten) != 0 ]]; then
  echo "FEHLER. Logs:" >&2
  docker compose logs --no-color laden einrichten | tail -40 >&2
  exit 1
fi
docker compose logs --no-color --no-log-prefix --since "$seit" einrichten | grep -E '^(»|   )' || true

# LAN-Adresse (macOS: en0/en1, Linux: hostname -I)
ip=$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null \
     || hostname -I 2>/dev/null | awk '{print $1}' || true)
ip=${ip:-$(hostname)}
basis="http://$ip:${WFS_PORT:-8080}/geoserver"

mkdir -p weitergeben
sed -e "s#^wfs_url = .*#wfs_url = \"$basis/bzb/ows\"#" \
    -e "s/^# auth_env = .*/auth_env = \"ZF_BZB_EIGEN_AUTH\"/" \
    ../quellen/bzb-eigen.toml.example > weitergeben/bzb-eigen.toml

cat <<EOF

================================================================================
 BZB-WFS läuft
--------------------------------------------------------------------------------
 WFS/WMS (für Kollegen):  $basis/bzb/ows
 Capabilities:            $basis/bzb/ows?service=WFS&request=GetCapabilities
 Benutzer / Passwort:     $WFS_BENUTZER / $WFS_PASSWORT
 Zugriff:                 $([[ $WFS_OEFFENTLICH == 1 ]] && echo "OHNE Login (WFS_OEFFENTLICH=1)" || echo "nur mit Login")

 GeoServer-Admin:         $basis/web   (admin / Passwort in .env)
 PostGIS (nur lokal):     postgresql://postgres@localhost:${DB_PORT:-5433}/bzb

 Zuständigkeitsfinder des Kollegen:
   1. weitergeben/bzb-eigen.toml in dessen Ordner quellen/ kopieren
   2. export ZF_BZB_EIGEN_AUTH='$WFS_BENUTZER:$WFS_PASSWORT'
   3. Server neu starten

 Erreicht der Kollege den Dienst nicht: macOS-Firewall (Systemeinstellungen >
 Netzwerk > Firewall) muss eingehende Verbindungen für Docker erlauben; beide
 Rechner müssen im selben Netz sein (Gäste-WLANs isolieren Geräte oft).
================================================================================
EOF
