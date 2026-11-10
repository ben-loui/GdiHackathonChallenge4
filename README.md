# Authority finder for Germany

A prototype for Challenge 4 at hack4GDI_DE. Enter a task such as `Auto anmelden`, choose a location and select the matching service. The result lists the associated authorities, with addresses, contacts, opening hours and online services where available.

The interface supports German and English. Most source records are German, so German search terms usually work better.

## Run locally

Python 3.10 or newer, internet access and a modern browser are required.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python app/server.py
```

On Windows, create the environment with `py -m venv .venv` and activate it with `.venv\Scripts\Activate.ps1` in PowerShell. The remaining commands are the same.

Open <http://127.0.0.1:5000>. Enter a task and an address, check the location candidates, then choose a service. A point on the map can be used instead of an address.

The server is intended for a small local demo. Public Nominatim allows at most one request per second for the whole application and prohibits autocomplete. The app enforces this within one process; separate instances do not share the limit. Photon also requires moderate use. Read the [provider rules](docs/data-sources.md#address-search) before running a shared instance.

## What the results mean

BKG boundaries identify the municipality; the Portalverbund search service supplies the services and associated authorities. Results help with orientation, but do not settle every case. District responsibilities, special rules and data gaps can affect the answer. An authority's general address may differ from the counter handling a particular service. Confirm the location and opening hours in the linked official portal before a visit.

## Development

```bash
python -m unittest discover -s tests -v
node --test tests/frontend.test.cjs
```

The frontend checks require Node.js 20 or newer. See [testing and demo](docs/testing-and-demo.md) for manual checks and the last validation results.

Optional configuration: `NOMINATIM_URL`, `PHOTON_URL` and `GEOCODER_CONTACT`. Use compatible endpoints and set a monitored project contact before a wider demo. Data transfers and source conditions are described in [data sources](docs/data-sources.md).

- [Architecture](docs/architecture.md)
- [Team workflow and open tasks](CONTRIBUTING.md)
- [Validation record](docs/validation-2026-11-10.md)
- [BKG exploration notebook](notebooks/explore_bzb.ipynb)
- [Original requirements notes, in German](docs/original-requirements-de.md)
