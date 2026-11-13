# Data license

> **This tool does not include, host, or redistribute any data.**
> `fim-portal-cli` is a *client*. It only accesses data served live by the **FIM
> Portal**, operated by **FITKO (Föderale IT-Kooperation)**. That data is the
> provider's and is governed by **their** terms. The license of this CLI's own
> source code is a separate matter — see [LICENSING.md](LICENSING.md).

> [!WARNING]
> **The data license is not explicitly published by the provider.** No FIM-Portal
> page, API doc, or FITKO documentation page reviewed states a license for the
> catalogue *data* itself. Do not assume open terms — see caveats.

| | |
|---|---|
| **Data provider** | FITKO (Föderale IT-Kooperation AöR), for the IT-Planungsrat |
| **API / source** | `https://fimportal.de` (Swagger: `https://fimportal.de/docs`) — XZuFi services, XDatenfelder, XProzess |
| **Data license** | **Unclear / not explicitly stated.** `dl-de/zero-2-0` (≈ CC0) is a plausible inference from FITKO/GovData open-data guidance, but **not confirmed** for this dataset. |
| **License text** | (none authoritative for the data) — DL-DE Zero 2.0 reference: https://www.govdata.de/dl-de/zero-2-0 |
| **Attribution** | Unclear; recommended as good practice (see below). |
| **Commercial use** | Unclear at the provider level; no prohibition found. |
| **Redistribution / modification** | No restriction found; FITKO framing emphasizes cross-level "Nachnutzung". Not formally confirmed. |

## Notes & caveats

- **Do not conflate the licenses in play:** FIM *documentation* = CC BY 4.0; the
  FIM Portal *source code* = EUPL-1.2; the catalogue **data** = no explicit
  statement found. (This CLI's own code is separately AGPL-3.0/commercial.)
- The FIM Portal homepage, Impressum, Datenschutz, `/docs` (Swagger) and the
  FITKO docs pages all lack an explicit data-license clause.
- No authoritative FITKO "FIM/LeiKa catalogue" dataset entry on GovData pins the
  license. Treat any "CC0 / DL-DE Zero" claim as **inferred, not confirmed**.
- For commercial reliance, seek written confirmation from FITKO
  (`fim@fitko.de` / `ticket@fimportal.de`).

## Attribution (recommended as risk mitigation)

```
Quelle: FIM Portal (Föderales Informationsmanagement), FITKO – Föderale
IT-Kooperation, https://fimportal.de
```

## Sources

- https://docs.fitko.de/fim/docs/quer/fimportal/fim_portal_sources/ — data sources (docs under CC BY 4.0; no data license stated)
- https://gitlab.opencode.de/fitko/fim/portal — portal source code (EUPL-1.2)
- https://docs.fitko.de/govdata/docs/library/licenses/ — FITKO/GovData open-data guidance (general, not FIM-data-specific)

---

*Good-faith summary compiled 2026-06-16; not legal advice. Because the provider
publishes no explicit data license, verify directly with FITKO before any reuse
beyond personal/evaluation, especially commercial use or redistribution.*
