#!/usr/bin/env bash
# =============================================================================
# Container "einrichten": GeoServer per REST konfigurieren (idempotent).
#
#   Workspace bzb, PostGIS-Store bzb_ows (Dienstkonto geoserver_bzb),
#   je lesbarer View ein Layer mit Titel/Abstract/Schlagwörtern aus bzb.datensatz,
#   Zugriff: Lesen nur mit Rolle ROLE_BZB_LESER (oder öffentlich), Schreiben nur Admin,
#   WFS-Konto für Kolleginnen und Kollegen.
#
# Umgebung: GS_URL, GEOSERVER_ADMIN_USER, GEOSERVER_ADMIN_PASSWORD, GEOSERVER_DB_PASSWORD,
#           WFS_BENUTZER, WFS_PASSWORT, WFS_OEFFENTLICH (1 = ohne Login),
#           KATALOG_MODUS (CHALLENGE|HIDE|MIXED, Standard CHALLENGE), PG* (Superuser)
# =============================================================================
set -euo pipefail

GS=${GS_URL:-http://geoserver:8080/geoserver}
ADMIN=${GEOSERVER_ADMIN_USER:-admin}
: "${GEOSERVER_ADMIN_PASSWORD:?}" "${GEOSERVER_DB_PASSWORD:?}" "${WFS_BENUTZER:?}" "${WFS_PASSWORT:?}"
WS=bzb
DS=bzb_ows
ROLLE=ROLE_BZB_LESER
ANTWORT=$(mktemp)

# gs METHODE PFAD [JSON]  -> gibt den HTTP-Status aus, Antwort in $ANTWORT
gs() {
  local args=(-sS -o "$ANTWORT" -w '%{http_code}' -u "$ADMIN:$GEOSERVER_ADMIN_PASSWORD" -X "$1")
  [[ $# -ge 3 ]] && args+=(-H 'Content-Type: application/json' --data-binary "$3")
  curl "${args[@]}" "$GS/rest$2"
}
# pruefe STATUS ERLAUBT... -> bricht mit Meldung ab, wenn STATUS nicht erlaubt ist
pruefe() {
  local status=$1 schritt=$2; shift 2
  for ok in "$@"; do [[ $status == "$ok" ]] && return 0; done
  echo "FEHLER bei '$schritt': HTTP $status" >&2; cat "$ANTWORT" >&2; echo >&2; exit 1
}
# anlegen_oder_aendern NAME GET-PFAD POST-PFAD PUT-PFAD JSON
anlegen_oder_aendern() {
  if [[ $(gs GET "$2") == 200 ]]; then
    pruefe "$(gs PUT "$4" "$5")" "$1 ändern" 200
  else
    pruefe "$(gs POST "$3" "$5")" "$1 anlegen" 201 200
  fi
}

echo "» Warte auf GeoServer ($GS)"
for _ in $(seq 1 150); do
  [[ $(gs GET /about/version.json 2>/dev/null || true) == 200 ]] && break
  sleep 2
done
pruefe "$(gs GET /about/version.json)" "GeoServer erreichbar" 200
jq -r '.about.resource[] | select(."@name"=="GeoServer") | "   GeoServer \(.Version)"' "$ANTWORT"

# ------------------------------------------------------------------ Workspace
if [[ $(gs GET "/workspaces/$WS.json") != 200 ]]; then
  pruefe "$(gs POST /workspaces '{"workspace":{"name":"bzb"}}')" "Workspace anlegen" 201
fi
pruefe "$(gs PUT "/namespaces/$WS" '{"namespace":{"prefix":"bzb","uri":"https://bzb.local/bzb"}}')" "Namespace" 200

# ---------------------------------------------------------------------- Store
store=$(jq -n --arg pw "$GEOSERVER_DB_PASSWORD" --arg host "${PGHOST:-db}" --arg db "${PGDATABASE:-bzb}" '{
  dataStore: {
    name: "bzb_ows",
    description: "BZB-Views (Schema bzb_ows), Dienstkonto geoserver_bzb",
    connectionParameters: { entry: [
      {"@key": "dbtype", "$": "postgis"},
      {"@key": "host", "$": $host},
      {"@key": "port", "$": "5432"},
      {"@key": "database", "$": $db},
      {"@key": "schema", "$": "bzb_ows"},
      {"@key": "user", "$": "geoserver_bzb"},
      {"@key": "passwd", "$": $pw},
      {"@key": "Primary key metadata table", "$": "bzb_ows.gt_pk_metadata"},
      {"@key": "Expose primary keys", "$": "true"},
      {"@key": "Estimated extends", "$": "false"},
      {"@key": "Loose bbox", "$": "true"}
    ]}
  }}')
anlegen_oder_aendern "Store $DS" "/workspaces/$WS/datastores/$DS.json" \
  "/workspaces/$WS/datastores" "/workspaces/$WS/datastores/$DS" "$store"

# --------------------------------------------------------------------- Layer
# Nur Views, die das Dienstkonto lesen darf (DB_LESEROLLE), Metadaten aus bzb.datensatz.
layer_json=$(psql -X -qtA -v ON_ERROR_STOP=1 -c "
  SELECT coalesce(json_agg(json_build_object(
           'name', d.datensatz_id, 'titel', d.titel, 'abstract', d.beschreibung,
           'schlagwoerter', d.schlagwoerter) ORDER BY d.sortierung), '[]')
  FROM bzb.datensatz d
  WHERE has_table_privilege('geoserver_bzb', format('bzb_ows.%I', d.datensatz_id), 'SELECT')")
anzahl=$(jq length <<<"$layer_json")
[[ $anzahl -gt 0 ]] || { echo "Dienstkonto darf keine View lesen (DB_LESEROLLE prüfen)" >&2; exit 1; }
echo "» $anzahl Layer veröffentlichen"

# Layer, die das Dienstkonto nicht (mehr) lesen darf, entfernen
pruefe "$(gs GET "/workspaces/$WS/datastores/$DS/featuretypes.json")" "Layerliste" 200
for alt in $(jq -r '.featureTypes.featureType? // [] | .[].name' "$ANTWORT" 2>/dev/null || true); do
  if ! jq -e --arg n "$alt" 'any(.[]; .name == $n)' <<<"$layer_json" >/dev/null; then
    echo "   entferne $alt"
    pruefe "$(gs DELETE "/workspaces/$WS/datastores/$DS/featuretypes/$alt?recurse=true")" "Layer $alt entfernen" 200
  fi
done

while IFS= read -r eintrag; do
  name=$(jq -r .name <<<"$eintrag")
  ft=$(jq '{featureType: {
      name: .name, nativeName: .name, title: .titel, abstract: .abstract,
      keywords: {string: .schlagwoerter},
      srs: "EPSG:25832", projectionPolicy: "FORCE_DECLARED", enabled: true}}' <<<"$eintrag")
  if [[ $(gs GET "/workspaces/$WS/datastores/$DS/featuretypes/$name.json") == 200 ]]; then
    pruefe "$(gs PUT "/workspaces/$WS/datastores/$DS/featuretypes/$name?recalculate=nativebbox,latlonbbox" "$ft")" "Layer $name ändern" 200
  else
    pruefe "$(gs POST "/workspaces/$WS/datastores/$DS/featuretypes" "$ft")" "Layer $name anlegen" 201
  fi
  echo "   $name"
done < <(jq -c '.[]' <<<"$layer_json")

# ------------------------------------------------------------------ Zugriff
echo "» Zugriff"
pruefe "$(gs GET /security/roles.json)" "Rollen lesen" 200
if ! jq -e --arg r "$ROLLE" '.roles | index($r)' "$ANTWORT" >/dev/null; then
  pruefe "$(gs POST "/security/roles/role/$ROLLE")" "Rolle anlegen" 201 200
fi

pruefe "$(gs GET /security/usergroup/users.json)" "Benutzer lesen" 200
benutzer=$(jq -n --arg u "$WFS_BENUTZER" --arg p "$WFS_PASSWORT" '{user: {userName: $u, password: $p, enabled: true}}')
if jq -e --arg u "$WFS_BENUTZER" '[.users[]?.userName] | index($u)' "$ANTWORT" >/dev/null; then
  pruefe "$(gs POST "/security/usergroup/user/$WFS_BENUTZER" "$benutzer")" "Benutzer ändern" 200
else
  pruefe "$(gs POST /security/usergroup/users "$benutzer")" "Benutzer anlegen" 201 200
fi
pruefe "$(gs POST "/security/roles/role/$ROLLE/user/$WFS_BENUTZER")" "Rolle zuweisen" 200 201

if [[ ${WFS_OEFFENTLICH:-0} == 1 ]]; then
  lesen="*"
  echo "   ACHTUNG: Lesen ohne Login (WFS_OEFFENTLICH=1)"
else
  lesen="$ROLLE,ROLE_ADMINISTRATOR"
fi
pruefe "$(gs GET /security/acl/layers.json)" "Layer-Regeln lesen" 200
vorhanden=$(cat "$ANTWORT")
for regel in "bzb.*.r=$lesen" "bzb.*.w=ROLE_ADMINISTRATOR"; do
  schluessel=${regel%%=*}
  body=$(jq -n --arg k "$schluessel" --arg v "${regel#*=}" '{($k): $v}')
  if jq -e --arg k "$schluessel" 'has($k)' <<<"$vorhanden" >/dev/null; then
    pruefe "$(gs PUT /security/acl/layers "$body")" "Regel $schluessel" 200
  else
    pruefe "$(gs POST /security/acl/layers "$body")" "Regel $schluessel" 200 201
  fi
  echo "   $schluessel = ${regel#*=}"
done

# Katalogmodus: CHALLENGE = Layerliste öffentlich, Datenabruf ohne Login -> 401 (Browser/QGIS fragen
# nach dem Passwort); HIDE = für Anonyme komplett unsichtbar (404, kein Login-Dialog); MIXED = dazwischen.
modus=${KATALOG_MODUS:-CHALLENGE}
[[ $modus =~ ^(CHALLENGE|HIDE|MIXED)$ ]] || { echo "KATALOG_MODUS muss CHALLENGE, HIDE oder MIXED sein" >&2; exit 1; }
pruefe "$(gs PUT /security/acl/catalog "{\"mode\":\"$modus\"}")" "Katalogmodus" 200
echo "   Katalogmodus = $modus"

echo "» GeoServer eingerichtet"
