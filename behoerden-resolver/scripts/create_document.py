"""Create the readable documentation from measured coverage, not stale constants."""
import json
from pathlib import Path
from docx import Document
from docx.shared import Cm,Pt,RGBColor
from docx.enum.table import WD_TABLE_ALIGNMENT,WD_CELL_VERTICAL_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.opc.constants import RELATIONSHIP_TYPE as RT

ROOT=Path(__file__).resolve().parents[1]
s=json.loads((ROOT/'data/coverage-summary.json').read_text())
sources=json.loads((ROOT/'src/behoerden_resolver/resources/sources.json').read_text())
radii=json.loads((ROOT/'src/behoerden_resolver/resources/fallback.json').read_text())['category_radius_km']
d=Document();sec=d.sections[0]
sec.page_height=Cm(29.7);sec.page_width=Cm(21)
sec.top_margin=Cm(1.8);sec.bottom_margin=Cm(1.8);sec.left_margin=Cm(1.7);sec.right_margin=Cm(1.7)
for name in ['Normal','Title','Subtitle','Heading 1','Heading 2','Heading 3']:
 st=d.styles[name];st.font.name='Arial';st.font.color.rgb=RGBColor(0,0,0)
 st.paragraph_format.space_after=Pt(6)
d.styles['Normal'].font.size=Pt(10)
d.styles['Normal'].paragraph_format.line_spacing=1.08
d.styles['Title'].font.size=Pt(23)
d.styles['Heading 1'].font.size=Pt(15)
d.styles['Heading 2'].font.size=Pt(12)
header=sec.header.paragraphs[0];header.text='Behördenresolver Deutschland   •   Datenstand und Abdeckung'
header.style='Normal';header.runs[0].font.size=Pt(8)
footer=sec.footer.paragraphs[0];footer.alignment=2
footer.add_run('Stand 13 November 2026   •   Seite ')
f=OxmlElement('w:fldSimple');f.set(qn('w:instr'),'PAGE');footer._p.append(f)
for r in footer.runs:r.font.size=Pt(8)

def p(text="",style=None):return d.add_paragraph(text,style)
def heading(text,level=1):d.add_heading(text,level)
def link(paragraph,text,url):
 h=OxmlElement('w:hyperlink');h.set(qn('r:id'),paragraph.part.relate_to(url,RT.HYPERLINK,is_external=True))
 r=OxmlElement('w:r');pr=OxmlElement('w:rPr');color=OxmlElement('w:color');color.set(qn('w:val'),'000000');pr.append(color)
 u=OxmlElement('w:u');u.set(qn('w:val'),'single');pr.append(u);r.append(pr)
 t=OxmlElement('w:t');t.text=text;r.append(t);h.append(r);paragraph._p.append(h)
def table(headers,rows,widths):
 t=d.add_table(rows=1,cols=len(headers));t.alignment=WD_TABLE_ALIGNMENT.CENTER;t.autofit=False
 props=t._tbl.tblPr;b=OxmlElement('w:tblBorders')
 for name in ['top','left','bottom','right','insideH','insideV']:
  x=OxmlElement('w:'+name);x.set(qn('w:val'),'single');x.set(qn('w:sz'),'4');x.set(qn('w:color'),'D9D9D9');b.append(x)
 props.append(b)
 for i,w in enumerate(widths):t.columns[i].width=Cm(w)
 for i,text in enumerate(headers):t.rows[0].cells[i].text=text
 repeat=OxmlElement('w:tblHeader');t.rows[0]._tr.get_or_add_trPr().append(repeat)
 for row in rows:
  cells=t.add_row().cells
  for i,text in enumerate(row):cells[i].text=str(text)
 for n,row in enumerate(t.rows):
  cant=OxmlElement('w:cantSplit');row._tr.get_or_add_trPr().append(cant)
  for i,c in enumerate(row.cells):
   c.width=Cm(widths[i]);c.vertical_alignment=WD_CELL_VERTICAL_ALIGNMENT.CENTER
   marg=OxmlElement('w:tcMar')
   for k in ['top','bottom','left','right']:
    e=OxmlElement('w:'+k);e.set(qn('w:w'),'75');e.set(qn('w:type'),'dxa');marg.append(e)
   c._tc.get_or_add_tcPr().append(marg)
   if n==0:
    fill=OxmlElement('w:shd');fill.set(qn('w:fill'),'EEEEEE');c._tc.get_or_add_tcPr().append(fill)
   for par in c.paragraphs:
    par.paragraph_format.space_after=Pt(2);par.paragraph_format.space_before=Pt(2)
    for r in par.runs:r.font.size=Pt(8.5);r.bold=(n==0)
 return t

for borders in d.styles.element.xpath('.//w:pBdr'):
 borders.getparent().remove(borders)

p('Behördenresolver Deutschland','Title')
p('Abdeckung Quellen und Standortergänzung','Subtitle')
p(f"Das ausführbare Projekt verarbeitet 36 Behördenkategorien und einen Punkt in WGS84. Der geladene Bestand enthält {format(s['authority_records'],',').replace(',','.')} Flächeneinträge in {s['categories_with_authorities']} Kategorien und {format(s['location_records'],',').replace(',','.')} Standortpunkte in {s['categories_with_locations']} Kategorien. Hinzu kommen {format(s['boundary_records'],',').replace(',','.')} reine Verwaltungsgebietsreferenzen. Nicht alle Kategorien besitzen bundesweit belegte Zuständigkeitsflächen.")
p('Diese Dokumentation zeigt für jede Kategorie den tatsächlich importierten Umfang, die verwendeten Quellen und verbleibende Lücken. Standortdaten erweitern die möglichen Anlaufstellen, belegen jedoch keine Zuständigkeit. Die Kennungen entsprechen dem benachbarten Behördenmatcher; dessen Programm wurde nicht verändert.')
heading('So entscheidet die Suche')
for text in [
 'Zuerst werden die für den Ort relevanten Fach WFS direkt abgefragt. Eine kleine BBOX liefert Kandidaten; die Prüfung erfolgt anschließend gegen das vollständige Polygon einschließlich Löchern und Grenzen.',
 'Wenn kein WFS Polygon passt, prüft der automatische Modus lokale, fachlich belegte Ergänzungen in PostGIS. Reine Verwaltungsgrenzen werden nicht als Fachzuständigkeiten ausgegeben.',
 'Erst ohne Flächentreffer werden nahegelegene echte Standortpunkte gesucht. Die Antwort nennt Entfernung und Radius sowie fallback_used=true und jurisdiction_verified=false. Bei einem WFS Fehler wird kein verdeckter Standortersatz ausgegeben.'
]:p(text,'List Number')
p('Die Standardradien sind Anwendungsvorgaben, keine amtlichen Entfernungsregeln. Sie sind pro Kategorie in fallback.json hinterlegt und überschreibbar. Standardmäßig werden bis zu drei nahe Punkte ausgegeben; --point-limit 1 liefert nur den nächsten. --no-point-fallback deaktiviert diese Ergänzung. Es werden keine Zuständigkeitskreise aus Büropunkten erzeugt.')
heading('Was die Abdeckungszahlen bedeuten')
p(f"Der Gemeindeindikator prüft je einem Repräsentativpunkt der {s['reference_municipalities']} geladenen VG25 Gemeindeschlüssel gegen die lokalen Fachpolygone. Vorhandene Teile eines AGS werden vereinigt und ST_PointOnSurface gebildet. Der Indikator misst weder Bevölkerung noch Fläche oder alle Adressen. Ein Treffer kann nur einen Teil einer Gemeinde betreffen; selbst 100 Prozent sind kein Vollständigkeitsbeweis.")
p('Die Länderliste bezeichnet Länder mit mindestens einem gemessenen Flächentreffer oder Standort. Sie bedeutet keine vollständige Landesabdeckung. Für ortsunabhängige und vom Anliegen abhängige Kategorien ist ein räumlicher Prozentwert nicht anwendbar. Alle Zahlen sind Quellzeilen; Institutionen und Dienststellen können mehrfach vorkommen.')

# Compact comparison with deliberate page boundaries and twelve records per page.
for offset in range(0,36,12):
 d.add_page_break();heading('Abdeckung je Kategorie'+(' Fortsetzung' if offset else ''))
 p('Flächen sind lokale Quellzeilen. Indikator ist der Anteil erfasster Gemeinde Referenzpunkte. Standorte werden nur nach erfolgloser Flächensuche verwendet.')
 rows=[]
 for c in s['categories'][offset:offset+12]:
  states=', '.join(v['state'] for v in c['municipal_reference_by_state']) or '–'
  if len(c['municipal_reference_by_state'])==16:states='Alle 16 Länder'
  points=', '.join(v['state'] for v in c['location_states']) or '–'
  if len(c['location_states'])==16:points='Alle 16 Länder'
  ind=f"{100*c['municipal_reference_matches']/s['reference_municipalities']:.1f} %" if c['resolution_mode']=='spatial' else 'Kontext nötig'
  rows.append([c['id'],str(c['authority_count'])+'\n'+ind,states,str(c['location_count'])+'\n'+points])
 table(['Kategorie','Flächen und Indikator','Länder mit Flächentreffern','Standorte und Länder'],rows,[4.4,3.1,4.7,5.4])
 p('Länderkürzel entsprechen ISO 3166 2 ohne DE Präfix. Alle 16 Länder: BW BY BE BB HB HH HE MV NI NW RP SL SN ST SH TH. Ein Nullwert kennzeichnet fehlende importierte Daten, keine fehlende Behörde.')
 heading('Quellen dieser Kategorien',2)
 for c in s['categories'][offset:offset+12]:
  ids=[r['source_id']+(' (Punkt)' if r['geometry_kind']=='point' else '') for r in s['source_counts'] if r['category']==c['id']]
  par=p(c['id']+': '+('; '.join(ids) if ids else 'Keine importierte Quelle.'))
  par.paragraph_format.space_after=Pt(3)
  for r in par.runs:r.font.size=Pt(8)

d.add_page_break();heading('Fachliche Grenzen je Kategorie')
for c in s['categories']:
 par=p();run=par.add_run(c['label']+' ');run.bold=True
 par.add_run(c['limitations']+f" Standort Radius {radii[c['id']]} km.")
 par.paragraph_format.space_after=Pt(7)
heading('GEMFA und vollständige Geometrien')
p('Der vollständige offizielle BZSt Export vom 2. November 2026 ist eingelesen. Eindeutige ganze Gemeinden ohne widersprechende Adressausnahme werden über ihren exakten AGS mit VG25 verbunden. Für 411 Finanzämter entstehen belegte Teilmengen ihres Bezirks. Diese Geometrien sind vollständig für die verarbeiteten Gemeindezuordnungen, aber nicht zwangsläufig für den gesamten Finanzamtsbezirk. Geteilte Gemeinden und nicht auflösbare Schlüssel bleiben offen. Bayern und Hamburg ergänzen echte Fachpolygone.')
p('Die Antwort weist GEMFA Teilmengen mit geometry_completeness=verified_municipality_subset_of_jurisdiction aus. Originalattribute, Namensregel, Beleglink, Lizenz und Source ID bleiben erhalten. Explizite GEMFA Anreden Stadtverwaltung oder Gemeindeverwaltung ermöglichen zusätzlich begrenzte kommunale Zuordnungen. Verwaltungsverbände werden nicht aus Mitgliedsgemeinden geraten.')
heading('Aktualität und Ausschlüsse')
p('Die Thüringer Gesundheits-, Veterinär- und Jugendamtsstandorte tragen im Atom Eintrag den Stand 16. September 2022, Schulamtsflächen den Stand 17. Juni 2024. Das Abrufdatum ist kein Nachweis einer neuen fachlichen Fortschreibung. Gesetzliche und redaktionelle Zuordnungen wurden am 13. November 2026 geprüft; ein erneuter Geometrieabruf aktualisiert diese Prüfung nicht.')
p('BZB ohne Open und POI Bund wurden nicht als frei nutzbare Quellen importiert. Der bayerische direkte Verwaltungsgerichtsflächenlayer enthält andere Institutionen und bleibt ausgeschlossen. Stattdessen wird die ausdrückliche gesetzliche Zuordnung der sechs Gerichte zu VG25 Regierungsbezirken verwendet. Eine Berliner Bauaufsichtsressource war beim Abruf nicht mehr verfügbar und wird nicht zur Abdeckung gezählt.')
heading('Quellen und Lizenzen')
p('Die folgenden IDs verweisen auf die je Kategorie genannten Importquellen. Das vollständige Manifest sources.json nennt zusätzlich genaue WFS Endpunkte, Layer, Filter, Lizenz URLs, Namensnennung und Verarbeitung. Jeder Snapshot enthält seine historische Konfiguration, Rohantworten und Prüfsummen. delivery-manifest.json listet die tatsächlich ausgelieferten Snapshots.')
for source in sources:
 if source.get('active') is False:continue
 par=p();r=par.add_run(source['id']);r.bold=True
 par.add_run('  '+source['scope']+'  •  '+source['kind']+'\n'+source['license']+'\n')
 link(par,'Amtliche Dokumentation' if source.get('source_quality')!='community' else 'Gemeinschaftsdaten und Lizenz',source['documentation'])
 if source.get('layer'):par.add_run('   Layer '+source['layer'])
 par.paragraph_format.keep_together=True
 par.paragraph_format.space_after=Pt(7)
 for r in par.runs:r.font.size=Pt(8.5)
p('Der integrierte OSM Abzug ist auf einen Suchbereich von 10 km um 50.0 N und 8.27 E im Raum Mainz und Wiesbaden begrenzt. Große Deutschlandabfragen und ein Versuch mit 16 Stadtbereichen überschritten die Zeitlimits und wurden verworfen. Daraus entsteht keine bundesweite Punktabdeckung. Der OSM Refresh ist ausdrücklich optional und erfolgt nicht bei jeder Resolverabfrage.')
p('Die MIT Lizenz gilt für den Programmcode. Daten behalten ihre jeweilige Lizenz. OpenStreetMap Standorte sind gemeinschaftlich gepflegt, nicht amtlich, und unter ODbL 1.0 lizenziert. Bei Nutzung und Weitergabe sind die Quellenangabe sowie einschlägige Weitergabepflichten zu beachten. OSM Quellzeilen bleiben vom amtlichen Flächenbestand unterscheidbar.')
heading('Nutzung und Prüfbarkeit')
p('Start im Projektordner: docker compose up -d db, danach docker compose build cli und docker compose run --rm cli load. Beispiel: docker compose run --rm cli resolve jobcenter --lat 49.488 --lon 8.466. Eine vollständige Anleitung mit allen Optionen steht in README.md. scripts/report.py erzeugt die Abdeckungszahlen erneut aus der laufenden Datenbank.')
p('Automatisierte Tests prüfen Flächenlöcher und Grenzmehrdeutigkeit, WFS Paging und Koordinatensysteme, atomare Importe, echte geodätische Entfernungen und den zwingenden Vorrang von Flächen vor Standorten. Aktuelle Testergebnisse und ausgeführte Containerabfragen stehen in docs/VALIDIERUNG.md. Die Lücken bleiben in dieser Dokumentation und in der JSON Antwort sichtbar.')
out=ROOT/'docs/Behoerdenresolver_Abdeckung_und_Quellen.docx'
for par in d.paragraphs:
 if par.style.name=='Normal':par.paragraph_format.keep_together=True
d.save(out);print(out)
