# Behördenfinder: Kategorie + Adresse → zuständige Stelle mit Kontakt

Die semantische Suche (Elasticsearch) liefert eine **Behördenkategorie** (eines von 36 Schlüsselwörtern, z. B. `finanzamt`) und optional einen **LeiKa-Leistungsschlüssel**. Der Behördenfinder ermittelt dazu am Wohnort die zuständige Stelle mit Anschrift, Telefon, E-Mail, Öffnungszeiten und Onlinediensten.

```
kategorie + adresse ──► Nominatim ──► Koordinate
                                         │
                       VG250 (BKG) ◄─────┤  Gemeinde + Amtlicher Regionalschlüssel (ARS)
            Zuständigkeitsflächen ◄──────┤  BZB-Open, eigener BZB-WFS: Name der Stelle
                                         ▼
          PVOG-Suchdienst (ARS + LeiKa) ──► zuständige Stelle, Anschrift, Telefon, Onlinedienste
                                         ▼
                     zusammenführen ──► Antwort mit Quellen und Hinweisen
```

## Schnittstelle

```bash
uvicorn api:app --port 8001        # Doku: http://localhost:8001/docs
```

| Endpunkt | Zweck |
|---|---|
| `GET /behoerde?kategorie=…&adresse=…` | Anfrage per URL; statt `adresse` auch `lat` + `lon`; `leika` mehrfach möglich |
| `POST /behoerde` | dasselbe als JSON: `{"kategorie": "finanzamt", "adresse": "…", "leika": ["99102002060001"]}` |
| `GET /kategorien` | die 36 Kategorien mit Abdeckung (Flächen, PVOG, nicht räumlich) |

Im MCP-Server steht dieselbe Funktion als Tool `behoerde_finden` bereit.

**Kategorie:** Schlüsselwort (`buergeramt`), Anzeigename (`Bürgeramt / Bürgerbüro`) oder Synonym (`Bürgerbüro`, `Landratsamt`, `BAMF` …). Groß-/Kleinschreibung, Umlaute und Satzzeichen sind egal. Unbekannte Kategorien ergeben HTTP 422 mit Vorschlag und Liste.

**Leistungsschlüssel (`leika`):** Wird zuerst bei PVOG versucht. Kennt PVOG ihn am Ort nicht, nimmt der Finder die Leitleistungen der Kategorie und meldet das unter `hinweise`.

### Antwort (gekürzt)

```json
{
  "kategorie": {"key": "finanzamt", "label": "Finanzamt"},
  "ort": {"lat": 49.97, "lon": 8.06, "anzeige": "…", "hinweise": [], "gemeinde": "Ingelheim am Rhein", "ars": "073390030030"},
  "stellen": [{
    "name": "Finanzamt Bingen-Alzey",
    "rolle": "Zuständige Stelle",
    "anschrift": {"art": "Hausanschrift", "strasse": "Rochusallee 10", "ort": "55411 Bingen am Rhein", "lat": 49.96, "lon": 7.9},
    "telefon": ["+49 6721 706-0"], "email": ["…"], "web": ["…"], "oeffnungszeiten": "…",
    "methode": "pvog", "quellen": ["pvog"]
  }],
  "eindeutig": true,
  "leistung": {"name": "Freibeträge für Kind unter 18 Jahren beantragen", "leika": "99102002060001", "portal_url": "…"},
  "onlinedienste": [{"titel": "…", "url": "…"}],
  "hinweise": ["In größeren Städten sind je nach Stadtteil oder Steuerart verschiedene Finanzämter zuständig."],
  "quellen": [{"id": "vg250", "quellenvermerk": "VG250 © BKG (dl-de/by-2-0)"}, {"id": "pvog", "…": "…"}]
}
```

| Feld | Bedeutung |
|---|---|
| `stellen[].methode` | `flaeche` (Name aus Zuständigkeitsfläche), `pvog`, oder `flaeche+pvog` (Fläche und PVOG-Stelle gleichen Namens zusammengeführt) |
| `stellen[].ergaenzend` | `true`: PVOG-Stelle ohne Gegenstück, wenn eine Fläche die maßgebliche Stelle liefert (z. B. allgemeine Hotline der Bundesagentur neben dem örtlichen Jobcenter) |
| `stellen[].traeger`, `gebiet`, `uebergeordnet` | Träger (z. B. „Landkreis Mainz-Bingen“), Gebiet (z. B. „Regierungsbezirk Köln“), übergeordnete Stelle |
| `eindeutig` | genau eine nicht-ergänzende Stelle. Sonst kommen mehrere in Frage (z. B. Bezirksämter in Hamburg) |
| `hinweise` | Einschränkungen, Datenlücken, Ausfälle einzelner Quellen. **Immer anzeigen** |
| `quellen` | Quellenvermerke der tatsächlich genutzten Daten (Lizenzpflicht) |

HTTP-Status: 200 auch bei Teilausfällen (stehen in `hinweise`), 404 Adresse nicht gefunden, 422 ungültige Eingabe, 502 Ortsbestimmung nicht möglich.

## Abdeckung der 36 Kategorien

Stand 13.11.2026, live geprüft in Mainz, Ingelheim (Landkreis Mainz-Bingen), München, Hamburg und Köln.

| Wie | Kategorien |
|---|---|
| **Fläche + PVOG-Kontakt** | Amtsgericht (Kontakt nur, wo PVOG das Gericht kennt, z. B. München, Hamburg), Jobcenter, Agentur für Arbeit, Kreisverwaltung, Stadtverwaltung |
| **Nur Fläche** | Landgericht, Regierungspräsidium (nur BW, BY, HE, NRW); mit eigenem BZB-WFS zusätzlich Staatsanwaltschaft, Hauptzollamt, Bundespolizei |
| **PVOG mit Kontakt** | Finanzamt, Ordnungsamt, Bürgeramt, Standesamt, Ausländerbehörde, Polizei, Jugendamt, Sozialamt, Familienkasse, Wohngeldstelle, Bauamt, Straßenverkehrsbehörde, Zulassungsstelle, Gesundheitsamt, Veterinäramt, Umweltamt, Gewerbeamt, IHK, Handwerkskammer, Rentenversicherung, BAföG-Amt, Schulamt, BAMF, Bundesverwaltungsamt |
| **Nicht räumlich** | Krankenkasse, Pflegekasse: nur Hinweis, keine Abfrage |
| **Keine Daten** | Verwaltungsgericht |

**PVOG-Lücken:** PVOG enthält nur, was die Länder einpflegen. Beobachtet wurde z. B. kein Finanzamt für Köln, kein Veterinäramt für Mainz und keine Handwerkskammer für Mainz. Dann bleibt `stellen` leer und `hinweise` sagt das. Mehrere Leitleistungen je Kategorie fangen einen Teil davon ab.

## Konfiguration

- **`kategorien.toml`:** Kategorien, Synonyme, Flächen-Typen, Leitleistungen (LeiKa) und Hinweise. Änderungen ohne Code; doppelte Synonyme und falsche Schlüssel brechen den Start mit Meldung ab.
- **`quellen/vg250.toml`:** Gemeinden, Kreise, Regierungsbezirke. Wird per Punktabfrage gelesen (`abfrage = "punkt"`), nicht komplett geladen.
- **Umgebung:** `ZF_PVOG_URL` (Standard `https://pvog.fitko.net/suchdienst/api`), `ZF_PVOG_CLIENT_ID` (optional, [beim PVOG beantragen](https://produktportal.pvog.fitko.de/docs/ressourcen/client-id/)), `ZF_KATEGORIEN` (andere Kategorien-Datei).

PVOG-Antworten werden 12 Stunden im Speicher gehalten. Fällt PVOG aus, liefert der Finder die Flächen-Ergebnisse mit Hinweis.

## Neue Leitleistung finden

```bash
.venv/bin/python -c "
import pvog
for h in pvog._get('/v7/servicedescriptions/073150000000', q='Hundesteuer', size=5)['serviceDescriptions']['content']:
    print(h['name'], h['leikakeys'])"
```

Den Schlüssel dann mit `pvog.zustaendige_stellen(ars, [leika])` an mehreren Orten prüfen. Die Schlüsselgruppe verrät oft den Träger: `99114…` Deutsche Rentenversicherung, `99158…` landwirtschaftliche Sozialversicherung.
