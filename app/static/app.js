'use strict';
const strings = {
  de: {
    skip:'Zum Inhalt springen', brand:'Zuständigkeitsfinder', settings:'Einstellungen', languageLabel:'Sprache', provider:'Adresssuchdienst',
    title:'Behördenzuständigkeit finden.', subtitle:'Anliegen und Standort eingeben.', concernLabel:'Anliegen', concernPlaceholder:'z. B. Auto anmelden', addressLabel:'Ort oder Adresse', addressPlaceholder:'Ort, Postleitzahl oder Adresse', addressSearch:'Ort suchen', find:'Zuständigkeit finden',
    privacyInfo:'Informationen zur Suche', privacy:'Der Suchtext wird an den Portalverbund, die Adresse an den ausgewählten Adresssuchdienst gesendet. Keine vertraulichen Daten eingeben. Bei Kartenauswahl wird keine Adresse an den Adresssuchdienst übermittelt.', noLocation:'Noch kein Standort ausgewählt', chooseMap:'Standort auf der Karte wählen', mapHelp:'Standort durch Klicken auswählen', map:'Karte', mapError:'Karte nicht verfügbar. Internetverbindung prüfen.',
    resultTitle:'Suchergebnis', sources:'Quellen', dataSources:'Datenquellen BZB', modified:'Gebiete zur Standortzuordnung ausgewählt; Geometrien bei Bedarf repariert.',
    nominatimNote:'Nominatim: Suche nur nach Bestätigung, keine automatischen Vorschläge. Höchstens eine Anfrage pro Sekunde für die gesamte Anwendung.', photonNote:'Photon: Vorschläge während der Eingabe. Öffentlicher Demo-Dienst, nur für maßvolle Nutzung.', providerPolicy:'Nutzungsbedingungen',
    enterConcern:'Anliegen eingeben.', enterAddress:'Ort oder Adresse eingeben.', chooseCandidate:'Passenden Standort auswählen:', noCandidates:'Kein passender Standort gefunden.', searchingAddress:'Standort wird gesucht …', failedSearch:'Adresssuche nicht verfügbar. Erneut versuchen oder Standort auf der Karte wählen.',
    outside:'Standort innerhalb Deutschlands wählen.', finding:'Zuständigkeit wird gesucht …', noPlace:'Keine Gemeinde für diesen Standort gefunden. Standort auf der Karte prüfen.', ambiguous:'Der Standort liegt an einer Gemeindegrenze. Gemeinde auswählen:', repaired:'Die Standortgeometrie wurde für die Analyse repariert. Die Zuordnung sollte vor allem an Grenzen geprüft werden.',
    failedPlace:'Gemeinde konnte nicht ermittelt werden. Erneut versuchen.', failedService:'Leistungssuche derzeit nicht verfügbar. Erneut versuchen.', noServices:'Keine passende Leistung gefunden. Anderen Suchbegriff verwenden.', chooseService:'Passendes Anliegen auswählen', possibleServices:'Passende Leistungen', moreDetails:'Details anzeigen', loadingDetails:'Informationen werden geladen …', failedDetails:'Informationen derzeit nicht verfügbar. Erneut versuchen.',
    resultFor:'Leistung', places:'Zugeordnete Stellen', noAuthorities:'Für diese Leistung wurde keine zuständige Stelle übermittelt.', incomplete:'Weitere Stellen sind vorhanden. Vollständige Angaben im Quellportal prüfen.', unavailable:'Einzelheiten momentan nicht verfügbar.', address:'Anschrift laut Quelle', hours:'Öffnungszeiten (Originalangaben)', contact:'Kontakt', directions:'Anfahrt anzeigen', duties:'Weitere Aufgaben (Originalangaben)', services:'Onlinedienste und Termine', source:'Offizielle Quelle', lastUpdated:'Stand der Quelldaten', print:'Auskunft drucken', back:'Zurück zur Auswahl',
    approx:'Die Gemeinde wurde anhand generalisierter BKG-Grenzen zugeordnet. Bei Grenzlagen und Sonderzuständigkeiten das Quellportal prüfen. Anschriften können allgemeine Behördenanschriften sein; den zuständigen Standort und die Öffnungszeiten vor einem Besuch bestätigen.',
    translatedData:'Angaben stammen aus dem jeweiligen Verwaltungsportal und können nur auf Deutsch vorliegen.', noAddress:'Keine Besuchsadresse angegeben.', noHours:'Keine Öffnungszeiten angegeben.', noContact:'Keine Kontaktdaten angegeben.', mapPoint:'Kartenpunkt', chooseMunicipality:'Gemeinde auswählen', nominatimPolicy:'https://operations.osmfoundation.org/policies/nominatim/', photonPolicy:'https://github.com/komoot/photon#demo-server'
  },
  en: {
    skip:'Skip to content', brand:'Authority finder', settings:'Settings', languageLabel:'Language', provider:'Address search provider',
    title:'Find the responsible authority.', subtitle:'Enter a concern and a location. German search terms may return more results.', concernLabel:'Concern', concernPlaceholder:'e.g. Auto anmelden', addressLabel:'Town or address', addressPlaceholder:'Town, postcode or address', addressSearch:'Find location', find:'Find authority',
    privacyInfo:'About this search', privacy:'The search text is sent to the German administrative portal network; the address is sent to the selected geocoder. Do not enter confidential information. Selecting a point on the map avoids sending an address to the geocoder.', noLocation:'No location selected yet', chooseMap:'Choose a location on the map', mapHelp:'Click the map to select a location', map:'Map', mapError:'Map unavailable. Check the internet connection.',
    resultTitle:'Search result', sources:'Sources', dataSources:'BZB data sources', modified:'Areas selected for location matching; geometries repaired where necessary.',
    nominatimNote:'Nominatim: searches only after confirmation; no automatic suggestions. The entire application must make no more than one request per second.', photonNote:'Photon: suggestions as text is entered. Public demo service; moderate use only.', providerPolicy:'Usage policy',
    enterConcern:'Enter a concern.', enterAddress:'Enter a town or address.', chooseCandidate:'Select a matching location:', noCandidates:'No matching location found.', searchingAddress:'Finding locations …', failedSearch:'Address search is unavailable. Try again or choose a location on the map.',
    outside:'Choose a location in Germany.', finding:'Finding the responsible authority …', noPlace:'No municipality was found for this location. Check the location on the map.', ambiguous:'The point lies on a municipal boundary. Select a municipality:', repaired:'The location geometry was repaired for analysis. Check the assignment, especially near boundaries.',
    failedPlace:'Municipality unavailable. Try again.', failedService:'Service search unavailable. Try again.', noServices:'No matching service found. Try a different search term.', chooseService:'Select the relevant service', possibleServices:'Matching services', moreDetails:'Show details', loadingDetails:'Loading information …', failedDetails:'Information unavailable. Try again.',
    resultFor:'Service', places:'Associated authorities', noAuthorities:'No responsible authority was supplied for this service.', incomplete:'More authorities are available. Check the source portal for the complete list.', unavailable:'Details are currently unavailable.', address:'Address from source', hours:'Opening hours (source text)', contact:'Contact', directions:'View directions', duties:'Other responsibilities (source text)', services:'Online services and appointments', source:'Official source', lastUpdated:'Source data updated', print:'Print result', back:'Back to results',
    approx:'The municipality was matched using generalised BKG boundaries. Check the source portal for boundary cases and special responsibilities. Addresses may be general authority addresses; confirm the service location and opening hours before visiting.',
    translatedData:'Information comes from the relevant administrative portal and may only be available in German.', noAddress:'No visiting address provided.', noHours:'No opening hours provided.', noContact:'No contact details provided.', mapPoint:'Map point', chooseMunicipality:'Select a municipality', nominatimPolicy:'https://operations.osmfoundation.org/policies/nominatim/', photonPolicy:'https://github.com/komoot/photon#demo-server'
  }
};
const $ = id => document.getElementById(id);
const t = key => strings[lang][key];
let lang = 'de', selected = null, marker = null, map = null, timer = null;
let geocodeSequence = 0, searchSequence = 0, lastSearch = null, lastDetail = null;
Object.assign(strings.de, {moreResults:'Weitere Leistungen laden', loadingMore:'Weitere Leistungen werden geladen …', failedMore:'Weitere Leistungen konnten nicht geladen werden. Erneut versuchen.', retry:'Erneut versuchen', duties:'Aufgaben und Zuständigkeiten (Originalangaben)', updatedRecord:'Datensatz aktualisiert'});
Object.assign(strings.en, {moreResults:'Load more services', loadingMore:'Loading more services …', failedMore:'More services could not be loaded. Try again.', retry:'Try again', duties:'Responsibilities (source text)', updatedRecord:'Record updated'});

function setLanguage(next) {
  lang = next; document.documentElement.lang = lang; document.title = t('brand');
  document.querySelectorAll('[data-i18n]').forEach(el => el.textContent = t(el.dataset.i18n));
  document.querySelectorAll('[data-i18n-aria]').forEach(el => { el.setAttribute('aria-label', t(el.dataset.i18nAria)); if (el.hasAttribute('title')) el.title = t(el.dataset.i18nAria); });
  $('language').textContent = lang === 'de' ? 'English' : 'Deutsch'; $('language').lang = lang === 'de' ? 'en' : 'de';
  $('concern').placeholder = t('concernPlaceholder'); $('address').placeholder = t('addressPlaceholder');
  updateProvider(); updateLocation();
  if (lastDetail) renderDetail(lastDetail, false); else if (lastSearch) renderServices(lastSearch, false);
}
function updateProvider() {
  const isNominatim = $('provider').value === 'nominatim';
  $('provider-note').replaceChildren(document.createTextNode(t(isNominatim ? 'nominatimNote' : 'photonNote') + ' '));
  const link=document.createElement('a'); link.href=t(isNominatim ? 'nominatimPolicy' : 'photonPolicy'); link.textContent=t('providerPolicy'); $('provider-note').append(link);
  $('candidates').replaceChildren(); clearTimeout(timer); geocodeSequence++;
}
function updateLocation() { $('location').textContent = selected ? `${selected.label || t('mapPoint')} (${selected.lat.toFixed(5)}, ${selected.lon.toFixed(5)})` : t('noLocation'); }
function clearResult() { lastDetail=null; lastSearch=null; searchSequence++; $('result-section').hidden=true; $('result').replaceChildren(); }
function showMessage(message) { $('result-section').hidden=false; const box=$('result'); box.className='result-empty'; box.replaceChildren(); const p=document.createElement('p'); p.textContent=message; box.append(p); }
function setLocation(lat, lon, label='') {
  if (!(lat>=47 && lat<=56 && lon>=5 && lon<=16)) {
    selected=null; clearResult(); updateLocation();
    if(marker && map) {map.removeLayer(marker); marker=null;}
    showMessage(t('outside')); return false;
  }
  selected={lat,lon,label}; clearResult(); updateLocation();
  if (map) { if(marker) map.removeLayer(marker); marker=L.circleMarker([lat,lon],{radius:8,color:'#fff',weight:3,fillColor:'#b62331',fillOpacity:1}).addTo(map); }
  return true;
}
async function post(url, payload) { const response=await fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)}); if (!response.ok) throw new Error('request'); return response.json(); }
async function geocode(autocomplete=false, searchAfter=false) {
  const q=$('address').value.trim(), provider=$('provider').value, sequence=++geocodeSequence;
  if(q.length<3) { if(!autocomplete) $('candidates').textContent=t('enterAddress'); return; }
  $('candidates').textContent=t('searchingAddress');
  try {
    const data=await post('/api/geocode',{q,provider,autocomplete}); if(sequence!==geocodeSequence) return;
    $('candidates').replaceChildren();
    if(!data.length) { $('candidates').textContent=t('noCandidates'); return; }
    const title=document.createElement('p'); title.textContent=t('chooseCandidate'); $('candidates').append(title);
    data.forEach(item=>{const button=document.createElement('button'); button.type='button';button.className='candidate';button.textContent=item.label;button.addEventListener('click',()=>{geocodeSequence++; if(!setLocation(item.lat,item.lon,item.label)) return; if(map) map.setView([item.lat,item.lon],13); $('candidates').replaceChildren(); if(searchAfter && $('concern').value.trim().length>=2) startSearch();});$('candidates').append(button);});
  } catch {if(sequence===geocodeSequence) $('candidates').textContent=t('failedSearch');}
}
function element(tag, className, text) { const node=document.createElement(tag); if(className) node.className=className; if(text) node.textContent=text; return node; }
function addLink(container, url, label) { try { const parsed=new URL(url); if(!['http:','https:'].includes(parsed.protocol)) return; const a=element('a','external-link',label); a.href=parsed.href; a.target='_blank'; a.rel='noopener noreferrer'; container.append(a); } catch {} }
function focusResult() { const heading=$('result').querySelector('h2'); if(heading) {heading.tabIndex=-1;heading.focus();} }
function renderServices(result, moveFocus=true) {
  $('result-section').hidden=false; const root=$('result'); root.className='result-card'; root.replaceChildren();
  root.append(element('p','kicker',`${result.place.name}${result.place.state ? ', '+result.place.state : ''}`),element('h2','results-heading',t('possibleServices')));
  if(result.repaired) root.append(element('p','notice',t('repaired')));
  if(!result.services.length) {root.append(element('p','empty-copy',t('noServices')));if(moveFocus)focusResult();return;}
  root.append(element('p','result-instruction',t('chooseService')));
  for(const item of result.services) {const button=element('button','service-option');button.type='button';button.append(element('strong','',item.name));button.addEventListener('click',()=>loadDetail(result,item));root.append(button);}
  if(result.hasMore) {
    const more=element('button','secondary more-button',t('moreResults'));more.type='button';
    more.addEventListener('click',()=>loadMore(result,more));root.append(more);
  }
  if(moveFocus) focusResult();
}
async function loadMore(result,button) {
  const sequence=++searchSequence;button.disabled=true;button.textContent=t('loadingMore');
  try {
    const data=await post('/api/services',{ars:result.place.ars,q:result.query,page:result.page+1});
    if(sequence!==searchSequence)return;
    const known=new Set(result.services.map(item=>item.id));
    result.services.push(...data.services.filter(item=>!known.has(item.id)));
    result.page=data.page;result.hasMore=data.has_more;renderServices(result,false);
    const options=$('result').querySelectorAll('.service-option');if(options.length)options[Math.min(options.length-1,known.size)].focus();
  }catch{if(sequence===searchSequence){button.disabled=false;button.textContent=t('retry');button.insertAdjacentElement('beforebegin',element('p','field-note',t('failedMore')));}}
}
function renderDetail(detail, moveFocus=true) {
  $('result-section').hidden=false; const root=$('result');root.className='result-card';root.replaceChildren();
  const back=element('button','back-button','← '+t('back'));back.type='button';back.addEventListener('click',()=>{searchSequence++;lastDetail=null;renderServices(lastSearch);});root.append(back,element('p','kicker',`${t('resultFor')} · ${detail.place.name}`),element('h2','results-heading',detail.name));
  if(lang==='en') root.append(element('p','field-note',t('translatedData')));
  const print=element('button','secondary print-button',t('print'));print.type='button';print.addEventListener('click',()=>window.print());root.append(print);
  if(detail.repaired) root.append(element('p','notice',t('repaired')));
  if(detail.truncated) root.append(element('p','notice',t('incomplete')));
  root.append(element('h3','section-title',t('places')));
  if(!detail.organizations.length)root.append(element('p','empty-copy',t('noAuthorities')));
  detail.organizations.forEach(org=>{
    const card=element('article','authority');card.append(element('h4','',org.name));if(org.role)card.append(element('p','authority-role',org.role));
    if(org.details_unavailable){card.append(element('p','empty-copy',t('unavailable')));root.append(card);return;}
    const grid=element('div','detail-grid');
    const address=element('div','detail-block');address.append(element('strong','',t('address')));
    if(org.addresses.length) org.addresses.forEach(a=>{if(a.text)address.append(element('p','',a.text));const lat=Number(a.latitude),lon=Number(a.longitude); if(a.latitude!=null&&a.longitude!=null&&Number.isFinite(lat)&&Number.isFinite(lon)&&lat>=47&&lat<=56&&lon>=5&&lon<=16)addLink(address,`https://www.openstreetmap.org/directions?to=${encodeURIComponent(lat+','+lon)}`,t('directions'));if(a.accessibility)address.append(element('p','field-note',a.accessibility));}); else address.append(element('p','',t('noAddress')));grid.append(address);
    const contact=element('div','detail-block');contact.append(element('strong','',t('contact')));if(org.communications.length)org.communications.forEach(c=>contact.append(element('p','',`${c.name}: ${c.value}`)));else contact.append(element('p','',t('noContact')));grid.append(contact);card.append(grid);
    const hours=element('details','inline-details');hours.append(element('summary','',t('hours')));if(org.hours.length)org.hours.forEach(text=>hours.append(element('p','source-text',text)));else hours.append(element('p','empty-copy',t('noHours')));card.append(hours);
    if(org.description){const duties=element('details','inline-details');duties.append(element('summary','',t('duties')),element('p','source-text',org.description));card.append(duties);}
    if(org.links.length){const links=element('div','link-list');org.links.forEach(x=>addLink(links,x.url,x.title));card.append(links);}root.append(card);
    if(org.updated)card.append(element('p','field-note',`${t('updatedRecord')}: ${org.updated.slice(0,10)}`));
  });
  if(detail.links.length){const box=element('div','result-links');box.append(element('h3','section-title',t('services')));detail.links.forEach(x=>addLink(box,x.url,x.title));root.append(box);}
  const provenance=element('details','evidence');provenance.append(element('summary','',t('source')),element('p','',t('approx')));if(detail.updated)provenance.append(element('p','field-note',t('lastUpdated')+': '+detail.updated.slice(0,10)));detail.sources.forEach(x=>addLink(provenance,x.url,x.title));addLink(provenance,'https://pvog.fitko.de/','Portalverbund Online-Gateway');root.append(provenance);
  if(moveFocus) focusResult();
}
async function loadDetail(result,item) {
  const sequence=++searchSequence; showMessage(t('loadingDetails'));
  try {const data=await post('/api/service-detail',{id:item.id,ars:result.place.ars});if(sequence!==searchSequence)return;lastDetail={...data,sources:data.sources.length?data.sources:(item.sources||[]),place:result.place,repaired:result.repaired};renderDetail(lastDetail);}catch{
    if(sequence!==searchSequence)return;
    showMessage(t('failedDetails'));
    const back=element('button','secondary',t('back'));back.type='button';back.addEventListener('click',()=>renderServices(result));
    const retry=element('button','secondary',t('retry'));retry.type='button';retry.addEventListener('click',()=>loadDetail(result,item));$('result').append(back,retry);
  }
}
async function searchPlace(place,repaired,sequence) {
  const query=$('concern').value.trim();
  try {const data=await post('/api/services',{ars:place.ars,q:query});if(sequence!==searchSequence)return;lastSearch={place,services:data.services,repaired,query,page:data.page,hasMore:data.has_more};lastDetail=null;renderServices(lastSearch);}catch{if(sequence===searchSequence)showMessage(t('failedService'));}
}
async function startSearch() {
  const concern=$('concern').value.trim(); if(concern.length<2){showMessage(t('enterConcern'));$('concern').focus();return;}
  if(!selected){if($('address').value.trim().length<3){showMessage(t('enterAddress'));$('address').focus();return;}geocode(false,true);return;}
  const sequence=++searchSequence;lastSearch=null;lastDetail=null;showMessage(t('finding'));
  try {const data=await post('/api/municipalities',{lat:selected.lat,lon:selected.lon});if(sequence!==searchSequence)return;if(!data.places.length){showMessage(t('noPlace'));return;}if(data.places.length===1){await searchPlace(data.places[0],data.geometry_repaired,sequence);return;}
    const root=$('result');root.className='result-card';root.replaceChildren(element('h2','results-heading',t('chooseMunicipality')),element('p','result-instruction',t('ambiguous')));
    data.places.forEach(place=>{const button=element('button','service-option',`${place.name} (${place.state})`);button.type='button';button.addEventListener('click',()=>{const next=++searchSequence;showMessage(t('finding'));searchPlace(place,data.geometry_repaired,next);});root.append(button);});
  }catch{if(sequence===searchSequence)showMessage(t('failedPlace'));}
}
$('year').textContent=new Date().getFullYear();
$('language').addEventListener('click',()=>setLanguage(lang==='de'?'en':'de'));
$('provider').addEventListener('change',updateProvider);
$('search-form').addEventListener('submit',event=>{event.preventDefault();clearTimeout(timer);startSearch();});
$('address-button').addEventListener('click',()=>{clearTimeout(timer);geocode(false,false);});
$('address').addEventListener('input',()=>{selected=null;updateLocation();clearResult();clearTimeout(timer);geocodeSequence++;$('candidates').replaceChildren();if($('provider').value==='photon'&&$('address').value.trim().length>=5)timer=setTimeout(()=>geocode(true,false),800);});
$('concern').addEventListener('input',clearResult);
$('map-details').addEventListener('toggle',()=>{if($('map-details').open&&map)map.invalidateSize();});
let printDetails=[];
window.addEventListener('beforeprint',()=>{printDetails=[...$('result').querySelectorAll('details')].filter(node=>!node.open);printDetails.forEach(node=>node.open=true);});
window.addEventListener('afterprint',()=>{printDetails.forEach(node=>node.open=false);printDetails=[];});
document.querySelectorAll('.info-button').forEach(button=>{button.addEventListener('click',()=>{const open=button.getAttribute('aria-expanded')!=='true';button.setAttribute('aria-expanded',String(open));button.parentElement.classList.toggle('is-open',open);});button.parentElement.addEventListener('focusout',event=>{if(!button.parentElement.contains(event.relatedTarget)){button.setAttribute('aria-expanded','false');button.parentElement.classList.remove('is-open');}});button.addEventListener('keydown',event=>{if(event.key==='Escape'){button.setAttribute('aria-expanded','false');button.parentElement.classList.remove('is-open');button.blur();}});});
if(window.L){map=L.map('map').setView([51.1,10.4],6);L.tileLayer.wms('https://sgx.geodatenzentrum.de/wms_topplus_open',{layers:'web_grau',format:'image/png',version:'1.3.0',attribution:'Kartendarstellung: © <a href="https://www.bkg.bund.de">BKG</a> ('+new Date().getFullYear()+') <a href="https://www.govdata.de/dl-de/by-2-0">dl-de/by-2-0</a>, <a href="https://sgx.geodatenzentrum.de/web_public/gdz/datenquellen/datenquellen_topplusopen.html">Datenquellen</a>'}).addTo(map);map.on('click',e=>{clearTimeout(timer);geocodeSequence++;$('address').value='';setLocation(e.latlng.lat,e.latlng.lng);$('candidates').replaceChildren();});}else $('map-error').hidden=false;
setLanguage('de');
