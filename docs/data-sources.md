# Data sources

Source notes checked on 10 November 2026.

## Services and authorities

The [Portalverbund Online-Gateway (PVOG)](https://pvog.fitko.de/) combines records from federal and state administrative portals. Its [search API](https://docs.fitko.de/pvog/docs/suchdienst/technisches_design/schnittstellen/if_010_if_016/) is accessible without authentication. The app searches by task and official regional key (ARS), then retrieves the selected service and associated authorities.

Coverage and detail vary. Some records lack contacts or opening hours; others identify a municipality or several offices rather than a specific counter. Source timestamps describe record updates, not a guarantee that every detail is current. Follow the linked source portal when checking or reusing its content. Official text is kept in its original wording and may only be available in German.

The [BayernPortal API](https://www.bayernportal-webservices.bayern.de/restapi.htm) requires a user account and is not connected directly. Bavarian records can be returned through PVOG.

## Boundaries and map

| Source | Use | Source notice |
| --- | --- | --- |
| [BKG VG250 WFS](https://gdz.bkg.bund.de/index.php/default/open-data/wfs-verwaltungsgebiete-1-250-000-stand-01-01-wfs-vg250.html) | Municipal boundaries and ARS. The product page listed 1 January 2025 as its data date when checked. | © BKG, year of access, dl-de/by-2-0; [VG data sources](https://sgx.geodatenzentrum.de/web_public/gdz/datenquellen/datenquellen_vg_nuts.pdf). |
| [BKG TopPlusOpen WMS](https://gdz.bkg.bund.de/index.php/default/wms-topplusopen-wms-topplus-open.html) | Grey background map, layer `web_grau`. | © BKG, year of access, dl-de/by-2-0; [TopPlusOpen data sources](https://sgx.geodatenzentrum.de/web_public/gdz/datenquellen/datenquellen_topplusopen.html). |

Both use [Data licence Germany – attribution 2.0](https://www.govdata.de/dl-de/by-2-0). The app links [BKG](https://www.bkg.bund.de), the licence and source directories. It selects boundary features for matching and reports geometry repairs. VG250 is generalised for 1:250,000 and may differ from current or detailed boundaries. WMS images provide the background, not the analysis geometry.

The separate notebook and older lookup endpoint use [BZB-Open](https://gdz.bkg.bund.de/index.php/default/wfs-behoerdenzustaendigkeitsbereiche-open-wfs-bzb-open.html), covering seven employment-administration and court categories. Its [source directory](https://sgx.geodatenzentrum.de/web_public/gdz/datenquellen/datenquellen_bzb-open.pdf) and attribution apply when that work is reused.

## Address search

- **[Public Nominatim](https://operations.osmfoundation.org/policies/nominatim/):** no autocomplete, at most one request per second across the application, and an identifying application header. The local server serializes requests and caches results briefly in memory. This does not coordinate multiple server processes or installations.
- **[Photon demo server](https://github.com/komoot/photon#demo-server):** supports suggestions but requires moderate use and can throttle or block traffic. A compatible own instance can be configured.

Both use OpenStreetMap data; [OpenStreetMap attribution](https://www.openstreetmap.org/copyright) is linked in the footer. Check the provider terms before changing the deployment or traffic level.

Address text goes to the chosen geocoder, the task and ARS go to PVOG, and the selected point goes to BKG. The geocoder cache holds up to 100 searches for five minutes; expired entries are removed on the next request. Searches are not intentionally saved to disk, but providers and hosting infrastructure may keep logs. Avoid confidential information in searches.
