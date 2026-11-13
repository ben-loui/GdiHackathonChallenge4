"""Regenerate measured coverage, all 36 categories, and delivery inventory."""
import json
from pathlib import Path
from behoerden_resolver.catalog import sources,resource
from behoerden_resolver.db import connect, coverage
from behoerden_resolver.etl import latest_snapshots, now, read_manifest

root=Path(__file__).resolve().parents[1]
report=coverage()
(root/'data/coverage-full.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,default=str)+'\n')
summary={'generated_at':now(),'authority_records':sum(c['authority_count'] for c in report['categories']),
         'location_records':sum(c['location_count'] for c in report['categories']),
         'boundary_records':sum(c['boundary_count'] for c in report['categories']),
         'categories_with_authorities':sum(c['authority_count']>0 for c in report['categories']),
         'categories_with_locations':sum(c['location_count']>0 for c in report['categories']),
         'categories_total':len(report['categories']),'national_coverage_guaranteed':False,'categories':report['categories']}
with connect() as conn:
 summary['geometry_checks']={}
 for table in ['authorities','boundaries','locations']:
  fixed='count(*) FILTER(WHERE geometry_repaired)' if table!='locations' else '0'
  summary['geometry_checks'][table]=conn.execute(f'SELECT count(*) AS records, {fixed} AS repaired, count(*) FILTER(WHERE NOT ST_IsValid(geom)) AS invalid FROM behoerden.{table}').fetchone()
 source_counts=conn.execute("""SELECT category,source_id,count(*) AS records,'polygon' AS geometry_kind FROM behoerden.authorities GROUP BY category,source_id
   UNION ALL SELECT category,source_id,count(*),'point' FROM behoerden.locations GROUP BY category,source_id ORDER BY category,source_id""").fetchall()
 summary['source_counts']=source_counts
 # One representative point per actual AGS, never a percentage of people or addresses.
 conn.execute("""CREATE TEMP TABLE municipal_reference AS SELECT properties->>'ags' AS ags,
   max(properties->>'lkz') AS state,ST_PointOnSurface(ST_UnaryUnion(ST_Collect(geom))) AS geom
   FROM behoerden.boundaries WHERE source_id='vg25_gem' GROUP BY properties->>'ags'""")
 conn.execute('CREATE INDEX ON municipal_reference USING gist(geom)')
 conn.execute('ANALYZE municipal_reference')
 totals=conn.execute('SELECT state,count(*) AS municipalities FROM municipal_reference GROUP BY state ORDER BY state').fetchall()
 summary['reference_municipalities']=sum(r['municipalities'] for r in totals)
 summary['reference_municipalities_by_state']=totals
 for c in summary['categories']:
  if not c['authority_count']:c['municipal_reference_matches']=0;c['municipal_reference_by_state']=[];continue
  print('Measure',c['id'],flush=True)
  metrics=conn.execute("""SELECT r.state,count(*) AS matched FROM municipal_reference r
    WHERE EXISTS(SELECT 1 FROM behoerden.authorities a WHERE a.category=%s AND a.geom && r.geom AND ST_Covers(a.geom,r.geom))
    GROUP BY r.state ORDER BY r.state""",(c['id'],)).fetchall()
  c['municipal_reference_matches']=sum(v['matched'] for v in metrics)
  c['municipal_reference_by_state']=metrics
 for c in summary['categories']:
  c['location_states']=conn.execute("""SELECT DISTINCT b.properties->>'lkz' AS state FROM behoerden.locations l JOIN behoerden.boundaries b
   ON b.source_id='vg25_krs' AND b.geom && l.geom AND ST_Covers(b.geom,l.geom) WHERE l.category=%s ORDER BY state""",(c['id'],)).fetchall() if c['location_count'] else []
(root/'data/coverage-summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
radii=json.loads(resource('fallback.json').read_text())['category_radius_km']
head=['# Deutschlandweite Abdeckung und Quellen je Behördenkategorie','',
      f"Stand der lokalen Messung: {summary['generated_at']}. **{summary['authority_records']:,} Flächeneinträge in {summary['categories_with_authorities']} Kategorien; {summary['location_records']:,} Standorte in {summary['categories_with_locations']} Kategorien; {summary['boundary_records']:,} reine Verwaltungsgebietsreferenzen.** Alle 36 Kategorien werden unterstützt, aber nicht alle besitzen bundesweit nachgewiesene Zuständigkeitsflächen.",'',
      'Die Mengen zählen Quellfeatures und Dienststellen einschließlich mehrfacher räumlicher Teile. Mehrere Quellen können dieselbe Institution enthalten. Ein Standort ist kein Nachweis für deren örtliche oder persönliche Zuständigkeit.','',
      '## Wie die Abdeckung gemessen wird','',
      f"Der Flächenindikator zählt die Gemeindeschlüssel, deren VG25-Repräsentativpunkt von mindestens einem importierten Fachpolygon erfasst wird. Basis: **{summary['reference_municipalities']} unterschiedliche AGS** aus dem tatsächlich geladenen VG25-Gemeindelayer. Pro AGS werden vorhandene Teile vereinigt und `ST_PointOnSurface` gebildet; geprüft wird `ST_Covers`. Diese reproduzierbare Stichprobe misst weder Flächenanteil noch Bevölkerung, Straßen oder sämtliche Adressen einer Gemeinde. Ein Treffer kann eine nur teilweise abgedeckte Gemeinde betreffen. Selbst ein Wert von 100 % beweist keine lückenlose Fachzuständigkeit und keine Aktualität aller Gebiete. Dienstgrenzen haben unterschiedliche Generalisierung und Quelldatenstände.",'',
      'Die Länderliste bei Flächen nennt Länder mit mindestens einem solchen Referenzpunkttreffer; bei Standorten nennt sie Länder, in denen die importierten Punkte tatsächlich liegen. Keine dieser Listen behauptet eine vollständige Landesabdeckung. Bundesweit angebotene BZB-Open-Datensätze gibt es für Amtsgericht, Landgericht, Jobcenter und Arbeitsagentur.','',
      '## Alle 36 Kategorien','',
      '| Kategorie | Flächeneinträge | Gemeindeindikator | Länder mit Flächentreffern | Standorte und Länder | Quellen |',
      '| --- | ---: | ---: | --- | --- | --- |']
for c in summary['categories']:
 states=', '.join(v['state'] for v in c['municipal_reference_by_state']) or '–'
 pointstates=', '.join(v['state'] for v in c['location_states']) or '–'
 fraction=f"{c['municipal_reference_matches']}/{summary['reference_municipalities']} ({100*c['municipal_reference_matches']/summary['reference_municipalities']:.1f} %)" if c['resolution_mode']=='spatial' else 'Nicht allein räumlich bestimmbar'
 ids=[r['source_id']+(' [Punkt]' if r['geometry_kind']=='point' else '') for r in source_counts if r['category']==c['id']]
 head.append(f"| `{c['id']}` | {c['authority_count']} | {fraction} | {states} | {c['location_count']}; {pointstates} | {'; '.join(ids) or 'Keine importierte Quelle'} |")
head+=['','Länderkürzel: BW Baden-Württemberg, BY Bayern, BE Berlin, BB Brandenburg, HB Bremen, HH Hamburg, HE Hessen, MV Mecklenburg-Vorpommern, NI Niedersachsen, NW Nordrhein-Westfalen, RP Rheinland-Pfalz, SL Saarland, SN Sachsen, ST Sachsen-Anhalt, SH Schleswig-Holstein, TH Thüringen.','',
       '## Fachliche Grenzen je Kategorie','']
for c in summary['categories']:
 head.append(f"- **{c['label']} (`{c['id']}`)**: {c['limitations']} Standort-Radius als Anwendungsvorgabe: {radii[c['id']]} km.")
head+=['','## Flächen haben Vorrang vor Standorten','',
       'Die automatische Abfrage prüft relevante live erreichbare Fach-WFS und, wenn dort keine Fläche passt, lokale fachlich belegte Ergänzungen. Erst wenn die abgeschlossene Flächensuche keinen Treffer liefert, wird der lokale Standortindex mit geodätischer Entfernung abgefragt. Ein WFS-Fehler gilt nicht als leere Flächenabdeckung: Die Abfrage meldet den Fehler und gibt keinen verdeckten Standortersatz aus. Lokaler Betrieb ist ausdrücklich mit `--backend local` wählbar.','',
       'Standorte bleiben echte Punkte. Es werden keine Zuständigkeitskreise um Büros erzeugt. Antworten enthalten `fallback_used=true`, `match_type=nearest_point_fallback`, `distance_m`, den verwendeten Radius, `jurisdiction_verified=false` und einen Warntext. Standardmäßig werden höchstens drei mögliche Anlaufstellen zurückgegeben. `--no-point-fallback` schaltet dies ab; `--radius-km` passt den Radius zwischen größer 0 und höchstens 300 km an. Die Kategorienradien sind nachvollziehbare Anwendungsvorgaben, keine amtlichen Entfernungsregeln.','',
       'Bei Krankenkasse, Pflegekasse, Rentenversicherung und Bundesverwaltungsamt bleibt der Status `non_spatial`; bei weiteren aufgabenabhängigen Kategorien `context_required`. Ein gegebenenfalls ausgegebener Standort ist nur eine Kontaktmöglichkeit. Er ersetzt weder Mitgliedschaft noch Leistung, Verfahren, Schulart oder sonstigen fehlenden Kontext.','',
       '## GEMFA und kommunale Zuordnungen','',
       'Der offizielle BZSt-GEMFA-Export ist vollständig eingelesen und mit den VG25-Gemeinden verknüpft. Finanzamtsflächen entstehen nur für eindeutig zugeordnete ganze Gemeinden ohne widersprechende Adressausnahme. Geteilte Städte und nicht auflösbare Schlüssel werden ausgelassen und im Snapshot auditiert. Die vereinigten Flächen sind **belegte Teilmengen eines Finanzamtsbezirks**, nicht zwangsläufig der vollständige Bezirk (`geometry_completeness=verified_municipality_subset_of_jurisdiction`). Für die räumliche Anfrage bleibt dort eine Abdeckungslücke. Bayern und Hamburg liefern zusätzlich echte Fachpolygone. Steuerart und Sonderzuständigkeit werden nicht allein aus dem Ort entschieden.','',
       'Für Stadtverwaltungen werden ausschließlich explizite GEMFA-Felder mit Anrede Stadtverwaltung oder Gemeindeverwaltung genutzt. Verbandsgemeinde-, Amts- oder Verwaltungsgemeinschaftsnamen werden nicht aus der einzelnen Mitgliedsgemeinde erfunden. Weitere Ergänzungen stammen aus ausdrücklich belegten regionalen Zuordnungen in Sachsen, Hessen, Baden-Württemberg und Nordrhein-Westfalen sowie aus Thüringer Schulamtsflächen.','',
       '## Quellen und Lizenzen','',
       'Jede nachfolgende Zeile nennt die tatsächlich konfigurierte Quelle. Endpunkt, Layer, Filter, Namensregel, Aktualitätshinweise und Lizenz stehen zusätzlich im maschinenlesbaren [Quellenmanifest](../src/behoerden_resolver/resources/sources.json). Snapshots enthalten ihre historische Quellkonfiguration und Rohantwortprüfsummen. [delivery-manifest.json](../data/delivery-manifest.json) listet die tatsächlich ausgelieferten vollständigen Snapshots.','']
for s in sources():
 if s.get('active') is False:continue
 head.append(f"- **`{s['id']}`** — {s['scope']}; {s['kind']}; {s['license']}. [Quelle]({s['documentation']})"+(f"; WFS `{s['endpoint']}`, Layer `{s['layer']}`." if s.get('layer') else f"; Datenzugang `{s.get('download_url',s.get('endpoint',s['documentation']))}`."))
head+=['','**OSM-Abdeckung:** Nur ein vollständig geladener Suchbereich von 10 km um 50.0 N, 8.27 E im Raum Mainz/Wiesbaden ist integriert. Deutschlandweite und 16-Stadt-Abfragen überschritten die Zeitlimits und wurden verworfen. Die Punktabdeckung darf daher nicht als bundesweit vollständig bezeichnet werden. Die Quelle wird nur ausdrücklich aktualisiert, nicht im Standard-Refresh und nicht bei jeder Standortsuche.','','Die Datenlizenzen gelten unabhängig von der MIT-Lizenz des Programmcodes. OpenStreetMap-Daten sind gemeinschaftlich gepflegt und unter ODbL 1.0 lizenziert; Namensnennung und die einschlägigen Weitergabepflichten bleiben bei Nutzung der Standortdaten bestehen. Amtliche Punkte und OSM-Punkte werden mit ihrer jeweiligen Quelle und Qualität ausgewiesen.','',
       '## Aktualität und offene Quellen','',
       'Abrufdatum und fachlicher Datenstand sind verschieden. Der GEMFA-Export stammt vom 2. November 2026. Die Thüringer Gesundheits-, Veterinär- und Jugendamtsstandorte tragen im Atom-Eintrag den Stand 16. September 2022, die Schulamtsdatei den Stand 17. Juni 2024. Diese älteren Daten werden als solche mitgeführt. Gesetzliche und redaktionelle Zuordnungen sind am 13. November 2026 geprüft; ein Geometrieabruf erneuert diese Prüfung nicht.','',
       'BZB ohne Open und POI-Bund werden wegen Zugangsbeschränkungen nicht als freie Daten importiert. Der direkte bayerische Verwaltungsgerichtsflächenlayer enthält andere Institutionen und bleibt ausgeschlossen. Eine Berliner Bauaufsichtsressource wurde gefunden, war beim Abruf aber nicht mehr vorhanden. Weitere kommunale Zuordnungen sind offen; eine nicht integrierte Quelle wird nicht als nachgewiesene Abdeckung gezählt. [Recherche](RECHERCHE.md) und [Validierung](VALIDIERUNG.md) erläutern diese Entscheidungen.','',
       '## Geometriekontrolle','']
for table,values in summary['geometry_checks'].items():
 head.append(f"- `{table}`: {values['records']} Datensätze; {values['invalid']} ungültige Geometrien; {values['repaired']} als repariert markiert.")
head+=['','Polygonreparaturen nutzen GEOS make_valid, behalten alle Flächenteile und können kollabierte Reste ohne Fläche entfernen. Originalantworten und Reparaturkennzeichen bleiben erhalten. Die vollständigen Quellengeometrien werden bei Abfragen zurückgegeben; der Gemeindeindikator verändert keine Daten.']
(root/'docs/ABDECKUNG.md').write_text('\n'.join(head)+'\n')
inventory=[]
for path in latest_snapshots(root/'data/snapshots'):
 m=read_manifest(path)
 inventory.append({'directory':str(path.relative_to(root)),'source_id':m['source']['id'],'records_per_category':m['records_per_category'],'records_sha256':m['records_sha256'],'records_file_bytes':(path/'records.jsonl.gz').stat().st_size,'completed_at':m['completed_at']})
(root/'data/delivery-manifest.json').write_text(json.dumps({'generated_at':now(),'snapshots':inventory},ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:v for k,v in summary.items() if k not in ('categories','source_counts')},ensure_ascii=False,indent=2))
