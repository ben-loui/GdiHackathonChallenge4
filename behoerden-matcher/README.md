# Authority Matcher v0.3 – FIM + Elasticsearch + öffentlicher PVOG-Live-Abgleich

**Ergebnisausgabe:** Standardmäßig gibt die CLI ausschließlich die Behördenkategorie und ihren aggregierten Ranking-Score aus. Bei `--json` besteht die Antwort exakt aus `behoerdenkategorie` und `score`, ohne Organisationsnamen oder Verwaltungsleistungen. Mit `--details` (alias `--debug`) können bei Bedarf die vollständigen PVOG-Belege und Diagnosedaten ausgegeben werden. Wenn keine eindeutige Kategorie ermittelt wurde, sind beide Werte `null`. Scores sind keine Prozentwahrscheinlichkeiten.

Beispiel (Score nur illustrativ):

```json
{
  "behoerdenkategorie": "buergeramt",
  "score": 0.03814
}
```

Eine deutsche Bürgeranfrage wird mit dem bereits importierten **FIM-Leistungskatalog** abgeglichen. Für die bestplatzierten Leistungen mit gültigem 14-stelligen LeiKa-Schlüssel fragt der Matcher **den öffentlichen PVOG-Suchdienst live** ab. Dabei verbindet er Leistungs-ID, JZuFi-Zuständigkeiten und amtliche Organisationseinheiten mit den **36 projektspezifischen Behördenkategorien** aus `data/categories.json`.

**Kein XZuFi-Export, keine Bereitstelldienst-Zugangsdaten, kein erneuter FIM-Download notwendig.** Die vorhandene SQLite-Datei `~/.local/share/authority-matcher/fim_catalog.sqlite3` bleibt erhalten. Nur für die öffentliche Leistungsabfrage sind Referenz-ARS nötig; keine Bürgeradresse wird erfragt oder an PVOG gesendet.

> **Reichweite:** Der öffentliche PVOG-Suchdienst liefert geografisch eingegrenzte Leistungen, nicht den gesamten deutschlandweiten Export. Deshalb ist die Klassifikation anhand einiger *Referenzregionen* eine Stichprobe. Eine regional anders organisierte Zuständigkeit kann fehlen. Die 36 Kategorien sind vom Hackathon definiert, nicht offiziell von LeiKa vorgegeben. Unbelegte, fehlgeschlagene oder widersprüchliche Zuordnungen werden nicht als eindeutig ausgegeben.

## Installation auf vorhandenem Mac

Alte FIM-Synchronisierung im ersten Terminal **mit `Ctrl+C` beenden**, bevor Python-Dateien überschrieben werden. Das Update-ZIP in `~/Desktop/GdiHackathonChallenge4` entpacken; der enthaltene Ordner `behoerden-matcher/` überschreibt nur den Quellcode im Projektordner, **niemals** die Datenbank in `~/.local/share/authority-matcher/`.

```bash
cd ~/Desktop/GdiHackathonChallenge4
unzip -o ~/Downloads/authority-matcher-pvog-live-v3.zip
cd behoerden-matcher
zsh update.command

authority-matcher --status
```

**Docker Desktop muss laufen**, damit die lokale Elasticsearch-Instanz gestartet werden kann. Beim ersten Start wird der schon geladene FIM-Bestand lokal indexiert; im Hybridmodus werden Embeddings mit `intfloat/multilingual-e5-small` erstellt und das Modell gegebenenfalls erstmals heruntergeladen. Der Indexaufbau kann erheblich länger dauern als einzelne Textanfragen. Er wird bei späteren Starts nicht nur deshalb wiederholt, weil PVOG-Daten hinzugekommen sind.

## Benutzung – ein Befehl

```bash
authority-matcher
```

Dann natürliche Anliegen eingeben:

```text
Anliegen> Ich habe einen Hund gekauft und will ihn anmelden
Anliegen> Meine Oma hat mir Geld geschenkt. Muss ich das melden?
Anliegen> Ich brauche einen Erbschein
```

In einem frischen System kann das Ergebnis zunächst „keine eindeutige Kategorie“ lauten. Das bedeutet, dass die öffentlichen PVOG-Abfragen für die betreffende Leistung/Referenzregion keinen prüfbaren Behördenbeleg ergaben. **Die drei Zeilen oben sind Eingabebeispiele, keine zugesicherten Ergebnisse.**

### Schnelltest / Diagnose

```bash
# BM25-Suche: kein Embedding-Download, trotzdem echter Elasticsearch-Index
# Erster Indexaufbau auch hier erforderlich.
authority-matcher --no-semantic

# Kompaktes Maschinen-JSON: genau Kategorie und Score
authority-matcher --json --no-semantic 'Ich möchte meinen Wohnsitz abmelden'

# Nur bei Fehleranalyse: komplette FIM-/PVOG-Nachweise anzeigen
authority-matcher --json --details --no-semantic 'Ich möchte meinen Wohnsitz abmelden'

# Vorhandene FIM-Einträge und belegte JZuFi-Links
authority-matcher --status

# Öffentliche PVOG-Suche für genau einen LeiKa-Schlüssel und ARS prüfen
# Gibt bei null regionalen Treffern eine Diagnose statt des früheren argparse-Fehlers aus.
authority-matcher jzufi-fetch --leika 99008001000000 --ars 110000000000
```

Eine andere Auswahl von **Referenzgebieten** (das sind keine Nutzerstandorte):

```bash
authority-matcher --reference-ars 110000000000,020000000000,073150000000
```

Standardmäßig werden die drei genannten ARS verwendet (Berlin, Hamburg, Mainz). Die Abfragen pro (LeiKa, ARS) werden gespeichert und nicht bei jeder Anfrage wiederholt. Fehlversuche werden nach etwa 5 Minuten, leere Treffer nach 24 Stunden und erfolgreiche Abfragen nach sieben Tagen erneut versucht. Für weniger Live-Aufrufe:

```bash
authority-matcher --live-top 1
```

Um ausschließlich mit den gecachten PVOG-Daten zu suchen:

```bash
authority-matcher --no-live
```

## Technische Pipeline

1. **Elasticsearch BM25 + Embeddings:** Sucht in den bereits importierten und normalisierten FIM-Leistungssteckbriefen und Stammtexten. Datenquelle: [FIM-Portal](https://fimportal.de/).
2. **LeiKa-Schlüssel → regionale LB-IDs:** `GET https://pvog.fitko.net/suchdienst/api/v3/servicedescriptions/leikaid?leikaIds=...&ars=...` mit `page`, `size`, `useArsHierarchy`, `withOrgIds`, `validDate`.
3. **JZuFi-Objekte:** `GET /v1/servicedescriptions/{id}/jzufi-2-3` und `GET /v1/relations/jzufi-2-3` für die amtlichen Beziehungen. Diese werden auf den 14-stelligen LeiKa-Schlüssel zurückgeführt.
4. **Amtliche Organisationstitel und Rollen:** `GET /v2/organisationunits/titles?lbids=...&ars=...`. Der Endpunkt ergänzt JZuFi und ist besonders hilfreich, wenn JZuFi-Transferhüllen nicht in allen Daten einheitlich sind. Nur Rollen `01` (zuständige Stelle + Ansprechpunkt) oder `02` (zuständige Stelle) gelten als Behördenbeleg; `03` (nur Ansprechpunkt) wird nicht als zuständige Stelle ausgegeben. Fehlende Rollen bleiben als ungeklärt erhalten.
5. **Behördennormierung:** Offizielle Namen wie „Bürgeramt Beispielstadt“ werden durch nachprüfbare Namens-Aliase der 36 Kategorien auf `buergeramt` abgebildet. Ergebnis und Originalbelege werden in den bestehenden, zusätzlich erstellten SQLite-Tabellen `jzufi_services`, `jzufi_orgs`, `jzufi_links` und `pvog_live_attempts` gespeichert.
6. **Anfrageergebnis:** Es wird eine Kategorie vorgeschlagen, wenn die belegte Zuordnung ausreichend eindeutig ist. Bei mehreren Behördenarten, regionalen Unterschieden oder Lücken wird die Unsicherheit offengelegt. Ein `score` ist ein **Ranking-Wert, keine Wahrscheinlichkeit**.

Die Bürgeranfrage wird **nur an die lokale Elasticsearch-Instanz** gesendet; PVOG erhält ausschließlich die LeiKa-IDs, die daraus ermittelten regionalen LB-IDs und die festen Referenz-ARS. Personenbezogene Angaben aus Nutzeranfragen werden nicht an PVOG übertragen.

### Grenzen und offene Qualitätssicherung

- Live-Antworten konnten in der Entwicklungsumgebung wegen fehlendem Netzwerkzugang nicht gegen `pvog.fitko.net` getestet werden. Die automatisierten API-Vertragstests verwenden **synthetische Antworten**.
- Der Suchdienst kann eine LeiKa-Leistung in einer Referenzregion nicht finden (z. B. weil keine regionale Leistungsbeschreibung vorhanden ist). Das ist kein Beweis für bundesweite Nichtzuständigkeit. Weitere ARS können helfen, garantieren aber keinen vollständigen Überblick.
- Nicht jeder FIM-Stammtext hat den für den Join nötigen LeiKa-Schlüssel; die Leistungssteckbriefe sind die verlässlichere Basis. Bei fehlenden Schlüsseln kann kein amtliches Mapping abgeleitet werden.
- Die PVOG-Rollen- und Organisationsinformationen können bei einzelnen Redaktionen unvollständig oder fehlerhaft sein. Eine Stichprobe sollte vor der Jury-Präsentation auf Genauigkeit und Kategorienabdeckung überprüft werden.
- FIM- und PVOG-Quellen stellen mehrere unterschiedlich granulaire Beschreibungen derselben Leistung bereit. Das Ranking muss anhand von realen Testanfragen validiert werden.
- Eine **vollständig deutschlandweite** Zuständigkeitsdatenbank lässt sich ohne berechtigten Gesamtdatenexport nicht garantieren. Die Live-Lösung liefert eine praktikable, nachvollziehbare *gezielte* Auflösung für die jeweilige Bürgeranfrage.

## Tests

```bash
cd ~/Desktop/GdiHackathonChallenge4/behoerden-matcher
.venv/bin/python -m pip install -e '.[test]'
.venv/bin/python -m pytest -q
```

32 automatisierte Tests, darunter neue Prüfungen für JZuFi-/FIM-Mapping, Caching, den bisherigen `--leika`-CLI-Fehler und Indexaufbau ohne bereits vorhandene Kategorien. Alle JZuFi-Fakes sind klar als synthetisch gekennzeichnet.

## Amtliche Quellen

- [PVOG – Öffentliche Suchdienst-API](https://pvog.fitko.de/docs/suchdienst/doku/)
- [FITKO – LeiKa-Schlüssel zur Leistungsbeschreibung](https://docs.fitko.de/efa-parametrisierung/docs/parametrisierung_anh%C3%A4nge/ermittlung_der_id_der_leistungsbeschreibung/)
- [PVOG – JZuFi-Zuständigkeitsbeziehungen 2.3](https://pvog.fitko.de/api/suchdienst/get-zs-tr-by-lb-id-and-ars-231-v-1/)
- [FITKO – Organisationseinheiten, Rollen, titles](https://docs.fitko.de/efa-parametrisierung/docs/parametrisierung_anh%C3%A4nge/ermittlung_zust%C3%A4ndige_organisationseinheit_im_pvog/)
- [PVOG – JZuFi-Datenformat 2.3.1](https://pvog.fitko.de/api/suchdienst/get-jzufi-lb-231-v-1/)
